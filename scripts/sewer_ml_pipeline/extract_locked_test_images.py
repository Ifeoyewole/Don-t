"""Select and extract a deterministic locked Sewer-ML test subset inside GCP only."""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import subprocess
import zipfile
from collections import defaultdict
from pathlib import Path

from google.cloud import storage

TARGETS = ["FS", "IS", "RB", "DE", "RO", "AF", "BE", "FO", "ND"]
BUCKET = "joint-inspection-510310-data"
ROOT = "datasets/sewer-ml/locked-test-v1"


def active_labels(row: dict[str, str]) -> tuple[str, ...]:
    labels = tuple(label for label in TARGETS if row.get(label) in {"1", "1.0"})
    return labels or ("OTHER",)


def main() -> None:
    random.seed(20261014)
    client = storage.Client()
    bucket = client.bucket(BUCKET)
    annotation_path = Path("/tmp/SewerML_Test.csv")
    bucket.blob("datasets/sewer-ml/original-annotations/SewerML_Test.csv").download_to_filename(annotation_path)
    with annotation_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("Official test annotation is empty")

    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[active_labels(row)].append(row)
    selected: dict[str, dict[str, str]] = {}
    for label_group in sorted(grouped):
        candidates = grouped[label_group]
        random.shuffle(candidates)
        for row in candidates[: min(150, len(candidates))]:
            selected[row["Filename"]] = row
    # Deterministic cap prevents downloading the entire 303 GB corpus.
    selected = dict(sorted(selected.items())[:2000])

    password = os.environ["SEWER_PASSWORD"].strip()
    extract_root = Path("/tmp/locked-test")
    extract_root.mkdir(parents=True, exist_ok=True)
    found: dict[str, str] = {}
    for archive in ("test00.zip", "test01.zip"):
        archive_path = Path("/tmp") / archive
        subprocess.run([
            "curl", "--location-trusted", "-u", f"operator:{password}", "-f", "-sS",
            "-o", str(archive_path), f"https://sciencedata.dk/public/Large%20AAU%20files/Sewer_ML/{archive}",
        ], check=True)
        with zipfile.ZipFile(archive_path) as zipped:
            for member in zipped.infolist():
                base = Path(member.filename).name
                if base not in selected or base in found:
                    continue
                destination = extract_root / base
                with zipped.open(member) as source, destination.open("wb") as target:
                    target.write(source.read())
                found[base] = archive
        archive_path.unlink()

    missing = sorted(set(selected) - set(found))
    if missing:
        raise RuntimeError(f"Locked test extraction incomplete: {len(missing)} selected images missing")

    manifest_rows = []
    for filename, row in selected.items():
        path = extract_root / filename
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        object_name = f"{ROOT}/images/{filename}"
        bucket.blob(object_name).upload_from_filename(path, content_type="image/png")
        manifest_rows.append({**row, "source_archive": found[filename], "sha256": digest, "GCS_URI": f"gs://{BUCKET}/{object_name}"})
        path.unlink()

    manifest_path = Path("/tmp/locked_test_manifest.csv")
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)
    bucket.blob(f"{ROOT}/manifest.csv").upload_from_filename(manifest_path)
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    report = {
        "status": "LOCKED", "sample_count": len(manifest_rows), "seed": 20261014,
        "manifest_sha256": manifest_sha, "source_archives": sorted(set(found.values())),
        "local_pc_dataset_bytes": 0, "selection_cap": 2000,
    }
    bucket.blob(f"{ROOT}/integrity.json").upload_from_string(json.dumps(report, indent=2), content_type="application/json")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
