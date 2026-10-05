/**
 * Vercel Secure API Gateway Route Handler for Computer Vision Endpoints
 *
 * Implements perimeter security (Consolidated Architecture):
 * 1. Strict Method and Path Allowlist Matrix (Phase 3)
 * 2. Route-based sliding window rate limiting (Phase 8)
 * 3. User authentication verification (pluggable abstraction, Phase 4)
 * 4. Inbound Header Security: strips client Authorization & internal headers (Phase 6)
 * 5. Acquires Google ID token via Vercel OIDC -> Workload Identity Federation (WIF, Phase 5)
 * 6. True streaming bytes-read ceiling enforcement (Memory DoS defense, Phase 9)
 * 7. Explicit production CORS with Vary: Origin (Phase 10)
 * 8. Minimal Public Liveness vs Authenticated Diagnostics (Phase 11)
 * 9. Calibration Access & Mutation Lock (Phase 12)
 * 10. Sanitizes all error responses returned to the client (Phase 34)
 */

import type { IncomingMessage, ServerResponse } from 'node:http'
import { ALLOWED_ORIGINS, GATEWAY_CONFIG } from '../../_lib/config'
import { verifyGatewayUser } from '../../_lib/auth-abstraction'
import { checkRateLimit } from '../../_lib/rate-limiter'
import {
  isMaliciousPath,
  normalizeRequestId,
  readStreamWithLimit,
  resolveGatewayRoute,
  sanitizeErrorResponse,
  sanitizeForwardHeaders,
  PayloadTooLargeError,
} from '../../_lib/gateway-guard'
import { getCloudRunIdToken } from '../../_lib/gcp-oidc'

function sendJson(
  res: ServerResponse,
  statusCode: number,
  data: unknown,
  extraHeaders: Record<string, string> = {}
) {
  const payload = JSON.stringify(data)
  res.writeHead(statusCode, {
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload),
    ...extraHeaders,
  })
  res.end(payload)
}

function getMatchedOrigin(req: IncomingMessage): string | null {
  const rawOrigin = req.headers.origin
  if (!rawOrigin || typeof rawOrigin !== 'string') return null
  const cleanOrigin = rawOrigin.trim()
  if (ALLOWED_ORIGINS.includes(cleanOrigin as typeof ALLOWED_ORIGINS[number])) {
    return cleanOrigin
  }
  return null
}

export default async function handler(req: IncomingMessage, res: ServerResponse) {
  let requestId = 'unknown'
  const corsHeaders: Record<string, string> = {
    'Vary': 'Origin',
  }
  try {
    requestId = normalizeRequestId(req.headers['x-request-id'])
    const method = req.method?.toUpperCase() || 'GET'
    const url = req.url || '/'
    const matchedOrigin = getMatchedOrigin(req)

    // 1. CORS Preflight & Origin Handling
  if (matchedOrigin) {
    corsHeaders['Access-Control-Allow-Origin'] = matchedOrigin
    corsHeaders['Access-Control-Allow-Credentials'] = 'true'
  }

  if (method === 'OPTIONS') {
    if (!matchedOrigin) {
      return sendJson(res, 403, { detail: 'Forbidden origin', request_id: requestId }, corsHeaders)
    }
    res.writeHead(204, {
      ...corsHeaders,
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Request-ID',
      'Access-Control-Max-Age': '86400',
    })
    return res.end()
  }

  // 2. Reject Malicious Scanner Paths
  if (isMaliciousPath(url)) {
    return sendJson(res, 404, { detail: 'Not found', request_id: requestId }, corsHeaders)
  }

  // 3. Strict Gateway Route Matrix Resolution (Phase 3)
  const route = resolveGatewayRoute(url, method)
  if (!route.allowed) {
    return sendJson(
      res,
      route.status,
      {
        detail: route.status === 405 ? 'Method not allowed' : 'Not found',
        request_id: requestId,
      },
      corsHeaders
    )
  }

  // 4. IP-Based Sliding Window Rate Limiting (Phase 8)
  const rateLimitResult = await checkRateLimit(req, route.routeCategory)
  if (!rateLimitResult.allowed) {
    return sendJson(
      res,
      429,
      {
        detail: 'Rate limit exceeded. Too many requests submitted.',
        request_id: requestId,
        retry_after_seconds: rateLimitResult.resetSeconds,
      },
      {
        ...corsHeaders,
        'Retry-After': String(rateLimitResult.resetSeconds),
      }
    )
  }

  // 5. User Authentication & Authorization (Phase 4 & 12)
  const authUser = await verifyGatewayUser(req)
  if (GATEWAY_CONFIG.USER_AUTH_MODE === 'provider' && !authUser) {
    return sendJson(
      res,
      401,
      {
        detail: 'Authentication required. Invalid or missing credentials.',
        request_id: requestId,
      },
      corsHeaders
    )
  }

  if (route.requiresAuth && !authUser) {
    return sendJson(
      res,
      401,
      {
        detail: 'Authentication required to access calibration profiles.',
        request_id: requestId,
      },
      corsHeaders
    )
  }

  if (route.requiresAdmin) {
    const hasAdminRole = authUser?.roles?.includes('ADMIN')
    if (!hasAdminRole) {
      return sendJson(
        res,
        403,
        {
          detail: 'Administrative authority required for calibration mutation.',
          request_id: requestId,
        },
        corsHeaders
      )
    }
  }

  // 6. Minimal Public Health vs Authenticated Diagnostics (Phase 11)
  const [, rawQuery] = url.split('?')
  const qParams = new URLSearchParams(rawQuery || '')
  qParams.delete('...route')
  qParams.delete('route')

  if (route.targetPath === 'api/v1/cv/health') {
    const wantsDiagnostics = qParams.get('diagnostics') === 'true'
    const isEngineerOrAdmin =
      authUser?.roles?.includes('ENGINEER') || authUser?.roles?.includes('ADMIN')

    // If public liveness probe without diagnostic authorization, return minimal response directly
    if (!wantsDiagnostics || !isEngineerOrAdmin) {
      return sendJson(res, 200, { status: 'ok' }, corsHeaders)
    }
  }

  // 7. Memory DoS Defense: Enforce Streaming Bytes-Read Ceiling (Phase 9)
  const maxAllowedBytes =
    route.routeCategory === 'multi-frame'
      ? GATEWAY_CONFIG.MAX_MULTI_FRAME_BYTES
      : GATEWAY_CONFIG.MAX_UPLOAD_SIZE_BYTES

  let bodyBuffer: Buffer | undefined
  if (['POST', 'PUT', 'PATCH'].includes(method)) {
    try {
      bodyBuffer = await readStreamWithLimit(req, maxAllowedBytes)
    } catch (err) {
      if (err instanceof PayloadTooLargeError) {
        return sendJson(
          res,
          413,
          {
            detail: err.message,
            request_id: requestId,
          },
          corsHeaders
        )
      }
      return sendJson(res, 400, { detail: 'Failed reading request payload', request_id: requestId }, corsHeaders)
    }
  }

  // 8. Workload Identity Federation (WIF): Acquire Cloud Run ID Token
  const idToken = await getCloudRunIdToken()

  // 9. Inbound Header Security: Strip Client Authorization & Internal Headers (Phase 6)
  const forwardHeaders = sanitizeForwardHeaders(req.headers)
  forwardHeaders['x-request-id'] = requestId

  if (idToken) {
    forwardHeaders['x-serverless-authorization'] = `Bearer ${idToken}`
    forwardHeaders['authorization'] = `Bearer ${idToken}`
  }

  // 10. Forward Request to Private Cloud Run Backend
  const forwardQuery = qParams.toString() ? `?${qParams.toString()}` : ''
  const targetUrl = `${GATEWAY_CONFIG.CLOUD_RUN_URL}/${route.targetPath}${forwardQuery}`

  try {
    const upstreamResponse = await fetch(targetUrl, {
      method,
      headers: forwardHeaders,
      body: bodyBuffer,
    })

    const responseBody = await upstreamResponse.arrayBuffer()
    const contentType = upstreamResponse.headers.get('content-type') || 'application/json'

    res.writeHead(upstreamResponse.status, {
      ...corsHeaders,
      'Content-Type': contentType,
      'X-Request-ID': requestId,
      'Cache-Control': 'no-store, max-age=0',
    })
    res.end(Buffer.from(responseBody))
    } catch (error) {
      console.error(`[GATEWAY-ERR-${requestId}] Upstream invocation failed:`, error)
      const sanitized = sanitizeErrorResponse(error, requestId)
      return sendJson(res, 502, sanitized, corsHeaders)
    }
  } catch (fatalError) {
    console.error(`[GATEWAY-FATAL-${requestId}]`, fatalError)
    return sendJson(res, 500, { detail: 'Gateway Internal Server Error', request_id: requestId }, corsHeaders)
  }
}
