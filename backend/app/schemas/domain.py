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


class JointConditionClass(str, Enum):
    """Standardized pipe joint structural condition classes."""
    NORMAL_JOINT = "normal_joint"
    DISPLACED_JOINT = "displaced_joint"
    OPEN_JOINT = "open_joint"
    DAMAGED_JOINT = "damaged_joint"
    INTRUDING_SEAL = "intruding_seal"


class MeasurementResultStatus(str, Enum):
    """Production decision gating based on statistically calibrated confidence."""
    ACCEPTED_MEASUREMENT = "ACCEPTED_MEASUREMENT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED_UNRELIABLE = "REJECTED_UNRELIABLE"


class SewerDefectCode(str, Enum):
    """Official Sewer-ML benchmark defect and hard negative distraction codes."""
    FS = "FS"  # Faulty joint / displacement
    RB = "RB"  # Cracks, breaks, collapse
    DE = "DE"  # Deformation
    IS = "IS"  # Intruding sealing material
    RO = "RO"  # Roots (hard negative distractor)
    AF = "AF"  # Settled deposits (hard negative distractor)
    BE = "BE"  # Attached deposits (hard negative distractor)
    FO = "FO"  # Obstacles (hard negative distractor)

