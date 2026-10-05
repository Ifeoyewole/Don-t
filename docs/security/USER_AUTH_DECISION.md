# User Authentication & Identity Decision Matrix
**Project**: Pipe Joint Inspection QA Platform (`joint-inspection`)  
**Status**: PENDING TEAM DECISION  
**Current Mode**: `USER_AUTH_MODE=disabled` (Perimeter Hardened by Secure Gateway)  
**Target Roles**: `ADMIN`, `ENGINEER`, `INSPECTOR`, `CLIENT_VIEWER`

---

## 1. Executive Summary

End-user authentication for the Pipe Joint Inspection platform has been decoupled through a provider-neutral abstraction layer (`api/lib/auth-abstraction.ts`). The platform does not currently lock into any single proprietary authentication provider.

Until a final corporate authentication architecture is approved, the Vercel Secure API Gateway enforces:
1. Strict IP-based sliding window rate limiting.
2. Network perimeter isolation with private Google Cloud Run execution.
3. Automated bot and scanner challenge/rejection.
4. Input sanitization and payload size limits.

When enabled, end-user authentication occurs at the Vercel gateway layer **before** any Google Cloud Run ID token is minted or forwarded.

---

## 2. Role-Based Access Control (RBAC) Specification

The system defines four standardized role tiers:

| Role | Permissions & Operational Scope |
| :--- | :--- |
| **`ADMIN`** | Full system administration, camera calibration register/update/delete, tenant billing, audit log review, role delegation. |
| **`ENGINEER`** | Pipeline defect tolerance standard modifications, batch multi-frame sequence analysis, report template approval. |
| **`INSPECTOR`** | Field operations: single photo upload, live sub-pixel gap measurement, visual HUD review, inspection note submission. |
| **`CLIENT_VIEWER`** | Read-only access to signed inspection reports, tolerance certificates, and high-level project KPIs. No upload/measurement rights. |

---

## 3. Decision Requirements Checklist

The engineering and executive team must evaluate the following business and security requirements:

- [ ] **Authentication Methods**:
  - Email/Password with breach detection?
  - Passwordless / Magic Link authentication?
  - FIDO2 / WebAuthn passkeys?
- [ ] **Enterprise Identity Federation (SSO)**:
  - Google Workspace OAuth (default field devices)?
  - Microsoft Entra ID (Azure AD) for enterprise clients?
  - SAML 2.0 / OIDC federation for enterprise industrial customers?
- [ ] **Multi-Tenancy & Organizations**:
  - Single-tenant application or isolated customer workspaces (e.g. Utility Company A vs Contractor B)?
  - Cross-tenant data isolation enforcement at database and report storage layers?
- [ ] **User Onboarding Policy**:
  - Open self-registration or strictly invite-only / administrator-provisioned accounts?
- [ ] **Multi-Factor Authentication (MFA)**:
  - Mandatory TOTP (Google/Microsoft Authenticator) or SMS (discouraged)?
  - Enforced MFA for `ADMIN` and `ENGINEER` roles?
- [ ] **Audit Logging & Compliance**:
  - Tamper-evident logging of inspection sign-offs, camera calibration changes, and user access events?
  - Retention requirements (e.g. 7-year pipeline inspection liability retention)?

---

## 4. Vendor Evaluation Matrix

| Provider | Strengths | Considerations | Recommendation Tier |
| :--- | :--- | :--- | :--- |
| **Google Cloud Identity Platform / Firebase Auth** | Native GCP integration, seamless service-to-service IAM alignment, SAML/OIDC enterprise add-on, low latency. | React client SDK overhead, enterprise SAML requires paid tier. | **Primary Contender** |
| **Auth0 by Okta** | Gold standard enterprise SSO, turnkey SAML/WS-Fed, extensive role and rule engines, SOC2/HIPAA ready. | Higher enterprise cost per active monthly user. | **Strong Enterprise Alternative** |
| **Supabase Auth** | Open-source foundation, built-in PostgreSQL Row-Level Security (RLS), affordable scaling. | Third-party cloud tenancy, separate from GCP core. | **Viable Alternative** |
| **Clerk** | Turnkey React UI components, rapid organization/multi-tenant onboarding, high developer velocity. | SaaS lock-in, external session management. | **High Velocity Option** |
| **Auth.js / Self-Hosted OIDC** | Zero vendor cost, complete infrastructure control. | Engineering overhead for key rotation, session storage, and security compliance. | **Not Recommended for Phase 1** |

---

## 5. Gateway Integration Contract

Once approved, the selected provider plugs directly into `api/lib/auth-abstraction.ts` by updating `PluggableUserAuthProvider`:

```typescript
export class ProductionUserAuthProvider implements UserAuthProvider {
  readonly providerName = 'selected-vendor'

  async verifyRequest(request: Request): Promise<AuthenticatedUser | null> {
    const token = extractBearerToken(request)
    if (!token) return null

    // Call chosen verification engine
    const claims = await vendorSdk.verifyToken(token)
    return {
      id: claims.sub,
      email: claims.email,
      roles: claims['https://joint-inspection.com/roles'] || ['INSPECTOR'],
    }
  }
}
```
No modifications to the private Cloud Run FastAPI AI/CV backend or sub-pixel measurement logic will be required.
