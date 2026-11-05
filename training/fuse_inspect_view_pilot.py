"""Class-aware pilot fusion using tuning labels only; development is report-only."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np

LABELS = [
    "NORMAL", "OPEN_JOINT", "FAULTY_JOINT", "JOINT_DISPLACEMENT",
    "JOINT_MISALIGNMENT", "DEFORMATION", "RUPTURE", "BROKEN_PIPE",
    "BLOCKAGE", "OBSTACLE", "INFILTRATION", "SURFACE_DAMAGE", "CORROSION",
    "PROTRUDING_LATERAL", "GEOMETRY_UNCERTAIN",
]
SEWER_MAP = {
    "ND": "NORMAL", "FS": "JOINT_DISPLACEMENT", "IS": "OBSTACLE",
    "RB": "BROKEN_PIPE", "DE": "DEFORMATION", "RO": "BLOCKAGE",
    "FO": "GEOMETRY_UNCERTAIN",
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def stats(truth: np.ndarray, probability: np.ndarray, threshold: float) -> dict:
    prediction = probability >= threshold
    truth = truth.astype(bool)
    tp = int((prediction & truth).sum()); fp = int((prediction & ~truth).sum())
    fn = int((~prediction & truth).sum()); tn = int((~prediction & ~truth).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    f2 = 5 * precision * recall / (4 * precision + recall) if 4 * precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "precision": precision,
            "recall": recall, "f1": f1, "f2": f2}


def best_threshold(truth: np.ndarray, probability: np.ndarray) -> tuple[float, dict]:
    options = [(value / 100, stats(truth, probability, value / 100)) for value in range(5, 96, 5)]
    return max(options, key=lambda item: (item[1]["f1"], item[1]["f2"], -item[0]))


def canonical_rows(path: Path) -> tuple[list[str], np.ndarray, dict[str, np.ndarray]]:
    rows = read_jsonl(path)
    ids = [row["sha256"] for row in rows]
    truth = np.asarray([[row["truth"][label] for label in LABELS] for row in rows], dtype=np.float32)
    values = {label: np.asarray([row["probabilities"][label] for row in rows], dtype=np.float32)
              for label in LABELS}
    return ids, truth, values


def legacy_rows(path: Path, reference_ids: list[str], adapted: bool = False,
                original: bool = False) -> dict[str, np.ndarray]:
    rows = read_jsonl(path)
    by_id = {
        row.get("source_sha256")
        or (Path(row["Filename"]).stem if row.get("Filename") else None)
        or Path(row["GCS_URI"]).stem: row
        for row in rows
    }
    ordered = [by_id[identity] for identity in reference_ids]
    class_key = "class_order" if adapted else "class_codes"
    class_order = ordered[0][class_key]
    matrix = np.asarray([row["probabilities"] for row in ordered], dtype=np.float32)
    if original:
        return {"JOINT_DISPLACEMENT": matrix[:, class_order.index("JD")]}
    output = {canonical: matrix[:, class_order.index(code)] for code, canonical in SEWER_MAP.items()}
    output["SURFACE_DAMAGE"] = np.maximum(matrix[:, class_order.index("AF")], matrix[:, class_order.index("BE")])
    return output


def report(truth: np.ndarray, probabilities: np.ndarray, thresholds: list[float]) -> dict:
    per_class, f1, f2 = {}, [], []
    for index, label in enumerate(LABELS):
        support = int(truth[:, index].sum())
        if not support:
            per_class[label] = {"support": 0, "evaluated": False, "threshold": thresholds[index]}
            continue
        value = stats(truth[:, index], probabilities[:, index], thresholds[index])
        value.update({"support": support, "evaluated": True, "threshold": thresholds[index]})
        per_class[label] = value; f1.append(value["f1"]); f2.append(value["f2"])
    return {"macro_f1": float(np.mean(f1)) if f1 else 0.0,
            "macro_f2": float(np.mean(f2)) if f2 else 0.0,
            "evaluated_classes": len(f1), "per_class": per_class}


def run(args):
    root = args.input_dir
    tune_ids, tune_truth, conv_tune = canonical_rows(root / "convnext-tiny-threshold_tune.jsonl")
    dev_ids, dev_truth, conv_dev = canonical_rows(root / "convnext-tiny-development_report.jsonl")
    eff_tune = canonical_rows(root / "efficientnet-b0-threshold_tune.jsonl")[2]
    eff_dev = canonical_rows(root / "efficientnet-b0-development_report.jsonl")[2]
    tune = {"convnext-tiny": conv_tune, "efficientnet-b0": eff_tune}
    dev = {"convnext-tiny": conv_dev, "efficientnet-b0": eff_dev}
    sources = [
        ("sewer-condition-v1", "sewer-condition-v1", False, False),
        ("sewer-condition-v2", "sewer-condition-v2", False, False),
        ("wrc-adapted", "wrc-adapted", True, False),
        ("wrc-original", "wrc-inceptionresnetv2-original", False, True),
    ]
    for name, stem, adapted, original in sources:
        tune[name] = legacy_rows(root / f"{stem}-threshold_tune.jsonl", tune_ids, adapted, original)
        dev[name] = legacy_rows(root / f"{stem}-development_report.jsonl", dev_ids, adapted, original)

    fused_tune = np.column_stack([conv_tune[label] for label in LABELS])
    fused_dev = np.column_stack([conv_dev[label] for label in LABELS])
    selections, thresholds = {}, []
    for index, label in enumerate(LABELS):
        truth = tune_truth[:, index]
        available = {name: values[label] for name, values in tune.items() if label in values}
        recipes = [({name: 1.0}, values) for name, values in available.items()]
        for left, right in itertools.combinations(available, 2):
            for weight in (0.25, 0.5, 0.75):
                recipes.append(({left: weight, right: 1 - weight},
                                weight * available[left] + (1 - weight) * available[right]))
        scored = []
        for weights, probability in recipes:
            threshold, metric = best_threshold(truth, probability)
            scored.append((metric["f1"], metric["f2"], weights, threshold, probability))
        best_single = max((item for item in scored if len(item[2]) == 1), key=lambda item: item[:2])
        best = max(scored, key=lambda item: item[:2])
        if len(best[2]) > 1 and (best[0] < best_single[0] + args.minimum_blend_gain or best[1] <= best_single[1]):
            best = best_single
        _, _, weights, threshold, tune_probability = best
        dev_probability = sum(weight * dev[name][label] for name, weight in weights.items())
        fused_tune[:, index] = tune_probability; fused_dev[:, index] = dev_probability
        thresholds.append(threshold)
        selections[label] = {"weights": weights, "threshold": threshold,
                             "tuning_metrics": stats(truth, tune_probability, threshold)}

    fusion_report = report(dev_truth, fused_dev, thresholds)
    standalone = {}
    for name in ("convnext-tiny", "efficientnet-b0"):
        model_thresholds = [best_threshold(tune_truth[:, i], tune[name][label])[0]
                            for i, label in enumerate(LABELS)]
        matrix = np.column_stack([dev[name][label] for label in LABELS])
        standalone[name] = report(dev_truth, matrix, model_thresholds)
    strongest_name = max(standalone, key=lambda name: (standalone[name]["macro_f1"], standalone[name]["macro_f2"]))
    strongest = standalone[strongest_name]
    result = {
        "schema_version": 1, "model_id": "inspect-view-pilot-fusion-r2",
        "selection_split": "threshold_tune", "evaluation_split": "development_report",
        "selection": selections, "development_report": fusion_report,
        "standalone_reports": standalone,
        "acceptance_gate": {"accepted": fusion_report["macro_f1"] > strongest["macro_f1"] and
                             fusion_report["macro_f2"] > strongest["macro_f2"],
                            "rule": "strictly exceed strongest standalone macro-F1 and macro-F2",
                            "best_standalone_model": strongest_name,
                            "best_standalone_macro_f1": strongest["macro_f1"],
                            "best_standalone_macro_f2": strongest["macro_f2"]},
        "threshold_tuning_count": len(tune_ids), "development_report_count": len(dev_ids),
        "locked_test_evaluated": False, "production_approved": False,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"fusion_macro_f1": fusion_report["macro_f1"],
                      "fusion_macro_f2": fusion_report["macro_f2"],
                      "acceptance": result["acceptance_gate"]}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-blend-gain", type=float, default=0.02)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
