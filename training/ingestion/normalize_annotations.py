"""Annotation Normalization Module.

Normalizes diverse annotation formats (COCO, YOLO, Pascal VOC, custom JSON)
into the authoritative JointInspect Canonical Annotation Schema:
- Normalized label taxonomy:
    NORMAL_JOINT, DISPLACED_JOINT, DAMAGED_JOINT, INTRUDING_SEAL,
    DEPOSITS_OBSTACLES, DIFFICULT_CONDITION
- Standardized bounding boxes [xmin, ymin, xmax, ymax]
- Normalized segmentation polygons and mask references
- Strict physical gap metadata (ground_truth_gap_mm, measurement_method)
- Joint visibility flags: FULL_VISIBILITY, PARTIAL_VISIBILITY, OBSCURED, UNUSABLE
"""

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


LABEL_MAPPING = {
    # Normal mappings
    "normal": "NORMAL_JOINT",
    "normal_joint": "NORMAL_JOINT",
    "intact": "NORMAL_JOINT",
    "ok": "NORMAL_JOINT",
    "good": "NORMAL_JOINT",
    # Displaced mappings
    "displaced": "DISPLACED_JOINT",
    "displaced_joint": "DISPLACED_JOINT",
    "offset": "DISPLACED_JOINT",
    "misaligned": "DISPLACED_JOINT",
    "angular_deflection": "DISPLACED_JOINT",
    # Damaged mappings
    "damaged": "DAMAGED_JOINT",
    "damaged_joint": "DAMAGED_JOINT",
    "broken": "DAMAGED_JOINT",
    "cracked": "DAMAGED_JOINT",
    "spalling": "DAMAGED_JOINT",
    "fracture": "DAMAGED_JOINT",
    # Intruding seal mappings
    "intruding_seal": "INTRUDING_SEAL",
    "seal": "INTRUDING_SEAL",
    "gasket": "INTRUDING_SEAL",
    "intruding_gasket": "INTRUDING_SEAL",
    "gasket_extrusion": "INTRUDING_SEAL",
    # Deposits / obstacles
    "deposits": "DEPOSITS_OBSTACLES",
    "roots": "DEPOSITS_OBSTACLES",
    "blockage": "DEPOSITS_OBSTACLES",
    "obstacle": "DEPOSITS_OBSTACLES",
    "sediment": "DEPOSITS_OBSTACLES",
    # Difficult
    "difficult": "DIFFICULT_CONDITION",
    "turbid": "DIFFICULT_CONDITION",
    "submerged": "DIFFICULT_CONDITION",
}

VALID_VISIBILITY = {"FULL_VISIBILITY", "PARTIAL_VISIBILITY", "OBSCURED", "UNUSABLE"}


class NormalizedAnnotation(BaseModel):
    condition_class: str
    is_joint_visible: bool
    bbox_xyxy: Optional[List[float]] = None  # [xmin, ymin, xmax, ymax]
    bbox_normalized: Optional[List[float]] = None  # [xmin/w, ymin/h, xmax/w, ymax/h]
    polygon_points: Optional[List[List[float]]] = None  # [[x, y], ...]
    mask_path: Optional[str] = None
    visibility_status: str = "FULL_VISIBILITY"
    ground_truth_gap_mm: Optional[float] = None
    measurement_method: Optional[str] = None  # e.g., "CALIPER_FEELER", "SYNTHETIC_EXACT", "ESTIMATED"
    instrument_name: Optional[str] = None
    pipe_diameter_mm: Optional[float] = None
    raw_source_label: str = ""


def normalize_label(raw_label: str) -> str:
    """Maps arbitrary external dataset labels to JointInspect canonical classes."""
    clean = raw_label.strip().lower().replace("-", "_").replace(" ", "_")
    return LABEL_MAPPING.get(clean, "DIFFICULT_CONDITION")


def normalize_bbox(
    bbox: List[float],
    format_type: str,
    img_width: int,
    img_height: int,
) -> Tuple[List[float], List[float]]:
    """Converts diverse bbox formats (xywh, yolo, etc.) to [xmin, ymin, xmax, ymax] in pixels and normalized."""
    if format_type.lower() == "xyxy":
        xmin, ymin, xmax, ymax = bbox[0], bbox[1], bbox[2], bbox[3]
    elif format_type.lower() == "xywh":
        xmin, ymin = bbox[0], bbox[1]
        xmax, ymax = xmin + bbox[2], ymin + bbox[3]
    elif format_type.lower() == "yolo":  # cx, cy, w, h in normalized coords
        cx, cy, w, h = bbox[0] * img_width, bbox[1] * img_height, bbox[2] * img_width, bbox[3] * img_height
        xmin = cx - w / 2.0
        ymin = cy - h / 2.0
        xmax = cx + w / 2.0
        ymax = cy + h / 2.0
    else:
        raise ValueError(f"Unsupported bbox format: {format_type}")

    # Clip to image boundaries
    xmin = max(0.0, min(float(xmin), float(img_width)))
    ymin = max(0.0, min(float(ymin), float(img_height)))
    xmax = max(0.0, min(float(xmax), float(img_width)))
    ymax = max(0.0, min(float(ymax), float(img_height)))

    pixel_bbox = [round(xmin, 2), round(ymin, 2), round(xmax, 2), round(ymax, 2)]
    norm_bbox = [
        round(xmin / img_width, 4) if img_width > 0 else 0.0,
        round(ymin / img_height, 4) if img_height > 0 else 0.0,
        round(xmax / img_width, 4) if img_width > 0 else 0.0,
        round(ymax / img_height, 4) if img_height > 0 else 0.0,
    ]
    return pixel_bbox, norm_bbox


def create_normalized_annotation(
    raw_label: str,
    is_joint_visible: bool = True,
    bbox: Optional[List[float]] = None,
    bbox_format: str = "xyxy",
    img_width: int = 1920,
    img_height: int = 1080,
    polygon_points: Optional[List[List[float]]] = None,
    mask_path: Optional[str] = None,
    visibility_status: str = "FULL_VISIBILITY",
    ground_truth_gap_mm: Optional[float] = None,
    measurement_method: Optional[str] = None,
    instrument_name: Optional[str] = None,
    pipe_diameter_mm: Optional[float] = None,
) -> NormalizedAnnotation:
    """Builds a verified, validated NormalizedAnnotation object."""
    canon_class = normalize_label(raw_label)

    pixel_bbox, norm_bbox = None, None
    if bbox is not None and len(bbox) == 4:
        pixel_bbox, norm_bbox = normalize_bbox(bbox, bbox_format, img_width, img_height)

    vis = visibility_status if visibility_status in VALID_VISIBILITY else "FULL_VISIBILITY"

    return NormalizedAnnotation(
        condition_class=canon_class,
        is_joint_visible=is_joint_visible,
        bbox_xyxy=pixel_bbox,
        bbox_normalized=norm_bbox,
        polygon_points=polygon_points,
        mask_path=mask_path,
        visibility_status=vis,
        ground_truth_gap_mm=ground_truth_gap_mm,
        measurement_method=measurement_method,
        instrument_name=instrument_name,
        pipe_diameter_mm=pipe_diameter_mm,
        raw_source_label=raw_label,
    )
