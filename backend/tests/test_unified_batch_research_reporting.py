"""GPU-independent tests for descriptive-only Unified Vision batch research."""

import pytest

from scripts.cloud.inspect_view_sam2_batch_vertex import build_summary, safe_failure
from scripts.cloud.prepare_unified_batch_worklist import select_candidates


def test_research_summary_never_invents_f1_or_commercial_permission():
    records = [
        {
            "run_status": "REVIEW_REQUIRED",
            "rights_status": "RESEARCH_QUARANTINE",
            "source_label": "Utility intrusion",
            "annotation_status": "UNVERIFIED_SOURCE_LABEL",
            "segmentation_status": "CANDIDATE_REVIEW",
            "pixel_candidate": None, "gemini_status": "NOT_PROVIDED",
            "reasons": ["NO_SUPPORTED_PIXEL_GEOMETRY"],
        },
        {
            "run_status": "REVIEW_REQUIRED",
            "rights_status": "RESEARCH_QUARANTINE",
            "source_label": "Joint offset",
            "annotation_status": "REVIEWED_GROUND_TRUTH",
            "segmentation_status": "UNAVAILABLE_OR_REJECTED",
            "pixel_candidate": 10.1, "gemini_status": "ADVISORY_DOMAIN_ACCEPTED",
            "reasons": ["MASK_TARGET_IDENTITY_NOT_VERIFIED"],
        },
    ]
    summary = build_summary(
        "batch-001", records, image_digest="a"*64,
        output_prefix="gs://joint-inspection-510310-data/models/batch-001",
        gpu_model="research",
    )
    assert summary["batch_status"] == "REVIEW_REQUIRED_COMPLETE"
    assert summary["count"] == 2
    assert summary["f1"] is None
    assert summary["precision"] is None
    assert summary["recall"] is None
    assert summary["rights_counts"]["RESEARCH_QUARANTINE"] == 2
    assert summary["sam2_candidate_count"] == 1
    assert summary["gemini_receipt_accepted_count"] == 1


def test_errors_mark_batch_incomplete():
    s = build_summary(
        "batch-001", [{
            "run_status": "FRAME_ERROR",
            "rights_status": "RESEARCH_QUARANTINE",
            "annotation_status": "UNVERIFIED_SOURCE_LABEL",
            "reasons": ["FRAME_ERROR"],
        }],
        image_digest="a"*64, output_prefix="gs://joint-inspection-510310-data/x",
        gpu_model="research",
    )
    assert s["batch_status"] == "REVIEW_REQUIRED_INCOMPLETE"
    assert safe_failure("CHECKSUM_FAILED")["engineering_result"] is None


def _registry(names):
    return {
        "dataset_name": "quarantine",
        "commercial_training_eligible": False,
        "records": [
            {
                "dataset_name": "source",
                "source": "https://example.invalid/source",
                "source_labels": [name],
                "sha256": f"{i+1:064x}",
                "dhash": f"{i+1:016x}",
                "width": 600, "height": 400,
                "split": "train",
                "original_image_path": f"train/images/{i}.png",
                "original_media_id": str(i),
                "duplicate_status": "NOT_EXACT_DUPLICATE_NEAR_DUPLICATES_UNCHECKED",
            }
            for i, name in enumerate(names)
        ],
    }


def test_worklist_is_80_review_candidates_never_engineered_roi():
    source = ["Joint offset"]*30 + ["Utility intrusion"]*30 + ["Leak"]*1 + ["Crack"]*80
    rows = select_candidates([_registry(source)], target=80)
    assert len(rows) == 80
    assert all(row["review_status"] == "NEEDS_HUMAN_REVIEW" for row in rows)
    assert all(not row["image_uri_TO_VERIFY"] for row in rows)
    assert all(not row["roi_x0"] for row in rows)
    assert all(row["annotation_review"] == "UNVERIFIED_SOURCE_LABEL" for row in rows)
    assert not any(row["candidate_bucket"] == "OPEN_JOINT" for row in rows)
    assert len({r["image_sha256"] for r in rows}) == 80


def test_worklist_handles_no_infiltration_without_fabricating_it():
    rows = select_candidates([_registry(["Joint", "Crack", "Hole"])], target=80)
    assert len(rows) == 3
    assert all(row["candidate_bucket"] == "HARD_NEGATIVE_OR_OTHER_CANDIDATE" for row in rows)


def test_registry_eligibility_is_explicitly_quarantine():
    with pytest.raises(ValueError):
        select_candidates([{"commercial_training_eligible": True, "records": []}])


def test_nonjoint_authenticated_receipt_is_counted_without_changing_joint_gate():
    records=[{'run_status':'REVIEW_REQUIRED','rights_status':'RESEARCH_QUARANTINE',
              'annotation_status':'UNVERIFIED_SOURCE_LABEL','gemini_status':status}
             for status in ['ADVISORY_DOMAIN_ACCEPTED','RESEARCH_PIPE_INTERIOR_ACCEPTED','NOT_PROVIDED']]
    summary=build_summary('mixed',records,image_digest='a'*64,
                         output_prefix='gs://joint-inspection-510310-data/test',gpu_model='research')
    assert summary['gemini_receipt_accepted_count']==2
    assert summary['gemini_status_counts']=={'ADVISORY_DOMAIN_ACCEPTED':1,'NOT_PROVIDED':1,'RESEARCH_PIPE_INTERIOR_ACCEPTED':1}
    assert summary['f1'] is None and summary['recall'] is None
