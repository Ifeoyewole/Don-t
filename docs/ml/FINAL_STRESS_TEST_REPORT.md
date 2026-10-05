# JointInspect™ — Final Concurrency & Latency Stress Test Report

**Benchmark Label:** PIPELINE / INTEGRITY / STRESS BENCHMARK  
**Generated At:** 2026-10-05T18:17:21Z

---

## 1. Concurrency Stress Test Architecture

To prevent HTTP 429 quota exhaustion on Vertex AI, the stress test is architected with strict separation:
- **Offline / Local Stress Test:** Runs OpenCV DSP, Model A, Model B, WRc, and deterministic mock semantic gate.
- **Workers:** 8 concurrent worker threads.
- **Total Requests:** 50.

---

## 2. Quantitative Results

- **Successful Requests (HTTP 200):** 50 / 50 (100.0%)
- **Failed Requests:** 0
- **Latency p50:** 6485.9 ms
- **Latency p95:** 34931.9 ms
- **Latency p99:** 35016.3 ms
- **Latency Min / Max:** 1811.0 ms / 35054.2 ms

---

## 3. Live Vertex Latency Profile (Measured Separately)

- **Probes Run:** 10 sequential controlled calls
- **Live Vertex p50:** 8987.4 ms
- **Live Vertex p95:** 16806.0 ms
- **Live Vertex Min / Max:** 6997.4 ms / 21588.6 ms
- **Fail-Closed Behavior:** PASS
