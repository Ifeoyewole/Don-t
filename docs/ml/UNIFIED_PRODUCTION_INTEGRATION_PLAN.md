# Unified Vision production integration — feature-flagged design only

No production flag, authentication, endpoint, deployment or model weight is
changed by this plan. Research outputs remain REVIEW_REQUIRED with no physical
millimetres or engineering PASS. Commercial model/data eligibility and independent
held-out evaluation remain release blockers.

Future disabled-by-default capabilities: semantic assessment -> explicit task
router -> (joint: classifier + segmenter + OpenCV; object: classifier + segmenter;
infiltration review: visual + temporal evidence) -> one canonical decision.
Keep component evidence and disagreement reasons in the audit record; do not
average incompatible confidence scores into a pretend final certainty.

Before enabling any production flag, require independently validated commercial
weights and datasets, authenticated per-image provenance, reviewed tasks/masks,
calibrated geometry, agreed acceptance criteria and explicit release approval.
Start in offline/shadow comparison with no engineering decision authority.
Unsupported scenes/classes abstain. A signed Gemini scene result is advisory,
a SAM2 mask is not a defect identity, and still imagery cannot confirm active
infiltration. Missing/invalid semantic receipts cannot reverse the existing gate.

Use the existing normal inspection endpoint and one result contract when a
separate release is authorized. Preserve existing user authorization and API
credentials; isolate research identities and signing secrets. Version models,
flags, manifests, receipts and evaluation reports. Never replace the rollback
checkpoint. Monitor abstention, false negatives on adjudicated cases, task routing,
latency and failure categories. Roll back by disabling the future feature flag
and returning to the preserved production revision; do not delete artifacts.

Merging research preparation is NOT production deployment approval. The connected
main branch currently auto-deploys to Vercel, so merges remain gated until an
operator approves a temporary deployment pause or equivalent verified safeguard.
