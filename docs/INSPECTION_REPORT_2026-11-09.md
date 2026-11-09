# Full-width inspection report and millimetre workflow

Started from Ifeoyewole/Don-t main `af2152f` after pulling 127 newer commits.
The existing per-photo diameter/camera selection, manhole-specific references
and server-owned authority checks are retained.

The results page uses a single full-width report column, wraps long references
and explanations, and stacks evidence details on narrow screens. Expand report
fills the viewport; the button or Escape exits. Model guidance is collapsed so
the inspection evidence stays prominent. Millimetres are the default display;
pixels remain available as technical evidence. Unit selection does not change
saved measurements or engineering status.

The close-up seam detector no longer derives scale from 65% of the image width.
A registered measured reference must match the exact uploaded image bytes and
rectified resolution; see CALIBRATION_AUTHORITY.md. Circular views retain the
verified-diameter path. No production calibration evidence was invented or
registered by this change, so uncalibrated images still withhold mm.

Verification: desktop/mobile browser checks at 390, 768, 1024 and 1440 pixels,
inside the actual app shell, found no report overflow or clipped body content.
Verified mm display, uncalibrated handling, full-width cards, expansion and
Escape were exercised with synthetic local fixtures. Focused backend suites
passed 65 tests; focused frontend suites passed 30 tests. Additional build/CI
and live rollout results are recorded below when completed.

Required local checks completed: all 261 backend tests and all 39 frontend tests
passed; lint, production build and API TypeScript checks passed. Existing Vite
OpenCV externalization and bundle-size warnings remain. Backend image build
`c42602c6-51f9-479f-b39f-31291e831474` is in progress. Previous live backend
revision `pipe-joint-api-00013-wel` remains active until tagged smoke checks pass.

## Live rollout

Implementation commit `b7ade31ed6b865345ec86802b1c86489e347aad6` was pushed directly
to Ifeoyewole/Don-t main; no PR was opened. Its Git-triggered Vercel production
deployment `dpl_DVC9BDMh7Rkqnrnbx2roQtsUQyin` is READY on the existing aliases.
Live normal-report browser checks with synthetic records kept entirely in the
test browser passed at 390, 1024 and 1440px: no overflow/clipping or page errors,
mm selected, verified fixture displayed in mm, expansion and Escape working.
These are layout tests, not evidence of field measurement accuracy.

Cloud Build `c42602c6-51f9-479f-b39f-31291e831474` succeeded with image digest
`sha256:b92c647b6a17a250bf3259b744e84da8d6b42743fb59299e7403295ee0f739ba`.
Cloud Run revision `pipe-joint-api-00015-fej` now serves 100% traffic;
`pipe-joint-api-00013-wel` remains the rollback revision. Runtime health confirmed
Inspect View r5 loaded and Gemini 3.1 Pro Preview/global configured. Tagged and
normal public gateway synthetic-image tests rejected a generated non-pipe image
with no authoritative mm and engineering REVIEW. A made-up calibration reference
was correctly rejected by the new read-only registry endpoint.

Next action: obtain genuine camera/reference calibration evidence for the
engineers' pipe sizes, register the validated records through protected
configuration, then explicitly remeasure field photos. No production reference
or millimetre value was fabricated. Old saved reports remain unchanged.
