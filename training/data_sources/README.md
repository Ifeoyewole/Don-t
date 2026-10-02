# Commercial Data Source Registry

## Overview
This registry governs all datasets used in JointInspect. To safeguard commercial deployment, no data may enter the production training pipeline without:
1. Verified original legal provenance.
2. Verified commercial training and deployment rights (`commercial_training_allowed = true`).
3. Explicit administrative or legal approval (`approval_status = "APPROVED_PRODUCTION"`).

## Strict Invariant: Fail Closed on Unknown Rights
If a data source has `approval_status = "UNKNOWN_RIGHTS"`, the ingestion pipeline automatically and strictly enforces:
```json
"production_eligible": false,
"commercial_training_allowed": false
```
Under no circumstances may unverified public datasets (from Kaggle, Roboflow, Hugging Face, or GitHub) bypass the Quarantine Layer.

## Source Types
- **`OWNED_REAL`**: Real-world field captures or physical test rig footage directly owned by JointInspect or authorized under signed customer MSAs.
- **`SYNTHETIC`**: Procedural pipe-joint 3D renders generated with exact mathematical ground-truth geometry.
- **`PUBLIC_LICENSED`**: External datasets with audited commercial licenses (e.g. Apache 2.0, CC-BY 4.0 with no Non-Commercial riders).
- **`PARTNER_DATA`**: Data from licensed utility partners with verified data use agreements.
- **`BENCHMARK_ONLY`**: Datasets restricted to non-commercial academic comparison (e.g. Sewer-ML). Forbidden from production training.
