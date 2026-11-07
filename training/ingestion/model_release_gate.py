"""Fail-closed commercial model release *policy* screening.

This is not a legal opinion and does not verify signed documents or chain of
title on its own. It prevents automatic promotion of research-derived weights,
unreviewed source data, undisclosed pretrained ancestors, and unknown licenses.
Keep legal evidence outside the public repository; store only ticket pointers.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PERMISSIVE_CODE_LICENSES = {"Apache-2.0", "MIT", "BSD-3-Clause", "BSD-2-Clause", "ISC"}
_BLOCKED_ANCESTRY_TERMS = ("sewer-ml", "sewerml", "noncommercial", "cc-by-nc", "cc by-nc", "agpl", "ultralytics")


def screen_model_manifest(manifest: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    """Evaluate evidence metadata; never silently infer that an artifact is clear."""
    blockers: list[str] = []
    model_id = manifest.get("model_id")
    if not isinstance(model_id, str) or not model_id.strip():
        blockers.append("Missing model identifier")

    architecture = manifest.get("architecture") or {}
    if architecture.get("code_license") not in _PERMISSIVE_CODE_LICENSES:
        blockers.append("Architecture code license not on explicit permissive allowlist")
    if not isinstance(architecture.get("upstream_revision"), str) or len(architecture["upstream_revision"]) < 8:
        blockers.append("Upstream source must be pinned to a reviewable revision")
    if not isinstance(architecture.get("license_notice_reference"), str) or not architecture["license_notice_reference"].strip():
        blockers.append("License and NOTICE obligations need an evidence record")

    weights = manifest.get("weights") or {}
    if weights.get("origin") != "TRAINED_FROM_SCRATCH":
        blockers.append("Only from-scratch weights are eligible in this clean-commercial pilot")
    digest = weights.get("sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        blockers.append("Final model artifact needs a valid SHA-256 digest")
    if weights.get("pretrained_weights_used") is not False:
        blockers.append("Pretrained checkpoint ancestry must be explicitly absent")
    ancestors = weights.get("ancestor_model_ids")
    if not isinstance(ancestors, list) or ancestors:
        blockers.append("Nonempty or undeclared pretrained/model-fusion ancestry")
    if weights.get("inspect_view_fusion_used") is not False:
        blockers.append("Sewer-ML-derived Inspect View fusion is forbidden in clean commercial candidate")

    registry_sources = {x.get("source_id"): x for x in registry.get("sources", [])}
    source_ids = manifest.get("training_source_ids")
    if not isinstance(source_ids, list) or not source_ids:
        blockers.append("Training sources not enumerated")
    else:
        for source_id in source_ids:
            src = registry_sources.get(source_id)
            if not src:
                blockers.append(f"Unregistered training source: {str(source_id)[:80]}")
                continue
            if not all((
                src.get("production_eligible") is True,
                src.get("commercial_training_allowed") is True,
                src.get("commercial_deployment_allowed") is True,
                src.get("provenance_verified") is True,
                src.get("benchmark_only") is False,
                src.get("approval_status") == "APPROVED_PRODUCTION",
                isinstance(src.get("rights_document_reference"), str),
                bool((src.get("rights_document_reference") or "").strip()),
            )):
                blockers.append(f"Source does not meet production eligibility and rights evidence: {source_id}")
            license_name = (src.get("license_name") or "").lower()
            source_identity = f"{source_id} {src.get('name', '')} {license_name}".lower()
            if any(term in source_identity for term in _BLOCKED_ANCESTRY_TERMS):
                blockers.append(f"Restricted or research-only lineage in source: {source_id}")

    review = manifest.get("independent_rights_review") or {}
    if not all((
        review.get("status") == "APPROVED_FOR_COMMERCIAL_TRAINING_AND_DEPLOYMENT",
        isinstance(review.get("reviewer"), str) and bool(review["reviewer"].strip()),
        isinstance(review.get("rights_evidence_reference"), str) and
        bool(review["rights_evidence_reference"].strip()),
        isinstance(review.get("review_date"), str) and bool(review["review_date"].strip()),
    )):
        blockers.append("Independent documentary rights sign-off missing")

    return {
        "model_id": model_id,
        "policy_screen_passed": not blockers,
        "commercial_release_eligible": not blockers,
        "blockers": blockers,
        "limitation": "Metadata screening only; independent legal and source-document verification is required.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--registry",
        default=Path("training/data_sources/source_registry.json"),
        type=Path,
    )
    args = parser.parse_args()
    report = screen_model_manifest(
        json.loads(args.manifest.read_text(encoding="utf-8")),
        json.loads(args.registry.read_text(encoding="utf-8")),
    )
    print(json.dumps(report, indent=2))
    return 0 if report["policy_screen_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
