# JointInspect GCP read-only diagnosis

Run the **GCP Read-only Diagnostics** GitHub Action manually. It queries the
Cloud Run service specification and aggregates recent Cloud Logging error counts.
It does **not** deploy, restart, configure, retrain, upload datasets, download
secrets, execute Gemini inference, or change IAM or billing.

## One-time GitHub ↔ GCP setup

Create a *separate GitHub Actions* Workload Identity Federation OIDC provider.
The existing Vercel OIDC provider is **not** a GitHub provider. Restrict the
Google provider with an attribute condition requiring
`assertion.repository == "Ifeoyewole/Don-t" && assertion.ref == "refs/heads/main"`. This main-branch restriction is required; do not trust other branches or pull requests.
Bind the provider principal for this repository ONLY to a dedicated service
account with `roles/iam.workloadIdentityUser` (on that SA).

Grant this diagnostic service account the minimum **read-only** permissions:
- `roles/run.viewer` on the Cloud Run project or target service.
- `roles/logging.viewer` if you want aggregated recent error counts.
- No `roles/editor`, `roles/owner`, Storage object admin, Secret Accessor,
  Cloud Run Admin, Vertex training, IAM policy mutation, or billing mutation.

In GitHub → **Ifeoyewole/Don-t** → Settings → Secrets and variables → Actions
→ **Variables**, add these **non-secret** repository variables (not JSON keys):

| Variable | Value |
| --- | --- |
| `GCP_DIAGNOSTICS_PROJECT_ID` | `joint-inspection-510310` |
| `GCP_DIAGNOSTICS_REGION` | `europe-west2` |
| `GCP_DIAGNOSTICS_SERVICE` | `pipe-joint-api` |
| `GCP_DIAGNOSTICS_WIF_PROVIDER` | GCP resource name of your GitHub-specific OIDC provider |
| `GCP_DIAGNOSTICS_SERVICE_ACCOUNT` | Dedicated diagnostics-reader service account email |

Then navigate to Actions → **GCP Read-only Diagnostics** → **Run workflow**
using the protected `main` branch. Read the generated job summary.

## What to look for

1. `PRIMARY_CONDITION_CLASSIFIER`: default is `wrc`, not `inspect_view`.
2. For WRc: verify a revision built using `cloudbuild.yaml`, which copies and
   SHA-256-verifies WRc ONNX weights into the image. Missing or bad ONNX file,
   dependency failure or a different image can cause `primary_classifier.loaded=false`.
3. For Inspect View: the configured checkpoint path, file SHA and PyTorch loader
   must be valid. Do not enable research preview on production without review.
4. `VERTEX_INSPECTION_MODEL` and `VERTEX_INSPECTION_LOCATION` describe Gemini
   configuration, not whether any individual image request succeeded.
5. The health route `/api/v1/cv/health` reports the primary classifier and
   Gemini configuration separately, but its `status=ok` is not model readiness.
6. This workflow never prints entire environment variable lists, tokens,
   secret references, image payloads, or raw log messages.

If WIF fails, check the repo/provider issuer and attribute mapping, read-only SA
binding, GCP API enablement and GitHub workflow reference. Do not fall back to
committing a service-account JSON key. More information:
https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines
https://github.com/google-github-actions/auth
