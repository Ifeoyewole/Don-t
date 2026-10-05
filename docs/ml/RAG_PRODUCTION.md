# Production-Safe RAG Knowledge Architecture

## 1. Principles & Independence from Restricted Datasets

The JointInspect Retrieval-Augmented Generation (RAG) system provides context-aware engineering advisory guidance to human inspectors and pipeline operators.

### Independent Knowledge Provenance
To comply with commercial licensing and copyright law:
- **Zero Sewer-ML Contamination**: The production RAG knowledge base contains **zero** Sewer-ML images, **zero** Sewer-ML vector embeddings, and **zero** Sewer-ML metadata.
- **Allowed Knowledge Sources**:
  1. In-house engineering standard operating procedures (SOPs).
  2. Official international pipeline standards (ASTM, WRc, ISO, DIN).
  3. Verified project-owned physical inspection records.
  4. Verified synthetic exemplars from `training/synthetic/` (clearly labeled `VERIFIED_SYNTHETIC_EXAMPLE`).
  5. Optical camera calibration and zero-guessing safety rules.

---

## 2. Seven Canonical Record Types

Every entry in the production RAG knowledge base (`data/rag/production_rag_corpus.json`) is strictly categorized under one of seven canonical types:

| Record Type | Description | Example Content |
| :--- | :--- | :--- |
| `PROCEDURE` | Operational engineering protocols for camera operation and inspection. | Axial positioning, lighting glare mitigation, crawl speed. |
| `DEFECT_REFERENCE` | Formal morphological defect definitions and engineering criteria. | Distinguishing axial pull vs angular deflection. |
| `VERIFIED_REAL_EXAMPLE` | Field or test rig captures verified by human inspection engineers. | Physical test rig captures with feeler gauge ground truth. |
| `VERIFIED_SYNTHETIC_EXAMPLE` | Parametric 3D scenes with mathematically exact geometry. | Synthetic PVC 300mm pipe with 4.0mm annular gap. |
| `CALIBRATION_GUIDANCE` | Rules for deriving optical scale (px/mm) and lens rectification. | Inner diameter scaling, laser triangulation calibration. |
| `SYSTEM_SAFETY_RULE` | Inviolable system architecture and safety invariants. | Zero-guessing invariant: RAG has zero measurement authority. |
| `MODEL_LIMITATION` | Known boundary conditions where computer vision is impaired. | Standing water $>20\%$ diameter, turbulent froth, camera tilt $>15^\circ$. |

### Schema per Record (10 Mandatory Fields):
- `record_id`: Unique identifier (e.g. `SOP-001`, `EX-SYN-0001`).
- `record_type`: One of the 7 canonical types above.
- `source_id`: Originating source identifier (`SRC-OWN-001`, `SRC-SYN-001`).
- `source_type`: `OWNED_REAL`, `SYNTHETIC`, or `INTERNAL_ENGINEERING`.
- `license`: Full legal license reference (e.g. `Proprietary (In-House)`).
- `production_eligible`: Boolean flag (strictly `true` for production RAG).
- `human_verified`: Boolean confirmation of engineering audit.
- `content`: Unambiguous textual guidance or defect narrative.
- `image_uri`: Optional relative URI to verified visual exemplar.
- `embedding_version`: Version identifier of the visual/text feature encoder.
- `created_at`: ISO 8601 UTC timestamp.

---

## 3. Real Visual Embeddings vs Test Vectors

Production vector retrieval operates over genuine visual feature representations (`extract_real_visual_features` in `training/rag/index_pipeline.py`):
- Multi-scale directional edge energy histograms (Sobel $dx/dy$).
- Radial luminance intensity distributions across 32 concentric sectors.
- Spatial frequency energy distributions.
- L2-normalized 64-dimensional float vector embeddings.
- Every vector artifact tracks: `encoder`, `encoder_version`, `weights_sha256`, `embedding_dimension`, `image_sha256`.

> **RULE**: Deterministic pseudorandom hash vectors are strictly designated **`TEST_ONLY`** and are restricted to test suites and offline mock simulations.

---

## 4. Zero-Guessing Measurement Authority Invariant

The RAG subsystem is strictly **advisory and explanatory**:

```
+-------------------------------------------------------------+
|                 AUTHORITATIVE MEASUREMENT                   |
|  OpenCV Sub-Pixel Geometry  -->  Camera Calibration Engine  |
|                               |                             |
|                               v                             |
|                    Authoritative Gap in mm                  |
+-------------------------------------------------------------+
                                |
                                v (Read-Only)
+-------------------------------------------------------------+
|                     PRODUCTION RAG                          |
|  - Matches similar visual exemplars                         |
|  - Provides engineering SOP citations                       |
|  - Explains morphological defect categories                 |
|                                                             |
|  STRICT PROHIBITION:                                        |
|  RAG CANNOT ALTER, OVERRIDE, OR CALCULATE:                  |
|  * measured_gap_mm                                          |
|  * pixels_per_mm                                            |
|  * calibration values                                       |
|  * tolerance status (PASS / FAIL)                           |
|  * confidence ratings                                       |
+-------------------------------------------------------------+
```
