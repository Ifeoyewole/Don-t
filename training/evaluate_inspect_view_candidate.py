"""Evaluate a versioned Inspect View checkpoint on the shared development contract."""
from __future__ import annotations

import argparse
import io
import json
import tempfile
from pathlib import Path

import torch
from google.cloud import storage
from torch.utils.data import DataLoader

from inspect_view_representation import (
    ManifestDataset,
    balanced_cap,
    create_model,
    macro_metrics,
    partition_validation,
    read_bytes,
    tune_thresholds,
    upload_create_only,
)


def infer(model, loader, device):
    truth, logits = [], []
    model.eval()
    with torch.no_grad():
        for images, targets in loader:
            logits.append(model(images.to(device)).cpu())
            truth.append(targets)
    return torch.cat(truth), torch.cat(logits)


def prediction_rows(rows, truth, logits, labels, split):
    probabilities = torch.sigmoid(logits).tolist()
    targets = truth.int().tolist()
    return [
        {
            "original_media_id": row["original_media_id"],
            "dataset_name": row["dataset_name"],
            "media_family_id": row["media_family_id"],
            "sha256": row["sha256"],
            "evaluation_split": split,
            "truth": dict(zip(labels, target)),
            "probabilities": dict(zip(labels, probability)),
        }
        for row, target, probability in zip(rows, targets, probabilities)
    ]


def run(args):
    client = storage.Client(project=args.project)
    labels = json.loads(args.labels.read_text(encoding="utf-8"))["canonical_labels"]
    rows = [json.loads(line) for line in read_bytes(client, args.manifest).decode().splitlines() if line.strip()]
    labeled = [row for row in rows if row.get("jointinspect_labels") and row["split"] == "val"]
    val_rows = balanced_cap(labeled, args.max_val)
    tune_rows, report_rows = partition_validation(val_rows)

    checkpoint_bytes = read_bytes(client, args.checkpoint)
    checkpoint = torch.load(io.BytesIO(checkpoint_bytes), map_location="cpu", weights_only=True)
    if checkpoint.get("labels") != labels:
        raise ValueError("Checkpoint and evaluator canonical label contracts differ")
    architecture = checkpoint.get("metrics", {}).get("architecture")
    if architecture not in {"efficientnet_b0", "convnext_tiny"}:
        raise ValueError(f"Unsupported checkpoint architecture: {architecture}")
    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu_only else "cpu")
    model = create_model(architecture, len(labels), pretrained=False).to(device)
    model.load_state_dict(checkpoint["model"], strict=True)

    def loader(selected):
        return DataLoader(ManifestDataset(selected, labels, client), batch_size=args.batch_size,
                          shuffle=False, num_workers=0)

    tune_truth, tune_logits = infer(model, loader(tune_rows), device)
    report_truth, report_logits = infer(model, loader(report_rows), device)
    thresholds = tune_thresholds(tune_truth, tune_logits)
    metrics = macro_metrics(report_truth, report_logits, thresholds, labels)
    metrics.update({
        "architecture": architecture,
        "checkpoint": args.checkpoint,
        "threshold_tune_records": len(tune_rows),
        "development_report_records": len(report_rows),
        "locked_test_evaluated": False,
        "production_approved": False,
    })
    outputs = {
        "threshold_tune_predictions.jsonl": prediction_rows(
            tune_rows, tune_truth, tune_logits, labels, "threshold_tune"
        ),
        "development_report_predictions.jsonl": prediction_rows(
            report_rows, report_truth, report_logits, labels, "development_report"
        ),
    }
    with tempfile.TemporaryDirectory(prefix="inspect-view-eval-") as directory:
        root = Path(directory)
        for name, values in outputs.items():
            (root / name).write_text("".join(json.dumps(value, sort_keys=True) + "\n" for value in values))
        (root / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
        metadata = {"config_id": args.config_id, "production_approved": "false"}
        for path in root.iterdir():
            upload_create_only(client, path, f"{args.output_prefix.rstrip('/')}/{path.name}", metadata)
    print(json.dumps(metrics, sort_keys=True))
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--config-id", required=True)
    parser.add_argument("--max-val", type=int, default=400)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--cpu-only", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
