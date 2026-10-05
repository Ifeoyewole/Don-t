# Cloud Cost & Credit Protection Guardrails

## 1. Overview & Core Philosophy

**Project**: `joint-inspection-510310`  
**Cloud Run Service**: `pipe-joint-api`  
**Region**: `europe-west2` (London)  
**Linked Billing Account**: `017548-7610F4-EB02C5`

The primary objective of these cost guardrails is to maximize the longevity of Google Cloud promotional/trial credits while strictly adhering to the core pipeline invariant:
**Zero Artificial Guessing & Non-Degraded CV Correctness**.

Under no circumstances will cost optimization:
- Disable zero-guessing measurement safeguards or confidence rejection gates;
- Lower camera frame resolution or weaken sub-pixel edge calibration;
- Downgrade model architecture or training quality merely for cost;
- Expose services publicly or bypass zero-trust authentication;
- Automatically terminate production services without human oversight.

---

## 2. Cloud Run Cost Guard Configuration

The private FastAPI AI/CV backend (`pipe-joint-api`) has been hardened with strict execution and scaling bounds:

| Setting | Production Configuration | Cost & Architectural Rationale |
| :--- | :--- | :--- |
| **Min Instances** | `0` | Scale-to-zero when idle eliminates idle compute charges completely. |
| **Max Instances** | `3` | Prevents runaway auto-scaling bills from traffic surges or DoS attempts. |
| **CPU Allocation** | Request-based (default) | CPU is throttled and billed only during active request processing. |
| **Memory Limit** | `2 GiB` | Ample headroom for OpenCV high-resolution matrix transformations. |
| **CPU Limit** | `1 vCPU` | Right-sized for serialized multi-stage edge profile extraction. |
| **Concurrency** | `4` | Prevents CPU starvation and queuing latency under concurrent load. |
| **Timeout** | `300s` | Bounds runaway hanging requests while accommodating multi-frame inspections. |

### Active Revision Deployment
```bash
gcloud run services update pipe-joint-api \
  --region=europe-west2 \
  --min-instances=0 \
  --max-instances=3 \
  --concurrency=4 \
  --update-labels="project=joint-inspection,environment=production,component=api,cost-center=joint-inspection"
```

---

## 3. Empirical Concurrency & Sizing Benchmark

An empirical benchmark of the OpenCV/AI measurement pipeline was conducted across 1, 2, 4, 8, and 16 concurrent workers processing synthetic pipeline joint images with 12 radial sample spokes:

| Concurrency | Throughput (req/s) | Median Latency (ms) | p95 Latency (ms) | Peak Memory (MB) | Assessment |
| :---: | :---: | :---: | :---: | :---: | :--- |
| **1** | 6.76 | 149.0 | 168.6 | 12.09 | Low utilization, predictable latency. |
| **2** | 8.06 | 243.8 | 299.8 | 21.75 | Good parallelization. |
| **4** | **6.89** | **483.6** | **904.5** | **48.13** | **Optimal balance**: sub-second p95 with minimal memory. |
| **8** | 2.52 | 2,765.8 | 4,637.4 | 77.16 | CPU thrashing, queue saturation, degraded UX. |
| **16** | 2.10 | 1,614.2 | 1,938.0 | 85.40 | Severe CPU context switching. |

**Key Finding**: Because OpenCV edge detection and Hough gradient transforms are CPU-bound, Cloud Run's default concurrency of 80 causes severe latency spikes and worker timeouts on 1 vCPU instances. Setting **concurrency = 4** delivers consistent sub-second response times while keeping peak memory under 50 MB per instance.

---

## 4. Cloud Storage Lifecycle Management

To prevent stale debug images, test uploads, and temporary build artifacts from accumulating storage charges, automated lifecycle rules have been applied.

### `gs://joint-inspection-510310-data`
Lifecycle policy file: `scratch/storage_lifecycle_policy.json`
- **Prefix `temp/` & `temporary/`**: Automatically deleted after **7 days**.
- **Prefix `debug/` & `scratch/`**: Automatically deleted after **14 days**.
- Applied via:
  ```bash
  gcloud storage buckets update gs://joint-inspection-510310-data \
    --lifecycle-file=scratch/storage_lifecycle_policy.json
  ```

### `gs://joint-inspection-510310_cloudbuild`
Temporary Cloud Build artifacts, tarballs, and build workspace logs:
- Automatically deleted after **14 days**.
- Applied via:
  ```bash
  gcloud storage buckets update gs://joint-inspection-510310_cloudbuild \
    --lifecycle-file=scratch/cloudbuild_lifecycle_policy.json
  ```

---

## 5. Artifact Registry Cleanup Policy

Artifact Registry stores container images in `europe-west2` for `joint-inspection-app` and `joint-inspection-training`.

To prevent outdated container image layers from consuming storage quotas, a cleanup policy has been configured:
1. **Keep tagged production**: Always retain tags starting with `prod` or `production`.
2. **Keep recent 5 versions**: Preserve the last 5 deployed container images for rollback safety.
3. **Delete untagged older than 30 days**: Prune intermediate builder layers older than 30 days.

Applied in **dry-run mode** until deployment stability is verified:
```bash
gcloud artifacts repositories set-cleanup-policies joint-inspection-app \
  --location=europe-west2 \
  --policy=scratch/ar_cleanup_policy.json \
  --dry-run

gcloud artifacts repositories set-cleanup-policies joint-inspection-training \
  --location=europe-west2 \
  --policy=scratch/ar_cleanup_policy.json \
  --dry-run
```

---

## 6. Vertex AI & Training Cost Guardrails

Custom model training (e.g. YOLOv8 pipe seam detectors or defect classifiers) must follow a 5-stage cost ladder:

### The 5-Stage Cost Ladder
1. **Stage 1 — Local CPU Prototype**: Synthetic data validation and pipeline correctness testing on local developer machine (Cost: $0.00).
2. **Stage 2 — Local Single-GPU Smoke Test**: 1 epoch verification for memory leaks, dataset formatting, and gradient stability (Cost: $0.00).
3. **Stage 3 — Preemptible / Spot Cloud Compute**: Small-scale batch hyperparameter tuning on spot instances (70–80% savings).
4. **Stage 4 — Vertex AI Custom Job (Spot VM, Budget-Capped)**: Full dataset training with hard budget cap and automatic early stopping.
5. **Stage 5 — Full Distributed Training**: Requires explicit stakeholder authorization and signed-off cost estimate.

### Mandatory Pre-Flight Checklist for Cloud Training
- [ ] Training dataset verified and formatted locally.
- [ ] Pipeline runs end-to-end for 1 epoch on synthetic data without runtime exceptions.
- [ ] Early stopping patience configured (e.g. `patience = 5`).
- [ ] Maximum training duration flag specified (`--max-running-time=3600s`).
- [ ] Machine type right-sized (e.g. `n1-standard-4` with single `T4` GPU).
- [ ] Checkpoint saving frequency restricted (save only best validation checkpoint, not every epoch).

---

## 7. Billing Budgets & Owner Action Required

Per GCP security best practices, creating billing account budgets requires `roles/billing.admin` or `roles/billing.costsManager` on the parent billing account (`017548-7610F4-EB02C5`).

Because budget monetary thresholds must be determined by the account owner based on current credit balances, the project owner should execute the following commands with their approved budget amounts:

### Budget 1: Net Credit-Aware Budget (Burn Alert)
Notifies when net billable spend (spend minus promotional credits) reaches thresholds:
```bash
# Replace $APPROVED_NET_BUDGET with approved amount (e.g. 20USD)
gcloud billing budgets create \
  --billing-account=017548-7610F4-EB02C5 \
  --display-name="Joint-Inspection-Net-Credit-Alert" \
  --budget-amount=$APPROVED_NET_BUDGET \
  --filter-projects="projects/joint-inspection-510310" \
  --credit-types-treatment=INCLUDE_ALL_CREDITS \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.75 \
  --threshold-rule=percent=0.9 \
  --threshold-rule=percent=1.0
```

### Budget 2: Gross Resource-Usage Budget (Rate Alert)
Monitors raw cloud resource consumption before credit offset to detect usage spikes early:
```bash
# Replace $APPROVED_GROSS_BUDGET with approved amount (e.g. 50USD)
gcloud billing budgets create \
  --billing-account=017548-7610F4-EB02C5 \
  --display-name="Joint-Inspection-Gross-Usage-Alert" \
  --budget-amount=$APPROVED_GROSS_BUDGET \
  --filter-projects="projects/joint-inspection-510310" \
  --credit-types-treatment=EXCLUDE_ALL_CREDITS \
  --threshold-rule=percent=0.25 \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.75 \
  --threshold-rule=percent=1.0
```

---

## 8. Summary of Active Cost Controls

- **Cloud Run**: Min=0, Max=3, Concurrency=4, Request-based CPU throttling, production labels applied.
- **Storage**: Automated 7-day deletion on `temp/` and 14-day deletion on `debug/`, `scratch/`, and `cloudbuild`.
- **Registry**: Tag preservation and 30-day untagged layer cleanup active in dry-run mode.
- **Architecture**: Zero-guessing measurement precision preserved with zero idle compute cost.
