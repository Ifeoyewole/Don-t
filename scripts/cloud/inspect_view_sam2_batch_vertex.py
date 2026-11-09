"""GCS-only, bounded Vertex AI research batch for Unified Vision v1.

Never trains on quarantined media, calls Gemini, grants physical measurements,
or alters production. Loads Inspect View r5 and SAM2.1 Tiny once per worker.
Every image has an inspector-selected ROI and an independently recorded SHA.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import tempfile
from time import perf_counter
from typing import Any, Callable, Mapping

from backend.app.core.cv.ai.signed_gemini_receipt import verify_signed_semantic_receipt
from backend.app.core.cv.ai.unified_batch_manifest import (
    MAX_IMAGE_BYTES, MAX_MANIFEST_BYTES, BUCKET,
    checked_gcs_uri, checked_sha, validate_batch_manifest,
)
from scripts.cloud.inspect_view_sam2_vertex import (
    INSPECT_R5_SHA256, stage_verified, upload_create_only,
)


def safe_failure(reason: str) -> dict[str, Any]:
    """Explicit per-frame abstention; never report an engineering verdict."""
    return {
        "research_only": True,
        "decision": "REVIEW_REQUIRED",
        "defect": "UNDETERMINED",
        "reasons": [reason],
        "geometry": {"physical_gap_mm": None},
        "engineering_result": None,
    }


def build_summary(
    manifest_id: str,
    records: list[dict[str, Any]],
    *,
    image_digest: str,
    output_prefix: str,
    gpu_model: str,
) -> dict[str, Any]:
    """Only descriptive operational counts, never unsupervised accuracy."""
    status = Counter(r["run_status"] for r in records)
    rights = Counter(r["rights_status"] for r in records)
    source_labels = Counter(
        r["source_label"] for r in records if r.get("source_label")
    )
    reasons = Counter(
        reason for r in records for reason in r.get("reasons", [])
    )
    tasks = Counter(r.get("task_type", "JOINT_GEOMETRY") for r in records)
    return {
        "schema_version": "1.0",
        "research_only": True,
        "batch_status": "REVIEW_REQUIRED_INCOMPLETE" if status.get("FRAME_ERROR") else "REVIEW_REQUIRED_COMPLETE",
        "manifest_id": manifest_id,
        "manifest_sha256": image_digest,
        "output_prefix": output_prefix,
        "container_model": gpu_model,
        "count": len(records),
        "run_status_counts": dict(sorted(status.items())),
        "research_task_counts": dict(sorted(tasks.items())),
        "rights_counts": dict(sorted(rights.items())),
        "source_label_counts_unverified": dict(sorted(source_labels.items())),
        "reason_counts": dict(sorted(reasons.items())),
        "sam2_candidate_count": sum(r.get("segmentation_status") == "CANDIDATE_REVIEW" for r in records),
        "pixel_geometry_candidate_count": sum(r.get("pixel_candidate") is not None for r in records),
        "gemini_receipt_accepted_count": sum(
            r.get("gemini_status") in {"ADVISORY_DOMAIN_ACCEPTED", "RESEARCH_PIPE_INTERIOR_ACCEPTED"}
            for r in records
        ),
        "gemini_status_counts": dict(sorted(Counter(
            r.get("gemini_status", "NOT_PROVIDED") for r in records
        ).items())),
        "annotation_reviewed_count": sum(r.get("annotation_status") == "REVIEWED_GROUND_TRUTH" for r in records),
        "f1": None,
        "precision": None,
        "recall": None,
        "note": (
            "Descriptive research evidence only. Source labels are not ground truth; "
            "no accuracy, physical-mm, PASS/FAIL, or commercial data clearance is established."
        ),
    }


def _receipt_from_file(
    receipt_path: Path,
    *,
    frame_sha256: str,
    signing_secret: str,
) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    return verify_signed_semantic_receipt(
        receipt, original_image_sha256=frame_sha256,
        signing_secret=signing_secret,
    )


def _get_signing_secret(resource: str) -> str:
    """Fetch secret value only inside the GPU worker; never log its contents."""
    if not resource.startswith("projects/") or "/secrets/" not in resource or "/versions/" not in resource:
        raise ValueError("Expected full Secret Manager version resource")
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(request={"name": resource})
    return response.payload.data.decode("utf-8")


def evaluate(args) -> dict[str, Any]:
    from google.cloud import storage
    import torch

    from backend.app.api.v1.endpoints.engineering_preview import load_preview
    from backend.app.core.cv.ai.research_sam2_adapter import (
        _sam2_predictor, _verified_checkpoint,
    )
    from scripts.benchmark_inspect_view_sam2_fusion import analyze_local_image
    from scripts.task_aware_unified_review import analyze_nonjoint_image

    if not torch.cuda.is_available():
        raise RuntimeError("Batch requires a CUDA GPU; do not silently fall back")
    checked_gcs_uri(args.manifest_uri)
    checked_gcs_uri(args.inspect_uri)
    checked_gcs_uri(args.sam_uri)
    checked_gcs_uri(args.output_prefix + "/summary.json")
    checked_sha(args.manifest_sha)
    if checked_sha(args.inspect_sha) != INSPECT_R5_SHA256:
        raise ValueError("Inspect View checkpoint must match the pinned r5 digest")
    checked_sha(args.sam_sha)
    if args.limit < 1 or args.limit > 100:
        raise ValueError("Invalid GPU batch item limit")
    client = storage.Client(project=args.project)

    with tempfile.TemporaryDirectory(prefix="jointinspect-batch-") as root:
        base = Path(root)
        manifest_path = base / "batch_manifest.json"
        stage_verified(client, args.manifest_uri, manifest_path,
                       args.manifest_sha, max_bytes=MAX_MANIFEST_BYTES)
        manifest = validate_batch_manifest(json.loads(manifest_path.read_text("utf-8")))
        if len(manifest["frames"]) > args.limit:
            raise ValueError("Batch exceeds explicit requested limit")

        has_receipts = any("gemini_receipt_uri" in f for f in manifest["frames"])
        if has_receipts and not args.gemini_hmac_secret_resource:
            raise ValueError("Signed Gemini receipts require a Secret Manager version")
        key = _get_signing_secret(args.gemini_hmac_secret_resource) if has_receipts else None
        try:
            models_dir = base / "models"
            models_dir.mkdir()
            inspect_ckpt = models_dir / "inspect_r5.pt"
            sam_ckpt = models_dir / "sam2.1_hiera_tiny.pt"
            stage_verified(client, args.inspect_uri, inspect_ckpt, args.inspect_sha)
            stage_verified(client, args.sam_uri, sam_ckpt, args.sam_sha)
            if not _verified_checkpoint(sam_ckpt, args.sam_sha):
                raise ValueError("SAM2 checkpoint checksum mismatch")
            os.environ["JOINTINSPECT_PREVIEW_MODEL_PATH"] = str(inspect_ckpt)
            os.environ["JOINTINSPECT_SAM2_DEVICE"] = "cuda"
            load_preview()  # Pinned r5 weights: one load per batch worker
            predictor = _sam2_predictor(sam_ckpt)  # SAM2 weights: one load

            records: list[dict[str, Any]] = []
            output = args.output_prefix.rstrip("/")
            for frame in manifest["frames"]:
                fid = frame["frame_id"]
                frame_start = perf_counter()
                frame_dir = base / "current_frame"
                frame_dir.mkdir(exist_ok=True)
                img_file = frame_dir / "source_image.png"
                receipt_path = frame_dir / "receipt.json"
                report_path = frame_dir / "report.json"
                overlay_file = frame_dir / "overlay.png"
                mask_file = frame_dir / "mask.png"
                diagnostics_file = frame_dir / "runtime_diagnostics.json"
                failure_file = frame_dir / "failure.json"
                failure = None
                report = None
                task = frame["task_type"]
                try:
                    stage_verified(
                        client, frame["image_uri"], img_file, frame["image_sha256"],
                        max_bytes=MAX_IMAGE_BYTES,
                    )
                    verified_gemini = None
                    if "gemini_receipt_uri" in frame:
                        stage_verified(
                            client, frame["gemini_receipt_uri"], receipt_path,
                            frame["gemini_receipt_sha256"], max_bytes=64 * 1024,
                        )
                        # Fail this frame on forged, stale, or mismatched receipts,
                        # rather than treating an unsigned receipt as provider truth.
                        verified_gemini = _receipt_from_file(
                            receipt_path, frame_sha256=frame["image_sha256"],
                            signing_secret=key,
                        )
                    if task == "JOINT_GEOMETRY":
                        report, overlay = analyze_local_image(
                            img_file, geometry=frame["geometry"],
                            bbox=tuple(frame["roi"]),
                            checkpoint_path=sam_ckpt, checkpoint_sha256=args.sam_sha,
                            inspect_view_local=True,
                            gemini_receipt_json=(
                                receipt_path if verified_gemini is not None else None
                            ),
                            sam2_predictor_factory=lambda _: predictor,
                            mask_output_path=mask_file,
                        )
                        report["unified_result"]["task_type"] = "JOINT_GEOMETRY"
                    else:
                        # NEVER force a non-joint frame into seam/ring geometry.
                        report, overlay = analyze_nonjoint_image(
                            img_file, task_type=task,
                            bbox=tuple(frame["roi"]),
                            checkpoint_path=sam_ckpt,
                            checkpoint_sha256=args.sam_sha,
                            sam2_predictor_factory=lambda _: predictor,
                            mask_output_path=mask_file,
                            verified_gemini_receipt=verified_gemini,
                        )
                    report["batch_evidence"] = {
                        "manifest_id": manifest["manifest_id"],
                        "frame_id": fid,
                        "task_type": task,
                        "image_sha256": frame["image_sha256"],
                        "source_id": frame["source_id"],
                        "source_family": frame["source_family"],
                        "rights_status": frame["rights_status"],
                        "annotation_status": frame["annotation_status"],
                        "source_label_is_ground_truth": False,
                        "reviewed_label": frame.get("reviewed_label")
                            if frame["annotation_status"] == "REVIEWED_GROUND_TRUTH" else None,
                        "commercial_training_eligible": False,
                    }
                    if mask_file.exists():
                        upload_create_only(client,mask_file,f"{output}/frames/{fid}/mask.png","image/png")
                    from scripts.cloud.research_runtime_diagnostics import runtime_diagnostics
                    diagnostics_file.write_text(json.dumps(runtime_diagnostics(),indent=2))
                    upload_create_only(client,diagnostics_file,f"{output}/frames/{fid}/runtime_diagnostics.json","application/json")
                    report_path.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
                    upload_create_only(
                        client, report_path, f"{output}/frames/{fid}/report.json",
                        "application/json",
                    )
                    if overlay is not None:
                        import cv2
                        if not cv2.imwrite(str(overlay_file), overlay):
                            raise RuntimeError("Overlay output could not be written")
                        upload_create_only(
                            client, overlay_file, f"{output}/frames/{fid}/overlay.png",
                            "image/png",
                        )
                except Exception as exc:
                    # Do not leak secret values or arbitrary GCS object paths in
                    # error outputs. Keep running to yield a complete audit.
                    failure = type(exc).__name__
                    failure_file.write_text(json.dumps({'frame_id':fid,'failure_type':failure,'task_type':task,'research_only':True}))
                    upload_create_only(client,failure_file,f"{output}/frames/{fid}/failure.json","application/json")
                finally:
                    mask_file.unlink(missing_ok=True)
                    diagnostics_file.unlink(missing_ok=True)
                    failure_file.unlink(missing_ok=True)
                    img_file.unlink(missing_ok=True)
                    receipt_path.unlink(missing_ok=True)
                    overlay_file.unlink(missing_ok=True)
                    report_path.unlink(missing_ok=True)
                unified = (report or {}).get("unified_result") or safe_failure("FRAME_ERROR")
                record = {
                    "frame_id": fid,
                    "task_type": task,
                    "source_id": frame["source_id"],
                    "source_family": frame["source_family"],
                    "rights_status": frame["rights_status"],
                    "annotation_status": frame["annotation_status"],
                    "source_label": frame.get("source_label"),
                    "run_status": "FRAME_ERROR" if failure else "REVIEW_REQUIRED",
                    "failure_type": failure,
                    "decision": unified.get("decision", "REVIEW_REQUIRED"),
                    "primary_advisory": unified.get("primary_advisory"),
                    "segmentation_status": unified.get("segmentation", {}).get("status"),
                    "pixel_candidate": unified.get("geometry", {}).get("pixel_candidate"),
                    "gemini_status": unified.get("gemini", {}).get("status", "NOT_PROVIDED"),
                    "reasons": unified.get("reasons", ["FRAME_ERROR"]),
                    "elapsed_seconds": round(perf_counter() - frame_start, 3),
                }
                records.append(record)
                print(json.dumps({"frame_id": fid, "task_type": task,
                                  "run_status": record["run_status"],
                                  "decision": record["decision"]}), flush=True)

            summary = build_summary(
                manifest["manifest_id"], records,
                image_digest=args.manifest_sha,
                output_prefix=output,
                gpu_model="r5+sam2.1+opencv+optional-gemini-3.1-pro-receipts",
            )
            summary_file = base / "summary.json"
            summary_file.write_text(json.dumps(summary, indent=2) + "\n", "utf-8")
            rows_file = base / "frames.jsonl"
            rows_file.write_text(
                "".join(json.dumps(item, sort_keys=True) + "\n" for item in records),
                "utf-8",
            )
            upload_create_only(
                client, rows_file, output + "/frames.jsonl", "application/jsonl",
            )
            upload_create_only(
                client, summary_file, output + "/summary.json", "application/json",
            )
            if summary["batch_status"] == "REVIEW_REQUIRED_INCOMPLETE":
                raise RuntimeError("One or more batch frames failed; inspect sanitized summary")
            return {
                "status": summary["batch_status"], "count": len(records),
                "summary_uri": output + "/summary.json",
                "frames_uri": output + "/frames.jsonl",
            }
        finally:
            # Minimize the time the receipt signing key is referenced.
            key = None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for required in (
        "project", "manifest-uri", "manifest-sha",
        "inspect-uri", "inspect-sha", "sam-uri", "sam-sha", "output-prefix",
    ):
        parser.add_argument("--" + required, required=True)
    parser.add_argument("--gemini-hmac-secret-resource", default=None,
                        help="Secret Manager version resource, not a secret value")
    parser.add_argument("--limit", type=int, default=100)
    print(json.dumps(evaluate(parser.parse_args()), sort_keys=True))


if __name__ == "__main__":
    main()
