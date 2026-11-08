# JointInspect Unified Vision v1 — research-only decision contract

Status: **implementation branch; not promoted to production**.

## Goal

Give the inspection application **one canonical research response** instead
of presenting independent, potentially contradictory Inspect View, SAM2, Gemini 3.1 Pro, and
OpenCV results as if they were equally authoritative diagnoses.

This milestone **does not merge neural weights** or replace the validated
separate models. The combined runner still loads Inspect View r5 (ConvNeXt),
SAM2.1 Tiny, and OpenCV; it now also emits a conservative `unified_result`.
Gemini 3.1 Pro already runs as the Vertex AI semantic gate in the normal
measurement endpoint. This research contract can reuse its same-image result
without making a second paid Gemini request.

## Unified result

`report.json` continues to contain the original per-model evidence for
audit and adds:

- `unified_result.decision`: always `REVIEW_REQUIRED` for this research version
- `unified_result.defect`: `UNDETERMINED`, not an invented diagnosis
- `unified_result.primary_advisory`: best threshold-gated, supported,
  exploratory defect suggestion, if any (NOT a final classification)
- `unified_result.advisory_candidates`: all exploratory supported suggestions
- `unified_result.segmentation`: SAM2 mask bbox and model-quality score if
  the existing same-frame fusion checks accepted the mask
- `unified_result.geometry`: OpenCV pixel candidate if supported; **never mm**
- `unified_result.gemini`: optionally reused semantic domain gate, quality,
  orientation suggestion, and whether processing was allowed
- `unified_result.reasons`: explicit blockers and conflicts
- `unified_result.image_sha256`: image byte digest for audit

Candidates require an Inspect View payload whose image SHA and model version
match the source and fusion report. A candidate must be `detected=true`
under Inspect View's *existing* per-class threshold and `EXPLORATORY` in
both the preview and fusion gates.

OPEN_JOINT, INFILTRATION and PROTRUDING_LATERAL remain unvalidated, even
if source data or a proposed mask appears suggestive. A promptable SAM mask
does not establish defect identity; a pixel width without camera calibration
does not establish physical separation.

## Four-source architecture, including Gemini 3.1 Pro

The intended unified research flow is: Gemini semantic scene/quality gate ->
Inspect View defect candidates -> SAM2 segmentation -> OpenCV geometry ->
one conservative research decision. It may execute components in parallel
only after the original image identity is locked.

The existing Cloud Run measurement API already uses
`backend/app/core/cv/ai/vertex_semantic_gate.py` with model
`gemini-3.1-pro-preview` in Vertex location `global`. It checks whether a
joint is actually visible, detects unrelated or low-quality images, and
isolates operator prompt instructions. This is advisory visual evidence;
Gemini cannot grant an engineering PASS, select an unverified calibration
or turn a SAM mask into a confirmed defect.

The research runner does **not** call Gemini again. An optional
server-created JSON receipt may contain the exact original image SHA-256
and the existing `VertexSemanticGateResult` serialized as `semantic_gate`:

```json
{
  "image_sha256": "<exact 64-hex original-image SHA-256>",
  "semantic_gate": {
    "model": "gemini-3.1-pro-preview",
    "domain_status": "PIPE_JOINT_INSPECTION",
    "pipe_visible": true, "joint_visible": true,
    "quality": "OK", "processing_allowed": true,
    "prompt_image_conflict": false,
    "suggested_joint_type": "VERTICAL_SEAM"
  }
}
```

Use a **trusted backend-generated receipt**, not untrusted operator text.
A matching SHA prevents accidental mixing of images but does not prove
who created the receipt. The existing backend gate remains authoritative
for blocking invalid measurements.

The local benchmark accepts `--gemini-receipt-json` for existing evidence.
The cloud research runner additionally accepts the optional pair
`--gemini-receipt-uri` and `--gemini-receipt-sha`, fetching the receipt
inside the ephemeral cloud worker and verifying file and original-image
hashes. Neither executes another Gemini request. Invalid or blocked
Gemini evidence suppresses research defect and pixel candidates; missing
Gemini evidence is explicitly `gemini.status=NOT_PROVIDED`.

A live four-source unified request still requires future integration into
the normal backend orchestration; this research PR makes no production
endpoint changes and does not imply Gemini ran in the previous GPU smoke.
## Tests

```powershell
python -m pytest backend/tests/test_unified_vision_v1.py backend/tests/test_research_inspect_view_sam2_fusion.py -q
```

No trained weights, CCTV source images, GPU or credentials are needed for
the contract tests.

## Promotion milestones

1. Build a reviewed, rights-checked and source-family-deduplicated sample of
   joint defects, true active infiltration and protruding laterals.
2. Compare the canonical v1 output against standalone r5 on a matching
   held-out source/video-family split; calibrate probabilities.
3. Verify mask target identity (not just model score), ROI accuracy and
   multi-frame geometry. Require explicit camera/pipe calibration for mm.
4. Test latency, GPU memory, missing-model/provenance failures, and human
   review. Keep production unchanged until evaluation gates are passed.
5. Consider a **separate** multitask/distillation training experiment for a
   genuinely single checkpoint. That cannot be produced by concatenating
   r5/SAM2 weights and requires segmentation ground truth.

## Current cloud status

The previously verified Spot Vertex smoke run demonstrated both checkpoints
loading and SAM2 yielding an advisory mask, but the target was hanging material,
not verified joint geometry. The new contract makes this failure mode explicit.
To run the new report generator on a GPU, build and deploy an **opt-in new
research image** from this branch; the already-built immutable container will
not contain these code changes.
