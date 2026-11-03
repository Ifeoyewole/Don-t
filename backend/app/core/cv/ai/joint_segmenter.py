"""AI Joint Segmentation Engine (Model A).

Responsible for:
- Localizing the physical pipe joint bounding box [x_min, y_min, x_max, y_max]
- Generating a binary segmentation mask (uint8 0/255) of the joint opening / gap
- Emitting boundary polygon contour coordinates
- Zero LLM fallback: strictly returns unconfident/unresolved status if local trained model is unavailable or below threshold.
"""

from typing import Any, List, Optional, Tuple
import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.cv.ai.model_registry import model_registry


class JointSegmentationResult(BaseModel):
    """Output contract for AI joint segmentation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    detected: bool = Field(..., description="True if a valid pipe joint was segmented with sufficient confidence")
    confidence: float = Field(..., description="Segmentation confidence score (0.0 to 1.0)")
    bbox: Optional[Tuple[int, int, int, int]] = Field(
        None,
        description="Bounding box [x_min, y_min, x_max, y_max] in image pixel space",
    )
    mask: Optional[Any] = Field(None, description="2D uint8 binary mask array (255 inside joint, 0 elsewhere)")
    contour_polygon: List[Tuple[float, float]] = Field(
        default_factory=list,
        description="Ordered (x, y) coordinates tracing the outer joint boundary",
    )
    reason: Optional[str] = Field(None, description="Failure diagnostic if joint is unresolvable")


class JointSegmenter:
    """Trained Pipe Joint Segmentation Model A wrapper."""

    def __init__(self, min_confidence: float = 0.40):
        """Initialize segmenter with configurable confidence threshold.

        Args:
            min_confidence: Configurable baseline below which detections are rejected (default 0.40).
        """
        self.min_confidence = min_confidence
        self._session = None
        self._load_backend()

    def _load_backend(self) -> None:
        """Attempt to load trained ONNX Runtime inference session."""
        info = model_registry.get_model_info("joint_segmenter")
        if info and info.is_available:
            try:
                import onnxruntime as ort
                available = set(ort.get_available_providers())
                providers = [
                    provider
                    for provider in ("CUDAExecutionProvider", "CPUExecutionProvider")
                    if provider in available
                ]
                if not providers:
                    self._session = None
                    return
                self._session = ort.InferenceSession(
                    str(info.weights_path),
                    providers=providers,
                )
            except Exception:
                self._session = None

    def segment_joint(
        self,
        image_bgr: np.ndarray,
        override_min_confidence: Optional[float] = None,
    ) -> JointSegmentationResult:
        """Execute joint boundary segmentation on inspection image.

        Args:
            image_bgr: Input color image in BGR format.
            override_min_confidence: Optional dynamic confidence override.

        Returns:
            JointSegmentationResult: Mask, bounding box, confidence, and detection flag.
        """
        min_conf = override_min_confidence if override_min_confidence is not None else self.min_confidence

        if image_bgr is None or image_bgr.size == 0:
            return JointSegmentationResult(
                detected=False,
                confidence=0.0,
                reason="Invalid or empty input image buffer.",
            )

        h, w = image_bgr.shape[:2]

        # 1. Production Mode: Trained ONNX / TensorRT Segmenter
        if self._session is not None:
            try:
                model_input = self._session.get_inputs()[0]
                input_shape = list(model_input.shape)
                if len(input_shape) != 4:
                    raise ValueError(f"Unsupported segmenter input rank: {input_shape}")
                channels = input_shape[1]
                if isinstance(channels, int) and channels != 3:
                    raise ValueError(f"Expected NCHW 3-channel input, got shape {input_shape}")

                target_h = input_shape[2] if isinstance(input_shape[2], int) and input_shape[2] > 0 else 640
                target_w = input_shape[3] if isinstance(input_shape[3], int) and input_shape[3] > 0 else 640

                blob = cv2.resize(image_bgr, (target_w, target_h))
                blob = blob.astype(np.float32) / 255.0
                blob = np.transpose(blob, (2, 0, 1))[np.newaxis, :]  # NCHW

                outputs = self._session.run(None, {model_input.name: blob})
                if not outputs:
                    raise ValueError("Segmenter returned no outputs.")

                # The current Model A exporter emits one probability-map output
                # (mask_prob). Keep compatibility with a future two-output model
                # that explicitly emits scalar confidence followed by the mask.
                explicit_confidence: Optional[float] = None
                if len(outputs) >= 2:
                    conf_array = np.asarray(outputs[0], dtype=np.float32).squeeze()
                    if conf_array.size != 1 or not np.isfinite(conf_array).all():
                        raise ValueError(f"Invalid segmenter confidence output shape: {np.asarray(outputs[0]).shape}")
                    explicit_confidence = float(conf_array.reshape(-1)[0])
                    if not 0.0 <= explicit_confidence <= 1.0:
                        raise ValueError(f"Segmenter confidence outside [0, 1]: {explicit_confidence}")
                    mask_output = outputs[1]
                else:
                    mask_output = outputs[0]

                raw_mask = np.asarray(mask_output, dtype=np.float32).squeeze()
                if raw_mask.ndim != 2 or raw_mask.size == 0:
                    raise ValueError(f"Invalid segmenter mask output shape: {np.asarray(mask_output).shape}")
                if not np.isfinite(raw_mask).all():
                    raise ValueError("Segmenter mask output contains non-finite values.")
                if float(raw_mask.min()) < 0.0 or float(raw_mask.max()) > 1.0:
                    raise ValueError("Segmenter mask output must be a probability map in [0, 1].")

                foreground_probs = raw_mask[raw_mask > 0.5]
                if foreground_probs.size == 0:
                    return JointSegmentationResult(
                        detected=False,
                        confidence=0.0,
                        reason="No foreground pixels exceeded the segmentation threshold.",
                    )

                # A single-output exporter has no independent detection-confidence
                # head. In that case expose the mean probability of the predicted
                # foreground as a mask-certainty score rather than inventing a
                # separate learned confidence value.
                conf = explicit_confidence if explicit_confidence is not None else float(np.mean(foreground_probs))
                if conf < min_conf:
                    return JointSegmentationResult(
                        detected=False,
                        confidence=round(conf, 3),
                        reason=f"Model confidence ({conf:.2f}) below threshold ({min_conf:.2f}).",
                    )

                mask = cv2.resize((raw_mask > 0.5).astype(np.uint8) * 255, (w, h))

                # Extract bounding box from mask contour
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not contours:
                    return JointSegmentationResult(
                        detected=False,
                        confidence=round(conf, 3),
                        reason="No valid segmentation contour found in output mask.",
                    )

                largest_cnt = max(contours, key=cv2.contourArea)
                x, y, bw, bh = cv2.boundingRect(largest_cnt)
                polygon = [(float(pt[0][0]), float(pt[0][1])) for pt in largest_cnt]

                return JointSegmentationResult(
                    detected=True,
                    confidence=round(conf, 3),
                    bbox=(x, y, x + bw, y + bh),
                    mask=mask,
                    contour_polygon=polygon,
                )

            except Exception as e:
                return JointSegmentationResult(
                    detected=False,
                    confidence=0.0,
                    reason=f"Inference runtime error: {str(e)}",
                )

        # 2. Pre-trained Weights Absent (Development / Initial Bootstrap)
        # STRICT RULE: NEVER fall back to LLM for measurement ground-truth.
        # Instead, indicate that trained model weights are required or unresolved.
        return JointSegmentationResult(
            detected=False,
            confidence=0.0,
            bbox=None,
            mask=None,
            contour_polygon=[],
            reason="MODEL_UNAVAILABLE: Trained joint segmentation model weights not loaded. Manual review required.",
        )
