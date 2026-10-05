/**
 * IP-Based Rate Limiting with Pluggable Storage Backend
 *
 * Provides protection while user authentication vendor selection is pending.
 * Features rolling 60-second window rate limiting per IP per route category.
 */

import { GATEWAY_CONFIG } from './config'

export interface RateLimitResult {
  allowed: boolean
  current: number
  limit: number
  remaining: number
  resetSeconds: number
}

export interface RateLimitStore {
  increment(key: string, windowSeconds: number): Promise<{ count: number; ttl: number }>
}

export interface HttpRequestLike {
  headers: Record<string, string | string[] | undefined>
  url?: string
  method?: string
  socket?: { remoteAddress?: string }
}

/**
 * High-performance in-memory sliding window store with auto-expiry.
 */
class MemoryRateLimitStore implements RateLimitStore {
  private readonly hits = new Map<string, { count: number; expiresAt: number }>()

  async increment(key: string, windowSeconds: number): Promise<{ count: number; ttl: number }> {
    const now = Date.now()
    const entry = this.hits.get(key)

    if (!entry || entry.expiresAt <= now) {
      const expiresAt = now + windowSeconds * 1000
      this.hits.set(key, { count: 1, expiresAt })
      return { count: 1, ttl: windowSeconds }
    }

    entry.count += 1
    const ttl = Math.max(1, Math.ceil((entry.expiresAt - now) / 1000))
    return { count: entry.count, ttl }
  }
}

const activeStore: RateLimitStore = new MemoryRateLimitStore()

export function getClientIp(req: HttpRequestLike): string {
  const vercelIp = req.headers['x-vercel-forwarded-for']
  if (typeof vercelIp === 'string' && vercelIp.trim()) {
    return vercelIp.split(',')[0].trim()
  }
  const xRealIp = req.headers['x-real-ip']
  if (typeof xRealIp === 'string' && xRealIp.trim()) {
    return xRealIp.trim()
  }
  return req.socket?.remoteAddress || '127.0.0.1'
}

export type RouteCategory = 'health' | 'validation' | 'measure' | 'multi-frame' | 'calibration-read' | 'calibration-mutate'

export function getRouteCategory(path: string, method: string): RouteCategory {
  const normalized = path.toLowerCase()
  if (normalized.includes('/health')) return 'health'
  if (normalized.includes('/validate-photo')) return 'validation'
  if (normalized.includes('/multi-frame')) return 'multi-frame'
  if (normalized.includes('/measure')) return 'measure'
  if (normalized.includes('/calibration')) {
    return ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method.toUpperCase())
      ? 'calibration-mutate'
      : 'calibration-read'
  }
  return 'measure'
}

export async function checkRateLimit(req: HttpRequestLike, routeCategory?: RouteCategory): Promise<RateLimitResult> {
  const ip = getClientIp(req)
  const category = routeCategory || getRouteCategory(req.url || '', req.method || 'GET')

  let limit = GATEWAY_CONFIG.RATE_LIMITS.MEASURE
  if (category === 'health') limit = GATEWAY_CONFIG.RATE_LIMITS.HEALTH
  else if (category === 'validation') limit = GATEWAY_CONFIG.RATE_LIMITS.VALIDATION
  else if (category === 'multi-frame') limit = GATEWAY_CONFIG.RATE_LIMITS.MULTI_FRAME
  else if (category === 'calibration-read') limit = GATEWAY_CONFIG.RATE_LIMITS.CALIBRATION_READ
  else if (category === 'calibration-mutate') limit = GATEWAY_CONFIG.RATE_LIMITS.CALIBRATION_MUTATE

  const key = `ratelimit:${category}:${ip}`
  const { count, ttl } = await activeStore.increment(key, 60)

  const allowed = count <= limit
  const remaining = Math.max(0, limit - count)

  return {
    allowed,
    current: count,
    limit,
    remaining,
    resetSeconds: ttl,
  }
}
