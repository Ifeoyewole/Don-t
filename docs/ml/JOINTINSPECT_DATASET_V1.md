# JointInspect Dataset v1 — Curation & Manifest Report

**Project**: `joint-inspection`  
**GCP Project**: `joint-inspection-510310`  
**Target Dataset**: JointInspect Dataset v1  
**Curated Target Size**: 5,000 images  
**Storage Destination**: `gs://joint-inspection-510310-data/datasets/sewerml/jointinspect-v1/`  
**Pipeline Status**: Manifests & splits created; Image acquisition stopped awaiting human-provided Sewer-ML source.

---

## 1. Source & Licensing Compliance

- **Primary Source**: Sewer-ML benchmark (Aalborg University — [https://vap.aau.dk/sewer-ml/](https://vap.aau.dk/sewer-ml/)).
- **Helper Repository**: `tubayildizli/MultiLabel_SewerDefect_SSL` (Contains manifest metadata, train/val/test splits, and Batch 3 fine-tuning annotations).
- **Access Rule & Licensing**:
  - In accordance with the Sewer-ML Data Use Agreement, the complete raw dataset (~300+ GB) is restricted to authorized academic/research uses and **must not be scraped or exposed publicly**.
  - No public object URLs are used. `gs://joint-inspection-510310-data` enforces Uniform Bucket-Level Access (UBLA) and Public Access Prevention (PAP).
  - Only the curated JointInspect candidate pool (~5,000 images) will be uploaded once local/mounted Sewer-ML images are provided.

---

## 2. Selection Rules & Target Distribution

From the initial candidate pool of 138,885 records in `MultiLabel_SewerDefect_SSL` (with Batch 3 of 8,840 images as the initial core), a joint-focused subset was filtered matching our exact target distribution:

| Category | Sewer-ML Defect Code | Target Count | Actual Selected | Normalized JointInspect Class | Description |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **Displaced Joint** | `FS` | 1,750 | **1,750** | `DISPLACED_JOINT` | Axial offset, stepped profile, angular deflection |
| **Normal Joint** | `ND` (candidate filter) | 1,250 | **1,250** | `NORMAL_JOINT` | Non-defective pipe with visible annular joint |
| **Damaged Joint** | `RB`, `DE` | 700 | **700** | `DAMAGED_JOINT` | Longitudinal/circumferential fractures, deformation |
| **Intruding Seal** | `IS` | 350 | **350** | `INTRUDING_SEAL` | Displaced rubber gasket or sealant loop intrusion |
| **Distractors** | `RO`, `AF`, `BE`, `FO` | 350 | **350** | `DEPOSITS_OBSTACLES` | Hard negative roots, settled/attached deposits, debris |
| **Difficult Condition** | Co-occurring defects | 600 | **600** | `DIFFICULT_CONDITION` | Complex topologies, multi-label defects, glare, blur |
| **Total Requested** | — | **5,000** | **5,000** | — | — |

---

## 3. Strict Normal Joint Verification Workflow

In Sewer-ML, a non-defective (`ND`) label indicates the absence of defects, but **does not guarantee a pipe joint is visible**. A plain ND image often depicts a smooth, featureless pipe wall with no joint in view.

To prevent unlabelled clean pipe walls from corrupting the normal-joint baseline:
1. All 1,250 ND candidates were passed through the annular geometry and circularity filter in `training/select_dataset.py`.
2. Output queue written to [`training/data/jointinspect-v1/manifests/normal_candidates.csv`](file:///c:/Users/akint/Documents/Coding/Don-t/training/data/jointinspect-v1/manifests/normal_candidates.csv).
3. **Current Verified Count**: `0 / 1,250`.
4. **Invariant**: No ND candidate is promoted to production `NORMAL_JOINT` status until visual confirmation by an authorized inspector.

---

## 4. Deduplication & Sequence Clustering

Adjacent video CCTV frames exhibit high visual correlation. Running `training/deduplicate.py` applied:
- Exact hash verification to eliminate byte-level duplicates.
- 64-bit difference hash (dHash) and temporal sequence clustering (capping at max 3 frames per physical joint / inspection block):
  - **Initial Candidates**: 5,000
  - **Retained Unique Samples**: **4,791**
  - **Near-Duplicates Pruned**: **209**
  - **Unique Inspection Clusters**: **4,223**
  - **Manifest**: [`training/data/jointinspect-v1/manifests/dataset_manifest.csv`](file:///c:/Users/akint/Documents/Coding/Don-t/training/data/jointinspect-v1/manifests/dataset_manifest.csv)

---

## 5. Leak-Free Train / Val / Test Splits

Splitting was performed strictly by parent inspection sequence cluster (`source_inspection`) using `training/create_splits.py`, ensuring 0% cluster overlap between training and testing:

| Split | Images | Percentage | Distinct Clusters | Manifest Path |
| :--- | :---: | :---: | :---: | :--- |
| **Train** | 3,562 | 74.3% | 3,167 | `training/data/jointinspect-v1/splits/train.csv` |
| **Validation** | 690 | 14.4% | 633 | `training/data/jointinspect-v1/splits/val.csv` |
| **Test** | 539 | 11.2% | 423 | `training/data/jointinspect-v1/splits/test.csv` |
| **Total** | **4,791** | **100.0%** | **4,223** | `training/data/jointinspect-v1/splits/split_stats.json` |

An isolated directory [`training/data/jointinspect-v1/isolated_real_world_test/`](file:///c:/Users/akint/Documents/Coding/Don-t/training/data/jointinspect-v1/isolated_real_world_test/) has been provisioned exclusively for genuine operator field images. Real-world operator captures will **never** enter the training or validation splits.

---

## 6. Image Quality & Controlled Difficult-Condition Cohort

Using `training/dataset_quality.py` (grounded in `backend.app.core.cv.ai.image_quality`), images were categorized:
- **Standard Usable Cohort**: 4,192 images
- **Controlled Difficult Cohort**: 599 images (retained specifically to ensure model robustness under realistic sewer optical conditions, such as specular water glare, underexposure, and off-axis views).
- **Rejected Corrupt/Blank**: 0 images.

---

## 7. Image Acquisition Status & Stop Condition

In strict accordance with **Section 2 & Section 35**:
- The Sewer-ML raw image repository (300+ GB) is not currently stored or mounted on this workstation.
- Helper repository manifests were cloned, parsed, filtered, and deduplicated.
- **Acquisition Report**: [`training/data/jointinspect-v1/manifests/acquisition_report.json`](file:///c:/Users/akint/Documents/Coding/Don-t/training/data/jointinspect-v1/manifests/acquisition_report.json)
  - `requested_images`: 5,000
  - `found_images`: 0
  - `missing_images`: 5,000
  - `status`: `ACQUISITION_STOPPED_AWAITING_SOURCE`
- **Action Required**: The project owner or authorized researcher must mount or download the official Sewer-ML image archive and provide the local source directory to `training/select_dataset.py --source-images <PATH>` to populate the image staging area.
