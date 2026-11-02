"""Bounded canonical multi-label representation trainer for Inspect View candidates."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import tempfile
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
        target = torch.zeros(len(self.labels), dtype=torch.float32)
        for label in row["jointinspect_labels"]:
            if label not in self.label_index:
                raise ValueError(f"Unknown canonical label: {label}")
            target[self.label_index[label]] = 1.0
        if not target.any():
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


def macro_metrics(truth: torch.Tensor, logits: torch.Tensor) -> dict:
    predicted = torch.sigmoid(logits) >= 0.5
    truth = truth.bool()
    f1_values, f2_values = [], []
    for index in range(truth.shape[1]):
        tp = (predicted[:, index] & truth[:, index]).sum().item()
        fp = (predicted[:, index] & ~truth[:, index]).sum().item()
        fn = (~predicted[:, index] & truth[:, index]).sum().item()
        if tp + fn == 0:
            continue
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1_values.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
        f2_values.append(5 * precision * recall / (4 * precision + recall) if 4 * precision + recall else 0.0)
    return {
        "macro_f1": sum(f1_values) / len(f1_values) if f1_values else 0.0,
        "macro_f2": sum(f2_values) / len(f2_values) if f2_values else 0.0,
        "evaluated_classes": len(f1_values),
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
    train_rows = stable_cap([row for row in labeled_rows if row["split"] == "train"], args.max_train)
    val_rows = stable_cap([row for row in labeled_rows if row["split"] == "val"], args.max_val)
    if not train_rows or not val_rows:
        raise ValueError("Both bounded train and validation samples are required")
    labels_config = json.loads(args.labels.read_text(encoding="utf-8"))
    labels = labels_config["canonical_labels"]
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu_only else "cpu")
    model = create_model(args.architecture, len(labels), args.pretrained).to(device)
    train_loader = DataLoader(ManifestDataset(train_rows, labels, client), batch_size=args.batch_size,
                              shuffle=True, num_workers=0)
    val_loader = DataLoader(ManifestDataset(val_rows, labels, client), batch_size=args.batch_size,
                            shuffle=False, num_workers=0)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    criterion = nn.BCEWithLogitsLoss()
    history = []
    for epoch in range(args.epochs):
        model.train(); total_loss = 0.0; batches = 0
        for images, targets in train_loader:
            images, targets = images.to(device), targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), targets)
            loss.backward(); optimizer.step()
            total_loss += loss.item(); batches += 1
        history.append({"epoch": epoch + 1, "train_loss": total_loss / max(batches, 1)})
    model.eval(); truth, logits = [], []
    with torch.no_grad():
        for images, targets in val_loader:
            logits.append(model(images.to(device)).cpu()); truth.append(targets)
    metrics = macro_metrics(torch.cat(truth), torch.cat(logits))
    metrics.update({
        "architecture": args.architecture, "epochs": args.epochs,
        "train_records": len(train_rows), "val_records": len(val_rows),
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
    parser.add_argument("--cpu-only", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
