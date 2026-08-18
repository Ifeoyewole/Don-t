"""Domain enums for pipe joint types and inspection tolerance classifications."""

from enum import Enum


class JointType(str, Enum):
    """Supported joint geometry types for pipe inspection."""
    CIRCULAR_OPENING = "CIRCULAR_OPENING"
    HORIZONTAL_SEAM = "HORIZONTAL_SEAM"
    VERTICAL_SEAM = "VERTICAL_SEAM"


class ToleranceStatus(str, Enum):
    """Standardized tolerance status for automated QA verification."""
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    REVIEW = "REVIEW"


class ExposureStatus(str, Enum):
    """Lighting / exposure conditions evaluated during preprocessing."""
    OK = "OK"
    UNDEREXPOSED = "UNDEREXPOSED"
    OVEREXPOSED = "OVEREXPOSED"
