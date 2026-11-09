# Isolated Gemini research receipt preparation

This change adds an isolated research adapter, not a production endpoint or
an enabled cloud service. No real Vertex/Gemini request is performed by tests
or a CLI. Production authentication, settings and semantic permissions stay intact.

The adapter uses the existing VertexSemanticGate plus existing receipt signer
and verifier. It pins gemini-3.1-pro-preview/global, the trusted issuer,
source-image SHA-256 and 30-day expiry. Reuse verifies signatures and rejects
wrong model, issuer, image, expiry or tampering. The cache key binds the original
image, exact semantic implementation hash and model/location; a changed or
arbitrary prompt hash cannot silently create a different paid request scope.
A local research client copies settings and sets retries=0 without mutating the
production settings singleton. It refuses models/locations that differ.

When live use is explicitly authorized, the scope must declare reviewed image
hashes, review and spending approval IDs, exact model/location/semantic contract,
currency cap, request cap and expiry. A create-only GCS claim is acquired before
the provider call. Repeated or failed/uncertain claimed requests are not retried
or automatically charged again. Authentic unexpired receipts are reused without
a second call. Stale/invalid receipts fail closed; manual diagnosis is required.
The declared currency cap still needs operator pricing and monitoring: it is
not a provider-side monetary kill switch. This module has no automatic runner.

## Required operator actions — not applied

1. Approve an isolated research signer identity. Grant only the required Vertex
   invoke and private research GCS permissions; do not reuse or edit production auth.
2. Create `projects/567370443508/secrets/jointinspect-research-semantic-hmac` and
   a strong secret version through approved Secret Manager tooling. Creating,
   storing and accessing versions can incur charges; no version or IAM binding
   is created in this work cycle. Never paste the value into chat or Git.
3. Pin a NUMERIC secret version. Grant secretAccessor on that single secret
   only to the isolated signer and the existing research trainer/receipt verifier.
   No public principals or project-wide secret grants. Existing production
   receipt keys are neither read nor modified. The live secret reader refuses
   other secret names, projects or floating `latest` versions.
4. Configure a private project-bucket prefix under
   `models/inspect-view/research-results/` for claims and receipts. The storage
   adapter uses generation=0 writes and generation-pinned reads.
5. Obtain a review and Gemini spending scope for the exact three images before
   calling the adapter. GPU spending and Gemini spending are separate permissions.

Current production receipt export remains disabled. Secret, IAM, review and
budget configuration are BLOCKED_INFRASTRUCTURE / BLOCKED_REVIEW / BLOCKED_BUDGET.
Offline tests use conspicuously synthetic keys, images and approval fixtures;
none are uploaded as real evidence. PIPE_INTERIOR_NO_JOINT can remain advisory
for object tasks without turning the production processing_allowed=false into
true. No millimetres or engineering PASS is created by this adapter.
