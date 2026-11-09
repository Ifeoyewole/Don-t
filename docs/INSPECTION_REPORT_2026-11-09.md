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
