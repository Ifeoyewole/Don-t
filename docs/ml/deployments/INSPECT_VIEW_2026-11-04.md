# Inspect View normal inspection integration

User requested the research checkpoint in the existing inspection endpoint and normal web results, without a separate page.

Backend: existing `pipe-joint-api`, revision `pipe-joint-api-00011-kod`, activated at 100% traffic. Rollback revision `pipe-joint-api-00010-ptx` retained.
Image: `europe-west2-docker.pkg.dev/joint-inspection-510310/joint-inspection-training/preview-web@sha256:68ac9c9a63efde8e4c0dbec9f78ca5a7f7b75af85289b8704e442bd4a7968859`.
Checkpoint: r5 SHA-256 `659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7`.

Live tagged revision smoke: `/health` and `/api/v1/cv/health` returned 200. `/api/v1/cv/measure` returned 200 with real Inspect View evidence, research-review state, and calibration-required rejection withholding authoritative millimetres. Existing local endpoint regression suite: 16 passed. Web build and evidence-state tests passed.

Production Vercel deployment submitted: `dpl_4oNXNMUCxs3v2iJszrQ3AMwcotz4`; verify READY and the normal web gateway before claiming complete browser-to-backend validation. A preview deployment was built first; promotion returned 422, so an explicit production deployment was submitted with the same tested source.

Inspect View is active for research review, not scientifically approved as a commercial production model. Open-joint/protruding-lateral outputs are unvalidated; infiltration/obstacle are unreliable. Classification cannot authorize engineering PASS or substitute for calibrated geometry. Existing calibration/Vertex gates remain enforced. The legacy health payload still lists WRc diagnostics; it must not be interpreted as Inspect View readiness.
