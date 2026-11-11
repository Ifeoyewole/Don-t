# Persistent Unified AI engineering preview

The lifecycle is `ENGINEERING_PREVIEW`, mode `PREVIEW`, with an explicit pause
switch. It has no calendar expiry, user login, automatic promotion or daily
financial top-up. Existing Cloud Run IAM authenticates the website service,
not the engineer. The normal commercial model path remains separate.

## Quotas and cumulative authorization

A single private GCS ledger, fixed across scope revisions and deployments, uses
object-generation compare-and-swap. It is never created/reset automatically.
Each accepted operation atomically reserves both its UTC daily quota and funds
before model/provider work. Defaults: five inspections and ten Gemini analyses
per day. Two analysis passes maximum per inspection remain unchanged.

The independent USD ledger has a fixed100USD research-cycle ceiling. Its opening
balance must include an operator-confirmed conservative upper bound of ALL prior
used/reserved funds, plus a separately encumbered infrastructure allowance
(default5USD for build/deployment/overhead). Unknown opening accounting blocks
paid work. Per-inspection reservations default1USD; Gemini analyses default2USD.
Reservations are conservative authorization encumbrances, not claimed invoices.
They are not automatically refunded after failures, cache hits, new dates or
new deployments. Budget exhaustion blocks new computation even after a daily
quota recovers. A manual pause also stops new paid work.

The ledger's currency, cycle,100USD ceiling, claims and reconstructed period
counts are validated on every reservation. Generation-CAS retries are bounded;
contention or storage errors fail closed. A new scope prefix/URI cannot redirect
or replace the financial ledger. Same executable contract + image + meaningful
options use stable response identity; changing an approval identifier does not
silently rerun completed input. The cache identity also binds the immutable image digest and server calibration-registry hash; deliberate executable or calibration changes invalidate stale results without resetting the financial ledger.

## Provider cost envelope

Official pricing retrieved from
https://cloud.google.com/vertex-ai/generative-ai/pricing lists Gemini3.1Pro
Preview global <=200K input tokens at2USD/M input and12USD/M output, including
reasoning. The configured conservative envelope is8USD/M input and64USD/M
output, comfortably above those observed prices. The existing8192-token output
bound remains unchanged. After a financial reservation, authenticated
`countTokens` checks the exact multimodal input; generation is rejected above
100000 input tokens. Required conservative reservation is1.324288USD; default
2USD exceeds it. No automatic provider retries are introduced.

The official token-count guide
https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/get-token-count
states no charge for CountTokens. There is at most one count request before
one generation attempt per reserved analysis. Missing/invalid count fails closed.
Pricing evidence is stored in the opening ledger. A provider price change beyond
the conservative envelope requires an explicit accounting review, not a hidden
calendar cutoff or a silent authorization increase.

This is an independently enforced application spending ALLOWANCE. It is not a
Google billing-account kill switch. Unrelated pre-existing project activity,
provider repricing, standing storage and invoices still need billing oversight.
The fixed infrastructure encumbrance does not assert those charges were measured.
Do not describe a usage estimate as an actual remaining billing balance.

## Initialization and deployment

`python -m scripts.cloud.prepare_persistent_preview --prior-usd <confirmed-upper-bound>
--evidence <accounting-source> --approval <authorization-reference> --image-digest sha256:<built-digest> --output <directory>`
prepares files only. It cannot upload, initialize cloud resources or infer an
unknown historical balance. Ledger upload MUST use generation-match0; existing
ledgers must never be overwritten to renew funds. Policy JSON is SHA-pinned by
`JOINTINSPECT_PHASE1_SCOPE_URI` / `JOINTINSPECT_PHASE1_SCOPE_SHA256`.

Deploy the existing private `jointinspect-unified-preview` service with the new
immutable image and pinned policy. Preserve trainer identity, invoker binding,
CPU2/memory4Gi, concurrency1, min0/max1, request120s and no GPU. Remove the obsolete
Vercel expiry/window variables; use `UNIFIED_PREVIEW_MODE=PREVIEW` and the existing
enable switch/worker URL. Changing to PRODUCTION is rejected by this research
policy; promotion remains a separate deliberate company action.

## Geometry policy

No OpenCV or model implementation is replaced. Existing rough-edge profiles,
seam/ellipse analysis, SAM assistance, Gemini reconciliation, server calibration
and mm-default formatting remain. Geometry remains independent of successful
classification. Missing valid boundaries/calibration yields null physical mm.

No matched legacy/current real-image evaluation with independent reference gap
measurements was recovered in the preceding audit. Historical127–134px estimates
are not verified accuracy. Consequently no legacy restoration, merge or claimed
measurement improvement is part of this change; historical code remains archived.

## Tests and limitations

Tests cover CAS races, duplicate claims, worker restart, scope revision,
daily rollover without money renewal, exhausted/paused/missing/corrupt budgets,
no-login/future-date access, unchanged IAM/gateway checks and provider token
bounds. Offline browser replay uses saved real artifacts, not a paid benchmark.
Cloud verification must report actual deployment/health state and must not
claim a new real inference from a mock or cache. Prior verified real executions
are documented in UNIFIED_AI_AND_MEASUREMENT_FULL_REPORT.md.

Final deployment status and accounting evidence are recorded in the delivery
report; no unknown opening balance may be invented to activate spending.

## Verification recorded for this change

398 backend tests passed, including20 persistent quota/finance/IAM tests;
50 frontend/gateway tests passed, plus native emitted-Node import verification,
lint and production build. The local HTTPS browser test returned200 without a
login or calendar window, persisted a saved-real-artifact unified result, and
exported JSON/PDF/ZIP with no browser errors. It was an offline replay, not new
Gemini inference. No OpenCV implementation file changed.

The initial read-only GCS inspection found no pre-existing financial ledger
(404), so activation paused until the owner supplied the opening accounting
figure. The owner subsequently confirmed5USD already used. The following records
supersede that initial deployment blocker.

## Activated deployment — 11 November 2026

The opening ledger was created once with generation-match0, recording the
owner-confirmed5USD prior use and a separate5USD infrastructure encumbrance.
No prior ledger was overwritten or replenished. The ledger was initialized
before the bounded CPU image build; only the new immutable policy was uploaded
after its image digest became known.

- Source/PR45 merge: `f286d7195d255b47fb4df2fe3c1f6c4ae99b7dd1`.
- Cloud Build: `62834b6d-7243-4e14-b10a-3909c46034e8`, SUCCESS.
- Immutable image: `sha256:ed619547abc10664bd37147cb5a75a13fbbeb3ab5e8936b602dee52fe6598f34`.
- Private worker: `jointinspect-unified-preview-00003-m24`, READY.
- Policy SHA-256: `6e19fdad804a2420656bfd78d2580b1141807767102d1ce0655bf415e32142d1`.
- Policy object: `gs://joint-inspection-510310-data/models/inspect-view/research-results/engineering-preview-persistent/v1/policies/6e19fdad804a2420656bfd78d2580b1141807767102d1ce0655bf415e32142d1.json`.
- Website deployment: `dpl_FEWSfiRaRwAUFT1upieQL5ouoH1M`, READY, production configuration of the existing website with research mode PREVIEW.

The existing website at https://joint-inspection.vercel.app returns200 from
`/api/unified`, reporting `mode=PREVIEW` and `user_sign_in_required=false`.
The obsolete expiry/window values were cleared; no calendar cutoff exists in
the active gateway or persistent policy. Normal website health returns200.
Anonymous direct worker access returns403. Service IAM still contains only the
existing Vercel invoker binding; no public invoker or additional IAM grant was
introduced. Commercial model weights/configuration and the OpenCV algorithms
were not changed by activation.

### One controlled real verification

A fresh website submission of the existing permitted frame26 completed with:

- HTTP200 in118.659 seconds, one submission and no automatic retry.
- Inspect View and ISWDS available; two actual SAM masks.
- Authenticated Gemini interpretation, two bounded analysis passes and
  `functional_path_complete=true`.
- The new input-token preflight succeeded before generation.
- One persisted unified inspection record; zero user cookies/browser errors.
- Primary unit mm. Physical measurement null because calibration/joint evidence
  did not authorize a physical joint-gap measurement; no field accuracy claim.

The model/fusion portion took83.7575 seconds; the browser timing also includes
initialization/network overhead. This is a successful real cloud request, not
an offline replay or saved-result-only readback. No GPU, training, new model,
legacy restoration or repeated paid verification run was performed.

Ledger readback after verification passed integrity validation: one inspection
and two Gemini reservations, three claims total. Allocations are5USD prior use,
5USD infrastructure,1USD inspection and4USD Gemini reservations:15USD encumbered,
**85USD unreserved**. Daily quota remaining at that observation: four inspections
and eight Gemini analyses. These reservations are not actual provider charges;
actual billing-account invoices were not available. Financial authorization does
not refill at daily rollover.

Deployment evidence (private research storage):
`gs://joint-inspection-510310-data/models/inspect-view/research-results/engineering-preview-persistent/v1/deployments/62834b6d-7243-4e14-b10a-3909c46034e8/deployment-report.json`.
Local browser evidence:
`/workspace/scratch/persistent-preview-deploy/live-verification/verification.json`,
`after-inspection.png` and `overlay.png`.
