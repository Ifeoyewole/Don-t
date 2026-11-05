"""Download and inventory the pinned SRuibo dataset for quarantined GCS import."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import storage
from huggingface_hub import snapshot_download
from PIL import Image


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def dhash(path: Path, size: int = 8) -> str:
    with Image.open(path) as image:
        gray = image.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
        pixels = list(gray.getdata())
    value = 0
    for row in range(size):
        offset = row * (size + 1)
        for column in range(size):
            value = (value << 1) | int(pixels[offset + column + 1] > pixels[offset + column])
    return f"{value:016x}"


def nearest_hamming(value: str, candidates: set[str], maximum: int = 4) -> int | None:
    number = int(value, 16)
    best = None
    for candidate in candidates:
        distance = (number ^ int(candidate, 16)).bit_count()
        if distance <= maximum and (best is None or distance < best):
            best = distance
            if best == 0:
                break
    return best


def baseline_hashes(client: storage.Client, uri: str) -> tuple[set[str], set[str]]:
    if not uri.startswith("gs://"):
        raise ValueError("Baseline manifest must be a gs:// URI")
    bucket, name = uri[5:].split("/", 1)
    manifest = json.loads(client.bucket(bucket).blob(name).download_as_text())
    return (
        {row["sha256"] for row in manifest["records"] if row.get("sha256")},
        {row["dhash"] for row in manifest["records"] if row.get("dhash")},
    )


def build_manifest(root: Path, revision: str, source_uri: str,
                   baseline_sha: set[str], baseline_dhash: set[str]) -> dict:
    dataset_root = root / "Sewer pipe defects"
    classes = [line.strip() for line in (dataset_root / "classes.txt").read_text().splitlines() if line.strip()]
    records = []
    for split in ("train", "val", "test"):
        image_root = dataset_root / "images" / split
        label_root = dataset_root / "labels" / split
        for image_path in sorted(path for path in image_root.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES):
            label_path = label_root / f"{image_path.stem}.txt"
            if not label_path.is_file():
                raise RuntimeError(f"Missing paired label: {label_path.relative_to(root)}")
            sha256 = hashlib.sha256(image_path.read_bytes()).hexdigest()
            perceptual = dhash(image_path)
            with Image.open(image_path) as image:
                width, height = image.size
            if sha256 in baseline_sha:
                duplicate_status = "EXACT_SHA256_BASELINE"
                near_distance = 0
            elif perceptual in baseline_dhash:
                duplicate_status = "EXACT_DHASH_BASELINE"
                near_distance = 0
            else:
                near_distance = nearest_hamming(perceptual, baseline_dhash)
                duplicate_status = "NEAR_DHASH_BASELINE" if near_distance is not None else "UNIQUE_TO_BASELINE"
            source_labels = sorted({classes[int(line.split()[0])] for line in label_path.read_text().splitlines() if line.strip()})
            records.append({
                "dataset_name": "SRuibo/Sewer-pipe-defects",
                "dataset_version": revision,
                "source": source_uri,
                "original_media_id": image_path.stem,
                "original_image_path": str(image_path.relative_to(root)),
                "original_annotation_path": str(label_path.relative_to(root)),
                "source_labels": source_labels,
                "jointinspect_labels": ["GEOMETRY_UNCERTAIN"],
                "sha256": sha256,
                "dhash": perceptual,
                "split": split,
                "annotation_type": "YOLO_BOUNDING_BOX",
                "width": width,
                "height": height,
                "date_imported": datetime.now(timezone.utc).isoformat(),
                "duplicate_status": duplicate_status,
                "near_duplicate_hamming_distance": near_distance,
                "training_eligibility": "QUARANTINED_PENDING_PROVENANCE_AND_LABEL_REVIEW",
                "model_experiments": [],
            })
    return {
        "schema_version": 1,
        "dataset_name": "SRuibo/Sewer-pipe-defects",
        "dataset_version": revision,
        "source": source_uri,
        "original_classes": classes,
        "record_count": len(records),
        "split_counts": {split: sum(row["split"] == split for row in records) for split in ("train", "val", "test")},
        "duplicate_counts": {
            status: sum(row["duplicate_status"] == status for row in records)
            for status in sorted({row["duplicate_status"] for row in records})
        },
        "records": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--baseline-manifest", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args()
    source = "https://huggingface.co/datasets/SRuibo/Sewer-pipe-defects"
    snapshot_download(
        repo_id="SRuibo/Sewer-pipe-defects", repo_type="dataset", revision=args.revision,
        local_dir=args.output_root,
        allow_patterns=["README.md", "Sewer pipe defects/**"],
        max_workers=1,
    )
    client = storage.Client(project=args.project)
    sha256, perceptual = baseline_hashes(client, args.baseline_manifest)
    manifest = build_manifest(args.output_root, args.revision, source, sha256, perceptual)
    args.manifest_output.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({key: manifest[key] for key in ("record_count", "split_counts", "duplicate_counts")}, indent=2))


if __name__ == "__main__":
    main()
