"""Research-only task-aware decisions for non-joint pipe interior imagery."""

import hashlib

import pytest

from backend.app.core.cv.ai.unified_task_decision import (
    build_nonjoint_research_result,
)

SHA = "a"*64
R5 = "repr-convnext-masked-r5-20261104"


def preview(classes=None):
    return {
        "research_preview": True,
        "model_ready": True,
        "model_version": R5,
        "image_sha256": SHA,
        "classes": classes or {
            "PROTRUDING_LATERAL": {
                "status": "EXPLORATORY", "detected": True,
                "probability": 0.99,
            },
            "SURFACE_DAMAGE": {
                "status": "EXPLORATORY", "detected": True,
                "probability": 0.78,
            },
        },
    }


def receipt(domain="PIPE_INTERIOR_NO_JOINT", **changes):
    gate = {
        "model": "gemini-3.1-pro-preview",
        "domain_status": domain,
        "pipe_visible": True,
        "joint_visible": domain == "PIPE_JOINT_INSPECTION",
        "quality": "OK",
        "prompt_image_conflict": False,
        "processing_allowed": domain == "PIPE_JOINT_INSPECTION",
    }
    gate.update(changes)
    return {"image_sha256": SHA, "semantic_gate": gate}


def build(task="OBJECT_SEGMENTATION", **changes):
    args = {
        "task_type": task,
        "image_sha256": SHA,
        "inspect_view_payload": preview(),
        "sam2_status": "MASK_CANDIDATE_RESEARCH",
        "sam2_bbox": (30, 40, 220, 300),
        "sam2_quality": 0.9,
        "mask_pixel_verified": True,
        "verified_gemini_receipt": receipt(),
    }
    args.update(changes)
    return build_nonjoint_research_result(**args)


def test_object_task_can_assess_nonjoint_pipe_without_overriding_live_gate():
    r = build()
    assert r["decision"] == "REVIEW_REQUIRED"
    assert r["defect"] == "UNDETERMINED"
    assert r["segmentation"]["status"] == "CANDIDATE_REVIEW"
    assert r["geometry"] == {
        "type": None, "status": "NOT_APPLICABLE_FOR_TASK",
        "pixel_candidate": None, "physical_gap_mm": None,
        "calibration_verified": False,
    }
    assert r["gemini"]["status"] == "RESEARCH_PIPE_INTERIOR_ACCEPTED"
    assert r["gemini"]["processing_allowed"] is False
    assert r["gemini"]["research_scene_eligible"] is True
    assert r["task_evidence"]["protruding_lateral_confirmed"] is False
    assert not any(row["label"] == "PROTRUDING_LATERAL"
                   for row in r["advisory_candidates"])


def test_infiltration_still_requires_temporal_confirmation():
    r = build("INFILTRATION_REVIEW")
    assert r["task_evidence"]["active_infiltration_confirmed"] is False
    assert r["task_evidence"]["temporal_confirmation"] == "REQUIRED"
    assert r["task_evidence"]["video_sequence_verified"] is False
    assert r["geometry"]["physical_gap_mm"] is None
    assert "WET_STAIN_IS_NOT_PROOF_OF_ACTIVE_INGRESS" in r["reasons"]


@pytest.mark.parametrize("gate", [
    receipt(domain="UNRELATED_IMAGE", pipe_visible=False),
    receipt(domain="LOW_QUALITY_IMAGE", quality="BLURRY"),
    receipt(domain="PIPE_INTERIOR_NO_JOINT", processing_allowed=True),
    receipt(domain="PIPE_INTERIOR_NO_JOINT", prompt_image_conflict=True),
    {"image_sha256": "b"*64, "semantic_gate": receipt()["semantic_gate"]},
])
def test_blocked_gemini_prevents_research_mask_acceptance(gate):
    r = build(verified_gemini_receipt=gate)
    assert r["gemini"]["status"] in ("BLOCKED", "UNVERIFIED")
    assert r["segmentation"]["status"] == "UNAVAILABLE_OR_REJECTED"
    assert r["primary_advisory"] is None
    assert r["geometry"]["pixel_candidate"] is None


def test_joint_visible_scene_still_admissible_for_object_review():
    r = build(verified_gemini_receipt=receipt("PIPE_JOINT_INSPECTION"))
    assert r["gemini"]["status"] == "ADVISORY_DOMAIN_ACCEPTED"
    assert r["gemini"]["processing_allowed"] is True
    assert r["defect"] == "UNDETERMINED"


def test_missing_gemini_receipt_is_explicit_not_fabricated():
    r = build(verified_gemini_receipt=None)
    assert r["gemini"]["status"] == "NOT_PROVIDED"
    assert r["gemini"]["research_scene_eligible"] is False
    assert r["segmentation"]["status"] == "CANDIDATE_REVIEW"
    assert "GEMINI_SEMANTIC_RECEIPT_NOT_PROVIDED" in r["reasons"]


def test_mask_pixel_provenance_is_required():
    r = build(mask_pixel_verified=False)
    assert r["segmentation"]["bbox"] is None
    assert r["segmentation"]["status"] == "UNAVAILABLE_OR_REJECTED"
    assert r["defect"] == "UNDETERMINED"


def test_unsupported_task_rejected():
    with pytest.raises(ValueError):
        build("JOINT_GEOMETRY")
    with pytest.raises(ValueError):
        build("DEFECT_CONFIRMATION")


def test_supported_probability_remains_only_exploratory():
    r = build()
    assert r["primary_advisory"] == {
        "label": "SURFACE_DAMAGE",
        "probability": 0.78,
        "classification_status": "EXPLORATORY",
    }
    assert r["engineering_result"] is None


def test_mismatched_inspect_view_hash_disables_classifier():
    bad = preview()
    bad["image_sha256"] = "0"*64
    r = build(inspect_view_payload=bad)
    assert r["inspect_view_version"] is None
    assert r["primary_advisory"] is None
    assert r["segmentation"]["status"] == "CANDIDATE_REVIEW"


def test_nonfinite_or_boolean_probs_are_not_advisories():
    bad = preview({
        "SURFACE_DAMAGE": {"status": "EXPLORATORY", "detected": True,
                           "probability": float("nan")},
        "BROKEN_PIPE": {"status": "EXPLORATORY", "detected": True,
                         "probability": True},
    })
    r = build(inspect_view_payload=bad)
    assert r["primary_advisory"] is None
