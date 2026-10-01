# Pipe Joint Dataset & Training Pipeline

This directory provides the dataset curation and training pipeline for the Pipe Joint AI/CV system.

## 1. Class Mapping (Sewer-ML Benchmark CVPR 2021)

| Category | Sewer-ML Official Defect Codes | Target Count | Purpose |
| :--- | :--- | :--- | :--- |
| **Displaced Joints** | `FS` | 1,750 | Primary defect class |
| **Normal Healthy Joints** | Clean inspection videos (multi-stage filtered) | 1,250 | Clean concentric joints |
| **Cracks & Deformation** | `RB`, `DE` | 700 | Structural degradation near joints |
| **Intruding Seal** | `IS` | 350 | Displaced sealing material/gaskets |
| **Hard Negative Distractors**| `RO`, `AF`, `BE`, `FO` | 350 | Roots, deposits, obstacles to prevent false positives |
| **Difficult Conditions** | Dark, Overexposed, Wet, Blurry | 600 | Real-world underground camera noise |

## 2. Multi-Stage Normal Joint Selection

A normal Sewer-ML image often shows a plain pipe wall without any joint visible. To prevent teaching the model that a featureless wall is a joint:
1. Candidate pool of ~20,000 normal inspection frames is extracted.
2. `select_dataset.py` runs an automated annular feature detector to discard plain pipe segments.
3. Candidate thumbnails are generated for human inspector review.
4. Exactly 1,250 verified healthy joints are retained.

## 3. Leak-Free Grouped Splitting

Frames are grouped strictly by `Inspection_ID` / `Video_ID`:
- **75% Train**: For transfer learning.
- **15% Validation**: For hyperparameter tuning.
- **10% Test**: For offline benchmark evaluation.
- Entire inspections remain strictly inside a single split to prevent adjacent video frames from leaking.

## 4. Execution Workflow

```bash
# 1. Select candidate metadata from Sewer-ML
python training/select_dataset.py --csv SewerML_annotations.csv --image_dir sewer_images/

# 2. Eliminate near-duplicate video frames (pHash/dHash)
python training/deduplicate.py --input_csv training/data/selected_candidates.csv

# 3. Create leak-free grouped splits
python training/create_splits.py --input_csv training/data/deduplicated_dataset.csv

# 4. Evaluate physical measurement accuracy against ground truth
python training/evaluate_measurement.py
```
