"""Application configuration and runtime environment settings."""

import os
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Global application settings and configuration."""

    PROJECT_NAME: str = "Pipe Joint Optical Measurement & QA Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "production")
    ENABLE_DOCS: bool = os.getenv("ENABLE_DOCS", "false").lower() in ("true", "1", "yes")
    CALIBRATION_MUTATION_ENABLED: bool = os.getenv("CALIBRATION_MUTATION_ENABLED", "false").lower() in ("true", "1", "yes")

    # Strict CORS Configuration - Wildcard origin forbidden in production
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS",
                "https://joint-inspection.vercel.app,http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
            ).split(",")
            if origin.strip() and origin.strip() != "*"
        ]
    )

    # Payload & File Security Limits
    MAX_UPLOAD_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
    MAX_MULTI_FRAME_BYTES: int = 30 * 1024 * 1024  # 30 MB
    MAX_MULTI_FRAME_COUNT: int = 30
    MAX_IMAGE_DIMENSION_PX: int = 8192
    MAX_IMAGE_TOTAL_PIXELS: int = 50_000_000

    # Computer Vision Quality Thresholds
    DEFAULT_BLUR_THRESHOLD: float = 100.0
    DEFAULT_MIN_BRIGHTNESS: float = 45.0
    DEFAULT_MAX_BRIGHTNESS: float = 215.0
    DEFAULT_GLARE_PIXEL_INTENSITY: int = 250
    DEFAULT_MAX_GLARE_PERCENTAGE: float = 4.0

    # Tolerance Standards (in millimeters)
    STANDARD_TOLERANCE_MIN_PASS_MM: float = 3.0
    STANDARD_TOLERANCE_MAX_PASS_MM: float = 15.0
    STANDARD_TOLERANCE_MAX_REVIEW_MM: float = 25.0

    # External Sewer Defect Baseline Classifier (WRc InceptionResNetV2 - Advisory Only)
    WRC_BASELINE_ENABLED: bool = os.getenv("WRC_BASELINE_ENABLED", "true").lower() in ("true", "1", "yes")
    WRC_BASELINE_MODEL_ID: str = os.getenv("WRC_BASELINE_MODEL_ID", "wrc-inceptionresnetv2-baseline-v1")
    WRC_BASELINE_PATH: str = os.getenv(
        "WRC_BASELINE_PATH",
        str(Path(__file__).resolve().parent.parent / "models" / "external" / "wrc" / "wrc_inceptionresnetv2_baseline_v1.onnx"),
    )
    WRC_BASELINE_MIN_SCORE: float = float(os.getenv("WRC_BASELINE_MIN_SCORE", "0.20"))


settings = Settings()


def get_settings() -> Settings:
    """Return application settings singleton."""
    return settings

