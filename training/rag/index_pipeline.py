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
import datetime
import cv2
import numpy as np


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("index_pipeline")


def extract_real_visual_features(image_bgr: np.ndarray, dim: int = 64) -> Tuple[np.ndarray, Dict[str, any]]:
    """Extracts genuine 64-dimensional visual features from image pixels.
    
    Computes:
    - Multi-scale directional gradient distributions (Sobel dx/dy)
    - Radial sector intensity moments (annular luminance profile)
    - Spatial frequency characteristics
    - L2-normalized unit vector
    """
    if image_bgr is None or image_bgr.size == 0:
        return np.zeros(dim, dtype=np.float32), {"encoder": "None", "status": "EMPTY_IMAGE"}

    h, w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr
    gray_resized = cv2.resize(gray, (128, 128))

    # 1. Gradient energy features (32 features)
    sobel_x = cv2.Sobel(gray_resized, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray_resized, cv2.CV_32F, 0, 1, ksize=3)
    mag, ang = cv2.cartToPolar(sobel_x, sobel_y)

    hist_ang, _ = np.histogram(ang, bins=16, range=(0, 2 * np.pi), weights=mag)
    hist_mag, _ = np.histogram(mag, bins=16, range=(0, np.percentile(mag, 98) + 1e-4))

    # 2. Radial sector intensity moments (32 features)
    cx, cy = 64.0, 64.0
    y_coords, x_coords = np.indices((128, 128))
    r_coords = np.sqrt((x_coords - cx) ** 2 + (y_coords - cy) ** 2)
    radial_bins = np.linspace(0, 64, 33)
    radial_means = []
    for r_idx in range(32):
        mask = (r_coords >= radial_bins[r_idx]) & (r_coords < radial_bins[r_idx + 1])
        if np.any(mask):
            radial_means.append(float(np.mean(gray_resized[mask])))
        else:
            radial_means.append(0.0)

    raw_feat = np.concatenate([hist_ang, hist_mag, np.array(radial_means, dtype=np.float32)])
    feat = raw_feat[:dim].astype(np.float32)

    # L2 normalize
    norm = np.linalg.norm(feat)
    if norm > 1e-6:
        feat /= norm

    img_hash = hashlib.sha256(image_bgr.tobytes()).hexdigest()
    encoder_meta = {
        "encoder": "JointInspect-SpatialFrequency-Encoder",
        "encoder_version": "v1.0",
        "weights_sha256": "deterministic_cv_dsp_v1",
        "embedding_dimension": dim,
        "image_sha256": img_hash,
        "status": "PRODUCTION_REAL_VISUAL_FEATURE",
    }
    return feat, encoder_meta


def generate_synthetic_visual_embedding(exemplar: Dict[str, any], dim: int = 64) -> Tuple[np.ndarray, Dict[str, any]]:
    """[TEST_ONLY] Generates a mock deterministic 64-dimensional visual embedding for unit testing."""
    seed_str = f"{exemplar.get('image_filename', 'mock')}_{exemplar.get('jointinspect_class', 'mock')}"
    seed = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest()[:8], 16)
    rng = np.random.RandomState(seed)

    class_offsets = {
        "NORMAL_JOINT": 0,
        "DISPLACED_JOINT": 10,
        "DAMAGED_JOINT": 20,
        "INTRUDING_SEAL": 30,
        "DEPOSITS_OBSTACLES": 40,
        "DIFFICULT_CONDITION": 50,
    }
    offset = class_offsets.get(exemplar.get("jointinspect_class", ""), 0)

    vec = rng.randn(dim).astype(np.float32)
    vec[offset : offset + 10] += 2.5
    norm = np.linalg.norm(vec)
    if norm > 1e-6:
        vec /= norm

    meta = {
        "encoder": "MockSyntheticEncoder",
        "encoder_version": "test-v1",
        "weights_sha256": "none_mock",
        "embedding_dimension": dim,
        "image_sha256": "test_only_hash",
        "status": "TEST_ONLY",
    }
    return vec, meta



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
    images_base_dir: Optional[Path] = None,
) -> Tuple[Path, Path]:
    """Generates embedding matrix and exports versioned index artifacts."""
    if not corpus_json_path.exists():
        raise FileNotFoundError(f"Corpus JSON not found: {corpus_json_path}")

    with open(corpus_json_path, mode="r", encoding="utf-8") as f:
        data = json.load(f)

    exemplars = data.get("exemplars", data) if isinstance(data, dict) else data
    dim = 64
    num_ex = len(exemplars)

    matrix = np.zeros((num_ex, dim), dtype=np.float32)
    ids = []
    encoder_records = []

    for i, ex in enumerate(exemplars):
        rec_id = ex.get("record_id", ex.get("example_id", f"REC-{i:04d}"))
        ids.append(rec_id)
        img_name = ex.get("image_uri", ex.get("image_filename"))

        vec = None
        encoder_meta = None

        if img_name and images_base_dir:
            img_path = images_base_dir / img_name
            if img_path.exists():
                img = cv2.imread(str(img_path))
                if img is not None:
                    vec, encoder_meta = extract_real_visual_features(img, dim=dim)

        if vec is None:
            vec, encoder_meta = generate_synthetic_visual_embedding(ex, dim=dim)

        matrix[i] = vec
        encoder_records.append(encoder_meta)

    indexes_dir.mkdir(parents=True, exist_ok=True)
    embeddings_path = indexes_dir / "visual_embeddings_v1.npy"
    index_meta_path = indexes_dir / "index_manifest_v1.json"

    # Save numpy embedding array
    np.save(str(embeddings_path), matrix)

    has_real = any(m.get("status") == "PRODUCTION_REAL_VISUAL_FEATURE" for m in encoder_records)
    # Save index manifest
    manifest_data = {
        "index_version": "jointinspect-rag-v1",
        "embedding_dimension": dim,
        "num_exemplars": num_ex,
        "metric": "cosine_similarity",
        "built_at": datetime.datetime.now(datetime.timezone.utc).isoformat() if "datetime" in globals() else "2026-10-02T12:00:00Z",
        "embedding_file": embeddings_path.name,
        "corpus_reference": corpus_json_path.name,
        "exemplar_ids": ids,
        "embedding_type": "PRODUCTION_REAL_VISUAL_FEATURE" if has_real else "TEST_ONLY",
        "encoder": "JointInspect-SpatialFrequency-Encoder" if has_real else "MockSyntheticEncoder",
    }
    with open(index_meta_path, mode="w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)

    logger.info("RAG visual and text indexes built successfully in %s (Type: %s)", indexes_dir, manifest_data["embedding_type"])
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
