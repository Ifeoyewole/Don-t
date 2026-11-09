# Pilot3 execution report — NOT EXECUTED

Status: BLOCKED_REVIEW, BLOCKED_BUDGET and BLOCKED_INFRASTRUCTURE.
No Vertex job ID, inference mask, model overlay, runtime result or charge exists
for this stage. Do not confuse the generated provisional-ROI review images
with SAM2 output. They are explicitly labelled NOT APPROVED / NOT MODEL OUTPUT.

All three original byte hashes, 416x416 dimensions and GCS paths were rechecked.
Frame 10 proposal [96,125,401,404] spans a partial curved joint boundary and a
caption; a straight seam or complete circular opening has NOT been approved.
Frames 26 [164,51,410,415] and 34 [42,109,375,248] cover visible object candidates;
object segmentation is plausible, but lateral identity and mask target approval
are unresolved. Family IDs PI005455, PI005286 and PI008113 remain filename hints,
not original-video evidence. Research quarantine and unverified labels remain.

The offline job builder requires a manifest-bound review, expiring GPU spending
scope and immutable image. It fixes one n1-standard-4/Spot T4 worker, three frames,
7200-second timeout, disableRetries=true and restartJobOnWorkerRestart=false.
It makes no submission call. Operator orchestration must also check actual active
jobs and hold the single-worker lease; a local argument alone cannot prevent
cross-process scheduling races. A runtime limit is not a hard monetary cap.

The worker preparation adds create-only verified candidate mask PNGs, per-frame
CPU/GPU memory diagnostics and sanitized failure files, alongside existing reports,
overlays, frames.jsonl and summary.json. Missing/unaccepted masks are omitted,
not fabricated. Masks are candidate pixels, not verified defects. No physical mm
or engineering PASS is introduced. GPU memory counters report actual process
state, not estimated accuracy or inference latency.

The supplied a3db9f...37c image exists and its baseline source was verified in
PR #32. It does not contain the new mask/diagnostic code or the pending summary
fix. Rebuild with the existing Cloud Build config ONLY after reviewed source is
merged and a build spending scope is approved; pin the new digest before GPU
execution. No Docker build or paid job was launched here.

Next: obtain actual per-image review including frame 10 geometry and original
lineage, configure isolated authenticated Gemini receipts, approve build and
pilot3 scopes, generate a valid manifest and inspect all prerequisites. Then
run ONE bounded job, save all artifacts and inspect masks/tasks/abstentions
before advancing to separately reviewed and budgeted pilot14. No precision,
recall, F1 or IoU can be reported from the current unexecuted pilot.
