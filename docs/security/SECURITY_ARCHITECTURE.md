# Joint Inspection — Zero-Trust Security Architecture
**Project**: Pipe Joint Optical Measurement & QA Engine (`joint-inspection`)  
**Status**: PRODUCTION-HARDENED  
**Date**: October 2026

---

## 1. Architectural Overview & Boundaries

The Joint Inspection system is architected around **Zero-Trust** security principles, establishing strict physical and identity boundaries between the public internet, the Vercel edge/serverless tier, and the Google Cloud Platform (GCP) private runtime environment.

```mermaid
flowchart TD
    subgraph ClientBrowser [Browser / Field Mobile Device]
        SPA[React 19 / Vite SPA]
    end

    subgraph VercelEdge [Vercel Managed Edge & Gateway]
        WAF[Vercel WAF & Security Headers]
        RateLimiter[IP Sliding-Window Rate Limiter]
        AuthAbs[Provider-Neutral Auth Abstraction]
        GatewayGuard[Perimeter Guard & Header Sanitizer]
        OIDCExchange[Vercel OIDC Token Exchanger]
    end

    subgraph GCPWIF [Google Cloud Identity]
        STS[Google Security Token Service (STS)]
        WIFPool[Workload Identity Pool: vercel]
        WIFProvider[OIDC Provider: vercel-production]
        InvokerSA[SA: joint-inspect-vercel-invoker]
    end

    subgraph GCPPrivateCore [Google Cloud Run - Private Network]
        CloudRun[FastAPI Sub-Pixel CV Engine<br>pipe-joint-api<br>Runtime SA: joint-inspection-runtime]
        GCS[(Private Cloud Storage<br>PAP Enforced / UBLA Active)]
        SM[(Secret Manager<br>Least-Privilege Bound)]
    end

    SPA -->|Same-Origin HTTPS<br>/api/v1/cv/*| WAF
    WAF --> RateLimiter
    RateLimiter --> AuthAbs
    AuthAbs --> GatewayGuard
    GatewayGuard --> OIDCExchange
    OIDCExchange -->|Vercel OIDC Token| STS
    STS -->|Federated Token| WIFPool
    WIFPool -->|Impersonate| InvokerSA
    InvokerSA -->|Signed Google ID Token| CloudRun
    CloudRun -->|Read Models| GCS
    CloudRun -->|Fetch Keys| SM
```

---

## 2. Zero-Trust Security Tenets

### 2.1 Private Cloud Run Ingress
- Cloud Run service `pipe-joint-api` enforces `--no-allow-unauthenticated`.
- `allUsers` and `allAuthenticatedUsers` permissions have been completely purged from the service's IAM policy.
- Direct invocation from arbitrary clients returns `HTTP 403 Forbidden`.
- Service runs under the dedicated, least-privileged runtime identity:  
  `joint-inspection-runtime@joint-inspection-510310.iam.gserviceaccount.com`.

### 2.2 Keyless Authentication via Workload Identity Federation (WIF)
- **Zero Static Credentials**: No service-account JSON key files or permanent secrets reside in Vercel.
- **Vercel OIDC Token**: Vercel dynamically provisions a short-lived OIDC token per invocation signed by `https://oidc.vercel.com`.
- **Google STS Exchange**: The Vercel gateway exchanges this token with Google STS (`https://sts.googleapis.com/v1/token`) against pool `vercel` and provider `vercel-production`.
- **Audience & Subject Scoping**: The provider verifies that the token's subject matches the exact project and production environment (`assertion.sub.endsWith(':environment:production')`).
- **Short-Lived ID Token**: The federated credential calls the IAM Credentials API to mint a Google-signed ID token whose audience is strictly the private Cloud Run URL.
- **Authorization Header Separation**: The token is transmitted via `X-Serverless-Authorization: Bearer <ID_TOKEN>`, preserving the standard `Authorization` header for prospective end-user bearer tokens.

### 2.3 Defense-in-Depth Gateway Sanitation
- **Client Header Stripping**: The gateway strips `x-serverless-authorization`, `x-vercel-oidc-token`, `x-forwarded-for`, `x-internal-*`, and `x-gcp-*` from client payloads.
- **Malicious Scanner Blocking**: Automated bot paths (such as `/wp-admin`, `/.env`, `/.git`, `/phpmyadmin`) are rejected immediately.
- **Payload & Format Bounds**:
  - Image payloads capped at 15 MB.
  - Multi-frame burst payloads capped at 30 MB / 30 frames.
  - Magic byte verification (`JPEG`, `PNG`, `WebP`) prevents executable injection.
  - Decompression bomb threshold: 50,000,000 pixels.
- **Error Sanitization**: Server-side Python exceptions and stack traces are suppressed. Clients receive generic error details alongside a correlation `request_id`.

---

## 3. Storage & Secret Security

1. **Cloud Storage Isolation**:
   - `joint-inspection-510310-app` and `joint-inspection-510310-data` have **Uniform Bucket-Level Access (UBLA)** enabled.
   - **Public Access Prevention (PAP)** is enforced across all buckets.
   - Separation of duty:
     - Runtime Service Account: `roles/storage.objectViewer` (read-only for model assets).
     - Trainer Service Account: `roles/storage.admin` (write access to training runs).
2. **Secret Manager**:
   - Secrets are versioned in Google Secret Manager.
   - Runtime account receives `roles/secretmanager.secretAccessor` only on required secrets. No Secret Manager Admin permissions.

---

## 4. Operational Telemetry & Monitoring

- **Correlation Tracking**: Every request generates an `X-Request-ID` correlation ID that flows from the Vercel gateway through Cloud Run and into Google Cloud Logging.
- **Rate Limit Telemetry**: IP sliding windows enforce 60 req/min on `/health`, 20 req/min on `/measure`, 5 req/min on `/multi-frame`, and 5 req/min on calibration endpoints.
- **Budget & Quota Controls**: Cloud Run max instances capped at 10 to protect against unexpected traffic surges or billing runaway.
