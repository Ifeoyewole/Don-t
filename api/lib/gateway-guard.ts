/**
 * Vercel Secure API Gateway Guard & Request Sanitizer
 *
 * Implements perimeter defense:
 * - Header stripping (prevents client header spoofing)
 * - Scanner/bot path blocking
 * - Payload size and MIME enforcement
 * - Magic byte inspection
 * - Unified error sanitization
 */

import { GATEWAY_CONFIG } from './config'

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

    // 1. Strip forbidden client-supplied headers
    if (FORBIDDEN_HEADER_PREFIXES.some((prefix) => lowerKey.startsWith(prefix))) {
      continue
    }

    // 2. Discard client-supplied X-Forwarded-For to prevent IP spoofing
    if (lowerKey === 'x-forwarded-for' || lowerKey === 'x-forwarded-host') {
      continue
    }

    // Retain standard operational headers
    clean[key] = value
  }

  return clean
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

export function sanitizeErrorResponse(error: unknown, requestId: string): { detail: string; request_id: string } {
  // Never leak stack traces, internal IP addresses, or raw system exceptions to the browser
  return {
    detail: 'An error occurred while processing the inspection request.',
    request_id: requestId,
  }
}
