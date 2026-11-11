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
silently rerun completed input.

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
--evidence <accounting-source> --approval <authorization-reference> --output <directory>`
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

Read-only GCS inspection found no pre-existing financial ledger at the fixed
URI (404). No opening balance or budget replenishment has been created. Runtime
activation/build awaits the confirmed historical used/reserved USD upper bound
requested from the owner. The existing worker still uses its earlier scope until
an accounting-backed deployment is performed; this report does not claim that
worker has already adopted the persistent policy.
