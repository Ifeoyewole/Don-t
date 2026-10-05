"""Production RAG Knowledge Corpus Builder for JointInspect.

Independent of Sewer-ML and restricted benchmark datasets:
Sources permitted:
- Verified internal examples
- Verified synthetic examples (explicitly marked SYNTHETIC)
- Engineering SOPs and calibration procedures owned by JointInspect
- Measurement rules and system safety invariants
- Approved public technical references (e.g. ASTM / WRc / ISO standards)

Seven Canonical Record Types:
1. PROCEDURE
2. DEFECT_REFERENCE
3. VERIFIED_REAL_EXAMPLE
4. VERIFIED_SYNTHETIC_EXAMPLE
5. CALIBRATION_GUIDANCE
6. SYSTEM_SAFETY_RULE
7. MODEL_LIMITATION

Schema per Record (10 mandatory attributes):
- record_id
- source_id
- source_type
- license
- production_eligible
- human_verified
- content
- image_uri
- embedding_version
- created_at
"""

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_rag_corpus")

VALID_RECORD_TYPES = {
    "PROCEDURE",
    "DEFECT_REFERENCE",
    "VERIFIED_REAL_EXAMPLE",
    "VERIFIED_SYNTHETIC_EXAMPLE",
    "CALIBRATION_GUIDANCE",
    "SYSTEM_SAFETY_RULE",
    "MODEL_LIMITATION",
}


class RAGCorpusRecord(BaseModel):
    record_id: str
    record_type: str
    source_id: str
    source_type: str  # OWNED_REAL, SYNTHETIC, INTERNAL_ENGINEERING
    license: str
    production_eligible: bool
    human_verified: bool
    content: str
    image_uri: Optional[str] = None
    embedding_version: str = "visual-feat-v1.0"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


ENGINEERING_SOPS = [
    {
        "record_id": "SOP-001",
        "record_type": "PROCEDURE",
        "title": "CCTV Crawler Camera Optical Calibration & Axial Positioning",
        "content": (
            "Before sewer inspection, the crawler camera must be centered along the pipe centerline axis. "
            "Lens distortion parameters (focal length fx/fy, principal point cx/cy, radial distortion k1/k2) "
            "must be calibrated against a known checkerboard or optical calibration chart. "
            "Ensure illumination does not create blooming glare on the pipe invert."
        ),
        "source_id": "SRC-OWN-001",
        "source_type": "INTERNAL_ENGINEERING",
        "license": "Proprietary",
        "production_eligible": True,
        "human_verified": True,
    },
    {
        "record_id": "SOP-002",
        "record_type": "PROCEDURE",
        "title": "Circumferential Radial Ray Profiling & Tolerance Assessment",
        "content": (
            "Radial spokes are cast outward from the inner pipe opening centroid across 72 angles (5-degree increments). "
            "Edge transitions are located using sub-pixel parabolic peak interpolation on directional Sobel gradients. "
            "Gaps exceeding the pipe design tolerance (default 2.0mm to 3.0mm) must trigger OPEN_JOINT classification."
        ),
        "source_id": "SRC-OWN-001",
        "source_type": "INTERNAL_ENGINEERING",
        "license": "Proprietary",
        "production_eligible": True,
        "human_verified": True,
    },
    {
        "record_id": "DEF-001",
        "record_type": "DEFECT_REFERENCE",
        "title": "Joint Defect Taxonomy: Angular Deflection vs Axial Pull",
        "content": (
            "Axial gap pull produces uniform gap width around all 360 degrees of the circumference. "
            "Angular deflection produces asymmetric gap width, where one sector is compressed and the opposing sector is widened. "
            "When radial gap variance across the 72 spokes exceeds 1.5mm, flag angular joint deflection."
        ),
        "source_id": "SRC-OWN-001",
        "source_type": "INTERNAL_ENGINEERING",
        "license": "Proprietary",
        "production_eligible": True,
        "human_verified": True,
    },
    {
        "record_id": "CAL-001",
        "record_type": "CALIBRATION_GUIDANCE",
        "title": "Pixels-per-Millimetre Scale Derivation from Known Pipe Diameter",
        "content": (
            "When physical laser calibration is not active, optical scale is derived from the known pipe diameter. "
            "The detected inner circular opening diameter in pixels is divided by the specified nominal diameter in mm: "
            "pixels_per_mm = diameter_px / pipe_diameter_mm. Scale derivation requires circular detection confidence >= 0.90."
        ),
        "source_id": "SRC-OWN-001",
        "source_type": "INTERNAL_ENGINEERING",
        "license": "Proprietary",
        "production_eligible": True,
        "human_verified": True,
    },
    {
        "record_id": "SAF-001",
        "record_type": "SYSTEM_SAFETY_RULE",
        "title": "Zero-Guessing Measurement Authority Rule",
        "content": (
            "MANDATORY INVARIANT: RAG advisory systems, LLMs, and classification models have ZERO authority to alter, "
            "interpolate, or correct physical millimetre gap measurements. "
            "All physical dimensions originate solely from calibrated sub-pixel OpenCV edge detection. "
            "If edge geometry is unresolvable or obscured, the system must report REVIEW_REQUIRED."
        ),
        "source_id": "SRC-OWN-001",
        "source_type": "INTERNAL_ENGINEERING",
        "license": "Proprietary",
        "production_eligible": True,
        "human_verified": True,
    },
    {
        "record_id": "LIM-001",
        "record_type": "MODEL_LIMITATION",
        "title": "Turbid Standing Water & Invert Siltation Limitations",
        "content": (
            "When standing water exceeds 20% of pipe diameter, bottom invert seam geometry cannot be reliably imaged. "
            "The system masks out submerged sectors and reports partial circumferential measurements, "
            "flagging the joint as PARTIAL_VISIBILITY with a mandatory recommendation for hydraulic jetting."
        ),
        "source_id": "SRC-OWN-001",
        "source_type": "INTERNAL_ENGINEERING",
        "license": "Proprietary",
        "production_eligible": True,
        "human_verified": True,
    },
]


def build_production_corpus(
    synthetic_dir: Optional[Path] = Path("data/synthetic/stage_a"),
    output_path: Path = Path("data/rag/production_rag_corpus.json"),
) -> List[RAGCorpusRecord]:
    """Constructs the production-safe RAG corpus from verified engineering records and synthetic exemplars."""
    records: List[RAGCorpusRecord] = []

    # 1. Add Engineering SOPs, Safety Rules, and Calibration Guidance
    for sop in ENGINEERING_SOPS:
        rec = RAGCorpusRecord(**sop)
        records.append(rec)

    # 2. Add Approved Synthetic Exemplars (Clearly marked as VERIFIED_SYNTHETIC_EXAMPLE)
    if synthetic_dir and synthetic_dir.exists():
        synth_files = sorted([f for f in synthetic_dir.glob("*.json") if f.name.startswith("JI-SYN-")])[:30]
        for idx, sf in enumerate(synth_files):
            with open(sf, "r", encoding="utf-8") as f:
                meta = json.load(f)

            rec_id = f"EX-SYN-{idx+1:04d}"
            condition = meta.get("condition", "NORMAL_JOINT")
            gap_mm = meta.get("gap_mm", 0.0)
            dia_mm = meta.get("pipe_diameter_mm", 300.0)
            mat = meta.get("pipe_material", "CONCRETE")

            content = (
                f"Synthetic reference exemplar of a {condition} in a {dia_mm}mm {mat} pipe. "
                f"Ground-truth annular gap is exactly {gap_mm}mm. "
                f"Rendered under {meta.get('lighting')} lighting with {meta.get('environment')} conditions."
            )

            rec = RAGCorpusRecord(
                record_id=rec_id,
                record_type="VERIFIED_SYNTHETIC_EXAMPLE",
                source_id="SRC-SYN-001",
                source_type="SYNTHETIC",
                license="Proprietary (In-House)",
                production_eligible=True,
                human_verified=True,
                content=content,
                image_uri=meta.get("files", {}).get("rgb_image"),
                metadata={
                    "sample_id": meta.get("sample_id"),
                    "condition": condition,
                    "gap_mm": gap_mm,
                    "pipe_diameter_mm": dia_mm,
                    "material": mat,
                },
            )
            records.append(rec)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([r.dict() for r in records], f, indent=2)

    logger.info("Built production RAG corpus with %d verified records at %s", len(records), output_path)
    return records


if __name__ == "__main__":
    build_production_corpus()
