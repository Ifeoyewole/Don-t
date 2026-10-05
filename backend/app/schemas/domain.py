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
    CALIBRATION_REQUIRED = "CALIBRATION_REQUIRED"
    TOLERANCE_CONFIGURATION_REQUIRED = "TOLERANCE_CONFIGURATION_REQUIRED"
    NOT_EVALUATED = "NOT_EVALUATED"


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
    DEPOSITS_OBSTACLES = "deposits_obstacles"
    DIFFICULT_CONDITION = "difficult_condition"
    CLASSIFICATION_UNAVAILABLE = "classification_unavailable"


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


class DomainStatus(str, Enum):
    """Semantic domain evaluation and visual eligibility gate."""
    PIPE_JOINT_INSPECTION = "PIPE_JOINT_INSPECTION"
    PIPE_INTERIOR_NO_JOINT = "PIPE_INTERIOR_NO_JOINT"
    UNRELATED_IMAGE = "UNRELATED_IMAGE"
    AMBIGUOUS_IMAGE = "AMBIGUOUS_IMAGE"
    LOW_QUALITY_IMAGE = "LOW_QUALITY_IMAGE"
    UNSUPPORTED_IMAGE = "UNSUPPORTED_IMAGE"
    DOMAIN_VALIDATION_UNAVAILABLE = "DOMAIN_VALIDATION_UNAVAILABLE"


class CalibrationSource(str, Enum):
    """Allowed verified provenance sources for physical millimeter calibration."""
    PROJECT_METADATA = "PROJECT_METADATA"
    MANHOLE_METADATA = "MANHOLE_METADATA"
    PHYSICAL_REFERENCE = "PHYSICAL_REFERENCE"
    CAMERA_CALIBRATION = "CAMERA_CALIBRATION"
    TEST_RIG = "TEST_RIG"
    UNVERIFIED_CLIENT = "UNVERIFIED_CLIENT"
    NONE = "NONE"

