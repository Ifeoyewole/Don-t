# JointInspect™ — Final Security Audit & Verification Report

**Date:** 2026-10-05  
**Audit Scope:** Perimeter Gateway, Edge Ingress, Cloud Run IAM, Header Stripping, Rate Limiting, Input Validation, Container Security, Zero Static Keys, and Private Beta Posture  
**Target Service:** `pipe-joint-api` (Cloud Run `europe-west2`, Project: `joint-inspection-510310`)  
**Public Gateway:** `https://joint-inspection.vercel.app`  
**Authentication Status:** **`DEFERRED_FOR_PUBLIC_PRODUCTION`**  

---

## 1. Executive Summary

JointInspect has undergone a comprehensive security, perimeter hardening, and AI authority isolation review. All legacy insecure routing paths, mock middlewares, dev-token bypasses, and uncalibrated physical estimation fallbacks have been permanently removed.

The readiness determination is **`READY_FOR_INTERNAL_BETA`**:
- **Internal Company Beta Status:** Approved for a small, known group of internal company testers.
- **End-User Authentication:** Deferred for public production (`AUTHENTICATION_STATUS = DEFERRED_FOR_PUBLIC_PRODUCTION`).
- **Public Open Access:** Prohibited until cryptographic end-user authentication and authorization are implemented.

---

## 2. Perimeter Gateway Hardening Matrix

| Security Control | Implementation | Verification Status |
| :--- | :--- | :--- |
| **Strict Route Allowlist** | `api/v1/cv/[...route].ts` enforces explicit regex allowlist matching `/api/v1/cv/(health\|validate-photo\|measure\|measure/multi-frame\|calibration/profiles)`. Legacy aliases (`/cv/...`, `/api/v1/cv/detect-joint`) return **404 Not Found**. | **PASS** |
| **Inbound Header Stripping** | `api/_lib/gateway-guard.ts` completely removes client-supplied `authorization`, `x-serverless-authorization`, `x-vercel-oidc-token`, and all `x-gcp-*` headers before forwarding. | **PASS** |
| **Request ID Normalization** | Client-supplied `x-request-id` is sanitized to `^[a-zA-Z0-9_\-]{1,64}$`. Oversized or non-alphanumeric IDs are discarded and replaced with a cryptographic UUIDv4. | **PASS** |
| **Streaming Byte-Read Ceiling** | Body reads are capped at `MAX_UPLOAD_BYTES = 20 * 1024 * 1024` (20 MB). Payload exceeding limit terminates immediately with HTTP 413. | **PASS** |
| **Test Token Fallback Elimination** | `DEV_CLOUD_RUN_ID_TOKEN` and `TEST_VERCEL_OIDC_TOKEN` throw critical configuration errors in production (`process.env.NODE_ENV === "production"`). | **PASS** |
| **CORS Policy** | Explicit origin `https://joint-inspection.vercel.app`. Wildcards (`*`) and dynamic origin reflection are strictly prohibited. | **PASS** |

---

## 3. Infrastructure & IAM Security Posture

### Cloud Run Private Ingress
- **Cloud Run Service:** `pipe-joint-api`
- **Ingress Setting:** `allUsers` = **0** bindings (Public anonymous requests rejected with **HTTP 403 Forbidden**).
- **Authenticated Invokers:** `allAuthenticatedUsers` = **0** bindings.
- **Authorized Invoker:** Service Account `joint-inspect-vercel-invoker@joint-inspection-510310.iam.gserviceaccount.com` bound exclusively to `roles/run.invoker`.
- **Identity Token Exchange:** Vercel Edge Serverless functions generate signed Google OIDC ID tokens via Workload Identity Federation (WIF) targeting audience `https://pipe-joint-api-7d5y5wcyta-nw.a.run.app`.

### Service Account Credential Integrity & Secrets
- **Static Google Service-Account Keys:** **0** (Zero `.json` private keys exist, are stored in repos, or are mounted).
- **Vertex Credentials in Browser:** **NO** (Client browser only communicates with edge proxy; Google Cloud credentials never leave serverless runtime).
- **Raw Tokens in Logs:** **NO** (Authorization headers and JWT tokens are stripped before logging).
- **Dataset Separation:** Sewer-ML dataset was **NOT** used for model training or baseline integration; genuine WRc baseline weights are isolated as external advisory.

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

## 5. Decision & Future Public-Production Roadmap

- **Security Gate Decision:** **`READY_FOR_INTERNAL_BETA`**
- **Public-Production Milestone Item:**
  - Before unrestricted public launch: implement cryptographic end-user authentication and authorization (`USER_AUTH_MODE`).
  - This item does not block the internal company beta testing milestone.
