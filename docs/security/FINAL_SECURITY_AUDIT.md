# JointInspect™ — Final Security Audit & Verification Report

**Date:** 2026-10-05  
**Audit Scope:** Perimeter Gateway, Edge Ingress, Cloud Run IAM, Header Stripping, Rate Limiting, Input Validation, and Container Security  
**Target Service:** `pipe-joint-api` (Cloud Run `europe-west2`, Project: `joint-inspection-510310`)  
**Public Gateway:** `https://joint-inspection.vercel.app`  

---

## 1. Executive Summary

JointInspect has undergone a comprehensive 58-phase end-to-end security and perimeter hardening pass. All legacy insecure routing paths, mock middlewares, dev-token bypasses, and uncalibrated physical estimation fallbacks have been permanently removed.

The production release determination is **`PRIVATE_BETA_GO`**:
- **Private Beta Status:** Approved for verified beta operators and closed field trials.
- **Public Open Access:** Prohibited until user authentication vendor cryptographic tokens are enforced at the edge gateway.

---

## 2. Perimeter Gateway Hardening Matrix

| Security Control | Implementation | Verification Status |
| :--- | :--- | :--- |
| **Strict Route Allowlist** | `api/v1/cv/[...route].ts` enforces explicit regex allowlist matching `/api/v1/cv/(health\|validate-photo\|measure\|measure/multi-frame\|calibration/profiles)`. Legacy aliases (`/cv/...`, `/api/v1/cv/detect-joint`) return **404 Not Found**. | **PASS** (Verified via unit & gateway tests) |
| **Inbound Header Stripping** | `api/_lib/gateway-guard.ts` completely removes client-supplied `authorization`, `x-serverless-authorization`, `x-vercel-oidc-token`, and all `x-gcp-*` headers before forwarding. | **PASS** (Zero header spoofing possible) |
| **Request ID Normalization** | Client-supplied `x-request-id` is sanitized to `^[a-zA-Z0-9_\-]{1,64}$`. Oversized or non-alphanumeric IDs are discarded and replaced with a cryptographic UUIDv4. | **PASS** (DoS & injection resistant) |
| **Streaming Byte-Read Ceiling** | Body reads are capped at `MAX_UPLOAD_BYTES = 20 * 1024 * 1024` (20 MB). Payload exceeding limit terminates immediately with HTTP 413. | **PASS** (Memory exhaustion prevented) |
| **Test Token Fallback Elimination** | `DEV_CLOUD_RUN_ID_TOKEN` and `TEST_VERCEL_OIDC_TOKEN` throw critical configuration errors in production (`process.env.NODE_ENV === "production"`). | **PASS** (Zero bypass in production) |
| **CORS Policy** | Explicit origin `https://joint-inspection.vercel.app`. Wildcards (`*`) and dynamic origin reflection are strictly prohibited. | **PASS** (CORS preflight verified) |

---

## 3. Infrastructure & IAM Security Posture

### Cloud Run Private Ingress
- **Cloud Run Service:** `pipe-joint-api`
- **Ingress Setting:** `allUsers` = **0** bindings (Public anonymous requests rejected with **HTTP 403 Forbidden**).
- **Authorized Invoker:** Service Account `joint-inspect-vercel-invoker@joint-inspection-510310.iam.gserviceaccount.com` bound exclusively to `roles/run.invoker`.
- **Identity Token Exchange:** Vercel Edge Serverless functions generate signed Google OIDC ID tokens targeting audience `https://pipe-joint-api-7d5y5wcyta-nw.a.run.app`.

### Google Cloud Storage (GCS)
- **Bucket:** `gs://joint-inspection-510310-data`
- **Public Access Prevention:** `enforced` (No public internet access).
- **Uniform Bucket-Level Access:** `enabled`.
- **Retention / Lifecycle Policy:** Auto-deletion lifecycle rules active; zero persistent storage of ephemeral inspection frames.

### Service Account Credential Integrity
- **User-Managed Keys:** **0** (Zero `.json` private keys exist or are mounted).
- **Authentication Method:** Google Workload Identity & Metadata Server automatic token generation.

---

## 4. Input Validation & Error Sanitization

1. **File Type Filtering:**
   - Web frontend file picker restricted strictly to `image/jpeg,image/png,image/webp`. Generic `image/*` disabled.
   - Backend `validate_upload_file` inspects magic bytes (JPEG `FF D8 FF`, PNG `89 50 4E 47`, WebP `52 49 46 46`).
2. **Error Leakage Prevention:**
   - Backend 500 exceptions log internal tracebacks to Cloud Logging (`google.cloud.logging`) and return sanitized client responses: `{"detail": "Internal processing error. Diagnostic reference logged."}`.
3. **Interactive Documentation:**
   - FastAPI `/docs`, `/redoc`, and `/openapi.json` are disabled in production via `ENABLE_DOCS=false`.

---

## 5. Decision & Release Gate

- **Security Gate Decision:** **`PRIVATE_BETA_GO`**
- **Action Items for Public Production:**
  1. Integrate Supabase / WorkOS cryptographic JWT verification in `api/_lib/gateway-guard.ts`.
  2. Complete WRc commercial license legal review.
