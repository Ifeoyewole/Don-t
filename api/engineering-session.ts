import { createHash, randomBytes } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { authenticated, COOKIE, equal, sameOrigin, SESSION_SECONDS, sign } from './_lib/operator-session.js'
import { readStreamWithLimit, PayloadTooLargeError } from './_lib/gateway-guard.js'
import { checkRateLimit } from './_lib/rate-limiter.js'

/** Existing operator credentials; inspection access only, no operations proxy. */
export default async function handler(req: IncomingMessage, res: ServerResponse) {
  const send = (status: number, body: unknown) => {
    res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', Vary: 'Cookie' })
    res.end(JSON.stringify(body))
  }
  if (req.method === 'GET') return send(200, { authenticated: authenticated(req) })
  if (req.method !== 'POST') return send(405, { error: 'Method not allowed' })
  if (!sameOrigin(req)) return send(403, { error: 'Same-origin sign-in required' })
  const action = new URL(req.url || '/', 'https://localhost').searchParams.get('action')
  if (action === 'logout') {
    res.setHeader('Set-Cookie', `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict`)
    return send(200, { authenticated: false })
  }
  if (action !== 'login') return send(405, { error: 'Operation is not allowed' })
  if (!(await checkRateLimit(req, 'validation')).allowed) return send(429, { error: 'Sign-in limit reached' })
  if (!process.env.CODE_ACCESS_PASSWORD || !process.env.CODE_SESSION_SECRET) return send(503, { error: 'Operator authentication is not configured' })
  try {
    const input = JSON.parse((await readStreamWithLimit(req, 8192)).toString('utf8'))
    if (typeof input?.password !== 'string') return send(400, { error: 'Invalid sign-in request' })
    const actual = createHash('sha256').update(input.password).digest('hex')
    const expected = createHash('sha256').update(process.env.CODE_ACCESS_PASSWORD).digest('hex')
    if (!equal(actual, expected)) return send(401, { error: 'Invalid operator credentials' })
    const value = `${Math.floor(Date.now()/1000)+SESSION_SECONDS}.${randomBytes(16).toString('base64url')}`
    res.setHeader('Set-Cookie', `${COOKIE}=${value}.${sign(value)}; Path=/; Max-Age=${SESSION_SECONDS}; HttpOnly; Secure; SameSite=Strict`)
    return send(200, { authenticated: true })
  } catch (error) {
    return send(error instanceof PayloadTooLargeError ? 413 : 400, { error: 'Invalid sign-in request' })
  }
}
