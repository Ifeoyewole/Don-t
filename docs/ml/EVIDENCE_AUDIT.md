# JointInspect Evidence & Provenance Audit

**Audit Date**: October 2, 2026  
**Auditor**: Antigravity Machine Learning Quality & Compliance  
**Repository**: `Ifeoyewole/Don-t`  
**Google Cloud Project**: `joint-inspection-510310`  
**Primary Bucket**: `gs://joint-inspection-510310-data`

---

## 1. Executive Summary & Truthfulness Mandate

This audit establishes the factual baseline of the JointInspect computer vision and machine learning assets. Prior dry-runs and pipeline simulations have been audited to eliminate any ambiguity between pipeline plumbing tests and empirical production-trained assets.

### Core Provenance Truths:
1. **Sewer-ML Raw Images Acquired**: **0** (Downloaded images: 0 bytes. Helper repository manifests cloned: 138,885 records).
2. **Sewer-ML Commercial Rights Status**: **`BENCHMARK_PERMISSION_PENDING`** (`production_eligible = false`, `training_allowed = false`).
3. **Normal Candidates Human Verified**: **0 / 1,250** (All 1,250 ND candidates remain queued in `normal_candidates.csv` awaiting manual human review).
4. **Real Supervised Model A Training**: **`NOT_STARTED`** (Stage 0 was a CPU pipeline plumbing dry-run. No trained ONNX weights exist).
5. **Real Supervised Model B Training**: **`NOT_STARTED`** (Stage 0 was a CPU pipeline plumbing dry-run. No trained ONNX weights exist).
6. **Placeholder ONNX Artifacts**: **`REMOVED / DESTROYED`** (All fake placeholder `.onnx` files created during early dry-runs have been permanently removed from local scratch and candidate paths).
7. **RAG Visual Embeddings**: **`SYNTHETIC_TEST_ONLY`** (Generated from synthetic deterministic feature seeds for retrieval harness testing. Not production visual encoder weights).
8. **Physical Measurement Ground Truth**: OpenCV radial sub-pixel edge profiling remains the sole physical measurement authority. Sewer-ML image-level defect labels cannot and will not be used to claim physical millimeter accuracy.

---

## 2. Component-by-Component Evidence Matrix

| Component | Target Artifact / Script | Evidence Status | Verification Finding |
| :--- | :--- | :--- | :--- |
| **Sewer-ML Ingestion** | `training/select_dataset.py` | `PENDING_SOURCE_DATA` | Manifests parsed (5,000 wanted images specified); physical image acquisition stopped cleanly at Stage 0 awaiting source mounting. |
| **Candidate Manifests** | `training/data/jointinspect-v1/manifests/` | `READY` | `wanted_images.csv`, `wanted_images.txt`, `acquisition_report.json` complete and verified. |
| **Normal Joint Verification** | `manifests/normal_candidates.csv` | `PENDING_HUMAN_REVIEW` | 1,250 ND candidates extracted; 0 human-verified. Promotion to production blocked. |
| **Deduplication Engine** | `training/deduplicate.py` | `READY` | Evaluated across 5,000 records; pruned 209 near-duplicates across 4,223 clusters. |
| **Leak-Free Splits** | `training/create_splits.py` | `READY` | Grouped by inspection sequence; 74.3% train, 14.4% val, 11.2% test with 0% cluster leakage. |
| **Isolated Real-World Test** | `isolated_real_world_test/` | `READY` | Dedicated directory created; isolated from training loops. |
| **Model A (Segmenter)** | `backend/app/core/cv/ai/joint_segmenter.py` | `NOT_STARTED` | Code interface ready. Weights missing; returns `MODEL_UNAVAILABLE` and `confidence=0.0`. |
| **Model B (Classifier)** | `backend/app/core/cv/ai/joint_classifier.py` | `NOT_STARTED` | Code interface ready. Weights missing; returns `CLASSIFICATION_UNAVAILABLE` and `confidence=0.0`. Never defaults to `NORMAL_JOINT`. |
| **Training Task Engine** | `training/task.py` | `PIPELINE_DRY_RUN` | Stage 0 dry-run verified. Fake ONNX export removed. Real training blocked until commercial data approved. |
| **RAG Knowledge Corpus** | `training/rag/corpus/verified_corpus.json` | `SYNTHETIC_TEST_ONLY` | 600 exemplars with SOP guidance and visual characteristics; vectors derived from synthetic feature seeds. |
| **RAG Runtime Safety Gate**| `training/rag/runtime_advisory.py` | `READY` | Confirmed: RAG outputs advisory text only. Measurement values and safety gates are immutable by RAG. |
| **GCS Data Bucket** | `gs://joint-inspection-510310-data` | `READY` | Private storage enforced (UBLA + PAP). No public URLs. No static service-account JSON keys. |

---

## 3. Sewer-ML Legal & Governance Position

- **Current Designation**: `BENCHMARK_ONLY (PERMISSION_PENDING)`
- **Prohibitions**:
  - Sewer-ML images MUST NOT be used for commercial production training.
  - Sewer-ML images MUST NOT be used for fine-tuning, pre-training, or distillation.
  - Sewer-ML images MUST NOT be embedded into production RAG corpuses.
  - Sewer-ML images MUST NOT be uploaded to shared GCP storage without explicit signed commercial licensing.
- **Permitted Scope**:
  - Offline evaluation as an academic benchmark ONLY if and when explicit research permission is approved.
  - Evaluation against Sewer-ML must use frozen production models with zero backpropagation, zero weight updates, and zero batch retention.

---

## 4. Remediation Actions Executed

1. **Purged Placeholder ONNX Files**: Deleted `scratch/training_tmp/checkpoints/*`. Confirmed `gs://joint-inspection-510310-data/models/` contains zero fake weight files.
2. **Eliminated Default NORMAL_JOINT Assumption**: Updated `joint_classifier.py` so that an uninitialized model strictly returns `CLASSIFICATION_UNAVAILABLE` with `confidence=0.0`, never fabricating normal status.
3. **Eliminated Invented Confidence Scores**: Removed hardcoded `0.70` confidence defaults when weights are absent.
4. **Stage 0 Hardening**: Updated `training/task.py` so that Stage 0 runs as an explicit pipeline dry-run without writing dummy weights or recording fake candidate artifacts.
5. **Truth in Metrics**: Documented that all Stage 0 metric values were simulated tensor convergence tests, not real-world model accuracy. Real-world physical accuracy requires empirical data from our controlled physical test rig.
