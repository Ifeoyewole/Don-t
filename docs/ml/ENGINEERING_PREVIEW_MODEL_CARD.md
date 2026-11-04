# Inspect View engineering preview v1 — preparation card

Status: OFFLINE COMPARISON COMPLETE; NOT DEPLOYED; NO FUSION ACCEPTED.

Purpose: internal research evaluation by engineers and collection of reviewed failure cases. Existing production WRc remains primary. Sewer-ML-derived weights remain research-scoped pending suitable commercial rights.

## Candidate decision

Preserve both ConvNeXt r4 and r5. On 679 identical development images with explicit annotation masks, r4 scored macro-F1/F2 0.471758/0.534945 and r5 0.473169/0.526865. Tuning-only class selection produced 0.474929/0.519951, failing the declared fusion gate. No final primary preview checkpoint is approved yet. Engineer comparison should show both identities, never claim an improved fusion.

R5 artifact: `gs://joint-inspection-510310-data/models/inspect-view/research-candidates/repr-convnext-masked-r5-20261104/best.pt`.
R4 checksum: `37bd3a4ea4fa64aa269391c4606cbddc442e5f3fac6dfe6d414655f1c9efd053`.
R5 verified SHA-256: `659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7`. Local load and inference smoke passed. CPU latency median 108.36 ms over 18 repeated-image runs; peak process RSS 611,152 KiB. This is not deployed latency or model-only memory.

An isolated preview gate is implemented and its three tests pass. It is not connected to a live endpoint; endpoint integration and end-to-end testing remain required.

## Current evidence

R5 normal recall 94.54% on 183 positives; joint-displacement recall 97.97% on 443; broken-pipe recall 84.17% on 120; surface-damage recall 85.59% on 236. These are exploratory development results, not final test performance. The final locked test was not evaluated. Original video IDs and full ancestor/near-duplicate independence remain incompletely established.

Unsupported: OPEN_JOINT and PROTRUDING_LATERAL. INFILTRATION is experimental and unreliable: both candidates missed all six development positives. Other output heads lacking observed targets in this evaluation are unvalidated here; inherited weights do not establish current accuracy.

## Infiltration visual review

Source IDs 00022216/17/18 show pipe-wall damage and dark/orange streaks under varying camera views. Source IDs 00023897/98/99 show highly similar connection-area views with reflective/wet-looking regions. These are six frames from two numeric families, not six independently verified physical events. Active ingress cannot be established confidently from the reviewed stills alone. Preserve original IN-positive annotations; request source video or specialist review. Do not relabel as normal on the basis of model failure.

## Engineer interface requirements

- Display checkpoint version, research-preview status and supported/unvalidated class states.
- Never interpret unsupported output or absent annotation as NORMAL or PASS.
- Distinguish defect classification from geometry/tolerance decisions.
- Return `joint_geometry_not_reliable` when calibration or geometry evidence is insufficient.
- Record source image SHA, prediction probabilities, thresholds, device/calibration IDs when provided, engineer correction and review status.
- Keep engineer corrections separate until reviewed; no automatic retraining from feedback.

## Before engineers use the live preview

Verify R5 artifact checksum, test model loading/preprocessing and CPU latency/memory, implement response gating and explicit model selection, and test the complete preview flow. Freeze the reviewed package with versioned manifests and a rollback pointer only after these checks. This card itself does not activate a model or change infrastructure.
