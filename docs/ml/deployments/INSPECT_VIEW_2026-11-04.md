# Inspect View normal inspection integration

User requested the research checkpoint in the existing inspection endpoint and normal web results, without a separate page.

Backend: existing `pipe-joint-api`, revision `pipe-joint-api-00011-kod`, activated at 100% traffic. Rollback revision `pipe-joint-api-00010-ptx` retained.
Image: `europe-west2-docker.pkg.dev/joint-inspection-510310/joint-inspection-training/preview-web@sha256:68ac9c9a63efde8e4c0dbec9f78ca5a7f7b75af85289b8704e442bd4a7968859`.
Checkpoint: r5 SHA-256 `659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7`.

Live tagged revision smoke: `/health` and `/api/v1/cv/health` returned 200. `/api/v1/cv/measure` returned 200 with real Inspect View evidence, research-review state, and calibration-required rejection withholding authoritative millimetres. Existing local endpoint regression suite: 16 passed. Web build and evidence-state tests passed.

Production Vercel deployment submitted: `dpl_4oNXNMUCxs3v2iJszrQ3AMwcotz4`; verify READY and the normal web gateway before claiming complete browser-to-backend validation. A preview deployment was built first; promotion returned 422, so an explicit production deployment was submitted with the same tested source.

Inspect View is active for research review, not scientifically approved as a commercial production model. Open-joint/protruding-lateral outputs are unvalidated; infiltration/obstacle are unreliable. Classification cannot authorize engineering PASS or substitute for calibrated geometry. Existing calibration/Vertex gates remain enforced. The legacy health payload still lists WRc diagnostics; it must not be interpreted as Inspect View readiness.

Final rollout verification: Vercel production deployment `dpl_4oNXNMUCxs3v2iJszrQ3AMwcotz4` is READY with aliases `joint-inspection.vercel.app` and `joint-inspection-vikkys-projects-77a08647.vercel.app`. The normal public gateway health request succeeded. A generated synthetic ring image traversed the public measurement gateway and was correctly rejected by the existing scene validator as unrelated, with no authoritative millimetres. This verifies gateway routing and fail-closed rejection, not live positive model accuracy. Real dataset-image inference was verified directly against the GCP tagged normal endpoint; automatic approval review rejected uploading that dataset image through Vercel, so no dataset image was sent to that external destination. Browser automation and engineer field-image verification remain unperformed.

## UI and Gemini Pro update — 2026-11-04

Production UI deployment `dpl_5PEuKZU18X387PX6i9SpVTEsc98Z` is READY at the existing aliases. Existing blue/navy palette retained; normal dashboard/results now explain supported evidence, unvalidated classes, copyable briefing and institutional/private dataset requests. Desktop 1440px and mobile 390px browser checks found no horizontal overflow. Frontend build, API type check, 14 focused frontend tests and 16 backend architecture tests passed.

Cloud Build `5f2fd787-d6bc-47ba-94d8-9c1ec9650c53` succeeded; image digest `sha256:030b8f11122d3ec287c63cede661a72caeb4d04ec2321c22be638184fb02aa76`. Cloud Run `pipe-joint-api-00013-wel` now serves 100%; rollback revision `pipe-joint-api-00011-kod` is preserved. Gemini model is `gemini-3.1-pro-preview`, location `global`, timeout 45 seconds. It is a preview provider model, not a measured guarantee of improved JointInspect accuracy.

Tagged runtime health confirmed Inspect View r5 loaded and Gemini configuration active. A generated synthetic ring image traversed the normal public `/api/v1/cv/measure` endpoint and returned `UNRELATED_IMAGE`, `processing_allowed=false`, `semantic_gate.model=gemini-3.1-pro-preview`, withholding measurements. The public basic health response intentionally exposes only status; detailed model diagnostics require the existing engineer/admin diagnostic route. No dataset image was uploaded through Vercel in this cycle.

Remaining: engineer-reviewed field testing, independent locked-test evaluation, missing-class acquisition and rights clearance. Next action: collect field examples and partner dataset responses using ENGINEER_BRIEFING.md; do not retrain or accept fusion based on the displayed development recall alone.
