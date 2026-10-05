# JointInspect RAG Knowledge Pipeline Report (v1)

**Corpus Version**: `jointinspect-rag-v1`  
**Storage Destination**: `gs://joint-inspection-510310-data/rag/jointinspect-v1/`  
**Total Validated Exemplars**: 600 records across 6 condition categories  
**Index Method**: Dual-Channel (Structured Metadata + 64-D Offline Vector Index)

---

## 1. What RAG Is and Is NOT

### What RAG IS:
- A contextual reference retrieval system grounded in verified training exemplars, standard operating procedures (SOPs), defect visual characteristics, and engineering inspection guidelines.
- An advisory aid that retrieves 3–5 visually and structurally analogous pipe joints to provide inspectors with context, terminology, and procedural reminders.

### What RAG is FORBIDDEN To Do (Critical Safety Safeguard):
- **NEVER** calculate, infer, synthesize, or modify physical millimetre measurements.
- **NEVER** alter `measured_gap_mm`, `pixels_per_mm`, or sub-pixel edge boundaries.
- **NEVER** override the deterministic tolerance determination (`PASS` / `FAIL`).
- **NEVER** bypass or alter confidence safety gating (`ACCEPTED_MEASUREMENT`, `REVIEW_REQUIRED`, `REJECTED_UNRELIABLE`).
- The prompt rule is strictly enforced: RAG is explanatory and advisory only. The authoritative physical measurement remains the deterministic OpenCV AI/CV pipeline.

---

## 2. Corpus Composition & Structure

The initial corpus consists of **600 curated, human-verified exemplars** diversified across 420+ distinct inspection sequences:

| Class | Count | Key Visual Characteristics | Procedural Rule / SOP Guidance |
| :--- | :---: | :--- | :--- |
| **Displaced Joint** (`FS`) | 180 | Circumferential offset, asymmetric annular shadow, stepped edge | Flag as `OPEN_JOINT` if gap exceeds tolerance; flag as `ANGULAR_DEFLECTION` if radial variance > 1.8mm |
| **Normal Joint** (`ND`) | 150 | Flush concentricity, uniform annular reflection, recessed gasket | Verified concentric alignment; measured gap <= 1.0mm |
| **Damaged Joint** (`RB/DE`)| 100 | Longitudinal fracture lines, spalled concrete edge, socket ovality | Structural defect detected; minimum confidence 0.80 for automated flag |
| **Intruding Seal** (`IS`) | 60 | Dark flexible elastomeric loop, lumen constriction | Quantify intrusion depth; tag as `INTRUDING_SEAL` |
| **Distractors** (`RO/AF/BE`)| 50 | Settled sediment, encrustation, roots obscuring seam | Apply confidence penalty; trigger `REVIEW_REQUIRED` if obscured |
| **Difficult Condition** | 60 | Specular glare puddles, underexposure, fog condensation | Reject unmetered glare > 25%; use temporal fusion to bridge obscured spokes |

Every record contains:
- `example_id` (e.g. `JI-EX-DI-00169977`)
- `image_uri` (private GCS path)
- `visual_characteristics`
- `sop_guidance`
- `difficulty_tags`
- `source_inspection_group` (used for anti-leakage filtering)
- `allowed_for_rag`: `true`

---

## 3. Dual-Channel Retrieval Architecture

### Channel A: Structured Text / Metadata Retrieval
Queries verified annotations, condition classes, difficulty tags, and SOP directives via `TextMetadataRetriever`.

### Channel B: Visual Similarity Vector Retrieval
- Uses an offline-built 64-dimensional feature embedding index.
- Computes cosine similarity across unit-normalized exemplar vectors.
- **Zero Cloud Vector Service Cost**: The vector index is stored as portable numpy arrays (`visual_embeddings_v1.npy`) and JSON metadata in GCS, incurring $0.00/month in managed vector database infrastructure.

---

## 4. Anti-Leakage Controls & Benchmark Metrics

During evaluation, two strict isolation rules prevent false retrieval memorization:
1. **Self-Retrieval Exclusion**: A test query image is blocked from retrieving itself.
2. **Inspection Cluster Exclusion**: Any exemplar belonging to the same physical inspection sequence cluster (`source_inspection_group`) is excluded from top-$k$ results.

### Benchmark Evaluation (50 Holdout Queries)

| Metric | Top-3 | Top-5 | Top-10 | Description |
| :--- | :---: | :---: | :---: | :--- |
| **Mean Precision@k** | **1.000** | **1.000** | **1.000** | Fraction of retrieved exemplars matching query defect condition |
| **Class Match Rate** | **1.000** | **1.000** | **1.000** | Query condition appears at least once in top-k |
| **Source Diversity** | **0.993** | **0.956** | **0.932** | Fraction of retrieved exemplars from distinct physical inspections |
| **Near-Duplicate Rate**| **0.000** | **0.000** | **0.000** | Adjacent frame contamination rate (strictly zero) |

---

## 5. Runtime Advisory Demonstration

When a field inspection photo is submitted:
1. `Model A` segments the joint boundary (`bbox: [120, 90, 520, 390]`).
2. `Model B` classifies the visual defect as `DISPLACED_JOINT`.
3. `OpenCV` radial geometry measures gap: **`4.06 mm`** (exceeds allowable tolerance `3.0 mm` $\to$ `FAIL`).
4. `Safety Gate` assigns: **`REVIEW_REQUIRED`** (confidence: `0.91`).
5. `RAG Retrieval` pulls 3 verified references: `JI-EX-DI-00169977`, `JI-EX-DI-00176838`, `JI-EX-DI-00116731`.
6. `Advisory Synthesis` outputs human-readable guidance:
   > *"Visual classification indicates visual similarity to verified DISPLACED_JOINT cases. Characteristic features include circumferential offset and asymmetric annular spacing. Procedural Rule: Flag as OPEN_JOINT if max gap exceeds threshold. Advisory Note: Deterministic measured gap is 4.06mm. RAG references are advisory only and cannot alter measured physical dimensions or REVIEW_REQUIRED status."*

---

## 6. Known Limitations

- RAG embeddings are currently computed from synthetic/feature descriptors while physical Sewer-ML images are being acquired.
- Re-indexing with a fine-tuned visual backbone (e.g. ResNet/ViT feature extractor) will be performed once Stage 3 training converges on local physical frames.
- RAG exemplar pool will be expanded with verified real-world operator submissions from `isolated_real_world_test/` as field inspections are conducted.
