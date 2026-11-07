# Inspect View engineering preview v1 — active research card

Status: DEPLOYED FOR ENGINEERING RESEARCH; NO FUSION ACCEPTED.

Purpose: engineering performance evaluation and collection of reviewed failure
cases. Inspect View r5 is primary on the normal measurement endpoint; WRc
artefacts are preserved. **Commercial production permission was reported by
the project owner on 2026-11-07 following a rights-holder go-ahead.** The
provider's server is unavailable and the agreement record is being recovered;
its coverage of the exact Sewer-ML-derived r5 checkpoint is not independently
verified here. See `INSPECT_VIEW_COMMERCIAL_PERMISSION_STATUS.md`.
The remaining research label relates to **model accuracy and release gates**,
not a claim that the owners refused commercial use.

## Candidate decision

Preserve both ConvNeXt r4 and r5. On 679 identical development images with explicit annotation masks, r4 scored macro-F1/F2 0.471758/0.534945 and r5 0.473169/0.526865. Tuning-only class selection produced 0.474929/0.519951, failing the declared fusion gate. R5 is selected for the deployed engineering-preview classifier. No better
multi-model fusion has yet passed the locked evaluation gate; this technical
status is independent of the reported commercial-use permission. Engineer comparison should show both identities, never claim an improved fusion.

R5 artifact: `gs://joint-inspection-510310-data/models/inspect-view/research-candidates/repr-convnext-masked-r5-20261104/best.pt`.
R4 checksum: `37bd3a4ea4fa64aa269391c4606cbddc442e5f3fac6dfe6d414655f1c9efd053`.
R5 verified SHA-256: `659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7`. Local load and inference smoke passed. CPU latency median 108.36 ms over 18 repeated-image runs; peak process RSS 611,152 KiB. This is not deployed latency or model-only memory.

The preview gate is connected to the normal `/api/v1/cv/measure` endpoint and existing inspection UI. Runtime loading and synthetic fail-closed rejection have been verified. See the deployment record for current revisions.

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

## Active workflow and remaining validation

Use the normal inspection page and `/api/v1/cv/measure`. There is no separate preview page. Inspect View classifies condition; OpenCV estimates geometry only with sufficient calibrated evidence; Gemini on Vertex validates visual suitability. Gemini 3.1 Pro Preview is configured globally with a 45-second timeout. Stronger provider tier does not establish better JointInspect accuracy without evaluation.

Cloud Run revision `pipe-joint-api-00013-wel` passed model-loading and synthetic unrelated-image rejection checks. Previous revision `pipe-joint-api-00011-kod` remains available for rollback. The normal public gateway still requires final rollout verification. Field-image engineering review, locked-test evaluation and full video-family independence remain outstanding.

The historical isolated `/engineering-preview` implementation is retained for compatibility; it is not the main user workflow. See `ENGINEER_BRIEFING.md` for copyable guidance and institutional dataset-request links.
