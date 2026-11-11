import { createHmac, timingSafeEqual } from 'node:crypto'
import type { IncomingMessage } from 'node:http'

// Preserve existing signed sessions and server-owned secret configuration.
export const COOKIE = '__Host-jointinspect-code'
export const SESSION_SECONDS = 8 * 60 * 60
export function equal(left: string, right: string) {
  const a = Buffer.from(left)
  const b = Buffer.from(right)
  return a.length === b.length && timingSafeEqual(a, b)
}

export function sign(value: string) {
  return createHmac('sha256', process.env.CODE_SESSION_SECRET || '').update(value).digest('base64url')
}

export function authenticated(req: IncomingMessage) {
  if (!process.env.CODE_SESSION_SECRET) return false
  const raw = req.headers.cookie?.split(';').map((item) => item.trim()).find((item) => item.startsWith(`${COOKIE}=`))?.slice(COOKIE.length + 1)
  const parts = raw?.split('.') || []
  if (parts.length !== 3) return false
  const value = `${parts[0]}.${parts[1]}`
  return Number(parts[0]) > Date.now() / 1000 && equal(parts[2], sign(value))
}

export function sameOrigin(req: IncomingMessage) {
  const authority = req.headers.host ?? req.headers[':authority']
  if (!req.headers.origin || typeof authority !== 'string') return false
  try { return new URL(req.headers.origin).host === authority } catch { return false }
}
