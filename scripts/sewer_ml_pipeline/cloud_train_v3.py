"""Cloud-only GCS staging and artifact publication for Sewer-ML v3.

The worker downloads only objects named by immutable split manifests, verifies every
image digest, invokes the native trainer, validates its required outputs, and uploads
the research candidate with create-only GCS preconditions. It never reads locked-test
data and never permits a workstation execution path.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from curate_staged import TARGETS, gcp_attestation, group_id, verify_disjoint

MAX_FILES = 30_000
MAX_TOTAL_BYTES = 250 * 1024**3
REQUIRED_ARTIFACTS = ("best.pt", "model.onnx", "metrics.json", "history.json", "model_card.json")
SPLITS = ("train", "early_stop", "threshold_tune", "dev_report")


def parse_gs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"Expected gs:// URI: {uri}")
    bucket, sep, name = uri[5:].partition("/")
    if not sep or not bucket or not name or ".." in PurePosixPath(name).parts:
        raise ValueError(f"Unsafe GCS URI: {uri}")
    return bucket, name


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_rows(split_rows: dict[str, list[dict]], allowed_bucket: str | None = None) -> dict[str, int]:
    if set(split_rows) != set(SPLITS) or any(not split_rows[name] for name in SPLITS):
        raise ValueError("All four non-empty training/development splits are required")
    verify_disjoint(split_rows)
    total = 0
    for split, rows in split_rows.items():
        for row in rows:
            filename = str(row.get("Filename", ""))
            if Path(filename).name != filename or not group_id(row):
                raise ValueError(f"{split}: unsafe filename or missing group provenance")
            if len(str(row.get("sha256", ""))) != 64:
                raise ValueError(f"{split}: missing SHA-256 for {filename}")
            bucket_name, _ = parse_gs_uri(str(row.get("GCS_URI", "")))
            if allowed_bucket and bucket_name != allowed_bucket:
                raise ValueError(f"{split}: image is outside the approved GCS bucket")
            if not any(row.get(code) in ("1", "1.0", 1, 1.0) for code in TARGETS):
                raise ValueError(f"{split}: {filename} has no recognized target label")
            total += 1
    if total > MAX_FILES:
        raise ValueError(f"Manifest exceeds {MAX_FILES} image safety cap")
    return {name: len(rows) for name, rows in split_rows.items()}


def read_csv_bytes(payload: bytes) -> list[dict]:
    text = payload.decode("utf-8-sig").splitlines()
    return list(csv.DictReader(text))


def download_verified(blob, destination: Path, expected_sha256: str, remaining_bytes: int) -> int:
    blob.reload()
    size = int(blob.size or 0)
    if size < 1 or size > remaining_bytes:
        raise RuntimeError("GCS staging byte limit exceeded")
    destination.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(destination))
    if sha256_file(destination) != expected_sha256.lower():
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Checksum mismatch: {blob.name}")
    return size


def artifact_inventory(output: Path) -> list[dict]:
    missing = [name for name in REQUIRED_ARTIFACTS if not (output / name).is_file()]
    if missing:
        raise RuntimeError(f"Missing training artifacts: {missing}")
    card = json.loads((output / "model_card.json").read_text())
    if card.get("production_approved") is not False or card.get("locked_test_evaluated") is not False:
        raise RuntimeError("Research-candidate safety flags are invalid")
    return [
        {"name": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(output.iterdir()) if path.is_file() and path.name != "resume.pt"
    ]


def run(args) -> None:
    gcp_attestation(args.project)
    from google.cloud import storage

    client = storage.Client(project=args.project)
    work = Path(tempfile.mkdtemp(prefix="sewerml-v3-", dir=args.scratch_root))
    try:
        manifests = work / "manifests"
        images = work / "images"
        output = work / "output"
        manifests.mkdir(); images.mkdir(); output.mkdir()
        split_rows = {}
        manifest_hashes = {}
        for split in SPLITS:
            bucket_name, object_name = parse_gs_uri(getattr(args, split))
            if bucket_name != args.allowed_bucket:
                raise ValueError("Manifest is outside the approved GCS bucket")
            payload = client.bucket(bucket_name).blob(object_name).download_as_bytes()
            manifest_hashes[split] = hashlib.sha256(payload).hexdigest()
            (manifests / f"{split}.csv").write_bytes(payload)
            split_rows[split] = read_csv_bytes(payload)
        split_counts = validate_rows(split_rows, args.allowed_bucket)
        consumed = 0
        seen = set()
        for rows in split_rows.values():
            for row in rows:
                filename = row["Filename"]
                if filename in seen:
                    continue
                seen.add(filename)
                bucket_name, object_name = parse_gs_uri(row["GCS_URI"])
                consumed += download_verified(
                    client.bucket(bucket_name).blob(object_name), images / filename,
                    row["sha256"], MAX_TOTAL_BYTES - consumed,
                )
        out_bucket, out_prefix = parse_gs_uri(args.output_prefix)
        if out_bucket != args.allowed_bucket:
            raise ValueError("Output is outside the approved GCS bucket")
        checkpoint_bucket = client.bucket(out_bucket)
        for name in ("resume.pt", "best.pt"):
            checkpoint = checkpoint_bucket.blob(f"{out_prefix.rstrip('/')}/checkpoints/{name}")
            if checkpoint.exists():
                checkpoint.download_to_filename(str(output / name))
        command = [
            sys.executable, str(Path(__file__).with_name("train_v3.py")),
            "--project", args.project,
            "--train", str(manifests / "train.csv"),
            "--early-stop", str(manifests / "early_stop.csv"),
            "--threshold-tune", str(manifests / "threshold_tune.csv"),
            "--dev-report", str(manifests / "dev_report.csv"),
            "--images-dir", str(images), "--output", str(output),
            "--config-id", args.config_id, "--architecture", args.architecture,
            "--epochs", str(args.epochs), "--batch-size", str(args.batch_size),
            "--workers", str(args.workers), "--resume",
            "--checkpoint-prefix", f"gs://{out_bucket}/{out_prefix.rstrip('/')}/checkpoints",
        ]
        subprocess.run(command, check=True)
        inventory = artifact_inventory(output)
        provenance = {
            "config_id": args.config_id, "manifest_sha256": manifest_hashes,
            "split_counts": split_counts, "staged_image_bytes": consumed,
            "artifacts": inventory, "production_approved": False,
            "locked_test_evaluated": False,
        }
        (output / "candidate_manifest.json").write_text(json.dumps(provenance, indent=2))
        for path in sorted(output.iterdir()):
            if not path.is_file() or path.name == "resume.pt":
                continue
            target = client.bucket(out_bucket).blob(f"{out_prefix.rstrip('/')}/{path.name}")
            target.metadata = {"sha256": sha256_file(path), "config_id": args.config_id,
                               "production_approved": "false"}
            target.upload_from_filename(str(path), if_generation_match=0)
        print(json.dumps({"uploaded": True, "output_prefix": args.output_prefix,
                          "artifacts": len(inventory) + 1, "production_approved": False}))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="joint-inspection-510310")
    parser.add_argument("--allowed-bucket", default="joint-inspection-510310-data")
    for name in SPLITS:
        parser.add_argument("--" + name.replace("_", "-"), required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--config-id", required=True)
    parser.add_argument("--architecture", choices=("efficientnet_b0", "convnext_tiny"), default="efficientnet_b0")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--scratch-root", default="/workspace/tmp")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
