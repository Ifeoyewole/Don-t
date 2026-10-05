# Supervised Production Training Specification

## 1. Overview & Architecture Strategy

JointInspect utilizes two specialized deep-learning vision models to assist deterministic OpenCV inspection:
- **Model A (Joint Localization & Segmentation)**: Predicts the circumferential joint boundary, spatial bounding box, and defect mask.
- **Model B (Joint Condition Classification)**: Categorizes the morphological visual condition of the joint across canonical defect classes.

### Strict Physical Measurement Invariant
The machine-learning models **do not estimate millimetre gap numbers**:
1. Model A produces bounding boxes and joint mask regions to guide OpenCV region-of-interest focus.
2. OpenCV executes sub-pixel radial edge profiling (`measure_circular_gap`) to derive the authoritative physical gap measurement in millimetres.
3. If the measured gap exceeds structural tolerances, the joint is classified as **`OPEN_JOINT`** deterministically. Visual Model B **never overrides physical measurement authority**.

---

## 2. Model Architectures & Selection Rationale

### Model A: Joint Localization & Segmentation
- **Architecture**: Lightweight Convolutional Encoder-Decoder with separable spatial feature convolutions and multi-scale contextual aggregation.
- **Deployment Criteria**:
  - Export format: Standard ONNX computation graph (`opset 17+`).
  - CPU Inference: Target $< 45\text{ ms}$ on standard 2-vCPU Cloud Run instances.
  - Model Binary Size: $< 25\text{ MB}$.
- **Loss Function**: $\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{BCE}} + \mathcal{L}_{\text{Dice}}$
- **Empirical Validation Metrics**:
  - Mean Intersection-over-Union (mIoU)
  - Soft Dice Coefficient
  - Boundary Precision & Recall

### Model B: Joint Condition Classification
- **Architecture**: Lightweight Convolutional Network with Global Average Pooling (GAP) and Linear Softmax head.
- **Canonical Output Classes**:
  1. `NORMAL_JOINT`: Intact concentric joint with zero structural degradation.
  2. `DISPLACED_JOINT`: Radial offset, angular misalignment, or eccentric deflection.
  3. `DAMAGED_JOINT`: Chipped socket, broken edge, spalling, cracks, or mechanical fracture.
  4. `INTRUDING_SEAL`: Displaced elastomeric sealing ring or rubber gasket extrusion.
  5. `DEPOSITS_OBSTACLES`: Invert siltation, gravel accumulation, root intrusion, or debris blockage.
  6. `DIFFICULT_CONDITION`: Heavy turbid standing water, reflections, or complex non-standard geometries.
- **Loss Function**: Categorical Cross-Entropy with label smoothing.
- **Empirical Validation Metrics**: Macro-F1, Weighted-F1, per-class Precision and Recall.

---

## 3. Safe Fallback Behavior (Missing Model Weights)

Under zero-trust and zero-guessing principles:
- **If Model A weights are unavailable**:
  - Status: `MODEL_UNAVAILABLE`
  - Confidence: `0.0`
  - Action: Bounding box set to `None`; flags `REVIEW_REQUIRED`.
- **If Model B weights are unavailable**:
  - Status: `CLASSIFICATION_UNAVAILABLE`
  - Confidence: `0.0`
  - Action: Flags `REVIEW_REQUIRED`.
  - **PROHIBITION**: The system **NEVER** defaults missing Model B to `NORMAL_JOINT`, and **NEVER** fabricates confidence probabilities.

---

## 4. Cost-Protective Training Ladder

To protect Google Cloud promotional credits and prevent unnecessary GPU costs:

| Stage | Name | Compute | Dataset Scope | Artifact Export | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Stage 0** | `PIPELINE_DRY_RUN` | Local CPU ($0.00) | 0 samples | **NONE** (No ONNX generated) | Validate CLI wiring, GCP IAM, parameters. |
| **Stage 1** | `REAL SMOKE TRAINING` | Local / Cheap CPU | 100–500 approved samples | Candidate ONNX | Real forward/backward pass, convergence, loss & metrics. |
| **Stage 2** | `BASELINE` | Vertex AI CPU / T4 | ~2,000 approved samples | Candidate ONNX | Hyperparameter tuning, learning rate scheduling. |
| **Stage 3** | `FULL PRODUCTION V1` | Vertex AI GPU | Complete approved dataset | Production ONNX | Full training to convergence with early stopping. |

---

## 5. Model Versioning & Artifact Governance

All trained models are governed by the immutable versioning registry in `training/model_versioning.py`:

```
models/
├── segmenter/
│   ├── candidates/
│   │   └── <model_version>/
│   │       ├── model.onnx
│   │       └── model_version.json
│   └── production/
└── classifier/
    ├── candidates/
    │   └── <model_version>/
    │       ├── model.onnx
    │       └── model_version.json
    └── production/
```

### Required Version Attributes (`model_version.json`):
1. `model_version`: Immutable string identifier.
2. `dataset_version`: Manifest version utilized for training.
3. `dataset_manifest_sha256`: Cryptographic digest of source dataset manifest.
4. `git_commit`: Source control commit hash.
5. `training_run_id`: Unique execution run identifier.
6. `architecture`: Formal architecture specification.
7. `weights_sha256`: SHA-256 digest of `model.onnx` binary.
8. `training_date`: ISO 8601 UTC timestamp.
9. `validation_metrics`: Dict containing real empirical validation scores.
10. `production_approved`: Boolean flag (default `False`).
11. `approved_by`: Email / ID of authorizing engineer.

> **RULE**: Model versions are strictly write-once. Overwriting an existing model version directory throws an immediate `FileExistsError`.
