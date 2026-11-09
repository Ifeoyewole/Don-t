# Unified Vision next development and evaluation protocol

## Current programme status

| Work | Status |
|---|---|
| 1,034-record technical audit | COMPLETED |
| Evaluation protocol and 3/14/80 review packages | COMPLETED (preparation only) |
| Pilot3 / pilot14 / research80 / eligible-dataset inference | BLOCKED_REVIEW |
| Live authenticated Gemini receipt integration for research | BLOCKED_INFRASTRUCTURE |
| GPU and Gemini spending scopes | BLOCKED_BUDGET (not approved) |
| Commercial release eligibility | BLOCKED_RIGHTS |

## Evaluation protocol

1. Preserve original splits as metadata. Freeze no evaluation IDs until real source-video lineage is established. Ninety-eight conservative filename/similarity groups are grouping constraints, not verified videos; 964 records occur in groups crossing the publisher's original splits. Never randomly split related frames.
2. Obtain task/label adjudication blind to model predictions, with reviewer identity and rationale; independently review locked held-out labels. Maintain separate exploratory, tuning and locked evaluation sets, with no training on evaluation data. There are currently zero independently verified positives for displacement, lateral, open joint and active infiltration.
3. Use reviewed masks for IoU/Dice; the 64 discovered polygons are source annotations awaiting review. Require temporal/field evidence for active infiltration. Ordinary 'Joint', dark stains, empty annotation files, SAM2 masks and Gemini observations do not establish defect truth.
4. Keep research inference, evaluation ground truth, training authorization, commercial rights and production validation as separate flags. Publish no F1/recall/precision/accuracy until actual adjudicated examples and independent grouping justify them.
5. Until then, report only denominated operational outcomes: completion, mask availability/quality distributions, routing correctness, semantic outcomes, abstentions and failure categories. A model quality score is not segmentation accuracy.

## Gemini and unified architecture

Exact configured model: `gemini-3.1-pro-preview`, location `global`. Existing tests cover HMAC, wrong-image binding, missing/tampered/stale receipts, model mismatch, task-aware nonjoint acceptance and strict joint gating. Maximum receipt age is 30 days; reuse only authentic same-image receipts.

Runtime metadata shows receipt export disabled, no export token or HMAC configuration present, and no objects at the documented receipt prefix. Do not read or expose secret values, fabricate receipts, enable production export or silently substitute a model. Prepare an isolated research signing/receipt arrangement and approve any Gemini scope separately. Model/receipt contracts passed; live four-model fusion has not executed in this cycle.

Joint tasks keep OpenCV geometry conditional; object/infiltration tasks never emit seam widths. Nonjoint PIPE_INTERIOR_NO_JOINT may support advisory research suitability without changing processing_allowed=false in the production gate. Physical mm and engineering PASS remain unavailable in research. Disagreements must be categorized as classification uncertainty, mask target mismatch, geometry uncertainty, semantic mismatch, insufficient evidence, annotation uncertainty or unsupported class, rather than averaged away.

## Exact resumable next action

1. Assign an inspection reviewer to `gs://joint-inspection-510310-data/models/inspect-view/research-results/unified-audit/20261109T164513Z-85af07dc/stage-review/pilot3_review.csv`. Confirm #10 geometry/ROI and #26/#34 object targeting and real video lineage. Do not replace family evidence with filename hints.
2. Review the PR containing audit tools, polygon regression coverage and the nonjoint receipt-count fix. Merge only with checks and required approval. The research image is unchanged; rebuild only after approving a worker change, then record its NEW digest.
3. Establish isolated research receipts/Secret Manager access without mutating production. Price one bounded pilot3 and any required Gemini calls, then obtain that specific approval. No submit command is executed by this handoff.
4. Run approved pilot3; inspect routing, masks, geometry abstention, semantic consistency, provenance and safety. Advance through reviewed pilot14, research80 and every eligible <=100-frame batch, each within its approved scope.
5. Preserve success-ledger entries and source/model/manifest hashes; do not resubmit completed identical work or retry Spot failures automatically. Save every frame error and classify it before advancement.

No reviewer is currently available, so the correct next external dependency is documented review—not another GPU run.

## Reproducibility and limits

Private audit artifacts: `gs://joint-inspection-510310-data/models/inspect-view/research-results/unified-audit/20261109T164513Z-85af07dc`. Original data and registry objects are unchanged. Model identities: Inspect View `repr-convnext-masked-r5-20261104` (SHA `659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7`); SAM2.1 Tiny (SHA `7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69`); OpenCV; Gemini `gemini-3.1-pro-preview`, configured location `global`.

Existing image: `europe-west2-docker.pkg.dev/joint-inspection-510310/joint-inspection-training/inspect-view-sam2-research@sha256:a3db9ffaa1d0704290ccee7c3dd9af81c9af860755be3a076187b9fe866db37c`; build `77fef1c6-b099-49e2-a9d3-840f3d936a52`. Seven baseline worker/receipt/model-loader source files match its build archive after Windows CRLF/BOM normalization and Python AST comparison. The new summary-count regression fix is not in that image and needs normal review before an approved rebuild. No rebuild was performed.

Tests: **274 backend tests passed**, including audit, task routing, signed receipts and the reporting regression. Compilation and diff checks passed. This proves software contracts, not current-container model accuracy or a new SAM2 runtime load. GPU jobs this cycle: **none**. Gemini calls this cycle: **none**. Exact cloud currency charges are unavailable; ordinary GCS operations/storage were used, not new paid compute jobs.

Production remains on `pipe-joint-api-00015-fej`; no APIs, gates, weights, IAM or runtime settings changed. Inspect View weights and these datasets remain research-scoped. No commercial release or production PASS is authorized.

Artifact upload verified: **81 create-only objects**, 13,899,846 bytes including the upload manifest. `upload_manifest.json` SHA-256: `9138fa9f03880dff6340d18f45ac265580ba81ef93754f65452f903d4f153a33`.
