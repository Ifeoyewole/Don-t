# WRc InceptionResNetV2 Baseline Integration

**Model Identifier**: `wrc-inceptionresnetv2-baseline-v1`  
**Classification Role**: `ADVISORY_BASELINE`  
**Measurement & Engineering Authority**: `NONE`  
**Provenance Status**: `EXTERNAL_PRETRAINED` / `PENDING_REVIEW`  

---

## 1. Executive Summary & Architecture

The pretrained WRc sewer defect classifier developed by Alex George (`alexgeorge13/WRc-Dataset-Classification`) has been verified and integrated into JointInspect as an external advisory visual baseline.

The JointInspect architecture strictly isolates advisory classification systems from deterministic physical gap geometry:

```
Image Input
  │
  ▼
Domain Gate / Semantic Filter (Vertex AI)
  │
  ├─► UNRELATED / NO-PIPE ──► Gated Reject (Zero Guessing)
  │
  ▼
Model A Joint Localization (`seg-smoke-v1`, experimental)
  │
  ▼
OpenCV Deterministic Geometry Engine
  │  (Sub-pixel edge detection, ellipse fitting, ray sampling)
  │
  ├─► Physical Gap (mm)  [AUTHORITATIVE DIMENSIONAL MEASUREMENT]
  │
  ▼
Visual Classification Advisory Layer (Parallel)
  ┌─────────────────────────────────────────────────────────┐
  │ A. WRc InceptionResNetV2 External Sewer Baseline (ONNX) │
  │    Model ID: wrc-inceptionresnetv2-baseline-v1         │
  │    Advisory: Real sewer dataset defect classification   │
  │                                                         │
  │ B. JointInspect Model B Native Candidate                │
  │    Model ID: cls-smoke-v1                               │
  │    Advisory: Experimental synthetic smoke model         │
  └─────────────────────────────────────────────────────────┘
  │
  ▼
Tolerance-Primary Decision Authority
  │  (Calibrated gap mm > max_tolerance -> OPEN_JOINT / FAIL)
  │  Visual classifiers CANNOT override physical tolerance breach
  │
  ▼
Engineering RAG System (Advisory Standard Clauses)
  │
  ▼
Vertex AI Explainer & Context Synthesis
  │
  ▼
Inspector UI / Telemetry Gating
```

---

## 2. Weight Provenance & Verification

| Property | Verified Value | Status |
| :--- | :--- | :--- |
| **Source Repository** | `https://github.com/alexgeorge13/WRc-Dataset-Classification` | PASS |
| **Source Commit** | `7ac0b0f9edf430d43e5f180466e2e456d98fdfe7` | PASS |
| **Original Weight Path** | `trainedWRc_inceptionresnetv2_focalLoss/weights.h5` | PASS |
| **Weight File Size** | `231,566,563 bytes` | PASS (Non-LFS Pointer) |
| **Weight SHA256** | `42527D8C4D38E6113F079BCB007715A5476D39CD3CC327F4BA87269D3C7DE253` | PASS (Matches LFS meta) |
| **Exported ONNX Path** | `gs://joint-inspection-510310-data/models/external/wrc/inceptionresnetv2/v1/wrc_inceptionresnetv2_baseline_v1.onnx` | PASS |
| **ONNX File Size** | `219,476,235 bytes` | PASS |
| **Max Parity Delta** | `3.576e-07` | PASS (< 1e-4) |
| **Top-1 Parity** | `Deposit` (`tf_score=0.6203`, `onnx_score=0.6203`) | PASS |

---

## 3. Strict Non-Authority Governance Rules

1. **Zero Measurement Authority**: The WRc model is a closed-set image classifier. It outputs categorical defect probabilities, never spatial dimensions. It has 0% authority over millimeter clearances.
2. **Tolerance-Primary Authority**: If the OpenCV deterministic geometry engine measures a joint gap exceeding allowable tolerance (e.g. 6.2 mm vs 3.0 mm allowable), the authoritative status is strictly `OPEN_JOINT / FAIL`. No classifier prediction can soften or override this failure.
3. **No Automatic NORMAL Defaulting**: If the model weights are unavailable, corrupt, or uninitialized, the system strictly reports `EXTERNAL_CLASSIFIER_UNAVAILABLE` with `confidence=0.0`. It never assumes `NORMAL_JOINT`.
4. **Separation from Model B**: JointInspect's native experimental model (`cls-smoke-v1`) remains isolated under its own identity. It is not replaced by the WRc model.
5. **Domain Gate Precedence**: Images without inspectable pipe geometry are rejected before visual classification to prevent closed-set hallucination.

---

## 4. Multi-System Disagreement Tracking

During beta testing, JointInspect records multi-system agreement telemetry across:
- **WRc Baseline Prediction** (`Deposit`, `Displaced Joint`, `Crack`, etc.)
- **JointInspect Model B Prediction** (`normal_joint`, `displaced_joint`, `open_joint`, `damaged_joint`, `intruding_seal`)
- **Vertex AI Semantic Observation**

When high-confidence visual models disagree (e.g., WRc confidence $\ge 0.70$ vs Native confidence $\ge 0.60$), the inspection is flagged with `human_review_required = true`. These flagged telemetry samples form the foundation for training JointInspect's next-generation native visual classifier.
