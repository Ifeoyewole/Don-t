"""WRc InceptionResNetV2 External Sewer Baseline Classifier.

Model ID: wrc-inceptionresnetv2-baseline-v1
Source: alexgeorge13/WRc-Dataset-Classification
Role: ADVISORY_BASELINE

Contract & Safety Rules:
1. Strict visual classification advisory role only.
2. ZERO physical measurement authority.
3. ZERO engineering tolerance authority.
4. Calibrated millimeter measurements remain strictly governed by the OpenCV deterministic geometry engine.
5. Never defaults to NORMAL_JOINT on model absence or low confidence.
6. Returns raw WRc predictions along with conservative JointInspect mappings.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from backend.app.config import get_settings
from backend.app.schemas.domain import JointConditionClass
from backend.app.schemas.measurement import (
    ExternalClassTopK,
    ExternalClassifierResult,
    ModelComparisonResult,
)

logger = logging.getLogger(__name__)

# Canonical WRc class taxonomy
WRC_CLASS_MAP_PATH = Path(__file__).resolve().parent / "wrc_class_map.json"


class WRCInceptionClassifier:
    """Inference adapter for WRc InceptionResNetV2 sewer defect classifier."""

    def __init__(self, model_path: Optional[str | Path] = None):
        self.model_id = "wrc-inceptionresnetv2-baseline-v1"
        self.source = "WRc"
        self._session = None
        self._classes: List[Dict[str, Any]] = []
        self._class_names: List[str] = []
        self._class_codes: List[str] = []
        self._load_taxonomy()

        settings = get_settings()
        self.enabled = getattr(settings, "WRC_BASELINE_ENABLED", True)
        self.min_score = getattr(settings, "WRC_BASELINE_MIN_SCORE", 0.30)
        self.model_path = model_path or getattr(settings, "WRC_BASELINE_PATH", None)

        if self.enabled:
            self._init_session()

    def _load_taxonomy(self) -> None:
        """Load canonical WRc class taxonomy from wrc_class_map.json."""
        if not WRC_CLASS_MAP_PATH.exists():
            logger.error("WRc class mapping file missing at %s", WRC_CLASS_MAP_PATH)
            return

        try:
            with open(WRC_CLASS_MAP_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._classes = data.get("classes", [])
            self._class_names = [c["wrc_description"] for c in self._classes]
            self._class_codes = [c.get("wrc_code", "") for c in self._classes]
            logger.info("Loaded WRc taxonomy with %d classes.", len(self._classes))
        except Exception as e:
            logger.error("Failed loading WRc class mapping: %s", e)

    def _resolve_model_path(self) -> Optional[Path]:
        """Resolve model ONNX path from configured directories or backend models."""
        candidates = []
        if self.model_path:
            candidates.append(Path(self.model_path))

        env_models_dir = os.getenv("PIPE_CV_MODELS_DIR")
        if env_models_dir:
            candidates.append(Path(env_models_dir) / "wrc_inceptionresnetv2_baseline_v1.onnx")

        # Standard backend locations
        repo_root = Path(__file__).resolve().parents[5]
        candidates.append(repo_root / "models" / "external" / "wrc" / "wrc_inceptionresnetv2_baseline_v1.onnx")
        candidates.append(repo_root / "models" / "wrc_inceptionresnetv2_baseline_v1.onnx")
        candidates.append(repo_root / "backend" / "models" / "wrc_inceptionresnetv2_baseline_v1.onnx")

        for path in candidates:
            if path and path.exists() and path.is_file():
                return path

        return None

    def _init_session(self) -> None:
        """Initialize ONNX runtime inference session with immutable SHA-256 verification."""
        resolved_path = self._resolve_model_path()
        if not resolved_path:
            logger.info("WRc baseline model weights not found in search paths. Status: unavailable.")
            self._session = None
            return

        valid_hashes = {
            "8a6115e9f6f6f3a5a4f5cc749cc35420a623a4547e904174ae9a18ceab63f9f4",  # Converted ONNX model
            "42527d8c4d38e6113f079bcb007715a5476d39cd3cc327f4ba87269d3c7de253",  # Source Keras weights.h5
        }
        try:
            h = hashlib.sha256()
            with open(resolved_path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
            actual_hash = h.hexdigest()
            if actual_hash not in valid_hashes:
                logger.error(
                    "EXTERNAL_CLASSIFIER_INTEGRITY_FAILURE: WRc ONNX hash mismatch! Got %s",
                    actual_hash,
                )
                self._integrity_failure = True
                self._session = None
                return
            logger.info("WRc ONNX integrity verified with SHA-256: %s", actual_hash)
        except Exception as e:
            logger.error("Failed computing SHA-256 for WRc ONNX model: %s", e)
            self._integrity_failure = True
            self._session = None
            return

        try:
            import onnxruntime as ort

            # Configure single-process CPU session with reasonable thread count
            sess_options = ort.SessionOptions()
            sess_options.intra_op_num_threads = 2
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self._session = ort.InferenceSession(
                str(resolved_path),
                sess_options,
                providers=["CPUExecutionProvider"],
            )
            self.model_path = str(resolved_path)
            logger.info("WRc InceptionResNetV2 baseline loaded successfully from %s", resolved_path)
        except Exception as e:
            logger.error("Failed to initialize WRc ONNX session: %s", e)
            self._session = None

    @property
    def is_available(self) -> bool:
        """Check if model session is initialized and ready for inference."""
        return self._session is not None and len(self._classes) > 0

    def preprocess_image(self, image_bgr: np.ndarray, target_size: Tuple[int, int] = (299, 299)) -> np.ndarray:
        """Exact parity preprocessing reproducing testImageClassification.ipynb.
        
        Preserves aspect ratio with LANCZOS interpolation, pads canvas with black (0,0,0) to 299x299,
        and outputs float32 [0.0, 255.0] RGB array of shape (1, 299, 299, 3).
        """
        # Convert BGR to RGB
        if len(image_bgr.shape) == 2:
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_GRAY2RGB)
        else:
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        original_img = Image.fromarray(image_rgb)
        original_width, original_height = original_img.size
        target_width, target_height = target_size

        scale = min(target_width / original_width, target_height / original_height)
        new_width = max(1, int(original_width * scale))
        new_height = max(1, int(original_height * scale))

        resized_img = original_img.resize((new_width, new_height), Image.LANCZOS)
        padded_img = Image.new("RGB", target_size, (0, 0, 0))

        paste_x = (target_width - new_width) // 2
        paste_y = (target_height - new_height) // 2
        padded_img.paste(resized_img, (paste_x, paste_y))

        # Convert to float32 [0.0, 255.0]
        img_array = np.array(padded_img, dtype=np.float32)
        img_array = np.expand_dims(img_array, axis=0)  # Shape: (1, 299, 299, 3)
        return img_array

    def classify(
        self,
        image_bgr: Optional[np.ndarray],
        top_k_count: int = 5,
    ) -> ExternalClassifierResult:
        """Execute advisory sewer defect classification.
        
        Args:
            image_bgr: Pipe image in BGR format.
            top_k_count: Number of top-k candidates to include in advisory payload.
            
        Returns:
            ExternalClassifierResult: Structured advisory result.
        """
        # 1. Check availability, integrity, and input validity
        if getattr(self, "_integrity_failure", False):
            return ExternalClassifierResult(
                model_id=self.model_id,
                source=self.source,
                raw_class_code=None,
                raw_class_name="UNKNOWN",
                confidence=0.0,
                top_k=[],
                jointinspect_mapping=None,
                mapping_status="UNMAPPED",
                advisory_only=True,
                status="EXTERNAL_CLASSIFIER_INTEGRITY_FAILURE",
            )

        if not self.is_available or image_bgr is None or image_bgr.size == 0:
            return ExternalClassifierResult(
                model_id=self.model_id,
                source=self.source,
                raw_class_code=None,
                raw_class_name="UNKNOWN",
                confidence=0.0,
                top_k=[],
                jointinspect_mapping=None,
                mapping_status="UNMAPPED",
                advisory_only=True,
                status="EXTERNAL_CLASSIFIER_UNAVAILABLE",
            )

        try:
            # 2. Preprocess with parity
            blob = self.preprocess_image(image_bgr, target_size=(299, 299))

            # 3. ONNX forward pass
            input_name = self._session.get_inputs()[0].name
            raw_out = self._session.run(None, {input_name: blob})[0]
            probs = raw_out[0]  # shape (13,)

            # 4. Top-1 extraction
            top1_idx = int(np.argmax(probs))
            top1_score = float(probs[top1_idx])
            top1_class_info = self._classes[top1_idx] if top1_idx < len(self._classes) else {}

            raw_code = top1_class_info.get("wrc_code")
            raw_name = top1_class_info.get("wrc_description", "Unknown")
            ji_mapping = top1_class_info.get("jointinspect_mapping")
            mapping_status = top1_class_info.get("mapping_status", "UNMAPPED")

            # 5. Build Top-K distribution
            sorted_indices = np.argsort(probs)[::-1][:top_k_count]
            top_k_list: List[ExternalClassTopK] = []
            for idx in sorted_indices:
                c_idx = int(idx)
                c_score = float(probs[c_idx])
                c_info = self._classes[c_idx] if c_idx < len(self._classes) else {}
                top_k_list.append(
                    ExternalClassTopK(
                        index=c_idx,
                        raw_class_name=c_info.get("wrc_description", f"Class_{c_idx}"),
                        raw_class_code=c_info.get("wrc_code"),
                        score=round(c_score, 4),
                        jointinspect_mapping=c_info.get("jointinspect_mapping"),
                    )
                )

            # 6. Status determination based on confidence threshold
            if top1_score < self.min_score:
                status = "LOW_CONFIDENCE_CLASSIFICATION"
            else:
                status = "SUCCESS"

            return ExternalClassifierResult(
                model_id=self.model_id,
                source=self.source,
                raw_class_code=raw_code,
                raw_class_name=raw_name,
                confidence=round(top1_score, 4),
                top_k=top_k_list,
                jointinspect_mapping=ji_mapping,
                mapping_status=mapping_status,
                advisory_only=True,
                status=status,
            )

        except Exception as e:
            logger.error("Error during WRc inference: %s", e)
            return ExternalClassifierResult(
                model_id=self.model_id,
                source=self.source,
                raw_class_code=None,
                raw_class_name="ERROR",
                confidence=0.0,
                top_k=[],
                jointinspect_mapping=None,
                mapping_status="UNMAPPED",
                advisory_only=True,
                status="EXTERNAL_CLASSIFIER_UNAVAILABLE",
            )


def compare_models(
    wrc_result: Optional[ExternalClassifierResult],
    native_result: Optional[Any],
    vertex_observation: Optional[str] = None,
    segmenter_result: Optional[Any] = None,
    vertex_live: bool = False,
) -> ModelComparisonResult:
    """Compare predictions across advisory systems and track disagreements for beta evaluation.
    
    Args:
        wrc_result: WRc external classifier result.
        native_result: JointInspect native Model B JointConditionResult.
        vertex_observation: Optional textual observation from Vertex AI domain gate.
        segmenter_result: Optional JointSegmenter Model A result.
        vertex_live: Whether Vertex executed as a live cloud call.
        
    Returns:
        ModelComparisonResult: Agreement metrics, human review flag, and system availability.
    """
    wrc_pred = wrc_result.jointinspect_mapping if (wrc_result and wrc_result.status == "SUCCESS") else None
    wrc_score = wrc_result.confidence if (wrc_result and wrc_result.status == "SUCCESS") else None

    native_pred = None
    native_score = None
    if native_result is not None:
        cond = getattr(native_result, "condition", None)
        if cond and cond != JointConditionClass.CLASSIFICATION_UNAVAILABLE:
            native_pred = cond.value if hasattr(cond, "value") else str(cond)
        native_score = getattr(native_result, "confidence", None)

    # Multi-system availability tracking
    wrc_avail = "AVAILABLE" if (wrc_result and wrc_result.status == "SUCCESS") else "UNAVAILABLE"
    native_avail = "AVAILABLE" if (native_pred is not None) else "UNAVAILABLE"
    model_a_avail = "AVAILABLE" if (segmenter_result and getattr(segmenter_result, "detected", False)) else "UNAVAILABLE"
    vertex_avail = "LIVE" if vertex_live else ("AVAILABLE" if vertex_observation else "UNAVAILABLE")

    availability = {
        "vertex": vertex_avail,
        "model_a": model_a_avail,
        "model_b": native_avail,
        "wrc": wrc_avail,
    }
    all_executed = all(v in ("LIVE", "AVAILABLE") for v in availability.values())
    run_mode = "FULL_MULTI_MODEL" if all_executed else "PARTIAL_MULTI_MODEL"

    # 1. WRc vs Native
    if not wrc_pred or not native_pred:
        wrc_vs_native = "NOT_COMPARABLE" if (not wrc_pred and not native_pred) else "UNMAPPED"
    elif wrc_pred.strip().upper() == native_pred.strip().upper():
        wrc_vs_native = "AGREE"
    else:
        wrc_vs_native = "DISAGREE"

    # 2. WRc vs Vertex
    if not wrc_pred or not vertex_observation:
        wrc_vs_vertex = "NOT_COMPARABLE"
    else:
        v_lower = vertex_observation.lower()
        w_tokens = [t for t in wrc_pred.lower().replace("_", " ").split() if len(t) > 3 and t != "joint"]
        if any(tok in v_lower for tok in w_tokens):
            wrc_vs_vertex = "AGREE"
        else:
            wrc_vs_vertex = "DISAGREE"

    # 3. Native vs Vertex
    if not native_pred or not vertex_observation:
        native_vs_vertex = "NOT_COMPARABLE"
    else:
        v_lower = vertex_observation.lower()
        n_tokens = [t for t in native_pred.lower().replace("_", " ").split() if len(t) > 3 and t != "joint"]
        if any(tok in v_lower for tok in n_tokens):
            native_vs_vertex = "AGREE"
        else:
            native_vs_vertex = "DISAGREE"

    # 4. Human review required if strong disagreement between high confidence models
    human_review = False
    if wrc_vs_native == "DISAGREE":
        if (wrc_score or 0.0) >= 0.70 and (native_score or 0.0) >= 0.60:
            human_review = True

    return ModelComparisonResult(
        wrc_baseline_prediction=wrc_result.raw_class_name if (wrc_result and wrc_result.status == "SUCCESS") else None,
        wrc_baseline_score=wrc_score,
        native_model_b_prediction=native_pred,
        native_model_b_score=native_score,
        vertex_observation=vertex_observation,
        wrc_vs_native_agreement=wrc_vs_native,
        wrc_vs_vertex_agreement=wrc_vs_vertex,
        native_vs_vertex_agreement=native_vs_vertex,
        human_review_required=human_review,
        availability=availability,
        run_mode=run_mode,
    )


# Process-level singleton instance
_wrc_classifier: Optional[WRCInceptionClassifier] = None


def get_wrc_classifier() -> WRCInceptionClassifier:
    """Return process-level singleton instance of WRCInceptionClassifier."""
    global _wrc_classifier
    if _wrc_classifier is None:
        _wrc_classifier = WRCInceptionClassifier()
    return _wrc_classifier
