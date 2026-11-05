"""Canonical manifest loader and bounded CPU smoke validation for Inspect View."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

from google.cloud import storage
from PIL import Image


def split_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"Expected gs:// URI: {uri}")
    return uri[5:].split("/", 1)


def read_gcs(client: storage.Client, uri: str) -> bytes:
    bucket, name = split_gcs(uri)
    return client.bucket(bucket).blob(name).download_as_bytes()


def read_jsonl(client: storage.Client, uri: str) -> list[dict]:
    return [json.loads(line) for line in read_gcs(client, uri).decode().splitlines() if line.strip()]


def parse_yolo_annotations(payload: bytes) -> list[dict]:
    annotations = []
    for number, line in enumerate(payload.decode().splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        class_id = int(fields[0])
        values = tuple(float(value) for value in fields[1:])
        if class_id < 0 or any(value < 0 or value > 1 for value in values):
            raise ValueError(f"Invalid normalized YOLO box on line {number}")
        if len(values) == 4:
            annotation_type = "BOUNDING_BOX"
        elif len(values) >= 6 and len(values) % 2 == 0:
            annotation_type = "SEGMENTATION_POLYGON"
        else:
            raise ValueError(f"Unsupported YOLO line {number} with {len(fields)} fields")
        annotations.append({"class_id": class_id, "type": annotation_type, "values": values})
    return annotations


def parse_yolo_boxes(payload: bytes) -> list[tuple[int, float, float, float, float]]:
    """Compatibility helper for callers that require bounding boxes only."""
    annotations = parse_yolo_annotations(payload)
    if any(item["type"] != "BOUNDING_BOX" for item in annotations):
        raise ValueError("Annotation payload contains non-box geometry")
    return [(item["class_id"], *item["values"]) for item in annotations]


def deterministic_samples(rows: list[dict], per_split: int) -> list[dict]:
    selected = []
    for split in ("train", "val", "test"):
        candidates = [row for row in rows if row["split"] == split]
        candidates.sort(key=lambda row: hashlib.sha256(row["sha256"].encode()).digest())
        selected.extend(candidates[:per_split])
    return selected


def validate_manifest(client: storage.Client, manifest_uri: str, per_split: int) -> dict:
    rows = read_jsonl(client, manifest_uri)
    sha_values = [row["sha256"] for row in rows]
    if len(sha_values) != len(set(sha_values)):
        raise ValueError("Manifest contains repeated SHA-256 values")
    family_splits: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        family_splits.setdefault((row["dataset_name"], row["media_family_id"]), set()).add(row["split"])
    leaking = [key for key, splits in family_splits.items() if len(splits) != 1]
    if leaking:
        raise ValueError(f"Media family split leakage: {leaking[:3]}")
    sample_results = []
    for row in deterministic_samples(rows, per_split):
        image_payload = read_gcs(client, row["image_uri"])
        annotation_payload = read_gcs(client, row["annotation_uri"])
        with Image.open(io.BytesIO(image_payload)) as image:
            actual_size = image.size
            image.verify()
        if actual_size != (row["width"], row["height"]):
            raise ValueError(f"Dimension mismatch for {row['image_uri']}")
        annotations = parse_yolo_annotations(annotation_payload)
        sample_results.append({
            "dataset_name": row["dataset_name"],
            "split": row["split"],
            "sha256_verified": hashlib.sha256(image_payload).hexdigest() == row["sha256"],
            "width": actual_size[0],
            "height": actual_size[1],
            "annotation_count": len(annotations),
            "annotation_types": sorted({item["type"] for item in annotations}),
        })
    if not all(row["sha256_verified"] for row in sample_results):
        raise ValueError("Sampled media SHA-256 verification failed")
    return {
        "manifest_uri": manifest_uri,
        "status": "PASS",
        "record_count": len(rows),
        "family_count": len(family_splits),
        "split_counts": dict(Counter(row["split"] for row in rows)),
        "sample_count": len(sample_results),
        "sample_results": sample_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--manifest", action="append", required=True)
    parser.add_argument("--samples-per-split", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    client = storage.Client(project=args.project)
    reports = [validate_manifest(client, uri, args.samples_per_split) for uri in args.manifest]
    result = {"status": "PASS", "reports": reports}
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "manifests": [r["record_count"] for r in reports]}))


if __name__ == "__main__":
    main()
