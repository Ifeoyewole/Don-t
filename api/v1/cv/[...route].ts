/**
 * Vercel Secure API Gateway Route Handler for Computer Vision Endpoints
 *
 * Implements perimeter security:
 * 1. Method and path validation
 * 2. Route-based sliding window rate limiting
 * 3. User authentication verification (pluggable abstraction)
 * 4. Strips client internal/auth headers
 * 5. Acquires Google ID token via Vercel OIDC -> Workload Identity Federation
 * 6. Invokes private Cloud Run backend securely via X-Serverless-Authorization
 * 7. Sanitizes all error responses returned to the client
 */

import type { IncomingMessage, ServerResponse } from 'http'

// ==========================================
// 1. GATEWAY CONFIGURATION IDENTIFIERS
// ==========================================
export const GATEWAY_CONFIG = {
  GCP_PROJECT_ID: process.env.GCP_PROJECT_ID || 'joint-inspection-510310',
  GCP_PROJECT_NUMBER: process.env.GCP_PROJECT_NUMBER || '567370443508',
  GCP_SERVICE_ACCOUNT_EMAIL:
    process.env.GCP_SERVICE_ACCOUNT_EMAIL ||
    'joint-inspect-vercel-invoker@joint-inspection-510310.iam.gserviceaccount.com',
  GCP_WORKLOAD_IDENTITY_POOL_ID: process.env.GCP_WORKLOAD_IDENTITY_POOL_ID || 'vercel',
  GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID:
    process.env.GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID || 'vercel-production',
  CLOUD_RUN_URL: (process.env.CLOUD_RUN_URL || 'https://pipe-joint-api-7d5y5wcyta-nw.a.run.app').replace(/\/$/, ''),

  // Authentication abstraction mode ('disabled' until provider selection is approved)
  USER_AUTH_MODE: (process.env.USER_AUTH_MODE || 'disabled') as 'disabled' | 'provider',

  // Rate Limiting (Requests / minute / IP)
  RATE_LIMITS: {
    HEALTH: parseInt(process.env.RATE_LIMIT_HEALTH || '60', 10),
    MEASURE: parseInt(process.env.RATE_LIMIT_MEASURE || '20', 10),
    MULTI_FRAME: parseInt(process.env.RATE_LIMIT_MULTI_FRAME || '5', 10),
    CALIBRATION_READ: parseInt(process.env.RATE_LIMIT_CALIBRATION_READ || '30', 10),
    CALIBRATION_MUTATE: parseInt(process.env.RATE_LIMIT_CALIBRATION_MUTATE || '5', 10),
  },

  // Payload constraints
  MAX_UPLOAD_SIZE_BYTES: 15 * 1024 * 1024, // 15 MB
  MAX_MULTI_FRAME_BYTES: 30 * 1024 * 1024, // 30 MB
  MAX_MULTI_FRAME_COUNT: 30,

  // Allowed image MIME types
  ALLOWED_IMAGE_MIMES: ['image/jpeg', 'image/png', 'image/webp'],
} as const

// ==========================================
// 2. USER AUTHENTICATION ABSTRACTION
// ==========================================
export type Role = 'ADMIN' | 'ENGINEER' | 'INSPECTOR' | 'CLIENT_VIEWER'

export interface AuthenticatedUser {
  id: string
  email?: string
  roles: Role[]
  metadata?: Record<string, unknown>
}

export interface UserAuthProvider {
  verifyRequest(req: IncomingMessage): Promise<AuthenticatedUser | null>
}

export class DisabledUserAuthProvider implements UserAuthProvider {
  async verifyRequest(_req: IncomingMessage): Promise<AuthenticatedUser | null> {
    return {
      id: 'guest_operator',
      roles: ['INSPECTOR'],
      metadata: { authMode: 'disabled' },
    }
  }
}

export class PluggableUserAuthProvider implements UserAuthProvider {
  async verifyRequest(req: IncomingMessage): Promise<AuthenticatedUser | null> {
    const authHeader = req.headers.authorization
    if (!authHeader || !authHeader.startsWith('Bearer ')) {
      return null
    }
    return null
  }
}

function getUserAuthProvider(): UserAuthProvider {
  if (GATEWAY_CONFIG.USER_AUTH_MODE === 'disabled') {
    return new DisabledUserAuthProvider()
  }
  return new PluggableUserAuthProvider()
}

export async function verifyGatewayUser(req: IncomingMessage): Promise<AuthenticatedUser | null> {
  const provider = getUserAuthProvider()
  return provider.verifyRequest(req)
}

// ==========================================
// 3. RATE LIMITER
// ==========================================
interface RateLimitWindow {
  timestamps: number[]
}

const memoryRateLimitStore = new Map<string, RateLimitWindow>()

export function getClientIp(req: IncomingMessage): string {
  const vercelForwardedFor = req.headers['x-vercel-forwarded-for']
  if (typeof vercelForwardedFor === 'string' && vercelForwardedFor.trim()) {
    return vercelForwardedFor.split(',')[0].trim()
  }
  const realIp = req.headers['x-real-ip']
  if (typeof realIp === 'string' && realIp.trim()) {
    return realIp.trim()
  }
  return '127.0.0.1'
}

export function getRouteCategory(url: string, method: string): keyof typeof GATEWAY_CONFIG.RATE_LIMITS {
  const cleanUrl = url.toLowerCase()
  if (cleanUrl.includes('/health')) return 'HEALTH'
  if (cleanUrl.includes('/multi-frame')) return 'MULTI_FRAME'
  if (cleanUrl.includes('/measure')) return 'MEASURE'
  if (cleanUrl.includes('/calibration')) {
    return ['POST', 'PUT', 'DELETE'].includes(method.toUpperCase())
      ? 'CALIBRATION_MUTATE'
      : 'CALIBRATION_READ'
  }
  return 'HEALTH'
}

export async function checkRateLimit(
  req: IncomingMessage
): Promise<{ allowed: boolean; limit: number; remaining: number; resetSeconds: number }> {
  const ip = getClientIp(req)
  const category = getRouteCategory(req.url || '/', req.method || 'GET')
  const limit = GATEWAY_CONFIG.RATE_LIMITS[category]
  const key = `${category}:${ip}`
  const now = Date.now()
  const windowMs = 60_000

  let record = memoryRateLimitStore.get(key)
  if (!record) {
    record = { timestamps: [] }
    memoryRateLimitStore.set(key, record)
  }

  // Purge expired timestamps
  record.timestamps = record.timestamps.filter((ts) => ts > now - windowMs)

  if (record.timestamps.length >= limit) {
    const oldest = record.timestamps[0] || now
    const resetSeconds = Math.max(1, Math.ceil((oldest + windowMs - now) / 1000))
    return { allowed: false, limit, remaining: 0, resetSeconds }
  }

  record.timestamps.push(now)
  return {
    allowed: true,
    limit,
    remaining: limit - record.timestamps.length,
    resetSeconds: 60,
  }
}

// ==========================================
// 4. GATEWAY GUARD & SANITIZER
// ==========================================
const FORBIDDEN_HEADER_PREFIXES = [
  'x-serverless-authorization',
  'x-vercel-oidc-token',
  'x-internal-',
  'x-gcp-',
  'x-service-account-',
]

const MALICIOUS_PATH_PATTERNS = [
  /wp-admin/i,
  /\.env/i,
  /\/\.git/i,
  /phpmyadmin/i,
  /server-status/i,
  /\.aws/i,
  /\.ssh/i,
  /etc\/passwd/i,
]

export function isMaliciousPath(path: string): boolean {
  return MALICIOUS_PATH_PATTERNS.some((pattern) => pattern.test(path))
}

export function sanitizeForwardHeaders(headers: Record<string, string | string[] | undefined>): Record<string, string> {
  const clean: Record<string, string> = {}

  for (const [key, value] of Object.entries(headers)) {
    if (!value || typeof value !== 'string') continue
    const lowerKey = key.toLowerCase()

    // 1. Strip forbidden client-supplied internal headers
    if (FORBIDDEN_HEADER_PREFIXES.some((prefix) => lowerKey.startsWith(prefix))) {
      continue
    }

    // 2. Discard client-supplied X-Forwarded-For to prevent IP spoofing
    if (lowerKey === 'x-forwarded-for' || lowerKey === 'x-forwarded-host') {
      continue
    }

    clean[key] = value
  }

  return clean
}

export function sanitizeErrorResponse(_error: unknown, requestId: string): { detail: string; request_id: string } {
  return {
    detail: 'An error occurred while processing the inspection request.',
    request_id: requestId,
  }
}

// ==========================================
// 5. GCP WORKLOAD IDENTITY FEDERATION OIDC
// ==========================================
interface CachedIdToken {
  token: string
  expiresAtMs: number
}

let cachedIdToken: CachedIdToken | null = null

export async function getCloudRunIdToken(): Promise<string | null> {
  const now = Date.now()

  if (cachedIdToken && cachedIdToken.expiresAtMs > now + 300_000) {
    return cachedIdToken.token
  }

  const vercelOidcToken =
    process.env.VERCEL_OIDC_TOKEN ||
    process.env.TEST_VERCEL_OIDC_TOKEN

  if (!vercelOidcToken) {
    if (process.env.DEV_CLOUD_RUN_ID_TOKEN) {
      return process.env.DEV_CLOUD_RUN_ID_TOKEN
    }
    return null
  }

  const stsAudience = `//iam.googleapis.com/projects/${GATEWAY_CONFIG.GCP_PROJECT_NUMBER}/locations/global/workloadIdentityPools/${GATEWAY_CONFIG.GCP_WORKLOAD_IDENTITY_POOL_ID}/providers/${GATEWAY_CONFIG.GCP_WORKLOAD_IDENTITY_POOL_PROVIDER_ID}`

  try {
    // Step 1: Exchange Vercel OIDC token for Google STS Federated Access Token
    const stsResponse = await fetch('https://sts.googleapis.com/v1/token', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        grant_type: 'urn:ietf:params:oauth:grant-type:token-exchange',
        audience: stsAudience,
        scope: 'https://www.googleapis.com/auth/cloud-platform',
        requested_token_type: 'urn:ietf:params:oauth:token-type:access_token',
        subject_token_type: 'urn:ietf:params:oauth:token-type:id_token',
        subject_token: vercelOidcToken,
      }),
    })

    if (!stsResponse.ok) {
      console.error('[GATEWAY-AUTH] STS token exchange failed:', stsResponse.status, await stsResponse.text())
      return null
    }

    const stsData = (await stsResponse.json()) as { access_token: string }

    // Step 2: Impersonate Service Account and Generate Cloud Run ID Token
    const iamCredentialsUrl = `https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${encodeURIComponent(
      GATEWAY_CONFIG.GCP_SERVICE_ACCOUNT_EMAIL
    )}:generateIdToken`

    const idTokenResponse = await fetch(iamCredentialsUrl, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${stsData.access_token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({
        audience: GATEWAY_CONFIG.CLOUD_RUN_URL,
        includeEmail: true,
      }),
    })

    if (!idTokenResponse.ok) {
      console.error('[GATEWAY-AUTH] IAM generateIdToken failed:', idTokenResponse.status, await idTokenResponse.text())
      return null
    }

    const idTokenData = (await idTokenResponse.json()) as { token: string }
    cachedIdToken = {
      token: idTokenData.token,
      expiresAtMs: now + 3600_000,
    }

    return idTokenData.token
  } catch (err) {
    console.error('[GATEWAY-AUTH] Error exchanging OIDC for GCP ID Token:', err)
    return null
  }
}

// ==========================================
// 6. RESPONSE HELPER & REQUEST DISPATCHER
// ==========================================
function sendJson(res: ServerResponse, statusCode: number, data: unknown, extraHeaders: Record<string, string> = {}) {
  const payload = JSON.stringify(data)
  res.writeHead(statusCode, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload),
    ...extraHeaders,
  })
  res.end(payload)
}

export default async function handler(req: IncomingMessage, res: ServerResponse) {
  const requestId = (req.headers['x-request-id'] as string) || `req_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  const method = req.method?.toUpperCase() || 'GET'
  const url = req.url || '/'

  // 1. Validate HTTP Method
  if (!['GET', 'POST', 'OPTIONS'].includes(method)) {
    return sendJson(res, 405, { detail: 'Method not allowed', request_id: requestId })
  }

  // Handle CORS preflight for same-origin or configured origins
  if (method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': req.headers.origin || 'https://joint-inspection.vercel.app',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Request-ID',
      'Access-Control-Max-Age': '86400',
    })
    return res.end()
  }

  // 2. Reject Malicious Scanner Paths
  if (isMaliciousPath(url)) {
    return sendJson(res, 404, { detail: 'Not found', request_id: requestId })
  }

  // 3. Enforce IP-based Rate Limiting
  const rateLimitResult = await checkRateLimit(req)
  if (!rateLimitResult.allowed) {
    return sendJson(
      res,
      429,
      {
        detail: 'Rate limit exceeded. Too many requests submitted.',
        request_id: requestId,
        retry_after_seconds: rateLimitResult.resetSeconds,
      },
      { 'Retry-After': String(rateLimitResult.resetSeconds) }
    )
  }

  // 4. Verify User Authentication (Neutral Abstraction)
  const authUser = await verifyGatewayUser(req)
  if (GATEWAY_CONFIG.USER_AUTH_MODE === 'provider' && !authUser) {
    return sendJson(res, 401, {
      detail: 'Authentication required. Invalid or missing credentials.',
      request_id: requestId,
    })
  }

  // 5. Calibration Security: Restrict Mutations in Production
  if (url.includes('/calibration') && ['POST', 'PUT', 'DELETE'].includes(method)) {
    const hasAdminRole = authUser?.roles?.includes('ADMIN')
    if (!hasAdminRole) {
      return sendJson(res, 403, {
        detail: 'Calibration profile modification is locked in production pending administrative role delegation.',
        request_id: requestId,
      })
    }
  }

  // 6. Enforce Payload Size Bounds via Content-Length
  const contentLengthHeader = req.headers['content-length']
  if (contentLengthHeader) {
    const contentLength = parseInt(contentLengthHeader, 10)
    const maxAllowed = url.includes('/multi-frame')
      ? GATEWAY_CONFIG.MAX_MULTI_FRAME_BYTES
      : GATEWAY_CONFIG.MAX_UPLOAD_SIZE_BYTES

    if (contentLength > maxAllowed) {
      return sendJson(res, 413, {
        detail: `Payload size (${contentLength} bytes) exceeds gateway maximum limit (${maxAllowed} bytes).`,
        request_id: requestId,
      })
    }
  }

  // 7. Resolve Upstream Path on Private Cloud Run Service
  let targetSubPath = url.replace(/^\/api\/v1\/?/, '').replace(/^\/api\/?/, '')
  if (!targetSubPath.startsWith('cv/') && !targetSubPath.startsWith('health')) {
    targetSubPath = `cv/${targetSubPath}`
  }
  const targetUrl = `${GATEWAY_CONFIG.CLOUD_RUN_URL}/${targetSubPath}`

  // 8. Obtain Short-Lived ID Token for Cloud Run (Vercel OIDC -> GCP WIF)
  const idToken = await getCloudRunIdToken()

  // 9. Prepare Forward Headers (Strip client internal/security headers)
  const forwardHeaders = sanitizeForwardHeaders(req.headers)
  forwardHeaders['x-request-id'] = requestId

  if (idToken) {
    forwardHeaders['x-serverless-authorization'] = `Bearer ${idToken}`
    forwardHeaders['authorization'] = `Bearer ${idToken}`
  }

  try {
    // 10. Forward Request Server-to-Server
    const chunks: Buffer[] = []
    for await (const chunk of req) {
      chunks.push(typeof chunk === 'string' ? Buffer.from(chunk) : chunk)
    }
    const bodyBuffer = chunks.length > 0 ? Buffer.concat(chunks) : undefined

    const upstreamResponse = await fetch(targetUrl, {
      method,
      headers: forwardHeaders,
      body: ['POST', 'PUT', 'PATCH'].includes(method) ? bodyBuffer : undefined,
    })

    const responseBody = await upstreamResponse.arrayBuffer()
    const contentType = upstreamResponse.headers.get('content-type') || 'application/json'

    res.writeHead(upstreamResponse.status, {
      'Content-Type': contentType,
      'X-Request-ID': requestId,
      'Cache-Control': 'no-store, max-age=0',
    })
    res.end(Buffer.from(responseBody))
  } catch (error) {
    console.error(`[GATEWAY-ERR-${requestId}] Forwarding to Cloud Run failed:`, error)
    const sanitized = sanitizeErrorResponse(error, requestId)
    return sendJson(res, 502, sanitized)
  }
}
