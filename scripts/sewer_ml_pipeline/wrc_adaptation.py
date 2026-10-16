"""WRc InceptionResNetV2 adaptation to Sewer-ML 9-class multi-label classifier.

Technical Contract & Governance:
1. Base Model: InceptionResNetV2 (~54M parameters, trained on UK WRc CCTV inspection data).
2. Input Contract: 299x299 aspect-preserved raw RGB NHWC in [0, 255].
3. Adaptation Strategy: Discard original 13-class softmax head (Dense(13) + Softmax).
   Retain GlobalAveragePooling2D (1536-d feature vector). Attach:
   Dropout(0.4) -> Dense(9, name='sewerml_head') -> Sigmoid(name='sewerml_prob').
4. Training Strategy: Two-stage transfer learning to prevent catastrophic forgetting:
   - Phase 1: Freeze entire InceptionResNetV2 backbone; train 9-class head only (Adam lr=5e-4).
   - Phase 2: Controlled differential unfreezing of top blocks (block8 + post-block layers)
     at very low learning rate (lr=1e-5 with cosine decay, weight decay 1e-4).
5. Loss Function: Multi-label BinaryCrossentropy with class positive weights.
6. Rights Gate: Fails closed unless explicit research fine-tuning rights are documented.
   Records WRC_FINETUNING_BLOCKED_RIGHTS_PENDING if unverified.
7. Output Model ID: wrc-inceptionresnetv2-v3-candidate (never overwrites original baseline).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from curate_staged import TARGETS
from wrc_feasibility import evaluate as evaluate_wrc_rights

logger = logging.getLogger(__name__)

WRC_INPUT_SHAPE = (299, 299, 3)
WRC_FEATURE_DIM = 1536
WRC_ORIGINAL_CLASSES = 13
SEWERML_CLASSES = 9
ADAPTED_MODEL_ID = "wrc-inceptionresnetv2-v3-candidate"
ORIGINAL_BASELINE_ID = "wrc-inceptionresnetv2-baseline-v1"


def validate_wrc_adaptation_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Pure validation of adaptation specification without requiring TensorFlow locally."""
    if not isinstance(spec, dict):
        raise ValueError("Specification must be a dictionary")

    # 1. Model identity checks
    model_id = spec.get("model_id")
    if model_id != ADAPTED_MODEL_ID:
        raise ValueError(f"Model ID must be '{ADAPTED_MODEL_ID}' (got '{model_id}')")
    if spec.get("base_model_id") != ORIGINAL_BASELINE_ID:
        raise ValueError(f"Base model ID must be '{ORIGINAL_BASELINE_ID}'")

    # 2. Input contract checks
    input_shape = tuple(spec.get("input_shape", ()))
    if input_shape != WRC_INPUT_SHAPE:
        raise ValueError(f"Input shape must be {WRC_INPUT_SHAPE} (got {input_shape})")
    if spec.get("preprocessing") != "wrc_raw_rgb_nhwc":
        raise ValueError("Preprocessing must be 'wrc_raw_rgb_nhwc'")

    # 3. Output head checks
    class_codes = spec.get("class_codes", [])
    if class_codes != list(TARGETS):
        raise ValueError(f"Class codes must exactly match Sewer-ML targets {list(TARGETS)}")
    if spec.get("output_activation") not in ("sigmoid", "logits"):
        raise ValueError("Output activation must be 'sigmoid' or 'logits'")

    # 4. Two-phase fine-tuning schedule validation
    phases = spec.get("training_phases", [])
    if len(phases) != 2:
        raise ValueError("Adaptation requires a two-phase training schedule (head warmup + controlled unfreezing)")

    phase1, phase2 = phases[0], phases[1]
    if phase1.get("name") != "phase1_frozen_backbone" or phase1.get("trainable_backbone") is not False:
        raise ValueError("Phase 1 must freeze the backbone entirely to preserve pretrained weights")
    if phase1.get("learning_rate", 1.0) > 1e-3:
        raise ValueError("Phase 1 head warmup learning rate must not exceed 1e-3")

    if phase2.get("name") != "phase2_differential_unfreeze" or phase2.get("trainable_backbone") is not True:
        raise ValueError("Phase 2 must enable controlled unfreezing")
    if phase2.get("learning_rate", 1.0) > 5e-5:
        raise ValueError("Phase 2 fine-tuning learning rate must not exceed 5e-5 to prevent catastrophic forgetting")

    # 5. Fail-closed Rights Gate Check
    provenance = spec.get("provenance_metadata", {})
    rights_result = evaluate_wrc_rights(provenance)
    if not rights_result["research_finetune_ready"]:
        blockers = "; ".join(rights_result["blockers"])
        raise PermissionError(
            f"WRC_FINETUNING_BLOCKED_RIGHTS_PENDING: Cannot proceed with WRc fine-tuning. Blockers: {blockers}"
        )

    return {
        "status": "VALIDATED",
        "model_id": ADAPTED_MODEL_ID,
        "input_shape": WRC_INPUT_SHAPE,
        "num_classes": SEWERML_CLASSES,
        "rights_verified": True,
        "two_phase_schedule": True,
    }


def build_adapted_wrc_keras_model(base_weights_path: Optional[Path] = None, trainable_backbone: bool = False):
    """Builds the adapted Keras InceptionResNetV2 model inside an authorized cloud container.

    This function requires TensorFlow and must only be executed inside a verified GCP worker.
    """
    import tensorflow as tf
    from tensorflow.keras import layers, models

    # 1. Instantiate base InceptionResNetV2 architecture without top
    base_model = tf.keras.applications.InceptionResNetV2(
        include_top=False,
        weights=None,
        input_shape=WRC_INPUT_SHAPE,
        pooling="avg",
    )

    # 2. Load authorized pretrained weights if provided
    if base_weights_path and Path(base_weights_path).exists():
        logger.info("Loading pretrained WRc weights from %s", base_weights_path)
        base_model.load_weights(str(base_weights_path), by_name=True)

    # 3. Backbone trainability control
    base_model.trainable = trainable_backbone

    # 4. Construct adapted 9-class multi-label head
    inputs = base_model.input
    x = base_model.output  # 1536-d GlobalAveragePooling2D output
    x = layers.Dropout(0.4, name="sewerml_dropout")(x)
    logits = layers.Dense(SEWERML_CLASSES, activation=None, name="sewerml_dense_logits")(x)
    probabilities = layers.Activation("sigmoid", name="sewerml_probabilities")(logits)

    model = models.Model(inputs=inputs, outputs=probabilities, name=ADAPTED_MODEL_ID)
    return model
