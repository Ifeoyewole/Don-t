# Full eligible-dataset inference

Status: **BLOCKED_REVIEW**. Full technical audit completed for 1,034 records. Approved current task-aware GPU inference count: **0**, so no executable batches were created or run. There are 1,034 readable unique classification candidates, not 1,034 approved segmentation/evaluation examples.

Actual source polygons exist for 43 images but have unverified defect identity and targeting. All images lacking justified task, reviewed ROI or verified lineage remain inventory-only and in the review queue. No automatic proposal/classification-only mode was added to the existing runner, and no full-frame/guessed ROI was fabricated.

## Execution and cost gates

After approved 3/14/80 stages, calculate the actual eligible subset, exclude confirmed duplicates, keep family/similarity groups together, and create deterministic manifests of at most 100 images. Use the create-only run ledger and immutable manifest/model hashes to skip completed work. One GPU at a time, Spot T4 on n1-standard-4, <=7,200 seconds/job, no automatic retries. A timeout is not an exact currency cap.

No defensible full-dataset runtime or cost range is available yet: the staged pilots have not run, and the old one-image job does not measure their warm-up, resolution mix, receipt handling or failure distribution. Before requesting spending approval, combine measured startup + per-task processing distributions + upload time with then-current Spot GPU, VM, disk, storage and Gemini prices and a declared contingency. Present the estimate and receive a numeric cap before submission. No promotional-credit coverage or zero cost is assumed. Regional T4 and preemptible T4 quota each showed limit 1, usage 0; this does not guarantee Vertex capacity or authorize spend.

No operational inference rates or detection accuracy were calculated. `disagreement_analysis.json` records the categories for future results and leaves observed cross-model counts null. The technical audit is complete; the research programme and commercial validation are not.

Next action: appoint a reviewer, resolve receipts and review the PR, then unlock pilot3; do not bypass directly to full inference.

## Reproducibility and limits

Private audit artifacts: `gs://joint-inspection-510310-data/models/inspect-view/research-results/unified-audit/20261109T164513Z-85af07dc`. Original data and registry objects are unchanged. Model identities: Inspect View `repr-convnext-masked-r5-20261104` (SHA `659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7`); SAM2.1 Tiny (SHA `7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69`); OpenCV; Gemini `gemini-3.1-pro-preview`, configured location `global`.

Existing image: `europe-west2-docker.pkg.dev/joint-inspection-510310/joint-inspection-training/inspect-view-sam2-research@sha256:a3db9ffaa1d0704290ccee7c3dd9af81c9af860755be3a076187b9fe866db37c`; build `77fef1c6-b099-49e2-a9d3-840f3d936a52`. Seven baseline worker/receipt/model-loader source files match its build archive after Windows CRLF/BOM normalization and Python AST comparison. The new summary-count regression fix is not in that image and needs normal review before an approved rebuild. No rebuild was performed.

Tests: **274 backend tests passed**, including audit, task routing, signed receipts and the reporting regression. Compilation and diff checks passed. This proves software contracts, not current-container model accuracy or a new SAM2 runtime load. GPU jobs this cycle: **none**. Gemini calls this cycle: **none**. Exact cloud currency charges are unavailable; ordinary GCS operations/storage were used, not new paid compute jobs.

Production remains on `pipe-joint-api-00015-fej`; no APIs, gates, weights, IAM or runtime settings changed. Inspect View weights and these datasets remain research-scoped. No commercial release or production PASS is authorized.

Artifact upload verified: **81 create-only objects**, 13,899,846 bytes including the upload manifest. `upload_manifest.json` SHA-256: `9138fa9f03880dff6340d18f45ac265580ba81ef93754f65452f903d4f153a33`.

CPU readiness supplement: both pinned checkpoints were independently SHA-256 verified and instantiated on CPU (r5: 15 heads, 27,831,663 parameters; SAM2.1 Tiny: 38,962,498 parameters). No forward pass or dataset-image inference ran. Temporary weight copies were removed. Evidence: `gs://joint-inspection-510310-data/models/inspect-view/research-results/unified-audit/20261109T164513Z-85af07dc/supplements/cpu-model-load.json` (SHA-256 `6ed3237bb7b3929f8dbf6cbc3d1df667daa9598d84e167b9b426d470e81997b8`). This is one additional object beyond the 81-object core audit snapshot and does not establish GPU-stage success.
