# Commercial Data Source Registry Specification

## 1. Registry Architecture

The registry located at `training/data_sources/source_registry.json` serves as the authoritative inventory for every dataset ingested, staged, or benchmarked within JointInspect.

Schema: `training/data_sources/source_registry.schema.json`

### Allowed Source Types:
- `OWNED_REAL`: Footage captured on company-owned rigs or internal inspections.
- `PARTNER_DATA`: CCTV footage provided under signed commercial partner contracts.
- `PUBLIC_LICENSED`: External datasets under permissive commercial licenses (CC-BY 4.0, Apache 2.0, MIT) with verified primary provenance.
- `SYNTHETIC`: Procedurally generated scenes with known exact ground-truth geometry.
- `BENCHMARK_ONLY`: Datasets reserved strictly for post-training benchmark evaluation (e.g., Sewer-ML). Never ingested into training loops.

### Allowed Approval Statuses:
- `APPROVED_PRODUCTION`: Cleared by legal/engineering for commercial training & weights.
- `APPROVED_BENCHMARK_ONLY`: Cleared exclusively for evaluation of frozen models.
- `PENDING_REVIEW`: Under review. Quarantined.
- `REJECTED`: Rejected due to non-commercial clauses, copyleft, or suspicious provenance.
- `UNKNOWN_RIGHTS`: Unidentified or unverified license terms.

---

## 2. Invariant Enforcement

```python
if source.approval_status == "UNKNOWN_RIGHTS":
    source.production_eligible = False
    source.commercial_training_allowed = False

if source.benchmark_only or source.source_type == "BENCHMARK_ONLY":
    source.production_eligible = False
    source.commercial_training_allowed = False
```

Any attempt to import or promote assets linked to a source that violates these invariants will immediately fail closed and abort promotion.

---

## 3. Active Registry Entries

| Source ID | Name | Source Type | License | Approval Status | Production Eligible |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `SRC-SYN-001` | JointInspect Procedural Synthetic v1 | `SYNTHETIC` | Proprietary (In-House) | `APPROVED_PRODUCTION` | **YES** |
| `SRC-OWN-001` | JointInspect Physical Pipe Test Rig | `OWNED_REAL` | Proprietary (In-House) | `APPROVED_PRODUCTION` | **YES** |
| `SRC-FLD-001` | JointInspect Field CCTV Captures | `OWNED_REAL` | Proprietary (In-House) | `PENDING_REVIEW` | Pending Verification |
| `SRC-SWR-001` | Sewer-ML Benchmark Evaluation Dataset | `BENCHMARK_ONLY` | Sewer-ML Research License | `PENDING_REVIEW` | **NO (Benchmark Only)** |
| `SRC-QUARANTINE-DEFAULT` | Unverified External Ingestion Buffer | `PUBLIC_LICENSED` | Unknown | `UNKNOWN_RIGHTS` | **NO (Fail-Closed)** |
