from pathlib import Path

ROOT = Path.cwd()


def patch(path: str, old: str, new: str, count: int = 1) -> None:
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    if old not in text:
        raise RuntimeError(f'Expected block not found in {path}: {old[:180]!r}')
    p.write_text(text.replace(old, new, count), encoding='utf-8')
    print('patched', path)


def write(path: str, content: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.rstrip() + '\n', encoding='utf-8')
    print('wrote', path)

patch('api/_lib/auth-abstraction.ts', '''  async verifyRequest(request: RequestLike): Promise<AuthenticatedUser | null> {\n    const authHeader = request.headers['authorization'] || request.headers['Authorization']\n    if (!authHeader || typeof authHeader !== 'string' || !authHeader.startsWith('Bearer ')) {\n      return null\n    }\n\n    const token = authHeader.substring(7).trim()\n    if (!token) {\n      return null\n    }\n\n    // Provider token verification hook (e.g. Firebase Admin / Auth0 JWT / Supabase JWT)\n    // NOTE: This will be bound to the chosen vendor's verification SDK once approved in USER_AUTH_DECISION.md\n    return {\n      id: 'authenticated-user',\n      roles: ['INSPECTOR'],\n    }\n  }''', '''  async verifyRequest(_request: RequestLike): Promise<AuthenticatedUser | null> {\n    // Fail closed until a real provider verifier is installed.\n    // USER_AUTH_MODE=disabled remains the intentional public-product mode.\n    throw new Error(\n      'USER_AUTH_MODE=provider is not configured with a trusted token verifier.'\n    )\n  }''')

patch('api/v1/cv/[...route].js', '''var PluggableUserAuthProvider = class {\n  providerName = "provider";\n  async verifyRequest(request) {\n    const authHeader = request.headers["authorization"] || request.headers["Authorization"];\n    if (!authHeader || typeof authHeader !== "string" || !authHeader.startsWith("Bearer ")) {\n      return null;\n    }\n    const token = authHeader.substring(7).trim();\n    if (!token) {\n      return null;\n    }\n    return {\n      id: "authenticated-user",\n      roles: ["INSPECTOR"]\n    };\n  }\n};''', '''var PluggableUserAuthProvider = class {\n  providerName = "provider";\n  async verifyRequest(_request) {\n    throw new Error(\n      "USER_AUTH_MODE=provider is not configured with a trusted token verifier."\n    );\n  }\n};''')
patch('api/v1/cv/[...route].js', '''    const idToken = await getCloudRunIdToken();\n    const forwardHeaders = sanitizeForwardHeaders(req.headers);\n    forwardHeaders["x-request-id"] = requestId;\n    if (idToken) {\n      forwardHeaders["x-serverless-authorization"] = `Bearer ${idToken}`;\n      forwardHeaders["authorization"] = `Bearer ${idToken}`;\n    }''', '''    const idToken = await getCloudRunIdToken();\n    if (!idToken) {\n      console.error(`[GATEWAY-AUTH-${requestId}] Cloud Run identity token unavailable; refusing unauthenticated upstream invocation.`);\n      return sendJson(\n        res,\n        503,\n        {\n          detail: "Cloud inference service authentication is temporarily unavailable.",\n          request_id: requestId\n        },\n        corsHeaders\n      );\n    }\n    const forwardHeaders = sanitizeForwardHeaders(req.headers);\n    forwardHeaders["x-request-id"] = requestId;\n    forwardHeaders["x-serverless-authorization"] = `Bearer ${idToken}`;\n    forwardHeaders["authorization"] = `Bearer ${idToken}`;''')
patch('backend/Dockerfile', '    CMD curl -f http://localhost:${PORT:-8000}/cv/health || exit 1', '    CMD curl -f http://localhost:${PORT:-8000}/api/v1/cv/health || exit 1')

write('docs/RUNTIME_SECURITY.md', '''
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
''')

print('PR3 runtime hardening applied; user-facing access remains open')
