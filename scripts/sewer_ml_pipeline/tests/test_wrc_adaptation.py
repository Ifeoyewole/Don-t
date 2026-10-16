from pathlib import Path
import pytest
from curate_staged import TARGETS
from wrc_adaptation import (
    ADAPTED_MODEL_ID,
    ORIGINAL_BASELINE_ID,
    WRC_INPUT_SHAPE,
    validate_wrc_adaptation_spec,
)


@pytest.fixture
def valid_spec():
    return {
        "model_id": ADAPTED_MODEL_ID,
        "base_model_id": ORIGINAL_BASELINE_ID,
        "input_shape": WRC_INPUT_SHAPE,
        "preprocessing": "wrc_raw_rgb_nhwc",
        "class_codes": list(TARGETS),
        "output_activation": "sigmoid",
        "training_phases": [
            {
                "name": "phase1_frozen_backbone",
                "trainable_backbone": False,
                "learning_rate": 5e-4,
                "epochs": 5,
            },
            {
                "name": "phase2_differential_unfreeze",
                "trainable_backbone": True,
                "learning_rate": 1e-5,
                "epochs": 15,
            },
        ],
        "provenance_metadata": {
            "original_weights_sha256": "42527d8c4d38e6113f079bcb007715a5476d39cd3cc327f4ba87269d3c7de253",
            "source_commit": "7ac0b0f9edf430d43e5f180466e2e456d98fdfe7",
            "original_class_codes": ["B", "CN", "CK", "CND", "D", "DE", "JD", "F", "H", "J", "LL", "R", "W"],
            "preprocessing": "299x299 aspect-preserved padded raw RGB NHWC in [0,255]",
            "research_finetune_allowed": True,
            "commercial_release_allowed": False,
            "rights_evidence_uri": "gs://bucket/rights/signed-approval.pdf",
            "authorized_training_dataset": "Sewer-ML CCWI 2025 research partition",
            "architecture_available": True,
            "training_head_strategy": "new_multilabel_head",
            "label_mapping_verified": True,
        },
    }


def test_valid_adaptation_spec_passes(valid_spec):
    result = validate_wrc_adaptation_spec(valid_spec)
    assert result["status"] == "VALIDATED"
    assert result["rights_verified"] is True
    assert result["num_classes"] == 9


def test_unauthorized_rights_raises_permission_error(valid_spec):
    valid_spec["provenance_metadata"]["research_finetune_allowed"] = False
    with pytest.raises(PermissionError, match="WRC_FINETUNING_BLOCKED_RIGHTS_PENDING"):
        validate_wrc_adaptation_spec(valid_spec)


def test_wrong_input_shape_fails_closed(valid_spec):
    valid_spec["input_shape"] = (224, 224, 3)
    with pytest.raises(ValueError, match="Input shape"):
        validate_wrc_adaptation_spec(valid_spec)


def test_missing_two_phase_schedule_fails_closed(valid_spec):
    valid_spec["training_phases"] = valid_spec["training_phases"][:1]
    with pytest.raises(ValueError, match="two-phase"):
        validate_wrc_adaptation_spec(valid_spec)


def test_high_learning_rate_in_unfreeze_fails_closed(valid_spec):
    # Unfreezing backbone with high lr risks catastrophic forgetting
    valid_spec["training_phases"][1]["learning_rate"] = 1e-3
    with pytest.raises(ValueError, match="catastrophic forgetting"):
        validate_wrc_adaptation_spec(valid_spec)
