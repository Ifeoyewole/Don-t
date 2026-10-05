# Threat Model & Attack Surface Analysis
**Project**: Pipe Joint Optical Measurement & QA Engine (`joint-inspection`)  
**Standard**: STRIDE Threat Analysis Framework  
**Scope**: Frontend SPA, Vercel API Gateway, Google Cloud Run, Cloud Storage, Workload Identity Federation

---

## 1. Threat Actors & Motivations

1. **Anonymous Internet Scanners / Botnets**:
   - *Motivation*: Opportunistic exploitation of exposed environments, credential harvesting, resource hijacking for cryptocurrency mining.
2. **Malicious / Compromised Client**:
   - *Motivation*: Bypassing pipe quality gates, faking inspection pass results, corrupting calibration data to hide defective welds/joints.
3. **Malicious Insider / Rogue Contractor**:
   - *Motivation*: Unauthorized access to proprietary pipeline media, tampering with model weights or historical measurement certificates.
4. **Supply Chain / Third-Party Dependency Compromise**:
   - *Motivation*: Exfiltrating cloud credentials, poisoning JavaScript client bundles or Python container dependencies.

---

## 2. STRIDE Assessment & Mitigations

| Threat (STRIDE) | Attack Vector | Potential Impact | Implemented Mitigation |
| :--- | :--- | :--- | :--- |
| **Spoofing** | Adversary attempts to forge `X-Serverless-Authorization` or impersonate Vercel to invoke Cloud Run. | Direct access to private CV engine; unauthorized compute usage. | **Workload Identity Federation**: Cloud Run requires Google-signed ID tokens issued exclusively via STS to subject `assertion.sub.endsWith(':environment:production')`. Header is stripped at gateway perimeter if client-supplied. |
| **Tampering** | Field operator attempts to modify camera calibration parameters or bypass the zero-guessing safety gate. | Defective joints falsely recorded as PASS; loss of pipeline structural safety. | **Calibration Lock**: Mutations to `/calibration/profiles` are hard-blocked in production (`403 Forbidden`). Zero-guessing confidence gating is enforced in core CV algorithms and cannot be disabled via client flags. |
| **Repudiation** | Inspector denies conducting a rejected measurement or claims system altered measurement results. | Inability to audit defective joint installations during forensic reviews. | **Correlation Telemetry**: End-to-end `X-Request-ID` tracking paired with immutable sub-pixel debug vector dumps and Cloud Logging audit records. |
| **Information Disclosure** | Adversary sends malformed payloads to trigger stack traces, revealing internal paths, secrets, or library versions. | System reconnaissance; discovery of vulnerable sub-dependencies. | **Error Sanitization**: Raw Python exceptions (`str(exc)`) are suppressed. Production documentation endpoints (`/docs`, `/redoc`, `/openapi.json`) are disabled by default. |
| **Denial of Service** | Flooding heavy `/measure` or `/multi-frame` endpoints with high-resolution images or decompression bombs. | Exhaustion of Cloud Run vCPU/RAM; billing runaway; service unavailability. | **Multi-Tier DoS Protection**: IP-based rate limiting (20 req/min for measurement, 5 req/min for bursts). Image payload capped at 15 MB / 50 Megapixels. Cloud Run max instances capped at 10. |
| **Elevation of Privilege** | Compromised Vercel serverless function attempts to access Google Cloud Storage, Secret Manager, or Vertex AI. | Exfiltration of training datasets, model weights, or project-wide credentials. | **IAM Least Privilege**: Service account `joint-inspect-vercel-invoker` possesses *only* `roles/run.invoker` on service `pipe-joint-api`. It has zero Storage, Secret Manager, or Vertex AI permissions. |

---

## 3. Trust Boundaries & Data Flow Restrictions

1. **Boundary A (Internet -> Vercel Gateway)**:
   - Only same-origin HTTPS requests accepted.
   - Client headers matching `x-serverless-authorization`, `x-vercel-oidc-token`, and `x-internal-*` are discarded.
2. **Boundary B (Vercel Gateway -> Google Cloud Platform)**:
   - Strictly outbound HTTPS to Google STS and IAM Credentials APIs.
   - Credentials are short-lived ID tokens valid only for Cloud Run audience.
3. **Boundary C (Cloud Run -> GCP Internal Resources)**:
   - Cloud Run service account `joint-inspection-runtime` has read-only access to model buckets (`roles/storage.objectViewer`) and secret accessor rights to designated API keys only.
   - No project-level Owner or Editor roles assigned to any workload identity.
