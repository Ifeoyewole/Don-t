"""Unified Vision v1 research decision tests; no network, GPU, or model weights."""

from copy import deepcopy

import pytest

from backend.app.core.cv.ai.unified_vision_v1 import build_unified_result

SHA = "a" * 64
VERSION = "repr-convnext-masked-r5-20261104"


def _inputs():
    fusion = {
        "status": "MULTI_MODEL_REVIEW",
        "geometry": "VERTICAL_SEAM",
        "inspect_view_ready": True,
        "inspect_view_version": VERSION,
        "inspect_view_advisories": [
            {"label": "SURFACE_DAMAGE", "status": "EXPLORATORY", "probability": 0.82},
            {"label": "NORMAL", "status": "EXPLORATORY", "probability": 0.12},
            {"label": "OPEN_JOINT", "status": "UNVALIDATED", "probability": None},
            {"label": "INFILTRATION", "status": "UNVALIDATED", "probability": None},
            {"label": "PROTRUDING_LATERAL", "status": "UNVALIDATED", "probability": None},
        ],
        "sam2_status": "MASK_CANDIDATE_RESEARCH",
        "mask_bbox": [100, 12, 201, 300],
        "mask_quality": 0.93,
        "cv_status": "REVIEW_REQUIRED",
        "cv_pixel_candidate": None,
    }
    preview = {
        "model_ready": True,
        "research_preview": True,
        "image_sha256": SHA,
        "model_version": VERSION,
        "classes": {
            "SURFACE_DAMAGE": {"status": "EXPLORATORY", "probability": 0.82, "detected": True},
            "NORMAL": {"status": "EXPLORATORY", "probability": 0.12, "detected": False},
            "OPEN_JOINT": {"status": "EXPLORATORY", "probability": 0.99, "detected": True},
            "INFILTRATION": {"status": "EXPLORATORY", "probability": 0.99, "detected": True},
            "PROTRUDING_LATERAL": {"status": "EXPLORATORY", "probability": 0.99, "detected": True},
        },
    }
    return fusion, preview


def test_single_canonical_answer_exposes_only_exploratory_advisory():
    fusion, preview = _inputs()
    result = build_unified_result(fusion, inspect_view_payload=preview, image_sha256=SHA)
    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["defect"] == "UNDETERMINED"
    assert result["primary_advisory"]["label"] == "SURFACE_DAMAGE"
    assert len(result["advisory_candidates"]) == 1
    assert result["segmentation"]["status"] == "CANDIDATE_REVIEW"
    assert result["geometry"]["physical_gap_mm"] is None
    assert result["engineering_result"] is None
    assert result["research_only"] is True


def test_rejected_mask_cannot_produce_usable_geometry():
    fusion, preview = _inputs()
    fusion.update(status="REVIEW_REQUIRED", sam2_status="REVIEW_REQUIRED",
                  cv_status="PIXEL_PROFILE_CANDIDATE", cv_pixel_candidate=15)
    result = build_unified_result(fusion, inspect_view_payload=preview, image_sha256=SHA)
    assert result["segmentation"]["bbox"] is None
    assert result["geometry"]["pixel_candidate"] is None


def test_even_pixel_profile_is_not_mm_or_pass():
    fusion, preview = _inputs()
    fusion.update(status="MULTI_MODEL_RESEARCH_EVIDENCE",
                  cv_status="PIXEL_PROFILE_CANDIDATE", cv_pixel_candidate=19.5)
    result = build_unified_result(fusion, inspect_view_payload=preview, image_sha256=SHA)
    assert result["geometry"]["pixel_candidate"] == 19.5
    assert result["geometry"]["physical_gap_mm"] is None
    assert result["decision"] == "REVIEW_REQUIRED"


def test_mismatched_image_digest_invalidates_classifier_candidates():
    fusion, preview = _inputs()
    preview["image_sha256"] = "b" * 64
    result = build_unified_result(fusion, inspect_view_payload=preview, image_sha256=SHA)
    assert result["primary_advisory"] is None
    assert result["inspect_view_version"] is None
    assert "INSPECT_VIEW_UNAVAILABLE_OR_IMAGE_PROVENANCE_UNVERIFIED" in result["reasons"]


def test_mismatched_version_invalidates_classifier():
    fusion, preview = _inputs()
    preview["model_version"] = "other"
    result = build_unified_result(fusion, inspect_view_payload=preview, image_sha256=SHA)
    assert not result["advisory_candidates"]


def test_unvalidated_classes_never_authorized_even_if_preview_claims_detected():
    fusion, preview = _inputs()
    fusion["inspect_view_advisories"] = [
        {"label": "OPEN_JOINT", "status": "EXPLORATORY", "probability": 0.99},
    ]
    result = build_unified_result(fusion, inspect_view_payload=preview, image_sha256=SHA)
    assert not result["advisory_candidates"]
    assert result["defect"] == "UNDETERMINED"


def test_conflicting_exploratory_predictions_never_get_final_defect():
    fusion, preview = _inputs()
    fusion["inspect_view_advisories"].append(
        {"label": "BROKEN_PIPE", "status": "EXPLORATORY", "probability": 0.88}
    )
    preview["classes"]["BROKEN_PIPE"] = {
        "status": "EXPLORATORY", "probability": 0.88, "detected": True
    }
    preview["classes"]["NORMAL"]["detected"] = True
    result = build_unified_result(fusion, inspect_view_payload=preview, image_sha256=SHA)
    assert result["primary_advisory"]["label"] == "BROKEN_PIPE"
    assert len(result["advisory_candidates"]) == 2
    assert "MULTIPLE_EXPLORATORY_DEFECT_CANDIDATES" in result["reasons"]
    assert "CONFLICTING_NORMAL_AND_DEFECT_ADVISORIES" in result["reasons"]
    assert result["decision"] == "REVIEW_REQUIRED"


def test_invalid_score_and_probabilities_are_ignored():
    fusion, preview = _inputs()
    fusion["mask_quality"] = float("nan")
    fusion["cv_status"] = "PIXEL_PROFILE_CANDIDATE"
    fusion["cv_pixel_candidate"] = float("nan")
    preview["classes"]["SURFACE_DAMAGE"]["probability"] = True
    result = build_unified_result(fusion, inspect_view_payload=preview, image_sha256=SHA)
    assert result["segmentation"]["status"] == "UNAVAILABLE_OR_REJECTED"
    assert result["primary_advisory"] is None
    assert result["geometry"]["pixel_candidate"] is None


def test_missing_model_and_mask_never_turns_into_normal():
    fusion, _ = _inputs()
    fusion.update(inspect_view_ready=False, status="REVIEW_REQUIRED",
                  sam2_status="MODEL_UNAVAILABLE", mask_bbox=None)
    result = build_unified_result(fusion, inspect_view_payload=None, image_sha256=SHA)
    assert result["defect"] == "UNDETERMINED"
    assert result["normal_advisory"] is False
    assert result["decision"] == "REVIEW_REQUIRED"


def test_invalid_source_sha_fails_closed():
    fusion, preview = _inputs()
    with pytest.raises(ValueError):
        build_unified_result(fusion, inspect_view_payload=preview, image_sha256="bad")


def _gemini_receipt(**overrides):
    gate = {
        "model": "gemini-3.1-pro-preview",
        "domain_status": "PIPE_JOINT_INSPECTION",
        "pipe_visible": True,
        "joint_visible": True,
        "processing_allowed": True,
        "prompt_image_conflict": False,
        "quality": "OK",
        "suggested_joint_type": "VERTICAL_SEAM",
        "observation": "Visible joint candidate; no measured gap",
    }
    gate.update(overrides)
    return {"image_sha256": SHA, "semantic_gate": gate}


def test_gemini_accepts_semantic_scope_without_upgrading_defect_or_mm():
    fusion, preview = _inputs()
    result = build_unified_result(
        fusion, inspect_view_payload=preview,
        image_sha256=SHA, gemini_receipt=_gemini_receipt(),
    )
    assert result["gemini"]["model"] == "gemini-3.1-pro-preview"
    assert result["gemini"]["status"] == "ADVISORY_DOMAIN_ACCEPTED"
    assert result["primary_advisory"]["label"] == "SURFACE_DAMAGE"
    assert result["defect"] == "UNDETERMINED"
    assert result["engineering_result"] is None
    assert result["gemini"]["semantic_evidence_authoritative"] is False


@pytest.mark.parametrize("overrides", [
    {"domain_status": "UNRELATED_IMAGE", "processing_allowed": False,
     "pipe_visible": False, "joint_visible": False},
    {"domain_status": "PIPE_INTERIOR_NO_JOINT", "processing_allowed": True,
     "joint_visible": False},
    {"quality": "BLURRY"},
    {"prompt_image_conflict": True},
    {"processing_allowed": False},
])
def test_gemini_rejections_suppress_defect_and_geometry_candidates(overrides):
    fusion, preview = _inputs()
    fusion.update(status="MULTI_MODEL_RESEARCH_EVIDENCE",
                  cv_status="PIXEL_PROFILE_CANDIDATE", cv_pixel_candidate=17.2)
    result = build_unified_result(
        fusion, inspect_view_payload=preview, image_sha256=SHA,
        gemini_receipt=_gemini_receipt(**overrides),
    )
    assert result["gemini"]["status"] == "BLOCKED"
    assert result["primary_advisory"] is None
    assert result["geometry"]["pixel_candidate"] is None
    assert result["decision"] == "REVIEW_REQUIRED"


def test_gemini_image_hash_mismatch_suppresses_candidates():
    fusion, preview = _inputs()
    receipt = _gemini_receipt()
    receipt["image_sha256"] = "b" * 64
    result = build_unified_result(fusion, inspect_view_payload=preview,
                                  image_sha256=SHA, gemini_receipt=receipt)
    assert result["gemini"]["status"] == "UNVERIFIED"
    assert result["primary_advisory"] is None
    assert "GEMINI_IMAGE_PROVENANCE_MISSING_OR_MISMATCHED" in result["reasons"]


def test_gemini_model_mismatch_suppresses_candidates():
    fusion, preview = _inputs()
    result = build_unified_result(
        fusion, inspect_view_payload=preview, image_sha256=SHA,
        gemini_receipt=_gemini_receipt(model="unknown-model"),
    )
    assert result["gemini"]["status"] == "UNVERIFIED"
    assert result["primary_advisory"] is None


def test_gemini_geometry_conflict_is_review_not_an_override():
    fusion, preview = _inputs()
    result = build_unified_result(
        fusion, inspect_view_payload=preview, image_sha256=SHA,
        gemini_receipt=_gemini_receipt(suggested_joint_type="CIRCULAR_OPENING"),
    )
    assert result["gemini"]["suggested_joint_type"] == "CIRCULAR_OPENING"
    assert result["geometry"]["type"] == "VERTICAL_SEAM"
    assert "GEMINI_GEOMETRY_SUGGESTION_CONFLICT" in result["reasons"]
    assert result["decision"] == "REVIEW_REQUIRED"


def test_no_gemini_receipt_is_explicit_not_included():
    fusion, preview = _inputs()
    result = build_unified_result(
        fusion, inspect_view_payload=preview, image_sha256=SHA,
    )
    assert result["gemini"]["status"] == "NOT_PROVIDED"
    assert result["gemini"]["processing_allowed"] is False
