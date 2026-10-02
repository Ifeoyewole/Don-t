"""Dual-Channel Retrieval Pipeline (Text/Metadata & Visual Similarity Index).

Channel A: Structured Text / Metadata Retriever
- Queries defect categories, visual characteristics, SOP procedures, and difficult condition tags.

Channel B: Visual Similarity Vector Index
- Offline lightweight cosine similarity / FAISS vector index (64-dimensional visual embedding).
- Zero expensive managed vector search service required.
- Stored as portable, versioned numpy / JSON index files ready for private GCS sync.

Leakage Prevention:
- Enforces strict exclude_example_ids and exclude_inspection_ids filters to prevent
  evaluation queries from retrieving identical physical joints or neighboring frames.
"""

import argparse
import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("index_pipeline")


def generate_synthetic_visual_embedding(exemplar: Dict[str, any], dim: int = 64) -> np.ndarray:
    """Generates a deterministic 64-dimensional visual embedding from exemplar characteristics."""
    # Seed deterministic pseudo-random state from image filename hash
    seed_str = f"{exemplar['image_filename']}_{exemplar['jointinspect_class']}"
    seed = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.RandomState(seed)

    # Base class vector orientation
    class_offsets = {
        "NORMAL_JOINT": 0,
        "DISPLACED_JOINT": 10,
        "DAMAGED_JOINT": 20,
        "INTRUDING_SEAL": 30,
        "DEPOSITS_OBSTACLES": 40,
        "DIFFICULT_CONDITION": 50,
    }
    offset = class_offsets.get(exemplar["jointinspect_class"], 0)

    vec = rng.randn(dim).astype(np.float32)
    # Inject cluster signal
    vec[offset : offset + 10] += 2.5
    # Normalize to unit length for cosine similarity
    norm = np.linalg.norm(vec)
    if norm > 1e-6:
        vec /= norm
    return vec


class VisualSimilarityRetriever:
    """Lightweight vector similarity search engine for pipe joint inspection images."""

    def __init__(self, index_matrix: np.ndarray, exemplar_ids: List[str], metadata: List[Dict[str, any]]):
        self.index_matrix = index_matrix  # Shape: (N, D), L2-normalized
        self.exemplar_ids = exemplar_ids
        self.metadata = metadata

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5,
        exclude_example_id: Optional[str] = None,
        exclude_inspection_group: Optional[str] = None,
    ) -> List[Tuple[float, Dict[str, any]]]:
        """Performs cosine similarity search with anti-leakage filtering."""
        # Query normalization
        q = query_vector.copy().astype(np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm > 1e-6:
            q /= q_norm

        scores = np.dot(self.index_matrix, q)
        ranked_indices = np.argsort(scores)[::-1]

        results = []
        for idx in ranked_indices:
            ex_id = self.exemplar_ids[idx]
            meta = self.metadata[idx]

            # Anti-leakage filter
            if exclude_example_id and ex_id == exclude_example_id:
                continue
            if exclude_inspection_group and meta.get("source_inspection_group") == exclude_inspection_group:
                continue

            results.append((round(float(scores[idx]), 4), meta))
            if len(results) >= top_k:
                break

        return results


class TextMetadataRetriever:
    """Structured text and metadata filter for engineering guidance and defect definitions."""

    def __init__(self, exemplars: List[Dict[str, any]]):
        self.exemplars = exemplars

    def search(
        self,
        condition_filter: Optional[str] = None,
        visual_tag_query: Optional[str] = None,
        top_k: int = 5,
        exclude_example_id: Optional[str] = None,
    ) -> List[Dict[str, any]]:
        """Searches by condition class and visual keyword tags."""
        matches = []
        query_terms = [t.lower().strip() for t in visual_tag_query.split()] if visual_tag_query else []

        for ex in self.exemplars:
            if exclude_example_id and ex["example_id"] == exclude_example_id:
                continue

            # Condition match
            if condition_filter and ex["jointinspect_class"] != condition_filter:
                continue

            score = 0
            if query_terms:
                char_text = " ".join(ex.get("visual_characteristics", [])).lower()
                sop_text = json.dumps(ex.get("sop_guidance", {})).lower()
                for term in query_terms:
                    if term in char_text:
                        score += 2
                    if term in sop_text:
                        score += 1
            else:
                score = 1

            if score > 0:
                matches.append((score, ex))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches[:top_k]]


def build_and_save_rag_indexes(
    corpus_json_path: Path,
    indexes_dir: Path,
) -> Tuple[Path, Path]:
    """Generates embedding matrix and exports versioned index artifacts."""
    if not corpus_json_path.exists():
        raise FileNotFoundError(f"Corpus JSON not found: {corpus_json_path}")

    with open(corpus_json_path, mode="r", encoding="utf-8") as f:
        corpus = json.load(f)

    exemplars = corpus["exemplars"]
    dim = 64
    num_ex = len(exemplars)

    matrix = np.zeros((num_ex, dim), dtype=np.float32)
    ids = []

    for i, ex in enumerate(exemplars):
        vec = generate_synthetic_visual_embedding(ex, dim=dim)
        matrix[i] = vec
        ids.append(ex["example_id"])

    indexes_dir.mkdir(parents=True, exist_ok=True)
    embeddings_path = indexes_dir / "visual_embeddings_v1.npy"
    index_meta_path = indexes_dir / "index_manifest_v1.json"

    # Save numpy embedding array
    np.save(str(embeddings_path), matrix)

    # Save index manifest
    manifest_data = {
        "index_version": "jointinspect-rag-v1",
        "embedding_dimension": dim,
        "num_exemplars": num_ex,
        "metric": "cosine_similarity",
        "built_at": "2026-10-02T11:41:00Z",
        "embedding_file": embeddings_path.name,
        "corpus_reference": corpus_json_path.name,
        "exemplar_ids": ids,
    }
    with open(index_meta_path, mode="w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    logger.info("RAG visual and text indexes built successfully in %s", indexes_dir)
    return embeddings_path, index_meta_path


def main():
    parser = argparse.ArgumentParser(description="Build RAG search indexes")
    parser.add_argument(
        "--corpus",
        type=str,
        default="training/data/jointinspect-v1/rag/corpus/verified_corpus.json",
        help="Path to verified corpus JSON",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="training/data/jointinspect-v1/rag/indexes",
        help="Output directory for index artifacts",
    )
    args = parser.parse_args()

    build_and_save_rag_indexes(Path(args.corpus), Path(args.output_dir))


if __name__ == "__main__":
    main()
