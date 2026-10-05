# Commercial Dataset Attributions & Legal Notices

This document details all third-party and licensed datasets approved for use within the JointInspect production ecosystem, along with their associated copyright notices, license texts, and required attributions.

> **Legal Policy**: Inclusion in this attribution document does not automatically imply commercial training eligibility. Every dataset listed must have an active `APPROVED_PRODUCTION` status in `training/data_sources/source_registry.json`.

---

## 1. Proprietary Datasets

### JointInspect Procedural Synthetic v1 (`SRC-SYN-001`)
- **Provider**: JointInspect Engineering
- **License**: Proprietary / JointInspect Internal
- **Attribution**: Copyright © 2025–2026 JointInspect. All rights reserved.
- **Modifications**: Created procedurally via JointInspect synthetic geometry generator.

### JointInspect Physical Pipe Test Rig Captures (`SRC-OWN-001`)
- **Provider**: JointInspect Hardware & Metrology Team
- **License**: Proprietary / JointInspect Internal
- **Attribution**: Copyright © 2025–2026 JointInspect. All rights reserved.
- **Modifications**: Raw capture with optical calibration and physical vernier / feeler gauge ground-truth measurement.

---

## 2. External Benchmark Datasets (Non-Production)

### Sewer-ML Benchmark (`SRC-SWR-001`)
- **Provider**: Department of Architecture, Design and Media Technology, Aalborg University
- **Status**: `BENCHMARK_PERMISSION_PENDING`
- **Commercial Training Allowed**: **NO**
- **Production Eligible**: **NO**
- **Benchmark Only**: **YES** (Pending permission)
- **Notice**: Sewer-ML is evaluated exclusively as a frozen external benchmark if permission is granted. No Sewer-ML images, weights, labels, or embeddings are utilized in production models or runtime RAG systems.
