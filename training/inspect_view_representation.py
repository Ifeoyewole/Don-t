"""Bounded canonical multi-label representation trainer for Inspect View candidates."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import tempfile
from collections import Counter
from pathlib import Path

import torch
from google.cloud import storage
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import (
    ConvNeXt_Tiny_Weights,
    EfficientNet_B0_Weights,
    convnext_tiny,
    efficientnet_b0,
)


def split_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"Expected gs:// URI: {uri}")
    return uri[5:].split("/", 1)


def read_bytes(client: storage.Client, uri: str) -> bytes:
    bucket, name = split_gcs(uri)
    return client.bucket(bucket).blob(name).download_as_bytes()


def stable_cap(rows: list[dict], maximum: int) -> list[dict]:
    rows = sorted(rows, key=lambda row: hashlib.sha256(row["sha256"].encode()).digest())
    return rows[:maximum] if maximum else rows


def balanced_cap(rows: list[dict], maximum: int) -> list[dict]:
    """Deterministically cap rows while prioritising the least represented labels."""
    ordered = stable_cap(rows, 0)
    if not maximum or len(ordered) <= maximum:
        return ordered
    remaining = list(ordered)
    selected: list[dict] = []
    counts: Counter[str] = Counter()
    while remaining and len(selected) < maximum:
        candidate = min(
            remaining,
            key=lambda row: (
                sum(counts[label] for label in row["jointinspect_labels"])
                / max(len(row["jointinspect_labels"]), 1),
                max((counts[label] for label in row["jointinspect_labels"]), default=0),
                hashlib.sha256(row["sha256"].encode()).digest(),
            ),
        )
        remaining.remove(candidate)
        selected.append(candidate)
        counts.update(candidate["jointinspect_labels"])
    return selected


def partition_validation(rows: list[dict], tune_fraction: float = 0.5) -> tuple[list[dict], list[dict]]:
    """Split validation by media family so threshold tuning cannot leak into reporting."""
    families: dict[tuple[str, str], list[dict]] = {}
    for row in rows:
        key = (row["dataset_name"], row["media_family_id"])
        families.setdefault(key, []).append(row)
    tune, report = [], []
    boundary = int(tune_fraction * 10_000)
    for key, family_rows in families.items():
        digest = hashlib.sha256("\0".join(key).encode()).digest()
        target = tune if int.from_bytes(digest[:4], "big") % 10_000 < boundary else report
        target.extend(family_rows)
    if not tune or not report:
        raise ValueError("Validation requires at least one threshold-tune and report family")
    return tune, report


class ManifestDataset(Dataset):
    def __init__(self, rows: list[dict], labels: list[str], client: storage.Client, image_size: int = 224):
        self.rows, self.labels, self.client = rows, labels, client
        self.label_index = {name: index for index, name in enumerate(labels)}
        self.transform = transforms.Compose([
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        row = self.rows[index]
        payload = read_bytes(self.client, row["image_uri"])
        if hashlib.sha256(payload).hexdigest() != row["sha256"]:
            raise RuntimeError(f"Image checksum mismatch: {row['image_uri']}")
        with Image.open(io.BytesIO(payload)) as image:
            tensor = self.transform(image.convert("RGB"))
        target = torch.full((len(self.labels),), -1.0, dtype=torch.float32)
        observed = row.get("observed_jointinspect_labels")
        if observed is None:
            raise ValueError("Manifest must explicitly declare observed_jointinspect_labels")
        for label in observed:
            if label not in self.label_index:
                raise ValueError(f"Unknown observed label: {label}")
            target[self.label_index[label]] = 0.0
        for label in row["jointinspect_labels"]:
            if label not in self.label_index:
                raise ValueError(f"Unknown canonical label: {label}")
            if label not in observed:
                raise ValueError(f"Positive label is not observed: {label}")
            target[self.label_index[label]] = 1.0
        if not (target >= 0).any():
            raise ValueError(f"Record has no canonical targets: {row['original_media_id']}")
        return tensor, target


def create_model(architecture: str, classes: int, pretrained: bool) -> nn.Module:
    if architecture == "efficientnet_b0":
        model = efficientnet_b0(weights=EfficientNet_B0_Weights.DEFAULT if pretrained else None)
        model.classifier[1] = nn.Linear(model.classifier[1].in_features, classes)
        return model
    model = convnext_tiny(weights=ConvNeXt_Tiny_Weights.DEFAULT if pretrained else None)
    model.classifier[2] = nn.Linear(model.classifier[2].in_features, classes)
    return model


def tune_thresholds(truth: torch.Tensor, logits: torch.Tensor) -> list[float]:
    probabilities = torch.sigmoid(logits)
    thresholds = []
    for index in range(truth.shape[1]):
        if not (truth[:, index] == 1).any():
            thresholds.append(0.5)
            continue
        best = (0.5, -1.0, -1.0)
        for threshold in (value / 100 for value in range(5, 96, 5)):
            result = macro_metrics(truth[:, index:index + 1], logits[:, index:index + 1], [threshold])
            score = (result["macro_f1"], result["macro_f2"])
            if score > best[1:]:
                best = (threshold, *score)
        thresholds.append(best[0] if probabilities[:, index].numel() else 0.5)
    return thresholds


def macro_metrics(truth: torch.Tensor, logits: torch.Tensor, thresholds: list[float] | None = None,
                  labels: list[str] | None = None) -> dict:
    thresholds = thresholds or [0.5] * truth.shape[1]
    predicted = torch.sigmoid(logits) >= torch.tensor(thresholds).reshape(1, -1)
    observed = truth >= 0
    truth = truth == 1
    f1_values, f2_values, per_class = [], [], {}
    for index in range(truth.shape[1]):
        tp = (observed[:, index] & predicted[:, index] & truth[:, index]).sum().item()
        fp = (observed[:, index] & predicted[:, index] & ~truth[:, index]).sum().item()
        fn = (observed[:, index] & ~predicted[:, index] & truth[:, index]).sum().item()
        support = tp + fn
        name = labels[index] if labels else str(index)
        if support == 0:
            per_class[name] = {"support": 0, "threshold": thresholds[index], "evaluated": False}
            continue
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f2 = 5 * precision * recall / (4 * precision + recall) if 4 * precision + recall else 0.0
        f1_values.append(f1); f2_values.append(f2)
        per_class[name] = {"support": support, "true_positive": tp, "false_positive": fp,
                           "false_negative": fn, "precision": precision, "recall": recall,
                           "f1": f1, "f2": f2, "threshold": thresholds[index], "evaluated": True}
    return {
        "macro_f1": sum(f1_values) / len(f1_values) if f1_values else 0.0,
        "macro_f2": sum(f2_values) / len(f2_values) if f2_values else 0.0,
        "evaluated_classes": len(f1_values),
        "per_class": per_class,
    }


def upload_create_only(client: storage.Client, path: Path, destination: str, metadata: dict[str, str]) -> None:
    bucket, name = split_gcs(destination)
    blob = client.bucket(bucket).blob(name)
    blob.metadata = metadata
    blob.upload_from_filename(path, if_generation_match=0)


def run(args) -> dict:
    torch.manual_seed(args.seed)
    client = storage.Client(project=args.project)
    rows = [json.loads(line) for line in read_bytes(client, args.manifest).decode().splitlines() if line.strip()]
    labeled_rows = [row for row in rows if row.get("jointinspect_labels")]
    excluded_unlabeled = len(rows) - len(labeled_rows)
    train_rows = balanced_cap([row for row in labeled_rows if row["split"] == "train"], args.max_train)
    val_rows = balanced_cap([row for row in labeled_rows if row["split"] == "val"], args.max_val)
    if not train_rows or not val_rows:
        raise ValueError("Both bounded train and validation samples are required")
    labels_config = json.loads(args.labels.read_text(encoding="utf-8"))
    labels = labels_config["canonical_labels"]
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu_only else "cpu")
    model = create_model(args.architecture, len(labels), args.pretrained).to(device)
    initialized_from = None
    if args.init_checkpoint:
        checkpoint_payload = read_bytes(client, args.init_checkpoint)
        checkpoint_sha256 = hashlib.sha256(checkpoint_payload).hexdigest()
        checkpoint = torch.load(io.BytesIO(checkpoint_payload), map_location=device, weights_only=True)
        if checkpoint.get("labels") != labels:
            raise ValueError("Initial checkpoint canonical label contract does not match")
        prior_architecture = checkpoint.get("metrics", {}).get("architecture")
        if prior_architecture and prior_architecture != args.architecture:
            raise ValueError(f"Initial checkpoint architecture mismatch: {prior_architecture}")
        model.load_state_dict(checkpoint["model"], strict=True)
        initialized_from = {"uri": args.init_checkpoint, "sha256": checkpoint_sha256}
    train_loader = DataLoader(ManifestDataset(train_rows, labels, client), batch_size=args.batch_size,
                              shuffle=True, num_workers=0)
    tune_rows, report_rows = partition_validation(val_rows)
    tune_loader = DataLoader(ManifestDataset(tune_rows, labels, client), batch_size=args.batch_size,
                             shuffle=False, num_workers=0)
    report_loader = DataLoader(ManifestDataset(report_rows, labels, client), batch_size=args.batch_size,
                               shuffle=False, num_workers=0)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    criterion = nn.BCEWithLogitsLoss(reduction="none")
    history = []
    for epoch in range(args.epochs):
        model.train(); total_loss = 0.0; batches = 0
        for images, targets in train_loader:
            images, targets = images.to(device), targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            observed = targets >= 0
            if not observed.any():
                raise ValueError("Batch contains no observed annotations")
            element_loss = criterion(model(images), targets.clamp_min(0))
            loss = (element_loss * observed).sum() / observed.sum()
            loss.backward(); optimizer.step()
            total_loss += loss.item(); batches += 1
        history.append({"epoch": epoch + 1, "train_loss": total_loss / max(batches, 1)})
    def infer(loader):
        truth, logits = [], []
        with torch.no_grad():
            for images, targets in loader:
                logits.append(model(images.to(device)).cpu()); truth.append(targets)
        return torch.cat(truth), torch.cat(logits)

    model.eval()
    tune_truth, tune_logits = infer(tune_loader)
    thresholds = tune_thresholds(tune_truth, tune_logits)
    report_truth, report_logits = infer(report_loader)
    metrics = macro_metrics(report_truth, report_logits, thresholds, labels)
    metrics.update({
        "architecture": args.architecture, "epochs": args.epochs,
        "train_records": len(train_rows), "val_records": len(val_rows),
        "threshold_tune_records": len(tune_rows), "development_report_records": len(report_rows),
        "thresholds": dict(zip(labels, thresholds)), "sampling": "deterministic_class_balanced_v1",
        "initialized_from": initialized_from,
        "annotation_policy": "explicit_observed_labels_v1",
        "device": str(device), "pretrained": args.pretrained,
        "excluded_unlabeled_records": excluded_unlabeled,
        "production_approved": False, "locked_test_evaluated": False,
    })
    with tempfile.TemporaryDirectory(prefix="inspect-view-repr-") as directory:
        root = Path(directory)
        checkpoint = root / "best.pt"
        torch.save({"model": model.state_dict(), "labels": labels, "metrics": metrics,
                    "config_id": args.config_id}, checkpoint)
        (root / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
        (root / "history.json").write_text(json.dumps(history, indent=2) + "\n")
        card = {
            "model_name": "Inspect View representation candidate",
            "config_id": args.config_id, "manifest": args.manifest,
            "canonical_labels": labels, "metrics": metrics,
            "production_approved": False, "locked_test_evaluated": False,
        }
        (root / "model_card.json").write_text(json.dumps(card, indent=2) + "\n")
        metadata = {"config_id": args.config_id, "production_approved": "false"}
        for path in root.iterdir():
            upload_create_only(client, path, f"{args.output_prefix.rstrip('/')}/{path.name}", metadata)
    print(json.dumps(metrics, sort_keys=True))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--config-id", required=True)
    parser.add_argument("--architecture", choices=("efficientnet_b0", "convnext_tiny"), default="efficientnet_b0")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--max-train", type=int, default=64)
    parser.add_argument("--max-val", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--pretrained", action="store_true")
    parser.add_argument("--init-checkpoint", help="Versioned gs:// checkpoint used to continue training")
    parser.add_argument("--cpu-only", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
