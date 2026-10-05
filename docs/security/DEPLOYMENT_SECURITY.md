# Deployment Security & Operational Checklist
**Project**: Pipe Joint Optical Measurement & QA Engine (`joint-inspection`)  
**Deployment Pipeline**: GitHub (`origin/main`) -> Vercel CI/CD + Google Cloud Build -> Cloud Run

---

## 1. Environment Variable Reference

Only public configuration identifiers are stored in the Vercel production environment. No private keys, service account JSON files, or permanent secrets are stored in Vercel:

| Variable | Type | Example / Value | Description |
| :--- | :--- | :--- | :--- |
| `GCP_PROJECT_ID` | Identifier | `joint-inspection-510310` | Target Google Cloud Project ID |
| `GCP_PROJECT_NUMBER` | Identifier | `567370443508` | Numeric GCP Project Identifier |
| `GCP_SERVICE_ACCOUNT_EMAIL` | Identifier | `joint-inspect-vercel-invoker@joint-inspection-510310.iam.gserviceaccount.com` | Dedicated Invoker Service Account |
| `GCP_WORKLOAD_IDENTITY_POOL_ID` | Identifier | `vercel` | Workload Identity Pool Name |
| `GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID` | Identifier | `vercel-production` | OIDC Provider Name within Pool |
| `CLOUD_RUN_URL` | Endpoint | `https://pipe-joint-api-7d5y5wcyta-nw.a.run.app` | Private Cloud Run Service URL |
| `USER_AUTH_MODE` | Setting | `disabled` (or `provider`) | User authentication enforcement mode |

---

## 2. Cloud Run Service Hardening Flags

When deploying the backend container to Google Cloud Run, execute using least-privilege service-account and explicit resource limits:

```bash
gcloud run deploy pipe-joint-api \
  --image europe-west2-docker.pkg.dev/joint-inspection-510310/joint-inspection-app/pipe-joint-api:latest \
  --region europe-west2 \
  --project joint-inspection-510310 \
  --service-account joint-inspection-runtime@joint-inspection-510310.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --max-instances 10 \
  --concurrency 80 \
  --timeout 60s \
  --set-env-vars ENVIRONMENT=production,ENABLE_DOCS=false,CALIBRATION_MUTATION_ENABLED=false
```

---

## 3. Workload Identity Federation (WIF) Verification

To verify that the Workload Identity Federation pool and OIDC provider are correctly linked:

```bash
# 1. Describe Workload Identity Pool
gcloud iam workload-identity-pools describe vercel \
  --location global \
  --project joint-inspection-510310

# 2. Describe OIDC Provider and Mapping
gcloud iam workload-identity-pools providers describe vercel-production \
  --workload-identity-pool vercel \
  --location global \
  --project joint-inspection-510310

# 3. Verify Service Account Token Creator & Invoker Permissions
gcloud iam service-accounts get-iam-policy \
  joint-inspect-vercel-invoker@joint-inspection-510310.iam.gserviceaccount.com \
  --project joint-inspection-510310
```

---

## 4. Operational Verification Checklist

- [x] **Direct Cloud Run Access**: `curl -i https://<cloud-run-url>/cv/health` returns `HTTP 403 Forbidden`.
- [x] **Gateway Health Check**: `curl -i https://joint-inspection.vercel.app/api/v1/cv/health` returns `HTTP 200 OK`.
- [x] **HSTS & Security Headers**: Verified `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Content-Security-Policy`.
- [x] **Oversized Upload Protection**: Uploads exceeding 15 MB return `HTTP 413 Payload Too Large`.
- [x] **Invalid MIME Rejection**: Non-image payloads or spoofed extensions return `HTTP 400 Bad Request`.
- [x] **Rate Limit Enforcement**: Exceeding route thresholds triggers `HTTP 429 Too Many Requests` with `Retry-After`.
- [x] **Calibration Tampering Protection**: Unauthenticated mutations to `/calibration/profiles` return `HTTP 403 Forbidden`.
- [x] **Zero-Guessing Invariance**: Sub-pixel geometric measurement, MAD outlier rejection, and rejection gates operate without degradation.
