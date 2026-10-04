"""Model registry and runtime configuration for AI segmentation and classification models."""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    """Metadata describing a registered AI vision model."""
    model_id: str
    model_type: str  # "segmenter" or "classifier"
    weights_path: Path
    input_size: int = Field(default=640, description="Square input resolution (e.g. 640x640)")
    version: str = "1.0.0"
    is_available: bool = False
    device: str = "cpu"


class ModelRegistry:
    """Central registry tracking active neural network weights and inference backends."""

    def __init__(self, models_dir: Optional[Path] = None):
        if models_dir is None:
            # Default to backend/models or environment variable
            env_path = os.getenv("PIPE_CV_MODELS_DIR")
            if env_path:
                self.models_dir = Path(env_path)
            else:
                self.models_dir = Path(__file__).resolve().parent.parent.parent.parent / "models"
        else:
            self.models_dir = models_dir

        self._models: Dict[str, ModelInfo] = {}
        self._initialize_registry()

    def _initialize_registry(self) -> None:
        """Register default model definitions and check weight file presence."""
        segmenter_weights = self.models_dir / "pipe_joint_segmenter_v1.onnx"
        classifier_weights = self.models_dir / "pipe_joint_classifier_v1.onnx"

        wrc_weights = self.models_dir / "wrc_inceptionresnetv2_baseline_v1.onnx"
        if not wrc_weights.exists():
            # Check external models directory
            alt_wrc = self.models_dir / "external" / "wrc" / "wrc_inceptionresnetv2_baseline_v1.onnx"
            if alt_wrc.exists():
                wrc_weights = alt_wrc

        self._models["joint_segmenter"] = ModelInfo(
            model_id="joint_segmenter",
            model_type="segmenter",
            weights_path=segmenter_weights,
            input_size=640,
            version="1.0.0",
            is_available=segmenter_weights.exists(),
        )

        self._models["joint_classifier"] = ModelInfo(
            model_id="joint_classifier",
            model_type="classifier",
            weights_path=classifier_weights,
            input_size=256,
            version="1.0.0",
            is_available=classifier_weights.exists(),
        )

        self._models["wrc-inceptionresnetv2-baseline-v1"] = ModelInfo(
            model_id="wrc-inceptionresnetv2-baseline-v1",
            model_type="external_classifier",
            weights_path=wrc_weights,
            input_size=299,
            version="1.0.0",
            is_available=wrc_weights.exists(),
        )

    def get_model_info(self, model_id: str) -> Optional[ModelInfo]:
        """Retrieve model metadata by ID."""
        return self._models.get(model_id)

    def register_weights(self, model_id: str, weights_path: Path) -> bool:
        """Register newly trained or downloaded weights file."""
        if model_id in self._models:
            info = self._models[model_id]
            info.weights_path = weights_path
            info.is_available = weights_path.exists()
            return info.is_available
        return False

    def list_models(self) -> Dict[str, Dict[str, Any]]:
        """Return status dictionary of all registered models."""
        return {
            mid: {
                "type": m.model_type,
                "version": m.version,
                "available": m.is_available,
                "weights": str(m.weights_path),
            }
            for mid, m in self._models.items()
        }


# Global singleton instance
model_registry = ModelRegistry()
