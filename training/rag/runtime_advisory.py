"""Runtime Advisory Integration Engine demonstrating RAG Guidance Isolation.

Executes the production inspection flow:
1. Input Image
2. Model A: Localization (Bounding box / annular seam boundary)
3. Model B: Condition classification
4. OpenCV Geometry + Camera Calibration (Physical millimetre gap measurement)
5. Statistical Confidence Safety Gate (ACCEPTED_MEASUREMENT / REVIEW_REQUIRED / REJECTED_UNRELIABLE)
6. RAG Advisory Retrieval (3–5 validated exemplars + SOP guidance)
7. Human-readable advisory synthesis

IMMUTABLE SAFETY INVARIANT:
RAG / LLM output CANNOT alter or calculate:
- measured_gap_mm
- pixels_per_mm
- calibration status
- tolerance status (PASS / FAIL)
- safety status (ACCEPTED / REVIEW / REJECTED)
RAG provides explanatory references, defect terminology, and procedural guidance ONLY.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from training.rag.index_pipeline import (
    VisualSimilarityRetriever,
    generate_synthetic_visual_embedding,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("runtime_advisory")


class JointInspectionPipeline:
    """Simulates the authoritative multi-stage CV measurement pipeline with advisory RAG."""

    def __init__(self, corpus_path: Path, indexes_dir: Path):
        with open(corpus_path, mode="r", encoding="utf-8") as f:
            self.corpus = json.load(f)
        self.exemplars = self.corpus["exemplars"]

        embeddings_file = indexes_dir / "visual_embeddings_v1.npy"
        matrix = np.load(str(embeddings_file))
        ids = [e["example_id"] for e in self.exemplars]
        self.retriever = VisualSimilarityRetriever(matrix, ids, self.exemplars)

    def process_inspection_frame(
        self,
        simulated_condition: str = "DISPLACED_JOINT",
        ground_truth_gap_mm: float = 4.25,
        pixels_per_mm: float = 12.5,
    ) -> Dict[str, any]:
        """Runs the deterministic physical measurement pipeline followed by isolated RAG advisory."""
        # 1. Model A: Joint Localization
        model_a_result = {
            "detected": True,
            "confidence": 0.92,
            "bbox": [120, 90, 520, 390],
            "role": "Joint Localization Authority (WHERE the joint is)",
        }

        # 2. Model B: Joint Condition
        model_b_result = {
            "predicted_condition": simulated_condition,
            "confidence": 0.89,
            "role": "Visual Condition Estimation (Sewer-ML mapped)",
        }

        # 3. OpenCV Geometry + Sub-pixel Edge Profiling
        raw_gap_pixels = ground_truth_gap_mm * pixels_per_mm + np.random.normal(0, 0.5)
        measured_gap_mm = round(raw_gap_pixels / pixels_per_mm, 2)

        # 4. Calibration & Tolerance Primary Authority
        max_allowable_gap_mm = 3.0
        is_open_joint = measured_gap_mm > max_allowable_gap_mm
        tolerance_status = "FAIL" if is_open_joint else "PASS"

        # 5. Confidence Safety Gate
        fused_confidence = 0.91
        if fused_confidence >= 0.88 and not is_open_joint:
            safety_status = "ACCEPTED_MEASUREMENT"
        elif is_open_joint or fused_confidence >= 0.70:
            safety_status = "REVIEW_REQUIRED"
        else:
            safety_status = "REJECTED_UNRELIABLE"

        authoritative_cv_result = {
            "measured_gap_mm": measured_gap_mm,
            "pixels_per_mm": pixels_per_mm,
            "max_allowable_gap_mm": max_allowable_gap_mm,
            "tolerance_status": tolerance_status,
            "safety_status": safety_status,
            "fused_confidence": fused_confidence,
            "authority": "DETERMINISTIC_OPENCV_AI_PIPELINE",
        }

        # 6. RAG Retrieval (Isolated Advisory Layer)
        dummy_query = {
            "image_filename": "runtime_query.png",
            "jointinspect_class": simulated_condition,
        }
        q_vec = generate_synthetic_visual_embedding(dummy_query, dim=64)
        top_exemplars = self.retriever.search(q_vec, top_k=3)

        retrieved_references = []
        for score, meta in top_exemplars:
            retrieved_references.append({
                "example_id": meta["example_id"],
                "similarity_score": score,
                "verified_condition": meta["jointinspect_class"],
                "visual_characteristics": meta["visual_characteristics"],
                "sop_guidance": meta.get("sop_guidance", {}).get("inspection_guidance", ""),
            })

        # 7. Synthesize Explanatory Advisory Note (Strictly Non-Authoritative)
        sop_rule = top_exemplars[0][1].get("sop_guidance", {}).get("cv_validation_rule", "")
        advisory_explanation = (
            f"Visual classification indicates visual similarity to verified {simulated_condition} cases "
            f"(exemplars {', '.join([r['example_id'] for r in retrieved_references])}). "
            f"Characteristic features include: {', '.join(retrieved_references[0]['visual_characteristics'])}. "
            f"Procedural Rule: {sop_rule}. "
            f"Advisory Note: Deterministic measured gap is {measured_gap_mm}mm. RAG references are advisory only "
            f"and cannot alter the measured physical dimensions or {safety_status} gating."
        )

        return {
            "inspection_id": "INSP_LIVE_DEMO_001",
            "model_a_localization": model_a_result,
            "model_b_classification": model_b_result,
            "authoritative_measurement": authoritative_cv_result,
            "rag_advisory": {
                "allowed_to_modify_measurement": False,
                "advisory_text": advisory_explanation,
                "retrieved_exemplars": retrieved_references,
            },
        }


def main():
    corpus_path = Path("training/data/jointinspect-v1/rag/corpus/verified_corpus.json")
    indexes_dir = Path("training/data/jointinspect-v1/rag/indexes")

    pipeline = JointInspectionPipeline(corpus_path, indexes_dir)
    result = pipeline.process_inspection_frame(simulated_condition="DISPLACED_JOINT", ground_truth_gap_mm=4.10)

    print("=== Joint Inspection Runtime Flow with Isolated RAG ===")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
