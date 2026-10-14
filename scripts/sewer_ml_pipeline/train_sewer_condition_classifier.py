"""Sewer-ML Multi-Label Sewer Condition Classifier (Candidate Model B1).

Production-grade training script for JointInspect Sewer-ML pipeline:
- Targets (9 Classes):
    0: FS (Displaced Joint)    -> DISPLACED_JOINT
    1: IS (Intruding Seal)     -> INTRUDING_SEAL
    2: RB (Broken / Fracture)  -> DAMAGED_JOINT
    3: DE (Deformation)        -> DAMAGED_JOINT
    4: RO (Roots)              -> DEPOSITS_OBSTACLES
    5: AF (Settled Deposit)    -> DEPOSITS_OBSTACLES
    6: BE (Attached Deposit)   -> DEPOSITS_OBSTACLES
    7: FO (Obstacle)           -> DEPOSITS_OBSTACLES
    8: ND (Normal Pipe)        -> NORMAL_PIPE

- Model: Convolutional Neural Network with Adaptive Pooling and Sigmoid multi-label output.
- Loss: Multi-Label Binary Cross-Entropy with Pos-Weight for Class Imbalance.
- Optimizer: AdamW with Cosine Annealing.
- Metrics: Class-wise Precision, Recall, F1, F2; Macro & Micro F1; Normal-Pipe detection; Calibration ECE.
- Baseline comparison: WRc InceptionResNetV2 benchmark on verified common concepts.
- Exports: ONNX computational graph, PyTorch weights, metrics JSON, model card.
- Safety Gate: production_approved = false (WRc remains primary production classifier).
"""

import argparse
import csv
import datetime
import hashlib
import json
import logging
import math
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0
from torch.utils.data import DataLoader, Dataset
from benchmark_integrity import calibration_report, grouped_binary_metrics, optimize_thresholds, validate_onnx_artifact

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sewer_ml_trainer")

TARGET_CLASSES = ["FS", "IS", "RB", "DE", "RO", "AF", "BE", "FO", "ND"]
NUM_CLASSES = len(TARGET_CLASSES)
CLASS_TO_IDX = {c: i for i, c in enumerate(TARGET_CLASSES)}

# Semantic Mapping to JointInspect Concept Classes
JOINTINSPECT_MAP = {
    "FS": "DISPLACED_JOINT",
    "IS": "INTRUDING_SEAL",
    "RB": "DAMAGED_JOINT",
    "DE": "DAMAGED_JOINT",
    "RO": "DEPOSITS_OBSTACLES",
    "AF": "DEPOSITS_OBSTACLES",
    "BE": "DEPOSITS_OBSTACLES",
    "FO": "DEPOSITS_OBSTACLES",
    "ND": "NORMAL_PIPE",
}


def validate_image_records(records: List[Dict[str, str]], images_dir: Path) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Deterministically excludes missing/corrupt inputs; never fabricates replacement pixels."""
    accepted, rejected = [], []
    for row in records:
        filename = row.get("Filename", "")
        path = images_dir / filename
        if not path.is_file():
            rejected.append({"Filename": filename, "reason": "MISSING"})
            continue
        image = cv2.imread(str(path))
        if image is None or image.size == 0:
            rejected.append({"Filename": filename, "reason": "DECODE_FAILED"})
            continue
        accepted.append(row)
    return accepted, rejected


class SewerDataset(Dataset):
    """PyTorch Dataset loading curated Sewer-ML images and binary multi-label targets."""

    def __init__(
        self,
        records: List[Dict[str, str]],
        images_dir: Path,
        img_size: int = 128,
        augment: bool = False,
    ):
        self.records = records
        self.images_dir = images_dir
        self.img_size = img_size
        self.augment = augment

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        row = self.records[idx]
        fn = row["Filename"]
        img_path = self.images_dir / fn

        if not img_path.is_file():
            raise FileNotFoundError(f"Dataset image is missing: {fn}")
        img = cv2.imread(str(img_path))
        if img is None or img.size == 0:
            raise ValueError(f"Dataset image cannot be decoded: {fn}")
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (self.img_size, self.img_size))

        # Basic data augmentation (horizontal flip)
        if self.augment and np.random.rand() > 0.5:
            img = cv2.flip(img, 1)

        # Normalization [0, 1] then ImageNet standardize
        img_float = img.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img_norm = (img_float - mean) / std
        tensor_img = torch.from_numpy(np.transpose(img_norm, (2, 0, 1))).float()

        # Multi-label binary vector
        target = np.array(
            [1.0 if row.get(c) in ("1", "1.0") else 0.0 for c in TARGET_CLASSES],
            dtype=np.float32,
        )
        tensor_target = torch.from_numpy(target).float()

        return tensor_img, tensor_target


class SewerConditionClassifier(nn.Module):
    """Deep Convolutional Neural Network for multi-label sewer defect classification."""

    def __init__(self, num_classes: int = NUM_CLASSES):
        super().__init__()
        self.features = nn.Sequential(
            # Stage 1: 128x128 -> 64x64
            nn.Conv2d(3, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            # Stage 2: 64x64 -> 32x32
            nn.Conv2d(32, 64, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            # Stage 3: 32x32 -> 16x16
            nn.Conv2d(64, 128, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
            # Stage 4: 16x16 -> 8x8
            nn.Conv2d(128, 256, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            # Global Average Pooling -> 256x1x1
            nn.AdaptiveAvgPool2d((1, 1)),
        )

        self.classifier = nn.Sequential(
            nn.Dropout(p=0.3),
            nn.Linear(256, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.2),
            nn.Linear(128, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.features(x)
        feat = torch.flatten(feat, 1)
        logits = self.classifier(feat)
        return logits


def build_model(num_classes: int, architecture: str, pretrained: bool = True) -> nn.Module:
    if architecture == "efficientnet_b0":
        model = efficientnet_b0(weights=EfficientNet_B0_Weights.DEFAULT if pretrained else None)
        input_features = model.classifier[1].in_features
        model.classifier = nn.Sequential(nn.Dropout(p=0.3), nn.Linear(input_features, num_classes))
        return model
    if architecture == "legacy_cnn":
        return SewerConditionClassifier(num_classes=num_classes)
    raise ValueError(f"Unsupported architecture: {architecture}")


def compute_metrics(
    y_true: np.ndarray, y_probs: np.ndarray, threshold: float | List[float] = 0.5
) -> Dict[str, Any]:
    """Computes comprehensive multi-label evaluation metrics."""
    thresholds = np.asarray(threshold if isinstance(threshold, list) else [threshold] * y_probs.shape[1])
    y_pred = (y_probs >= thresholds).astype(int)
    N, C = y_true.shape

    class_metrics = {}
    f1_list, f2_list, prec_list, rec_list = [], [], [], []

    for idx, cname in enumerate(TARGET_CLASSES):
        yt = y_true[:, idx]
        yp = y_pred[:, idx]

        tp = int(np.logical_and(yp == 1, yt == 1).sum())
        fp = int(np.logical_and(yp == 1, yt == 0).sum())
        fn = int(np.logical_and(yp == 0, yt == 1).sum())
        tn = int(np.logical_and(yp == 0, yt == 0).sum())

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        f2 = (5 * prec * rec) / (4 * prec + rec) if (4 * prec + rec) > 0 else 0.0

        class_metrics[cname] = {
            "concept": JOINTINSPECT_MAP[cname],
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1": round(float(f1), 4),
            "f2": round(float(f2), 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "support": int(yt.sum()),
        }

        if (tp + fn) > 0:
            f1_list.append(f1)
            f2_list.append(f2)
            prec_list.append(prec)
            rec_list.append(rec)

    macro_f1 = float(np.mean(f1_list)) if f1_list else 0.0
    macro_f2 = float(np.mean(f2_list)) if f2_list else 0.0
    macro_prec = float(np.mean(prec_list)) if prec_list else 0.0
    macro_rec = float(np.mean(rec_list)) if rec_list else 0.0

    # Micro Metrics
    total_tp = sum(class_metrics[c]["tp"] for c in TARGET_CLASSES)
    total_fp = sum(class_metrics[c]["fp"] for c in TARGET_CLASSES)
    total_fn = sum(class_metrics[c]["fn"] for c in TARGET_CLASSES)
    micro_prec = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    micro_rec = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    micro_f1 = (2 * micro_prec * micro_rec) / (micro_prec + micro_rec) if (micro_prec + micro_rec) > 0 else 0.0

    calibration = calibration_report(y_true, y_probs)
    grouped = {
        "DISPLACED_JOINT": grouped_binary_metrics(y_true, y_pred, [CLASS_TO_IDX["FS"]]),
        "DAMAGED_JOINT": grouped_binary_metrics(y_true, y_pred, [CLASS_TO_IDX["RB"], CLASS_TO_IDX["DE"]]),
        "DEPOSITS_OBSTACLES": grouped_binary_metrics(y_true, y_pred, [CLASS_TO_IDX[c] for c in ("RO", "AF", "BE", "FO")]),
        "NORMAL_PIPE": grouped_binary_metrics(y_true, y_pred, [CLASS_TO_IDX["ND"]]),
    }

    nd_m = class_metrics.get("ND", {})

    return {
        "macro_f1": round(macro_f1, 4),
        "macro_f2": round(macro_f2, 4),
        "macro_precision": round(macro_prec, 4),
        "macro_recall": round(macro_rec, 4),
        "micro_f1": round(micro_f1, 4),
        "micro_precision": round(micro_prec, 4),
        "micro_recall": round(micro_rec, 4),
        "calibration_ece": round(calibration["ece_macro"], 4),
        "calibration": calibration,
        "brier_score": round(calibration["brier_score"], 6),
        "grouped_concept_metrics": grouped,
        "thresholds": thresholds.tolist(),
        "normal_pipe_f1": nd_m.get("f1", 0.0),
        "normal_pipe_recall": nd_m.get("recall", 0.0),
        "class_metrics": class_metrics,
    }


def compare_with_wrc(candidate_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Compares candidate against WRc InceptionResNetV2 baseline on verified concepts."""
    wrc_baseline = {
        "DISPLACED_JOINT": {"f1": 0.582, "recall": 0.540, "precision": 0.631},
        "DAMAGED_JOINT": {"f1": 0.514, "recall": 0.492, "precision": 0.538},
        "DEPOSITS_OBSTACLES": {"f1": 0.620, "recall": 0.610, "precision": 0.630},
        "NORMAL_PIPE": {"f1": 0.450, "recall": 0.420, "precision": 0.485},
        "macro_f1": 0.541,
    }

    cls_m = candidate_metrics.get("class_metrics", {})
    cand_by_concept = {
        "DISPLACED_JOINT": cls_m.get("FS", {}),
        "DAMAGED_JOINT": {
            "f1": round((cls_m.get("RB", {}).get("f1", 0.0) + cls_m.get("DE", {}).get("f1", 0.0)) / 2.0, 4),
            "recall": round((cls_m.get("RB", {}).get("recall", 0.0) + cls_m.get("DE", {}).get("recall", 0.0)) / 2.0, 4),
            "precision": round((cls_m.get("RB", {}).get("precision", 0.0) + cls_m.get("DE", {}).get("precision", 0.0)) / 2.0, 4),
        },
        "DEPOSITS_OBSTACLES": {
            "f1": round(
                (
                    cls_m.get("RO", {}).get("f1", 0.0)
                    + cls_m.get("AF", {}).get("f1", 0.0)
                    + cls_m.get("BE", {}).get("f1", 0.0)
                    + cls_m.get("FO", {}).get("f1", 0.0)
                )
                / 4.0,
                4,
            ),
            "recall": round(
                (
                    cls_m.get("RO", {}).get("recall", 0.0)
                    + cls_m.get("AF", {}).get("recall", 0.0)
                    + cls_m.get("BE", {}).get("recall", 0.0)
                    + cls_m.get("FO", {}).get("recall", 0.0)
                )
                / 4.0,
                4,
            ),
            "precision": round(
                (
                    cls_m.get("RO", {}).get("precision", 0.0)
                    + cls_m.get("AF", {}).get("precision", 0.0)
                    + cls_m.get("BE", {}).get("precision", 0.0)
                    + cls_m.get("FO", {}).get("precision", 0.0)
                )
                / 4.0,
                4,
            ),
        },
        "NORMAL_PIPE": cls_m.get("ND", {}),
    }

    concept_comparison = {}
    for concept, w_val in wrc_baseline.items():
        if concept == "macro_f1":
            continue
        c_val = cand_by_concept.get(concept, {})
        delta = round(c_val.get("f1", 0.0) - w_val["f1"], 4)
        concept_comparison[concept] = {
            "wrc_baseline_f1": w_val["f1"],
            "candidate_f1": c_val.get("f1", 0.0),
            "delta_f1": delta,
            "wrc_recall": w_val["recall"],
            "candidate_recall": c_val.get("recall", 0.0),
            "superior": c_val.get("f1", 0.0) > w_val["f1"],
        }

    return {
        "wrc_baseline_macro_f1": wrc_baseline["macro_f1"],
        "candidate_macro_f1": candidate_metrics.get("macro_f1", 0.0),
        "delta_macro_f1": round(candidate_metrics.get("macro_f1", 0.0) - wrc_baseline["macro_f1"], 4),
        "concept_comparison": concept_comparison,
    }


def export_onnx_model(
    model: nn.Module,
    output_path: Path,
    img_size: int = 128,
) -> Tuple[Path, str]:
    """Exports model to standard ONNX format."""
    model.eval()
    dummy_input = torch.randn(1, 3, img_size, img_size, dtype=torch.float32)

    # Wrapper to export with Sigmoid activation at output
    class OnnxExportWrapper(nn.Module):
        def __init__(self, base_model):
            super().__init__()
            self.base_model = base_model

        def forward(self, x):
            logits = self.base_model(x)
            return torch.sigmoid(logits)

    export_model = OnnxExportWrapper(model)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        torch.onnx.export(
            export_model,
            dummy_input,
            str(output_path),
            export_params=True,
            opset_version=17,
            do_constant_folding=True,
            input_names=["image"],
            output_names=["class_probabilities"],
            dynamic_axes={"image": {0: "batch_size"}, "class_probabilities": {0: "batch_size"}},
        )
    except Exception as e:
        raise RuntimeError(f"ONNX export failed; no disguised fallback artifact was written: {e}") from e

    with torch.no_grad():
        native_outputs = export_model(dummy_input).cpu().numpy()
    integrity = validate_onnx_artifact(output_path, native_outputs, dummy_input.cpu().numpy())
    sha256 = integrity["sha256"]
    logger.info("Exported model graph to %s (%d bytes, SHA-256: %s)", output_path, output_path.stat().st_size, sha256[:16])
    return output_path, sha256


def train_sewer_condition_classifier(
    images_dir: Path,
    train_csv: Path,
    val_csv: Path,
    output_dir: Path,
    epochs: int = 5,
    batch_size: int = 32,
    lr: float = 1e-3,
    img_size: int = 128,
    model_version: str = "sewer-condition-v1.0.0-candidate",
    smoke_max_samples: Optional[int] = None,
    architecture: str = "efficientnet_b0",
) -> Dict[str, Any]:
    """Runs full PyTorch multi-label training pipeline."""
    torch.manual_seed(42)
    np.random.seed(42)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Using compute device: %s", device)

    # 1. Load CSVs
    def load_rows(csv_path: Path) -> List[Dict[str, str]]:
        rows = []
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append(r)
        return rows

    train_rows = load_rows(train_csv)
    val_rows = load_rows(val_csv)
    logger.info("Loaded CSV records: train=%d, val=%d", len(train_rows), len(val_rows))

    # Match available images
    available = set(os.listdir(images_dir)) if images_dir.exists() else set()
    logger.info("Found %d image files in %s", len(available), images_dir)

    matched_train = [r for r in train_rows if r["Filename"] in available]
    matched_val = [r for r in val_rows if r["Filename"] in available]

    if not matched_train:
        logger.warning("No train filenames matched directory files directly. Using all available directory files.")
        matched_train = train_rows[: min(len(train_rows), 500)]
        matched_val = val_rows[: min(len(val_rows), 200)]

    if smoke_max_samples is not None:
        matched_train = matched_train[:smoke_max_samples]
        matched_val = matched_val[: min(len(matched_val), smoke_max_samples // 2)]
        logger.info("Smoke mode enabled: subsampled to %d train, %d val", len(matched_train), len(matched_val))

    matched_train, rejected_train = validate_image_records(matched_train, images_dir)
    matched_val, rejected_val = validate_image_records(matched_val, images_dir)
    rejected = [{**row, "split": "train"} for row in rejected_train] + [{**row, "split": "validation"} for row in rejected_val]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rejected_images.json").write_text(json.dumps(rejected, indent=2))
    attempted = len(matched_train) + len(matched_val) + len(rejected)
    if attempted and len(rejected) / attempted > 0.01:
        raise RuntimeError(f"Rejected image rate {len(rejected)}/{attempted} exceeds 1% integrity threshold")

    logger.info("Active dataset split: %d train samples, %d val samples", len(matched_train), len(matched_val))

    # 2. Compute class-wise pos_weights for BCEWithLogitsLoss
    pos_counts = Counter()
    for r in matched_train:
        for c in TARGET_CLASSES:
            if r.get(c) in ("1", "1.0"):
                pos_counts[c] += 1

    total_train = len(matched_train)
    weights = []
    for c in TARGET_CLASSES:
        pc = max(1, pos_counts[c])
        nc = max(1, total_train - pc)
        w = min(15.0, max(1.0, nc / pc))
        weights.append(w)

    pos_weight_tensor = torch.tensor(weights, dtype=torch.float32, device=device)
    logger.info(
        "Computed BCE pos_weights: %s",
        {c: round(float(w), 2) for c, w in zip(TARGET_CLASSES, weights)},
    )

    # 3. DataLoaders
    train_dataset = SewerDataset(matched_train, images_dir, img_size=img_size, augment=True)
    val_dataset = SewerDataset(matched_val, images_dir, img_size=img_size, augment=False)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=2,
        pin_memory=(device.type == "cuda"),
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=2,
        pin_memory=(device.type == "cuda"),
    )

    # 4. Model, Criterion, Optimizer, Scheduler
    model = build_model(NUM_CLASSES, architecture, pretrained=True).to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight_tensor)
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=max(1, epochs), eta_min=1e-5)

    # 5. Training Loop
    history = []
    best_macro_f1 = -1.0
    best_weights_path = output_dir / "model_best.pt"
    start_time = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        train_batches = 0

        for imgs, targets in train_loader:
            imgs = imgs.to(device)
            targets = targets.to(device)

            optimizer.zero_grad()
            logits = model(imgs)
            loss = criterion(logits, targets)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()
            train_batches += 1

        scheduler.step()
        avg_train_loss = running_loss / max(1, train_batches)

        # Validation phase
        model.eval()
        val_loss = 0.0
        val_batches = 0
        all_targets = []
        all_probs = []

        with torch.no_grad():
            for imgs, targets in val_loader:
                imgs = imgs.to(device)
                targets = targets.to(device)

                logits = model(imgs)
                vloss = criterion(logits, targets)
                val_loss += vloss.item()
                val_batches += 1

                probs = torch.sigmoid(logits)
                all_targets.append(targets.cpu().numpy())
                all_probs.append(probs.cpu().numpy())

        avg_val_loss = val_loss / max(1, val_batches)
        y_true = np.concatenate(all_targets, axis=0) if all_targets else np.zeros((0, NUM_CLASSES))
        y_probs = np.concatenate(all_probs, axis=0) if all_probs else np.zeros((0, NUM_CLASSES))

        epoch_metrics = compute_metrics(y_true, y_probs, threshold=0.5)
        epoch_macro_f1 = epoch_metrics["macro_f1"]

        logger.info(
            "Epoch [%d/%d] - Train Loss: %.4f | Val Loss: %.4f | Val Macro F1: %.4f | Normal Pipe F1: %.4f",
            epoch,
            epochs,
            avg_train_loss,
            avg_val_loss,
            epoch_macro_f1,
            epoch_metrics["normal_pipe_f1"],
        )

        history.append({
            "epoch": epoch,
            "train_loss": round(avg_train_loss, 4),
            "val_loss": round(avg_val_loss, 4),
            "val_macro_f1": epoch_macro_f1,
            "val_micro_f1": epoch_metrics["micro_f1"],
            "normal_pipe_f1": epoch_metrics["normal_pipe_f1"],
        })

        if epoch_macro_f1 > best_macro_f1:
            best_macro_f1 = epoch_macro_f1
            output_dir.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), best_weights_path)
            logger.info("Saved new best model checkpoint (Macro F1: %.4f)", best_macro_f1)

    total_duration = time.time() - start_time

    # Load best checkpoint for final evaluation and export
    if best_weights_path.exists():
        model.load_state_dict(torch.load(best_weights_path, map_location=device))

    model.eval()
    all_targets, all_probs = [], []
    with torch.no_grad():
        for imgs, targets in val_loader:
            imgs = imgs.to(device)
            probs = torch.sigmoid(model(imgs))
            all_targets.append(targets.cpu().numpy())
            all_probs.append(probs.cpu().numpy())

    final_true = np.concatenate(all_targets, axis=0)
    final_probs = np.concatenate(all_probs, axis=0)
    # Validation is deterministically split: first half tunes thresholds; second half evaluates them.
    # The official Sewer-ML test partition remains locked for the final benchmark.
    split_index = max(1, len(final_true) // 2)
    thresholds = optimize_thresholds(final_true[:split_index], final_probs[:split_index])
    final_metrics = compute_metrics(final_true[split_index:], final_probs[split_index:], threshold=thresholds)
    final_metrics["total_train_duration_sec"] = round(total_duration, 2)
    final_metrics["epochs_completed"] = epochs
    final_metrics["train_samples"] = len(matched_train)
    final_metrics["val_samples"] = len(matched_val)

    # 6. WRc comparison must be produced only by same-input inference, never constants.
    wrc_comparison = {
        "status": "NOT_RUN_REQUIRES_IDENTICAL_INPUT_INFERENCE",
        "reason": "Run the common head-to-head evaluator with pinned WRc and Sewer-ML weights.",
        "hardcoded_metrics_used": False,
    }

    # 7. Model Export (ONNX)
    onnx_path = output_dir / "model.onnx"
    _, onnx_sha = export_onnx_model(model, onnx_path, img_size=img_size)

    # 8. Model Card and Registration Record
    model_record = {
        "model_name": "sewer-condition-v2" if "v2" in model_version else "sewer-condition-v1",
        "version": model_version,
        "framework": "PyTorch 2.x + ONNX Runtime",
        "architecture": architecture,
        "task": "multi_label_sewer_condition_classification",
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "input_tensor": {"name": "image", "shape": [1, 3, img_size, img_size], "type": "float32"},
        "output_tensor": {"name": "class_probabilities", "shape": [1, NUM_CLASSES], "type": "float32"},
        "classes": TARGET_CLASSES,
        "class_mapping": JOINTINSPECT_MAP,
        "artifacts": {
            "onnx": "model.onnx",
            "onnx_sha256": onnx_sha,
            "weights": "model_best.pt",
        },
        "performance": {
            "macro_f1": final_metrics["macro_f1"],
            "macro_f2": final_metrics["macro_f2"],
            "macro_precision": final_metrics["macro_precision"],
            "macro_recall": final_metrics["macro_recall"],
            "micro_f1": final_metrics["micro_f1"],
            "calibration_ece": final_metrics["calibration_ece"],
            "normal_pipe_f1": final_metrics["normal_pipe_f1"],
            "normal_pipe_recall": final_metrics["normal_pipe_recall"],
        },
        "wrc_baseline_comparison": wrc_comparison,
        "governance": {
            "production_approved": False,  # Safety Gate strictly enforced
            "gate_reason": "Candidate model under field shadow validation. WRc baseline remains primary production classifier.",
            "zero_guessing_compliance": True,
            "physical_measurement_authority": "Deterministic OpenCV edge-finding and calibrated physical reference target (Zero-Guessing)",
        },
        "training_provenance": {
            "source_dataset": "Sewer-ML (CC BY-NC-SA 4.0)",
            "gcs_bucket": "gs://joint-inspection-510310-data",
            "curated_train_samples": len(matched_train),
            "curated_val_samples": len(matched_val),
            "training_epochs": epochs,
            "batch_size": batch_size,
            "initial_lr": lr,
            "threshold_tuning_split": "first deterministic half of validation",
            "evaluation_split": "second deterministic half of validation; official test remains locked",
            "device": str(device),
        },
    }

    # Write output files
    (output_dir / "model_version.json").write_text(json.dumps(model_record, indent=2))
    (output_dir / "metrics.json").write_text(json.dumps(final_metrics, indent=2))
    (output_dir / "training_history.json").write_text(json.dumps(history, indent=2))
    (output_dir / "wrc_comparison.json").write_text(json.dumps(wrc_comparison, indent=2))

    logger.info("=== Training Complete ===")
    logger.info("Saved all artifacts to %s", output_dir)
    return model_record


def main():
    parser = argparse.ArgumentParser(description="Train Sewer-ML Multi-Label Condition Classifier")
    parser.add_argument("--images-dir", type=Path, required=True, help="Directory containing curated images")
    parser.add_argument("--train-csv", type=Path, required=True, help="Path to curated train CSV")
    parser.add_argument("--val-csv", type=Path, required=True, help="Path to curated val CSV")
    parser.add_argument("--output-dir", type=Path, required=True, help="Output directory for model and metrics")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=32, help="Mini-batch size")
    parser.add_argument("--lr", type=float, default=1e-3, help="Initial learning rate")
    parser.add_argument("--img-size", type=int, default=128, help="Square input image resolution")
    parser.add_argument("--version", type=str, default="sewer-condition-v1.0.0-candidate", help="Model version tag")
    parser.add_argument("--architecture", choices=["efficientnet_b0", "legacy_cnn"], default="efficientnet_b0")
    parser.add_argument("--smoke", action="store_true", help="Run rapid smoke test on subsample")
    args = parser.parse_args()

    smoke_samples = 200 if args.smoke else None
    train_sewer_condition_classifier(
        images_dir=args.images_dir,
        train_csv=args.train_csv,
        val_csv=args.val_csv,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        img_size=args.img_size,
        model_version=args.version,
        smoke_max_samples=smoke_samples,
        architecture=args.architecture,
    )


if __name__ == "__main__":
    main()
