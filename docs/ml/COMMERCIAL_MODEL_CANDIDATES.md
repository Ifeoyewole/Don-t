# Commercial-first vision-model architecture and rights review

**Status: RESEARCH / APPROVAL PENDING. Not a legal opinion.**

Last verified against public upstream source license declarations: 2026-11-07.
This report does not grant rights to third-party dataset images, model weights,
logos, pretrained checkpoints, or code packaged by unrelated dependencies.
A patent/license/chain-of-title professional review may still be necessary.

## Critical finding: current Inspect View cannot simply become commercial

The existing `training/releases/inspect_view_engineering_preview_v1.json`
identifies a research ConvNeXt checkpoint, declares `production_approved=false`,
and notes Sewer-ML-derived weights. Sewer-ML is CC BY-NC-SA 4.0; under the
published license it is not an acceptable unlicensed input to a commercial
training/deployment release. Blending this checkpoint into a new Apache-licensed
model **does not clean its ancestry**.

The current WRc InceptionResNetV2 software repository lists MIT source code,
but `docs/ml/WRC_INCEPTION_BASELINE_AUDIT.md` explicitly records
`EXTERNAL_PRETRAINED / PENDING_COMMERCIAL_REVIEW` for its weights.
Do not promote those weights either until their rights are independently cleared.

## Candidate architectures — code only; no checkpoint copied

| Component | Reference | Code license | Purpose | Current disposition |
|---|---|---|---|---|
| Meta SAM 2.1 Hiera Tiny | https://github.com/facebookresearch/sam2 | Apache-2.0 **for both official code and checkpoints, explicitly stated by Meta** | Promptable segmentation of an inspector/Gemini ROI and tracking boundaries in adjacent video frames | **Preferred pretrained candidate; not yet downloaded/approved** |
| MMSegmentation with SegFormer-B0 | https://github.com/open-mmlab/mmsegmentation | Apache-2.0 source code | JointInspect-trained pixel-level opening and irregular concrete/material-boundary segmentation | Preferred defect-specific train-from-scratch experiment, **untrained** |
| YOLOX-S | https://github.com/Megvii-BaseDetection/YOLOX | Apache-2.0 | Bounding-box localization for lateral, crack, joint, root/deposit, etc. | Optional second detector, **untrained** |
| MMDetection | https://github.com/open-mmlab/mmdetection | Apache-2.0 | Additional instance segmentation / detector alternative | Optional code reference; no integration |
| ONNX Runtime | https://github.com/microsoft/onnxruntime | MIT | Exported runtime inferencing alongside existing FastAPI | Existing dependency, audit transitive packages |

Check the exact code commit, full LICENSE, NOTICE, patent/third-party files and
dependency graph when integrating. The upstream repository's main code license
does **not** automatically apply to downloadable pretrained model checkpoints,
ImageNet/COCO training images, fine-tuned sewer models or separate datasets.

### Strongest pretrained candidate — Meta SAM 2.1

The official `facebookresearch/sam2` README at a pinned Git revision
(`2b90b9f5ceec907a1c18123530e92e794ad901a4`) specifically grants
Apache 2.0 licensing for **SAM 2 model checkpoints, training code and demo**.
This is significantly more useful than a repository whose *code* alone is
Apache/MIT while weight ownership is unclear.

- Official checkpoint: https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt
- Official license: https://github.com/facebookresearch/sam2/blob/2b90b9f5ceec907a1c18123530e92e794ad901a4/LICENSE
- Third-party optional mask post-processing: BSD-3-Clause `LICENSE_cctorch`.
- Training/data origins and dependency inventory still need review; SA-V
  **dataset download permissions are separate** from the checkpoint license.
  Do not import video datasets or unknown third-party model weights by association.
- SAM 2 is a **promptable mask segmenter**, not a trained sewer defect
  classifier. A good visual mask is not a proof of OPEN_JOINT, INFILTRATION,
  PROTRUDING_LATERAL, or physical gap in mm.
- Computational requirement: Python + PyTorch, potentially CUDA GPU for
  practical latency. Test SAM 2.1 Tiny in a separate optional process; do not
  silently bloat the CPU-only Cloud Run measurement service.
- Phase 1: independent publisher/notice/weights SHA review; run local
  opt-in promptable segmentation on operator-drawn ROI. Compare mask boundary
  against inspector labels on actual pipe imagery. Keep commercial production
  disabled until tests, complete rights record and release gate say otherwise.

External commercial restrictions to avoid without suitable permissions:
- Sewer-ML CC BY-NC-SA 4.0: not commercially cleared.
  https://creativecommons.org/licenses/by-nc-sa/4.0/
- Ultralytics YOLO: AGPL-3.0 or Enterprise under the publisher's stated
  proprietary deployment policy; do not substitute it for independently
  Apache-licensed YOLOX.
  https://www.ultralytics.com/license
- Unknown/wrapper model weights downloaded from Hugging Face, Roboflow,
  Kaggle or GitHub: treat all as **PENDING** until primary dataset/weight
  provenance and downstream rights are verified.
- The source registry lists several CC BY 4.0 external sets, but also
  `provenance_verified=false`, `production_eligible=false`, and
  `approval_status=PENDING_REVIEW`; their license badge alone is insufficient.

## Recommended two-track architecture

```
RESEARCH (restricted; not for commercial output):
  Inspect View r5 [Sewer-ML lineage] -- advisory class comparison
  WRc pretrained baseline [rights pending] -- research comparison

CLEAN-COMMERCIAL MODEL TRACK (disabled pending review):
  Option A — publisher-licensed SAM 2.1 Tiny [Apache-2.0 official checkpoint]
       -> inspector/Gemini-proposed ROI -> promptable mask [research evaluation]
       -> original OpenCV traced boundaries
       -> not a trained defect label; separate approved classifier needed

  Option B — from-scratch, commercially screened custom defect model:
  Inspector/owned-rights images + accepted in-house synthetic targets
       -> independent source/label/license review
       -> train SegFormer-B0 from random initialization (NO pretrained weights)
       -> optional independent YOLOX-S detector trained from random init
       -> ONNX (permissive/runtime audit) -> existing JointSegmenter mask/bbox contract
       -> original OpenCV rough boundary/ellipse geometry
       -> only server-owned spatial calibration issues mm; otherwise REVIEW
       -> per-class confidence and human review
```

Research results may guide **design/evaluation questions**, but do not copy
noncommercial examples, distill from research checkpoints, use their outputs as
commercial pseudo-labels, share their model weights, or train the commercial
model on their derived feature embeddings.

## Data governance & human review

The registry currently asserts some synthetic and in-house/partner data has
commercial rights. That is a project assertion, **not independently verified
chain-of-title**: signed contracts, sample-level permissions, authenticity,
rights scope (training, commercial deployment, derivatives, outsourcing) and
privacy obligations need inspection. In particular, the narrative
`docs/ml/DATA_SOURCE_REGISTRY.md` differs from the JSON registry regarding
field-source approval, so the JSON claim must not be treated as final legal
confirmation.

Needed before training/promotion:
1. Archive exact upstream license commit and all applicable notices.
2. Record actual originating copyright owner and copyright chain of every
   image/annotation; track use restrictions and revocation where applicable.
3. Confirm source family splits and original inspector-reviewed label meanings
   across OPEN_JOINT / INFILTRATION / PROTRUDING_LATERAL, plus negative examples.
4. Prepare and independently verify an in-house model artifact's actual SHA256
   and full list of parent checkpoints, or explicitly state random
   initialization with no checkpoint lineage.
5. Run reproducible per-class/pipe/material evaluation and calibration; compare
   against the strongest permitted clean baseline. No model precision claims
   based only on synthetic examples or on Sewer-ML labels.
6. Obtain documentary commercial rights approval referencing external private
   evidence/ticket. Do not commit confidential contracts into the public repo.
7. Preserve license attribution/notice text when distributing covered code,
   and verify production image SBOM/transitive dependencies.

## Technical gates implemented in this research PR

- `training/ingestion/validate_license.py` no longer treats unknown licenses
  as commercial by default; recognizes common noncommercial abbreviations.
  Private/owned data needs an explicit internal rights record and approval
  metadata. This first-line screen does NOT authenticate the underlying
  contracts.
- `training/ingestion/model_release_gate.py` checks code license, pinned
  upstream revision, license notice reference, artifact SHA256 metadata,
  from-scratch ancestry, no research-checkpoint fusion, approved source
  registry entries and explicit independent approval metadata.
- `training/commercial_candidates/*.json` records **three disabled** proposals:
  publisher-licensed SAM 2.1 Tiny, independently trainable MMSeg/SegFormer-B0,
  and YOLOX-S. No weights are in this repository. Running the model release
  gate on any candidate must return nonzero and show its unresolved blockers.
  The current gate intentionally accepts ONLY from-scratch weights; a distinct
  official-publisher-checkpoint allowance must be reviewed before authorizing
  SAM 2.1, including pinned checksum, publisher grant and transitive licenses.

Run:

```powershell
python -m pytest backend/tests/test_commercial_model_provenance.py -q
python -m training.ingestion.model_release_gate --manifest training/commercial_candidates/mmseg_segformer_b0.json
# Expected: exit code 2, no clearance. It is currently untrained.
```

**These automated checks are not legal certification.** A policy pass means
specified metadata is present and internally consistent; it does not prove
third-party ownership or authentic signatures. Neither model is presently
approved, trained, exported, deployed, integrated into Inspect View, nor
permitted to override physical engineering decisions.
