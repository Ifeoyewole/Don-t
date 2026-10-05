"""AI Joint Condition Classifier (Model B).

Classifies pipe joint condition across 5 primary classes:
- normal_joint: Intact, concentric, within standard engineering tolerance
- displaced_joint: Axial or angular offset / misalignment (Sewer-ML FS defect)
- open_joint: Measured gap exceeds allowable specification
- damaged_joint: Cracks, spalling, structural fractures (Sewer-ML RB / DE defect)
- intruding_seal: Displaced rubber gasket or sealant encroaching into lumen (Sewer-ML IS defect)

Tolerance-Primary Rule:
Physical gap measurement is the primary authority for open_joint. If measured_gap > max_gap_mm,
the definitive condition is OPEN_JOINT regardless of purely visual classifier estimation.
"""

from typing import Dict, Optional, Tuple
import cv2
import numpy as np
from pydantic import BaseModel, Field

from backend.app.core.cv.ai.model_registry import model_registry
from backend.app.schemas.domain import JointConditionClass


class JointConditionResult(BaseModel):
    """Output contract for joint condition assessment."""
    condition: JointConditionClass = Field(..., description="Determined joint condition category")
    confidence: float = Field(..., description="Classifier confidence score (0.0 to 1.0)")
    class_probabilities: Dict[str, float] = Field(
        default_factory=dict,
        description="Normalized probability distribution across all 5 condition classes",
    )
    is_tolerance_overridden: bool = Field(
        default=False,
        description="True if condition was determined by physical gap measurement exceeding max tolerance",
    )


class JointClassifier:
    """Trained Joint Condition Classifier Model B wrapper."""

    def __init__(self):
        self._session = None
        self._classes = [
            JointConditionClass.NORMAL_JOINT,
            JointConditionClass.DISPLACED_JOINT,
            JointConditionClass.OPEN_JOINT,
            JointConditionClass.DAMAGED_JOINT,
            JointConditionClass.INTRUDING_SEAL,
        ]
        self._load_backend()

    def _load_backend(self) -> None:
        """Attempt to load trained ONNX inference session."""
        info = model_registry.get_model_info("joint_classifier")
        if info and info.is_available:
            try:
                import onnxruntime as ort
                self._session = ort.InferenceSession(
                    str(info.weights_path),
                    providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
                )
            except Exception:
                self._session = None

    def classify_joint(
        self,
        image_bgr: np.ndarray,
        roi_bbox: Optional[Tuple[int, int, int, int]] = None,
        measured_gap_mm: Optional[float] = None,
        max_allowable_gap_mm: Optional[float] = None,
    ) -> JointConditionResult:
        """Classify condition of joint with tolerance-primary open_joint authority.

        Args:
            image_bgr: Full image or cropped joint image in BGR format.
            roi_bbox: Optional [x_min, y_min, x_max, y_max] crop coordinates.
            measured_gap_mm: Physical gap measured by OpenCV geometry engine.
            max_allowable_gap_mm: Engineering tolerance upper bound in mm.

        Returns:
            JointConditionResult: Classified condition, confidence, and distribution.
        """
        # Crop to ROI if specified
        if roi_bbox is not None and image_bgr is not None:
            x1, y1, x2, y2 = roi_bbox
            h, w = image_bgr.shape[:2]
            x1, x2 = max(0, x1), min(w, x2)
            y1, y2 = max(0, y1), min(h, y2)
            if x2 > x1 and y2 > y1:
                crop = image_bgr[y1:y2, x1:x2]
            else:
                crop = image_bgr
        else:
            crop = image_bgr

        # 1. Run local model if available
        if self._session is not None and crop is not None and crop.size > 0:
            try:
                blob = cv2.resize(crop, (256, 256)).astype(np.float32) / 255.0
                blob = np.transpose(blob, (2, 0, 1))[np.newaxis, :]  # NCHW
                input_name = self._session.get_inputs()[0].name
                logits = self._session.run(None, {input_name: blob})[0][0]

                # Softmax
                exp_logits = np.exp(logits - np.max(logits))
                probs = exp_logits / np.sum(exp_logits)
                top_idx = int(np.argmax(probs))
                predicted_cond = self._classes[top_idx]
                top_conf = float(probs[top_idx])

                prob_dict = {
                    cls.value: round(float(p), 3)
                    for cls, p in zip(self._classes, probs)
                }

            except Exception:
                predicted_cond = JointConditionClass.CLASSIFICATION_UNAVAILABLE
                top_conf = 0.0
                prob_dict = {cls.value: 0.0 for cls in self._classes}
        else:
            # Model weights not loaded: strictly report CLASSIFICATION_UNAVAILABLE with 0.0 confidence
            # NEVER default to NORMAL_JOINT or invent synthetic probabilities
            predicted_cond = JointConditionClass.CLASSIFICATION_UNAVAILABLE
            top_conf = 0.0
            prob_dict = {cls.value: 0.0 for cls in self._classes}

        # 2. Apply Tolerance-Primary Dimensional Authority for OPEN_JOINT
        # If OpenCV measured gap exceeds design tolerance, the authoritative ground-truth is OPEN_JOINT
        is_override = False
        if measured_gap_mm is not None and max_allowable_gap_mm is not None:
            if measured_gap_mm > max_allowable_gap_mm:
                predicted_cond = JointConditionClass.OPEN_JOINT
                is_override = True
                # Physical measurement is primary authority
                top_conf = 1.0
                prob_dict[JointConditionClass.OPEN_JOINT.value] = 1.0

        return JointConditionResult(
            condition=predicted_cond,
            confidence=round(top_conf, 3),
            class_probabilities=prob_dict,
            is_tolerance_overridden=is_override,
        )
