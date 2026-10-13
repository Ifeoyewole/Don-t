# JointInspect — Sewer-ML Cloud Ingestion & Candidate Classifier Report

**Date:** 2026-10-14  
**Project:** `joint-inspection-510310`  
**Model Name:** `sewer-condition-v1`  
**Version:** `sewer-condition-v1.0.0-candidate`  
**Production Status:** `production_approved: false` (Experimental Candidate / Advisory Mode)  
**Primary Production Classifier:** WRc InceptionResNetV2 Baseline (`wrc-inceptionresnetv2-baseline-v1`)  

---

## 1. Executive Summary

This report documents the authorized end-to-end cloud pipeline, empirical training, and quantitative evaluation of the **Sewer-ML Multi-Label Condition Classifier** for the JointInspect pipe joint inspection platform.

All ingestion, data processing, model training, evaluation, and ONNX export were executed **exclusively within Google Cloud Platform** (`europe-west2`). In accordance with strict security and system invariants:
- **Zero Local Downloads:** Zero dataset images, archives, video streams, or model weights were downloaded to developer personal machines.
- **Credential Hygiene:** Source download credentials and access tokens are managed via Google Secret Manager (`sewer-ml-download-password`) and were never exposed in Git history, shell scripts, or documentation.
- **Measurement Authority (Zero-Guessing):** The deterministic OpenCV edge detection pipeline combined with physical reference target calibration remains the absolute authority for millimeter gap measurements. Neural networks provide advisory visual defect recognition and are strictly barred from fabricating millimeter values.

---

## 2. Ingestion & Dataset Pipeline Provenance

- **Source Dataset:** Sewer-ML (Aalborg University / CC BY-NC-SA 4.0)
- **Total Remote Repository Volume:** 303.79 GB across 18 archive segments
- **Total Source Labels Analyzed:** 1,170,175 rows across `SewerML_Train.csv` (1,040,129 images) and `SewerML_Val.csv` (130,046 images)
- **Stratified Curated Ingestion:** 8,147 real images downloaded to ephemeral Cloud Build storage and uploaded directly to Google Cloud Storage:
  - `gs://joint-inspection-510310-data/datasets/sewer-ml/curated/images/`
- **Category Manifests Populated:**
  - `curated/displacement/manifest.csv`: 4,668 records
  - `curated/joint-related/manifest.csv`: 5,294 records
  - `curated/cracks-and-fractures/manifest.csv`: 1,489 records
  - `curated/deformation/manifest.csv`: 156 records
  - `curated/roots-and-deposits/manifest.csv`: 2,691 records
  - `curated/normal/manifest.csv`: 1,900 records
  - `curated/difficult-scenes/manifest.csv`: 5,347 records
  - `curated/negatives/manifest.csv`: 2,691 records

---

## 3. Training Architecture & Objective

- **Architecture:** `SewerConditionClassifier` (4-stage deep convolutional feature extractor with Batch Normalization, ReLU activations, Max-Pooling, Global Adaptive Average Pooling, and Dense Classification Head).
- **Task Objective:** Multi-label binary cross-entropy with empirical positive class weights (`pos_weight`) to account for severe label imbalance:
  $$\mathcal{L}_{BCE} = - \sum_{c=1}^C \left[ w_c \cdot y_c \log(\sigma(z_c)) + (1 - y_c) \log(1 - \sigma(z_c)) \right]$$
- **Optimizer:** AdamW ($\text{LR} = 0.001$, weight decay = $10^{-4}$) with Cosine Annealing learning rate schedule.
- **Input Resolution:** $128 \times 128 \times 3$ normalized to ImageNet statistics.
- **Compute:** Ephemeral GCP Cloud Build Worker (`E2_HIGHCPU_8`, 8 vCPUs, PyTorch OneDNN vectorization).

---

## 4. Quantitative Evaluation & Benchmark Comparison

The candidate model was trained across 6 epochs (total training duration: 578.3 seconds) on 6,447 training images and evaluated on 1,700 held-out validation images.

### 4.1 Class-Wise Performance

| Defect Class | JointInspect Mapped Concept | Validation Support | Precision | Recall | F1 Score | F2 Score |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **FS** (Displaced Joint) | `DISPLACED_JOINT` | 964 | **0.7027** | **0.9315** | **0.8011** | **0.8746** |
| **IS** (Intruding Seal) | `INTRUDING_SEAL` | 163 | 0.1453 | 0.6748 | 0.2391 | 0.3903 |
| **RB** (Broken / Fracture) | `DAMAGED_JOINT` | 279 | 0.1771 | 0.5986 | 0.2733 | 0.4055 |
| **DE** (Deformation) | `DAMAGED_JOINT` | 39 | 0.0673 | 0.1795 | 0.0979 | 0.1346 |
| **RO** (Roots) | `DEPOSITS_OBSTACLES` | 78 | 0.0862 | 0.8333 | 0.1563 | 0.3049 |
| **AF** (Settled Deposits) | `DEPOSITS_OBSTACLES` | 339 | 0.2608 | 0.8584 | 0.4000 | 0.5886 |
| **BE** (Attached Deposits)| `DEPOSITS_OBSTACLES` | 177 | 0.1345 | 0.7571 | 0.2285 | 0.3932 |
| **FO** (Obstacle) | `DEPOSITS_OBSTACLES` | 12 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| **ND** (Normal Pipe) | `NORMAL_PIPE` | 400 | **0.6927** | **0.6650** | **0.6786** | **0.6704** |

- **Overall Micro Recall:** **0.7907** (79.1% across all defects)
- **Overall Micro F1:** **0.4413**
- **Overall Macro Recall:** **0.6109**
- **Overall Macro F1:** **0.3194**
- **Calibration ECE (10 bins):** 0.5930

### 4.2 Comparison Against WRc InceptionResNetV2 Baseline

| Condition Concept | WRc Baseline F1 | Candidate F1 | Delta ($\Delta F_1$) | WRc Recall | Candidate Recall | Assessment |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **DISPLACED_JOINT** | 0.5820 | **0.8011** | **+0.2191** | 0.5400 | **0.9315** | **Substantial Superiority (+21.9% F1, +39.2% Recall)** |
| **NORMAL_PIPE** | 0.4500 | **0.6786** | **+0.2286** | 0.4200 | **0.6650** | **Substantial Superiority (+22.9% F1, +24.5% Recall)** |
| **DAMAGED_JOINT** | 0.5140 | 0.1856 | -0.3284 | 0.4920 | 0.3891 | WRc Baseline Superior |
| **DEPOSITS_OBSTACLES**| 0.6200 | 0.1962 | -0.4238 | 0.6100 | 0.6122 | WRc Baseline Superior |
| **Macro Average** | **0.5410** | 0.3194 | -0.2216 | - | - | **WRc Baseline Retained as Primary** |

---

## 5. Model A Joint Localization & Geometry Invariants

### Track B Finding: Sewer-ML Annotation Modality
Inspection of the official Sewer-ML annotations (`SewerML_Train.csv`, `SewerML_Val.csv`, `SewerML_Test.csv`) conclusively confirms:
1. **Sewer-ML contains strictly image-level multi-label defect classifications.**
2. **Sewer-ML contains NO bounding boxes, segmentation masks, pixel coordinates, or physical millimeter measurements.**
3. **No False Claims:** Sewer-ML cannot and must not be used to claim that Model A has been trained for supervised pixel-level joint segmentation or physical gap measurement.

### Track C: Physical Measurement Authority
- Deterministic OpenCV edge-finding, Canny/Hough/Contour analysis, and calibrated physical reference target detection remain the sole authority for physical gap measurements.
- Candidate visual models act exclusively as advisory defect classifiers (`advisory_mode`).
- The Zero-Guessing invariant is strictly enforced: `production_approved: false`.

---

## 6. GCS Artifact Registry

All artifacts are persisted in Google Cloud Storage:

- **Candidate Model Directory:**
  `gs://joint-inspection-510310-data/models/candidates/sewer-condition-v1/`
  - `model.onnx` (SHA-256: `f5cc05da983f95e019bb45d926e8c98fb5909cf2ae1aa2dc37a574f35b526a44`)
  - `model_best.pt` (PyTorch checkpoint)
  - `model_version.json` (Full model card & governance record)
  - `metrics.json` (Per-class empirical evaluation metrics)
  - `training_history.json` (6-epoch loss & convergence curves)
  - `wrc_comparison.json` (Automated comparison against WRc baseline)
- **Curated Dataset:**
  `gs://joint-inspection-510310-data/datasets/sewer-ml/curated/images/` (8,147 images)
  `gs://joint-inspection-510310-data/datasets/sewer-ml/splits/` (Stratified train & val CSVs)
  `gs://joint-inspection-510310-data/datasets/sewer-ml/quality-reports/sewer_ml_inventory.json`
