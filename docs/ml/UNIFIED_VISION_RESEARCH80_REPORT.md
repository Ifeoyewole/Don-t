# Eighty-image targeted research evaluation

Status: **BLOCKED_REVIEW**. Prepared 80 candidate records; **0 approved, 0 executed**. Additional gates: stage spending approval and authenticated Gemini receipt infrastructure. No reviewer is available.

Source/URI/hash bindings were checked against the full audit. Candidate buckets (not verified positives): `{"HARD_NEGATIVE_OR_OTHER_CANDIDATE": 15, "INFILTRATION_CANDIDATE_UNVERIFIED": 1, "JOINT_DISPLACEMENT_CANDIDATE": 44, "PROTRUDING_LATERAL_CANDIDATE_UNVERIFIED": 20}`. Distinct filename family hints: 13; these are not independently verified videos. All records retain RESEARCH_QUARANTINE and UNVERIFIED_SOURCE_LABEL.

Private package: `gs://joint-inspection-510310-data/models/inspect-view/research-results/unified-audit/20261109T164513Z-85af07dc/stage-review/research80_review.csv`. `taskaware_research80_manifest.json` is explicitly a **REVIEW_PACKAGE_NOT_EXECUTABLE**, with `executable_manifest=null`. Passing its worklist to the existing converter was tested and correctly rejected: no READY_FOR_RESEARCH rows. It is not a valid GPU manifest and must not be submitted.

Required review: inspect each exact original image; confirm target/task and applicable joint geometry; record a real ROI or confirm a legitimate source annotation, source/video lineage, reviewer identity and permission evidence. Source annotations are not automatically approved. Then use the existing converter and validator to generate the executable manifest.

The existing 80 candidates are retained for traceability with a per-row selection-review log; no automatic substitutions were made from unreviewed similarity flags. The proposed category counts remain 44 displacement, 20 possible laterals, one possible infiltration and 15 hard-negative/other. The single Leak candidate is not active-infiltration ground truth.

Advance only after pilot14 safety/routing failures are resolved and this stage has review and spending approval. Reuse successful identical per-frame evidence where valid; do not recharge completed identical batches. Class metrics remain null without independent labels.

Results, overlays, stage GPU job ID and actual cost: unavailable because the stage did not execute. A future job is one bounded Spot T4, no automatic resubmission, at most one concurrent GPU, with unique output paths. No paid job or Gemini request may start before applicable review and spending authorization.

Next action: complete the review fields and receipt infrastructure, obtain the specific stage cost cap, and revalidate all prerequisites.

## Reproducibility and limits

Private audit artifacts: `gs://joint-inspection-510310-data/models/inspect-view/research-results/unified-audit/20261109T164513Z-85af07dc`. Original data and registry objects are unchanged. Model identities: Inspect View `repr-convnext-masked-r5-20261104` (SHA `659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7`); SAM2.1 Tiny (SHA `7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69`); OpenCV; Gemini `gemini-3.1-pro-preview`, configured location `global`.

Existing image: `europe-west2-docker.pkg.dev/joint-inspection-510310/joint-inspection-training/inspect-view-sam2-research@sha256:a3db9ffaa1d0704290ccee7c3dd9af81c9af860755be3a076187b9fe866db37c`; build `77fef1c6-b099-49e2-a9d3-840f3d936a52`. Seven baseline worker/receipt/model-loader source files match its build archive after Windows CRLF/BOM normalization and Python AST comparison. The new summary-count regression fix is not in that image and needs normal review before an approved rebuild. No rebuild was performed.

Tests: **274 backend tests passed**, including audit, task routing, signed receipts and the reporting regression. Compilation and diff checks passed. This proves software contracts, not current-container model accuracy or a new SAM2 runtime load. GPU jobs this cycle: **none**. Gemini calls this cycle: **none**. Exact cloud currency charges are unavailable; ordinary GCS operations/storage were used, not new paid compute jobs.

Production remains on `pipe-joint-api-00015-fej`; no APIs, gates, weights, IAM or runtime settings changed. Inspect View weights and these datasets remain research-scoped. No commercial release or production PASS is authorized.

Artifact upload verified: **81 create-only objects**, 13,899,846 bytes including the upload manifest. `upload_manifest.json` SHA-256: `9138fa9f03880dff6340d18f45ac265580ba81ef93754f65452f903d4f153a33`.
