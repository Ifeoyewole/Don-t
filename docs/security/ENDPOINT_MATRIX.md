# JointInspect — Comprehensive Endpoint & Gateway Routing Matrix

**Generated Programmatically from FastAPI Route Table & Vercel Gateway Configuration.**
**Date:** October 2026

---

## 1. Canonical FastAPI Routes (Backend Execution Baseline)

| Method | Route Path | Handler / Name | Production Necessity | Gateway Exposed? | Auth / Identity Required |
|---|---|---|---|---|---|
| `GET` | `/` | `Root` | MINIMAL | NO (INTERNAL ONLY) | PUBLIC LIVENESS |
| `GET` | `/api/v1/cv/calibration/profiles` | `List All Active Camera Calibration Profiles` | ESSENTIAL | YES | AUTHENTICATED (WIF) |
| `POST` | `/api/v1/cv/calibration/profiles` | `Register or Update a Camera Profile` | ESSENTIAL | YES | ADMIN AUTH (MUTATION) |
| `GET` | `/api/v1/cv/calibration/profiles/{camera_id}` | `Get Specific Camera Profile` | ESSENTIAL | YES | AUTHENTICATED (WIF) |
| `GET` | `/api/v1/cv/health` | `Service Health & Diagnostics` | ESSENTIAL | YES | AUTHENTICATED (WIF) |
| `POST` | `/api/v1/cv/measure` | `Compute Calibrated AI/CV Sub-Pixel Gap Measurements` | ESSENTIAL | YES | AUTHENTICATED (WIF) |
| `POST` | `/api/v1/cv/measure/multi-frame` | `Compute Multi-Frame Fused Gap Measurements with MAD Outlier Rejection` | ESSENTIAL | YES | AUTHENTICATED (WIF) |
| `POST` | `/api/v1/cv/validate-photo` | `Validate Image Quality for CV Measurement` | ESSENTIAL | YES | AUTHENTICATED (WIF) |
| `GET` | `/health` | `Root Liveness` | ESSENTIAL | YES | PUBLIC LIVENESS |

---

## 2. Removed Duplicate / Legacy Route Inventory

The following routes previously exposed via root or duplicate router mounts have been **permanently eliminated** from production:

| Removed Path | Former Method | Status | Verified Return Code | Rationale |
|---|---|---|---|---|
| `/cv/health` | GET | **REMOVED** | `404 Not Found` | Canonical route is `/api/v1/cv/health` |
| `/cv/validate-photo` | POST | **REMOVED** | `404 Not Found` | Canonical route is `/api/v1/cv/validate-photo` |
| `/cv/measure` | POST | **REMOVED** | `404 Not Found` | Canonical route is `/api/v1/cv/measure` |
| `/cv/measure/multi-frame` | POST | **REMOVED** | `404 Not Found` | Canonical route is `/api/v1/cv/measure/multi-frame` |
| `/cv/calibration/profiles` | GET / POST | **REMOVED** | `404 Not Found` | Canonical route is `/api/v1/cv/calibration/profiles` |
| `/cv/calibration/profiles/{id}` | GET | **REMOVED** | `404 Not Found` | Canonical route is `/api/v1/cv/calibration/profiles/{id}` |
| `/api/v1/health` | GET | **REMOVED** | `404 Not Found` | Canonical route is `/api/v1/cv/health` or root `/health` |
| `/api/ai/measure-photo` | POST | **REMOVED** | `404 Not Found` | Legacy Netlify / Vite bypass eliminated; physical mm by AI forbidden |

---

## 3. Strict Gateway Allowlist Matrix (Vercel Perimeter)

The Vercel Serverless Gateway (`api/v1/cv/[...route].ts`) enforces an explicit allowlist and does **not** forward arbitrary wildcard subpaths.

| Method | Gateway Incoming Route | Cloud Run Target Route | Rate Limit Category | Max Payload | Auth / Role Gate | Expected Status |
|---|---|---|---|---|---|---|
| `GET` | `/api/v1/cv/health` | `/api/v1/cv/health` | `HEALTH` (60/min) | 0 B | Minimal public liveness (`{"status": "ok"}`) | `200 OK` |
| `POST` | `/api/v1/cv/validate-photo` | `/api/v1/cv/validate-photo` | `VALIDATION` (30/min) | 15 MB | Inspector | `200 OK` / `422` |
| `POST` | `/api/v1/cv/measure` | `/api/v1/cv/measure` | `MEASURE` (20/min) | 15 MB | Inspector | `200 OK` / `400` / `422` |
| `POST` | `/api/v1/cv/measure/multi-frame` | `/api/v1/cv/measure/multi-frame` | `MULTI_FRAME` (5/min) | 30 MB (max 30 frames) | Inspector | `200 OK` / `400` / `413` |
| `GET` | `/api/v1/cv/calibration/profiles` | `/api/v1/cv/calibration/profiles` | `CALIBRATION_READ` (30/min) | 0 B | Authenticated Inspector / Engineer | `200 OK` / `401` |
| `GET` | `/api/v1/cv/calibration/profiles/{id}` | `/api/v1/cv/calibration/profiles/{id}` | `CALIBRATION_READ` (30/min) | 0 B | Authenticated Inspector / Engineer | `200 OK` / `404` |
| `POST` | `/api/v1/cv/calibration/profiles` | `/api/v1/cv/calibration/profiles` | `CALIBRATION_MUTATE` (5/min) | 1 MB | ADMIN Role only + Mutation flag | `201 Created` / `403 Forbidden` |
| *ANY* | *Unknown Route* | *Blocked* | N/A | N/A | Denied | `404 Not Found` |
| *DISALLOWED* | *Wrong Method* | *Blocked* | N/A | N/A | Denied | `405 Method Not Allowed` |

---

## 4. Security Controls Summary

- **Inbound Header Stripping:** Client-supplied `Authorization`, `X-Serverless-Authorization`, `X-Vercel-OIDC-Token`, `X-GCP-*`, and `X-Internal-*` are stripped before server-side token injection.
- **Outbound ID Token Injection:** Gateway injects `Authorization: Bearer <Cloud Run ID Token>` acquired through Vercel OIDC -> Workload Identity Federation (WIF).
- **Private Cloud Run Access:** Cloud Run accepts requests only from authenticated Google service identities (`run.invoker`). Direct anonymous requests return `403 Forbidden`.
- **Zero-Guessing Physical Geometry:** Calibration required before millimeters are emitted. Uncalibrated images return pixel gaps with `CALIBRATION_REQUIRED`.