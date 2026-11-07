"""GCS-only input and output runner for Vertex AI Inspect View r5 + SAM2.1.

Weights and CCTV bytes are staged only inside the ephemeral cloud worker.
No local-PC downloads, production API changes or measurement authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter

INSPECT_R5_SHA256 = "659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7"
MAX_IMAGE_BYTES = 8 * 1024 * 1024


def split_gs(uri: str) -> tuple[str, str]:
    if not isinstance(uri, str) or not uri.startswith("gs://"):
        raise ValueError("Expected gs://bucket/object")
    parts = uri[5:].split("/", 1)
    if len(parts) != 2 or not parts[0] or not parts[1] or ".." in parts[1].split("/"):
        raise ValueError("Expected gs://bucket/object without traversal")
    return parts[0], parts[1]


def checked_sha(value: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
        raise ValueError("Expected a reviewed 64-character SHA-256 digest")
    return value.lower()


def stage_verified(client, uri: str, dest: Path, expected: str, *, max_bytes: int | None = None) -> None:
    bucket, key = split_gs(uri)
    digest = checked_sha(expected)
    blob = client.bucket(bucket).blob(key)
    blob.reload()
    if max_bytes is not None and (blob.size is None or blob.size > max_bytes):
        raise ValueError("GCS image exceeds evaluation input limit")
    blob.download_to_filename(str(dest), if_generation_match=blob.generation)
    hasher = hashlib.sha256()
    with dest.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    if hasher.hexdigest() != digest:
        dest.unlink(missing_ok=True)
        raise ValueError(f"GCS object checksum mismatch: {uri}")


def upload_create_only(client, source: Path, destination: str, content_type: str) -> None:
    bucket, key = split_gs(destination)
    client.bucket(bucket).blob(key).upload_from_filename(
        str(source), content_type=content_type, if_generation_match=0,
    )


def evaluate(args) -> dict:
    from google.cloud import storage
    import torch
    from scripts.benchmark_inspect_view_sam2_fusion import analyze_local_image

    if args.inspect_sha.lower() != INSPECT_R5_SHA256:
        raise ValueError("Inspect View checkpoint does not match pinned r5 release")
    if not torch.cuda.is_available():
        raise RuntimeError("GPU unavailable; fail closed rather than silently using CPU")
    checked_sha(args.sam_sha)
    checked_sha(args.image_sha)
    split_gs(args.output_prefix.rstrip("/") + "/report.json")
    client = storage.Client(project=args.project)

    with tempfile.TemporaryDirectory(prefix="jointinspect-cloud-fusion-") as tmp:
        base = Path(tmp)
        image = base / "frame.png"
        inspect = base / "inspect_r5.pt"
        sam = base / "sam2.1_hiera_tiny.pt"
        stage_verified(client, args.image_uri, image, args.image_sha, max_bytes=MAX_IMAGE_BYTES)
        stage_verified(client, args.inspect_uri, inspect, args.inspect_sha)
        stage_verified(client, args.sam_uri, sam, args.sam_sha)

        os.environ["JOINTINSPECT_PREVIEW_MODEL_PATH"] = str(inspect)
        os.environ["JOINTINSPECT_SAM2_DEVICE"] = "cuda"
        started = perf_counter()
        report, overlay = analyze_local_image(
            image, geometry=args.geometry, bbox=tuple(args.roi),
            checkpoint_path=sam, checkpoint_sha256=args.sam_sha,
            inspect_view_local=True,
        )
        duration = perf_counter() - started
        if not report.get("inspect_view_ready"):
            raise RuntimeError("Inspect View r5 inference did not load successfully")
        if (report.get("sam2_status") == "MODEL_UNAVAILABLE"
                or report.get("sam2_reason") == "sam2_dependency_or_inference_unavailable"):
            raise RuntimeError("SAM2 checkpoint or predictor could not be loaded")

        report["cloud_run_context"] = {
            "service": "vertex-ai-custom-job",
            "project": args.project, "device": "cuda",
            "elapsed_seconds": round(duration, 3),
            "peak_gpu_allocated_mb": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
            "image_uri": args.image_uri, "image_sha256": args.image_sha.lower(),
            "inspect_view_model_uri": args.inspect_uri,
            "inspect_view_sha256": args.inspect_sha.lower(),
            "sam2_model_uri": args.sam_uri, "sam2_sha256": args.sam_sha.lower(),
            "model_weights_on_operator_pc": False,
        }
        out = base / "report.json"
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        destination = args.output_prefix.rstrip("/")
        if overlay is not None:
            import cv2
            overlay_path = base / "overlay.png"
            if not cv2.imwrite(str(overlay_path), overlay):
                raise RuntimeError("Could not write cloud overlay")
            upload_create_only(client, overlay_path, destination + "/overlay.png", "image/png")
        upload_create_only(client, out, destination + "/report.json", "application/json")
        return {"status": report["status"], "sam2_status": report["sam2_status"],
                "report_uri": destination + "/report.json"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("project", "image-uri", "image-sha", "inspect-uri",
                 "inspect-sha", "sam-uri", "sam-sha", "output-prefix"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--geometry", choices=(
        "VERTICAL_SEAM", "HORIZONTAL_SEAM", "CIRCULAR_OPENING"), required=True)
    parser.add_argument("--roi", nargs=4, type=int, required=True,
                        metavar=("X0", "Y0", "X1", "Y1"))
    print(json.dumps(evaluate(parser.parse_args()), sort_keys=True))


if __name__ == "__main__":
    main()
