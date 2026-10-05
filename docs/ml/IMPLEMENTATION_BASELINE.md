# JointInspect ML Implementation Baseline & Registry

**Checkpoint**: WRc InceptionResNetV2 Integration & Beta Deployment  
**Status**: `BETA_READY`  

---

## 1. Visual Model Roster

| Model Designation | Model Identifier | Architecture | Source / Weights Origin | Role / Responsibility | Authority Level | Production Approved |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Model A** | `seg-smoke-v1` | Lightweight UNet | JointInspect Synthetic Pipeline | Joint Localization & ROI Cropping | Auxiliary / Fallback to Domain Gate | `false` (Experimental) |
| **Model B (Native)** | `cls-smoke-v1` | CNN Classifier | JointInspect Synthetic Pipeline | Native Experimental Defect Classifier | Advisory Candidate | `false` (Experimental) |
| **External Baseline** | `wrc-inceptionresnetv2-baseline-v1` | InceptionResNetV2 | `alexgeorge13/WRc-Dataset-Classification` (Real WRc Data) | Advisory Sewer Defect Classifier Baseline | Strictly Advisory Baseline | `false` (Beta Evaluation) |
| **Domain Gate** | Vertex AI Gemini 1.5 | Multimodal LLM | Google Cloud Vertex AI | Pipe Interior Validation & Semantic Context | Domain Gatekeeper | `true` (Active Gating) |
| **Geometry Authority**| OpenCV Sub-Pixel Engine | Deterministic Ellipse/Ray Fit | Calibrated C++ Math Kernels | Authoritative Physical Gap Measurement | **Authoritative (100%)** | `true` (Authoritative) |

---

## 2. Invariant Safety Rules

1. **Dimensional Authority**: Neither Model B nor the external WRc baseline may produce, modify, or override physical gap millimeter measurements.
2. **Tolerance-Primary Authority**: If the measured gap from OpenCV exceeds the design specification (e.g. gap > allowable max), the final QA status is `OPEN_JOINT / FAIL`. Visual models cannot soften this assessment.
3. **Zero Guessing Fallback**: If an image lacks pipe geometry, camera calibration, or clear lighting, JointInspect returns `REJECTED_UNRELIABLE` or `REVIEW_REQUIRED`. The system never guesses `NORMAL_JOINT`.
4. **Disagreement Telemetry**: Disagreements between WRc and Native Model B are logged for future training and human review.
