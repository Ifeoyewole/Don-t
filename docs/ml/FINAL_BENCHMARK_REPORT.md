# JointInspect™ — Comprehensive Pipeline, Integrity & Safety Benchmark Report

**Benchmark Label:** PIPELINE / INTEGRITY / STRESS BENCHMARK  
**Generated At:** 2026-10-05T18:17:21Z  
**Data Provenance:** Raw metrics generated from `docs/ml/benchmark/benchmark_results.json` without hardcoding.

---

## 1. Executive Summary

| Metric | Raw JSON Value | Target / Requirement | Verification |
| :--- | :--- | :--- | :--- |
| **Total Test Images** | 18 | Full repository assets | Checked |
| **Cryptographically Unique (SHA-256)** | 10 | Deduped | Checked |
| **Duplicate Images Detected** | 8 | Deduped | Checked |
| **Uncalibrated Authoritative mm** | 0 | **0** | **PASS** |
| **Rejected Geometry with Auth mm** | 0 | **0** | **PASS** |
| **Prompt-Induced Physical Changes** | 0 | **0** | **PASS** |
| **Zero-Guessing Fallback Violations** | 0 | **0** | **PASS** |
| **Offline Stress Success Rate** | 100.0% (50/50) | 100% | **PASS** |
| **Offline Stress p50 / p95 Latency** | 6485.9ms / 34931.9ms | Responsive | **PASS** |
| **Live Vertex Controlled Calls** | 10 calls | 8–12 controlled sequential calls | **PASS** |
| **Live Vertex Correct Domain Responses** | 9/9 | Accurate domain classification | **PASS** |
| **Live Vertex Prompt Conflicts Detected** | 4 | Structured conflict tracking | **PASS** |
| **Live Vertex Fail-Closed Enforcement** | PASS | Fail-closed | **PASS** |

---

## 2. Actual Measured Subsystem Latency Breakdown

Timings measured directly from instrumented execution (no estimated profile):
- **Image Decode:** 28.85 ms
- **Image Quality Check (OpenCV):** 110.32 ms
- **Joint Segmentation (Model A seg-smoke-v1):** 20.68 ms
- **Sub-pixel Geometry Engine (OpenCV):** 440.02 ms
- **Joint Classification (Model B cls-smoke-v1):** 22.04 ms
- **External Baseline Classifier (WRc InceptionResNetV2):** 3711.65 ms
- **Confidence Fusion & Authority Gate:** 0.1 ms
- **Local Total Pipeline:** 4333.66 ms
- **Live Vertex Cloud Latency (p50):** 8987.4 ms

---

## 3. Calibrated Gating Decisions (Full Dataset)

- **Accepted Measurement:** 0
- **Review Required:** 0
- **Rejected / Unreliable:** 18

---

## 4. Multi-Model Availability Truthfulness

| System | Model Identity | Status | Production Role |
| :--- | :--- | :--- | :--- |
| **Vertex AI** | Gemini 2.5 Flash | LIVE (Controlled Acceptance Pack) | Multimodal Semantic Gatekeeper & Context Engine |
| **Model A** | `seg-smoke-v1` | AVAILABLE | Experimental Candidate (Not production approved) |
| **Native Model B** | `cls-smoke-v1` | AVAILABLE | Experimental Candidate (Not production approved) |
| **WRc Baseline** | `wrc-inceptionresnetv2-baseline-v1` | AVAILABLE (SHA-256 Verified) | External Pretrained Advisory Baseline |
| **OpenCV Engine** | Deterministic Radial / Seam | ACTIVE | Authoritative Geometric Measurement |
