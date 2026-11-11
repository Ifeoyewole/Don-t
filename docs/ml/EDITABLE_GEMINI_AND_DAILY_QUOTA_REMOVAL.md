# Editable Gemini suggestions and daily quota removal

## Causes and changes

The upload page skipped context suggestions whenever Unified AI was selected and
incorrectly labelled that state offline. The calibration-check request used a
route omitted from the frontend gateway allowlist. Neither issue was a failure
of the OpenCV measurement algorithms.

The existing upload workflow now automatically selects the available unified
preview. Each uploaded photo requests image-specific Gemini context, provisional
joint orientation and reference guidance through the private IAM worker. Both
context and reference guidance remain editable. An asynchronous Gemini response
cannot overwrite inspector edits. Reference guidance is also included in the
untrusted inspection context passed to the unified pipeline. Suggestions use
Vertex directly without loading the three vision checkpoints.

Calibration lookup uses a fixed, authenticated private-worker route. Missing or
unregistered references return a successful CALIBRATION_REQUIRED response rather
than claiming that the verification service is unavailable. Unsaved metadata no
longer receives a fabricated UNVERIFIED reference identifier.

Gemini can suggest a reference target and explain perspective/occlusion limits.
It cannot invent a pipe diameter, camera identity, registered calibration,
physical gap or verified scale. Millimetres remain the default; unsupported mm
values remain null. The OpenCV geometry and calibration authority are unchanged.

## Limits

The five-inspections/day and ten-Gemini-analyses/day checks are removed entirely,
not raised or replaced with another daily quota. Financial-ledger schema2 has no
period limits, period duration or usage counters. The migration preserves every
prior reservation, opening balance, approval and financial ceiling. Historical
period fields inside old financial claims remain audit history only.

The previously authorized cumulative USD100 research allowance remains enforced
atomically across workers. Owner-confirmed prior consumption is USD5; subsequent
reservations and the existing infrastructure reserve are retained. A reservation
is a conservative authorization hold, not a measured GCP charge. Existing
same-origin checks, per-minute abuse protection, upload limits, private-worker
IAM, signed caches and no-automatic-retry handling remain.

## Verification

- 404 backend tests and 51 frontend tests passed before final documentation.
- TypeScript/production build and ESLint passed.
- Browser HTTP integration uses a recorded real frame-10 unified result plus an
  explicitly labelled offline advisory fixture. It verifies automatic preview,
  editable guidance surviving late AI, authenticated calibration lookup,
  persistence and JSON/PDF/evidence-ZIP export on desktop/mobile. It does not
  represent a new live model execution or an accuracy benchmark.
- Spending regression tests execute seven inspections and twelve Gemini claims
  in one period while within the financial allowance. Migration, exhaustion,
  idempotency and concurrent accounting tests remain enforced.

Live deployment and genuine Vertex verification are recorded separately after
release. No model weights, thresholds or geometry algorithms change here.
