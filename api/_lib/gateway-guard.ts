/**
 * Vercel Secure API Gateway Guard & Request Sanitizer
 *
 * Implements perimeter defense:
 * - Method & Path Allowlist Enforcement (Strict Gateway Route Matrix)
 * - Header stripping (prevents client Authorization and internal header spoofing)
 * - Scanner/bot path blocking
 * - True streaming bytes-read ceiling enforcement (memory DoS defense)
 * - Magic byte inspection
 * - Unified error sanitization
 */

import { randomUUID } from 'node:crypto'

const FORBIDDEN_HEADER_PREFIXES = [
  'authorization',
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

/**
 * Normalize and length-limit incoming request ID (Phase 6).
 */
export function normalizeRequestId(rawId?: string | string[]): string {
  if (typeof rawId === 'string') {
    const trimmed = rawId.trim()
    if (trimmed.length > 0 && trimmed.length <= 64 && /^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      return trimmed
    }
  }
  return `req_${Date.now()}_${randomUUID().slice(0, 8)}`
}

export function sanitizeForwardHeaders(headers: Record<string, string | string[] | undefined>): Record<string, string> {
  const clean: Record<string, string> = {}

  for (const [key, value] of Object.entries(headers)) {
    if (!value || typeof value !== 'string') continue
    const lowerKey = key.toLowerCase()

    // 1. Strip client-supplied Authorization and internal headers
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

export interface RouteResolution {
  allowed: boolean
  status: number
  targetPath?: string
  routeCategory: 'health' | 'validation' | 'measure' | 'multi-frame' | 'calibration-read' | 'calibration-mutate'
  requiresAuth: boolean
  requiresAdmin: boolean
}

/**
 * Strict Method & Path Allowlist Matrix (Phase 3).
 * Rejects unknown paths with 404 and disallowed methods with 405.
 */
export function resolveGatewayRoute(url: string, method: string): RouteResolution {
  const [rawPath] = url.split('?')
  // Normalize path removing duplicate slashes and trailing slashes
  let cleanPath = rawPath.replace(/\/+/g, '/').replace(/\/$/, '')
  if (!cleanPath.startsWith('/')) {
    cleanPath = `/${cleanPath}`
  }

  // Canonical paths may arrive as /api/v1/cv/... or via rewrite as /cv/...
  let subPath = cleanPath
  if (subPath.startsWith('/api/v1/cv')) {
    subPath = subPath.substring('/api/v1/cv'.length)
  } else if (subPath.startsWith('/api/v1')) {
    subPath = subPath.substring('/api/v1'.length)
  } else if (subPath.startsWith('/cv')) {
    subPath = subPath.substring('/cv'.length)
  }

  if (!subPath.startsWith('/')) {
    subPath = `/${subPath}`
  }

  const upperMethod = method.toUpperCase()

  // 1. Health Probe
  if (subPath === '/health') {
    if (upperMethod === 'GET') {
      return {
        allowed: true,
        status: 200,
        targetPath: 'api/v1/cv/health',
        routeCategory: 'health',
        requiresAuth: false,
        requiresAdmin: false,
      }
    }
    return { allowed: false, status: 405, routeCategory: 'health', requiresAuth: false, requiresAdmin: false }
  }

  // 2. Photo Validation Quality Gate
  if (subPath === '/validate-photo') {
    if (upperMethod === 'POST') {
      return {
        allowed: true,
        status: 200,
        targetPath: 'api/v1/cv/validate-photo',
        routeCategory: 'validation',
        requiresAuth: false,
        requiresAdmin: false,
      }
    }
    return { allowed: false, status: 405, routeCategory: 'validation', requiresAuth: false, requiresAdmin: false }
  }

  // 3. Single Frame Measurement
  if (subPath === '/measure') {
    if (upperMethod === 'POST') {
      return {
        allowed: true,
        status: 200,
        targetPath: 'api/v1/cv/measure',
        routeCategory: 'measure',
        requiresAuth: false,
        requiresAdmin: false,
      }
    }
    return { allowed: false, status: 405, routeCategory: 'measure', requiresAuth: false, requiresAdmin: false }
  }

  // 4. Multi-Frame Burst Measurement
  if (subPath === '/measure/multi-frame') {
    if (upperMethod === 'POST') {
      return {
        allowed: true,
        status: 200,
        targetPath: 'api/v1/cv/measure/multi-frame',
        routeCategory: 'multi-frame',
        requiresAuth: false,
        requiresAdmin: false,
      }
    }
    return { allowed: false, status: 405, routeCategory: 'multi-frame', requiresAuth: false, requiresAdmin: false }
  }

  // 5. Calibration Profiles Collection
  if (subPath === '/calibration/profiles') {
    if (upperMethod === 'GET') {
      return {
        allowed: true,
        status: 200,
        targetPath: 'api/v1/cv/calibration/profiles',
        routeCategory: 'calibration-read',
        requiresAuth: true,
        requiresAdmin: false,
      }
    }
    if (upperMethod === 'POST') {
      return {
        allowed: true,
        status: 201,
        targetPath: 'api/v1/cv/calibration/profiles',
        routeCategory: 'calibration-mutate',
        requiresAuth: true,
        requiresAdmin: true,
      }
    }
    return { allowed: false, status: 405, routeCategory: 'calibration-read', requiresAuth: false, requiresAdmin: false }
  }

  // 6. Specific Camera Profile
  const profileMatch = subPath.match(/^\/calibration\/profiles\/([a-zA-Z0-9_-]+)$/)
  if (profileMatch) {
    const cameraId = profileMatch[1]
    if (upperMethod === 'GET') {
      return {
        allowed: true,
        status: 200,
        targetPath: `api/v1/cv/calibration/profiles/${cameraId}`,
        routeCategory: 'calibration-read',
        requiresAuth: true,
        requiresAdmin: false,
      }
    }
    return { allowed: false, status: 405, routeCategory: 'calibration-read', requiresAuth: false, requiresAdmin: false }
  }

  // All other subpaths rejected with 404
  return {
    allowed: false,
    status: 404,
    routeCategory: 'health',
    requiresAuth: false,
    requiresAdmin: false,
  }
}

export class PayloadTooLargeError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'PayloadTooLargeError'
  }
}

/**
 * Stream request body with a hard byte-read ceiling (Phase 9 Memory DoS defense).
 * Immediately terminates reader if cumulative bytes exceed maxBytes.
 */
export async function readStreamWithLimit(
  stream: AsyncIterable<Buffer | string>,
  maxBytes: number
): Promise<Buffer> {
  const chunks: Buffer[] = []
  let totalBytes = 0

  for await (const chunk of stream) {
    const buf = typeof chunk === 'string' ? Buffer.from(chunk) : chunk
    totalBytes += buf.length
    if (totalBytes > maxBytes) {
      throw new PayloadTooLargeError(
        `Payload exceeded real byte limit (${totalBytes} > ${maxBytes} bytes). Transfer aborted.`
      )
    }
    chunks.push(buf)
  }

  return Buffer.concat(chunks)
}

export function validateMagicBytes(buffer: Buffer): boolean {
  if (buffer.length < 4) return false

  // JPEG: FF D8 FF
  if (buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) return true
  // PNG: 89 50 4E 47 0D 0A 1A 0A
  if (
    buffer.length >= 8 &&
    buffer[0] === 0x89 &&
    buffer[1] === 0x50 &&
    buffer[2] === 0x4e &&
    buffer[3] === 0x47 &&
    buffer[4] === 0x0d &&
    buffer[5] === 0x0a &&
    buffer[6] === 0x1a &&
    buffer[7] === 0x0a
  ) {
    return true
  }
  // WebP: 'RIFF' ... 'WEBP'
  if (
    buffer.length >= 12 &&
    buffer.subarray(0, 4).toString('ascii') === 'RIFF' &&
    buffer.subarray(8, 12).toString('ascii') === 'WEBP'
  ) {
    return true
  }

  return false
}

export function sanitizeErrorResponse(_error: unknown, requestId: string): { detail: string; request_id: string } {
  // Never leak stack traces, internal IP addresses, or raw system exceptions to the browser
  return {
    detail: 'An error occurred while processing the inspection request.',
    request_id: requestId,
  }
}
