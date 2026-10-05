# JointInspect™ — Comprehensive Production AI/CV Benchmark Report

**Date:** 2026-10-05  
**Artifacts Generated:**
- [final_benchmark_dashboard.png](file:///c:/Users/akint/Documents/Coding/Don-t/docs/ml/benchmark/final_benchmark_dashboard.png)
- [final_benchmark_gallery.png](file:///c:/Users/akint/Documents/Coding/Don-t/docs/ml/benchmark/final_benchmark_gallery.png)
- [context_comparison.png](file:///c:/Users/akint/Documents/Coding/Don-t/docs/ml/benchmark/context_comparison.png)
- [latency_report.png](file:///c:/Users/akint/Documents/Coding/Don-t/docs/ml/benchmark/latency_report.png)
- [stress_test_report.png](file:///c:/Users/akint/Documents/Coding/Don-t/docs/ml/benchmark/stress_test_report.png)
- [benchmark_results.json](file:///c:/Users/akint/Documents/Coding/Don-t/docs/ml/benchmark/benchmark_results.json)

---

## 1. Asset Deduplication & Hash Audit

The benchmark scanned all available test images across `public/` and `scratch/`:
- **Total Input Files Scanned:** 18
- **Cryptographically Unique Images (SHA-256):** 10
- **Identical / Perceptual Duplicates Detected:** 8
- **Duplicate Detection Method:** Exact SHA-256 matching and 64-bit difference hash (dHash).

### Duplicate Inventory:
- `WhatsApp Image 2026-10-01 at 15.05.04.jpeg` == `test 6.jpeg`
- `WhatsApp Image 2026-10-01 at 15.05.05 (1).jpeg` == `test 4.jpeg`
- `WhatsApp Image 2026-10-01 at 15.05.05 (2).jpeg` == `test 2.jpeg`
- `WhatsApp Image 2026-10-01 at 15.05.05 (3).jpeg` == `test 3.jpeg`
- `WhatsApp Image 2026-10-01 at 15.05.05 (4).jpeg` == `test 5.jpeg`
- `WhatsApp Image 2026-10-01 at 15.05.05.jpeg` == `test 1.jpeg`
- `WhatsApp Image 2026-10-01 at 15.05.06 (1).jpeg` == `test 7.jpeg`
- `WhatsApp Image 2026-10-01 at 15.05.06.jpeg` == `test 8.jpeg`

---

## 2. Invariant Compliance & Safety Metrics

| Safety Invariant | Expected Value | Audited Value | Compliance Status |
| :--- | :--- | :--- | :--- |
| **Uncalibrated Physical mm Emitted** | 0 | **0** | **100.0% PASS** |
| **Unrelated Physical Measurements** | 0 | **0** | **100.0% PASS** |
| **Prompt-Induced Physical Changes** | 0 | **0** | **100.0% PASS** |
| **Zero-Guessing Radial Profiler Infill** | 0 | **0** | **100.0% PASS** |
| **Adversarial Millimeter Override Rate** | 0% | **0.0% (0/108)** | **100.0% PASS** |
| **Stress Test Burst Success Rate** | 100% | **100.0% (25/25)** | **100.0% PASS** |

---

## 3. Optical CV vs Multi-Model Agreement

1. **Deterministic Optical CV:**
   - Evaluated using sub-pixel gradient ray tracing across 72 radial vectors.
   - Outliers excluded via Median Absolute Deviation (MAD > 3.0) without infilling.
2. **WRc InceptionResNetV2 Baseline Classifier:**
   - SHA-256 weight integrity verified: `42527d8c4d38e6113f079bcb007715a5476d39cd3cc327f4ba87269d3c7de253`.
   - Executed on every test image to provide independent sewer defect categorization.
3. **Vertex AI Multimodal Semantic Gate (Gemini 2.5 Flash):**
   - Verified via dedicated live cloud probe (`europe-west2`).
   - Domain determination: `PIPE_JOINT_INSPECTION`, Quality: `OK`, advisory semantic observation extracted successfully.

---

## 4. Latency Profiling

Across all sequential benchmark runs:
- **p50 Latency:** 1,837.6 ms
- **p90 Latency:** 4,864.9 ms
- **p95 Latency:** 7,288.8 ms
- **p99 Latency:** 9,162.3 ms
- **Min Latency:** 292.4 ms
- **Max Latency:** 9,240.4 ms
