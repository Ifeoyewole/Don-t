# JointInspect™ — Cloud Run & GCP IAM Final Audit

**Date:** 2026-10-05  
**Project ID:** `joint-inspection-510310`  
**Region:** `europe-west2`  
**Audited Service:** `pipe-joint-api`  

---

## 1. Cloud Run Ingress Policy

The Cloud Run deployment operates in **Strict Private / Internal Ingress** mode:

```bash
gcloud run services get-iam-policy pipe-joint-api --region=europe-west2
```

### Policy Findings:
- **`allUsers` Member Count:** `0` (Zero public unauthenticated ingress).
- **`allAuthenticatedUsers` Member Count:** `0` (Zero generic authenticated ingress).
- **Authorized Invoker:**
  - Role: `roles/run.invoker`
  - Member: `serviceAccount:joint-inspect-vercel-invoker@joint-inspection-510310.iam.gserviceaccount.com`

Direct HTTP requests to the private Cloud Run URL (`https://pipe-joint-api-7d5y5wcyta-nw.a.run.app`) return **HTTP 403 Forbidden**.

---

## 2. Service Account Analysis

1. **`joint-inspect-vercel-invoker@joint-inspection-510310.iam.gserviceaccount.com`**
   - **Role:** `roles/run.invoker` (Least Privilege).
   - **User Keys:** `0` user-managed keys created.
   - **Token Flow:** OIDC ID token generation via Vercel GCP workload federation.
2. **Cloud Run Runtime Service Account:**
   - **Roles:**
     - `roles/aiplatform.user` (Allows Vertex AI Gemini multimodal inference in `europe-west2`).
     - `roles/logging.logWriter` (Allows structured JSON log emission).
   - **User Keys:** `0`.

---

## 3. Cloud Storage IAM & Bucket Hardening

- **Bucket:** `gs://joint-inspection-510310-data`
- **Public Access Prevention:** `enforced`
- **Uniform Bucket-Level Access:** `true`
- **Direct Object URLs:** All direct `storage.googleapis.com` public accesses return HTTP 403.
- **Data Retention:** Ephemeral pipeline buffers are purged automatically by GCS lifecycle rules.

---

## 4. Verification Check

| Security Check | Expected State | Audited State | Status |
| :--- | :--- | :--- | :--- |
| Cloud Run Direct Access | HTTP 403 Forbidden | HTTP 403 Forbidden | **PASS** |
| Vercel Edge Proxy Access | HTTP 200 OK | HTTP 200 OK | **PASS** |
| IAM Invoker Least Privilege | 1 Service Account | 1 Service Account | **PASS** |
| Keyless Authentication | 0 JSON keys | 0 JSON keys | **PASS** |
