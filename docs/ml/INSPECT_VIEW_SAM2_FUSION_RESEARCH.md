# Inspect View r5 + SAM 2.1 Tiny + JointInspect OpenCV (opt-in research)

**Status: CODE INTEGRATION BUILT; LIVE FUSION NOT DEPLOYED.**

Inspect View is retained as a model in the intended production architecture,
not replaced by SAM. The JointInspect owner reported commercial-production
permission from the Inspect View rights holders on 2026-11-07. The agreement
record is being recovered and its exact rights/ancestor scope awaits external
verification; see
[`INSPECT_VIEW_COMMERCIAL_PERMISSION_STATUS.md`](INSPECT_VIEW_COMMERCIAL_PERMISSION_STATUS.md).

## Roles and outputs

| Stage | Input | Output | Cannot assert |
|---|---|---|---|
| Inspect View r5 | Exactly the source image bytes | Research class probabilities and supported/unsupported status | Open-joint gap, tolerance PASS, or verification of unvalidated classes |
| Meta SAM 2.1 Hiera Tiny | Same image + inspector-supplied pixel bounding box | Promptable image mask + confidence + original-image SHA | Defect category or measured concrete-edge separation |
| Original OpenCV | Verified same-image mask bounding region | Optional seam width profile or projected ring geometry **in pixels** | Physical mm, 3D axial gap or condition acceptance |
| Fusion adapter | All above and matching image provenance | Versioned research evidence and REVIEW reasons | Safety-certifiable or legally cleared production release |

The fusion combines **outputs**, not model weights, datasets or gradients.
Inspect View's historical deployed role is acknowledged; adding SAM 2.1 does
not inherit a blanket licence over SAM datasets or third-party images.

## Files

- `backend/app/core/cv/ai/research_sam2_adapter.py` validates a local,
  exact-SHA256 checkpoint, calls publisher's SAM 2.1 Tiny package only when
  opted in, tests masks and scores and records the source image digest.
- `backend/app/core/cv/ai/research_inspect_view_sam2_fusion.py` preserves
  Inspect View probabilities and status, checks SAM mask-to-image SHA and
  mask-to-bounding-box integrity, then passes the proposal to experimental
  seam/ellipse OpenCV. Unsupported labels never acquire false confidence.
- `scripts/benchmark_inspect_view_sam2_fusion.py` runs one local image,
  optionally loading the existing Inspect View r5 checkpoint or consuming
  an image-SHA-matched preview JSON. Outputs research JSON and SAM outline
  overlay; **never uploads images or secrets**.
- `backend/tests/test_research_sam2_adapter.py` and
  `backend/tests/test_research_inspect_view_sam2_fusion.py` use fully
  synthetic fake masks and labels. Neither downloads a model.

## Windows local run

From repository root:

```powershell
python -m pytest backend/tests/test_research_sam2_adapter.py backend/tests/test_research_inspect_view_sam2_fusion.py -q
```

Before running real SAM weights:

1. Review publisher's pinned [SAM 2 repository](https://github.com/facebookresearch/sam2)
   and official Apache 2.0 license, third-party notices and dependency
   licences. The official README states that source and official checkpoints
   are under Apache 2.0; this document does not replace legal review.
2. Use a separately isolated local Python environment with a compatible
   publisher SAM 2 installation, Torch and CPU/GPU support. Do **not** add
   SAM to the existing production Cloud Run Docker image yet.
3. Obtain `sam2.1_hiera_tiny.pt` **only from Meta's official checkpoint
   location**, verify its SHA-256 independently and keep the file out of Git.
4. Supply an operator-selected bounding box from the **original image**;
   do not trust image dimensions guessed by Gemini.
5. To include Inspect View on the same photograph, provide
   `JOINTINSPECT_PREVIEW_MODEL_PATH` to the existing local r5 file (verified
   by its own SHA) and select `--inspect-view-local`. Alternatively provide
   a saved engineering-preview JSON with `image_sha256` matching the exact
   source image byte stream.

```powershell
# From repository root; examples for the original concrete vertical opening.
# Replace the sample path, checkpoint path and hash with actual reviewed files.
$env:JOINTINSPECT_PREVIEW_MODEL_PATH = 'C:/models/inspect-view-r5/best.pt'
python -m scripts.benchmark_inspect_view_sam2_fusion `
  --image samples/pipe01.jpg --geometry VERTICAL_SEAM `
  --roi 180 20 630 1060 `
  --sam-checkpoint C:/models/sam2/sam2.1_hiera_tiny.pt `
  --sam-sha256 <YOUR_VERIFIED_SHA256> `
  --inspect-view-local `
  --report inspect-sam2-review.json --overlay inspect-sam2-review.jpg
```

If the SAM package or checkpoint is unavailable, the adapter explicitly
returns MODEL_UNAVAILABLE / REVIEW_REQUIRED. Missing Inspect View does not
silently fabricate class probabilities. CPU-only SAM may be too slow for a
cloud API; test latency and memory before considering an inference worker.

## Why this is not yet live production inference

- Current Inspect View r5 did not pass a final independent held-out locked
  test for all requested defect classes, including OPEN_JOINT,
  INFILTRATION and PROTRUDING_LATERAL. SAM is a region proposal model, not
  an automatic fix for those classification heads.
- Masks from different image bytes are rejected; masks whose claimed
  bounding box disagrees with their pixels are rejected.
- No px-to-mm conversion is added; real camera/scene calibration still needs
  server-owned, verified physical scale.
- Before integrating in Cloud Run, review model/checkpoint rights, obtain
  offline field segmentation labels, quantify latency, create a guarded
  feature flag, compare standalone/fused per-class macro F1/F2 on the same
  video-family holdout and keep unsupported classes in review.
- Production-deployment rights as **reported by owner** and technical
  production reliability are separate. This documentation does not
  alter the model's accuracy thresholds or permit engineering PASS by AI.
