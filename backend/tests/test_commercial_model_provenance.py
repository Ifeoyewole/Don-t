"""Commercial model candidate screen stays fail-closed until provenances cleared."""

import json
from pathlib import Path

from training.ingestion.validate_license import audit_license
from training.ingestion.model_release_gate import screen_model_manifest


BASE = Path("training/commercial_candidates")
REGISTRY = Path("training/data_sources/source_registry.json")


def registry():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_known_permissive_licenses_are_recognized_but_not_rights_verification():
    for text in ("MIT License", "Apache License 2.0", "Apache-2.0", "BSD 3-Clause",
                 "Creative Commons Attribution 4.0 International (CC BY 4.0)"):
        assert audit_license(text).is_commercial_valid, text


def test_unknown_and_noncommercial_licenses_rejected():
    for text in (
        "Unknown / Unverified", "No license", "", "Custom internal model license",
        "CC BY-NC-SA 4.0", "CC-BY-NC-4.0", "CC BY-NC-ND 4.0",
        "Creative Commons Attribution-NonCommercial-ShareAlike 4.0",
        "GPL-3.0", "AGPL-3.0", "CC BY-SA 4.0", "Research Use Only",
    ):
        assert not audit_license(text).is_commercial_valid, text


def test_owned_license_requires_explicit_record_reference():
    assert not audit_license("Proprietary / In-House Owned").is_commercial_valid
    assert not audit_license("Proprietary / In-House Owned",
                             approved_owned_source=True).is_commercial_valid
    assert audit_license("Proprietary / In-House Owned",
                         approved_owned_source=True,
                         rights_document_reference="COMPANY-ASSET-RIGHTS-2026").is_commercial_valid


def test_candidate_configs_are_blocked_and_do_not_bundle_weights():
    for name in ("mmseg_segformer_b0.json", "yolox_s.json"):
        candidate = json.loads((BASE / name).read_text(encoding="utf-8"))
        report = screen_model_manifest(candidate, registry())
        assert report["commercial_release_eligible"] is False
        assert report["blockers"]
        assert candidate["enabled_for_production"] is False
        assert candidate["weights"]["sha256"] is None
        assert candidate["training_source_ids"] == []


def clean_candidate():
    candidate = json.loads((BASE / "mmseg_segformer_b0.json").read_text(encoding="utf-8"))
    candidate["weights"] = {
        "origin": "TRAINED_FROM_SCRATCH",
        "sha256": "a" * 64,
        "pretrained_weights_used": False,
        "ancestor_model_ids": [],
        "inspect_view_fusion_used": False,
    }
    candidate["training_source_ids"] = ["SRC-SYN-001"]
    candidate["independent_rights_review"] = {
        "status": "APPROVED_FOR_COMMERCIAL_TRAINING_AND_DEPLOYMENT",
        "reviewer": "test reviewer",
        "review_date": "2026-01-01",
        "rights_evidence_reference": "TEST-TICKET-ONLY",
    }
    return candidate


def test_clean_lineage_passes_metadata_screen_only():
    result = screen_model_manifest(clean_candidate(), registry())
    assert result["policy_screen_passed"] is True
    assert "legal" in result["limitation"]


def test_sewerml_research_lineage_and_fusion_rejected_even_with_review_signoff():
    for mutation in (
        lambda x: x["training_source_ids"].append("SRC-SWR-001"),
        lambda x: x["weights"].update(ancestor_model_ids=["Inspect View r5"]),
        lambda x: x["weights"].update(inspect_view_fusion_used=True),
        lambda x: x["weights"].update(pretrained_weights_used=True),
        lambda x: x["weights"].update(origin="EXTERNAL_PRETRAINED"),
    ):
        candidate = clean_candidate()
        mutation(candidate)
        assert not screen_model_manifest(candidate, registry())["policy_screen_passed"]


def test_quarantined_dataset_cannot_get_past_model_gate():
    candidate = clean_candidate()
    candidate["training_source_ids"] = ["SRC-ROBOFLOW-RPDD-001"]
    report = screen_model_manifest(candidate, registry())
    assert not report["commercial_release_eligible"]
    assert any("rights evidence" in r for r in report["blockers"])


def test_missing_rights_signoff_and_weights_are_blockers():
    candidate = clean_candidate()
    candidate["independent_rights_review"]["status"] = "PENDING_REVIEW"
    candidate["weights"]["sha256"] = None
    result = screen_model_manifest(candidate, registry())
    assert not result["commercial_release_eligible"]
    assert any("SHA-256" in reason for reason in result["blockers"])
    assert any("sign-off" in reason for reason in result["blockers"])
