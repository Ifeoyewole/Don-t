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
import { GATEWAY_CONFIG } from '../../lib/config'
import { verifyGatewayUser } from '../../lib/auth-abstraction'
import { checkRateLimit, getRouteCategory } from '../../lib/rate-limiter'
import { getCloudRunIdToken } from '../../lib/gcp-oidc'
import {
  isMaliciousPath,
  sanitizeForwardHeaders,
  sanitizeErrorResponse,
} from '../../lib/gateway-guard'

export const config = {
  api: {
    bodyParser: false, // Stream raw multipart payloads directly
  },
}

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
    const hasAdminRole = authUser?.roles?.includes('ADMIN') || authUser?.roles?.includes('CALIBRATION_MANAGER')
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
  // Map /api/v1/cv/... -> Cloud Run /cv/... (or /api/v1/cv/...)
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
    // Cloud Run accepts X-Serverless-Authorization natively
    forwardHeaders['x-serverless-authorization'] = `Bearer ${idToken}`
    forwardHeaders['authorization'] = `Bearer ${idToken}`
  }

  try {
    // 10. Forward Request Server-to-Server
    // Buffer body for Node fetch dispatch
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
