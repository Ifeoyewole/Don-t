
# JointInspect runtime security boundaries

## Public user access

JointInspect intentionally remains open at the user-facing layer. Do not add a
login or authentication window unless the product requirement changes.

`USER_AUTH_MODE=disabled` is therefore the expected mode today.

The placeholder `provider` mode now fails closed. It must not be enabled until
a real provider verifier validates signatures, issuer, audience, expiry, and
roles.

## Cloud Run machine-to-machine boundary

Public browser access does not mean the inference service should be public.
The Vercel gateway must obtain a Google-signed ID token for the Cloud Run
audience. If Workload Identity Federation or ID-token generation fails, the
gateway returns 503 and does not forward an unauthenticated request upstream.

## Rate limiting

The current in-process `Map` limiter is best-effort only. Serverless instances
and cold starts do not share its counters. Do not describe it as a global
production enforcement control. Use a managed Redis/KV limiter when the
production infrastructure is finalized.

## Health and telemetry

Public health output may expose non-secret capability state such as API
reachability or whether the production classifier is loaded. Never expose
credentials, access tokens, workload identity assertions, service-account
secrets, or raw private infrastructure metadata through public health
endpoints.
