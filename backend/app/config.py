"""Application configuration and runtime environment settings."""

import os
from typing import List
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Global application settings and configuration."""

    PROJECT_NAME: str = "Pipe Joint Optical Measurement & QA Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

    # CORS Configuration
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://localhost:5173",
            "https://127.0.0.1:5173",
            "*",
        ]
    )

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


settings = Settings()
