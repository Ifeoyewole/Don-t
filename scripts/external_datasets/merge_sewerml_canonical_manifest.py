"""Merge verified Sewer-ML v4 records into a versioned canonical representation manifest."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

SEWER_MAP = {
    "ND": "NORMAL", "FS": "JOINT_DISPLACEMENT", "IS": "OBSTACLE",
    "RB": "BROKEN_PIPE", "DE": "DEFORMATION", "RO": "BLOCKAGE",
    "AF": "SURFACE_DAMAGE", "BE": "SURFACE_DAMAGE", "FO": "GEOMETRY_UNCERTAIN",
}


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def family_id(row: dict) -> str:
    stem = Path(row["Filename"]).stem
    try:
        return f"{row['source_group']}:{int(stem) // 100:06d}"
    except ValueError:
        return f"{row['source_group']}:{stem.casefold()}"


def canonical_labels(row: dict) -> tuple[list[str], list[str]]:
    source = [code for code in SEWER_MAP if row.get(code) in {"1", "1.0"}]
    return source, sorted({SEWER_MAP[code] for code in source})


def merge(args) -> dict:
    expanded = read_jsonl(args.expanded_manifest)
    metadata = {row["sha256"]: row for row in json.loads(args.sewerml_manifest.read_text())["records"]}
    seen_sha = {row["sha256"] for row in expanded}
    split_sha = {split: {row["sha256"] for row in expanded if row["split"] == split}
                 for split in ("train", "val", "test")}
    split_dhash = {split: {row["dhash"] for row in expanded if row["split"] == split and row.get("dhash")}
                   for split in ("train", "val", "test")}
    added, excluded = [], Counter()
    sources = [
        ("train", args.train, "train"),
        ("early_stop", args.early_stop, "val"),
        ("threshold_tune", args.threshold_tune, "val"),
        ("dev_report", args.dev_report, "val"),
    ]
    for original_split, path, target_split in sources:
        for row in read_csv(path):
            digest = row["sha256"]
            if digest in seen_sha:
                excluded["repeated_sha256"] += 1
                continue
            detail = metadata.get(digest, row)
            dhash = detail.get("dhash")
            other_splits = {name for name in split_dhash if name != target_split}
            if dhash and any(dhash in split_dhash[name] for name in other_splits):
                excluded["cross_split_exact_dhash"] += 1
                continue
            source_labels, labels = canonical_labels(row)
            if not labels:
                excluded["no_supported_canonical_label"] += 1
                continue
            record = {
                "dataset_name": "Sewer-ML",
                "dataset_version": "curated-v4-20k",
                "original_media_id": row["Filename"],
                "media_family_id": family_id(row),
                "original_split": original_split,
                "split": target_split,
                "image_uri": row["GCS_URI"],
                "annotation_uri": None,
                "source_labels": source_labels,
                "jointinspect_labels": labels,
                "annotation_type": "MULTILABEL_IMAGE_CLASSIFICATION",
                "sha256": digest,
                "dhash": dhash,
                "width": None,
                "height": None,
                "training_eligibility": "VERIFIED_SEWERML_V4_RESEARCH",
                "source_group": row["source_group"],
            }
            added.append(record); seen_sha.add(digest); split_sha[target_split].add(digest)
            if dhash: split_dhash[target_split].add(dhash)

    combined = expanded + added
    # Deduplicate exact perceptual hashes globally. Prefer held-out evidence so a
    # near-identical training record can never contaminate validation or test.
    split_priority = {"test": 0, "val": 1, "train": 2}
    grouped_dhash: dict[str, list[dict]] = {}
    without_dhash = []
    for row in combined:
        if row.get("dhash"):
            grouped_dhash.setdefault(row["dhash"], []).append(row)
        else:
            without_dhash.append(row)
    deduplicated = list(without_dhash)
    for rows in grouped_dhash.values():
        rows.sort(key=lambda row: (
            split_priority[row["split"]], row["dataset_name"],
            row["media_family_id"], row["sha256"],
        ))
        deduplicated.append(rows[0])
        excluded["global_exact_dhash_duplicate"] += len(rows) - 1
    combined = deduplicated
    combined.sort(key=lambda row: (row["split"], row["dataset_name"], row["media_family_id"], row["sha256"]))
    family_splits: dict[tuple[str, str], set[str]] = {}
    for row in combined:
        family_splits.setdefault((row["dataset_name"], row["media_family_id"]), set()).add(row["split"])
    leaking = [key for key, splits in family_splits.items() if len(splits) > 1]
    if leaking:
        raise RuntimeError(f"Media family split leakage: {leaking[:5]}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as destination:
        for row in combined:
            destination.write(json.dumps(row, separators=(",", ":")) + "\n")
    label_counts = {split: Counter() for split in ("train", "val", "test")}
    for row in combined:
        label_counts[row["split"]].update(row.get("jointinspect_labels", []))
    summary = {
        "schema_version": 1,
        "manifest_id": args.manifest_id,
        "base_records": len(expanded), "sewerml_records_added": len(added),
        "total_records": len(combined),
        "split_counts": dict(Counter(row["split"] for row in combined)),
        "label_counts": {split: dict(counts) for split, counts in label_counts.items()},
        "family_count": len(family_splits), "excluded": dict(excluded),
        "locked_test_included": False, "production_eligible": False,
    }
    args.summary.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expanded-manifest", type=Path, required=True)
    parser.add_argument("--sewerml-manifest", type=Path, required=True)
    for split in ("train", "early-stop", "threshold-tune", "dev-report"):
        parser.add_argument("--" + split, type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--manifest-id", required=True)
    args = parser.parse_args()
    print(json.dumps(merge(args), indent=2))


if __name__ == "__main__":
    main()
