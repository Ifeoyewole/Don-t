import { createHash, createHmac, randomBytes, timingSafeEqual } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { getCloudRunIdToken } from './_lib/gcp-oidc.ts'

const COOKIE = '__Host-jointinspect-code'
const SESSION_SECONDS = 8 * 60 * 60
const CONTROLLER_URL = (process.env.GPU_CONTROLLER_URL || '').replace(/\/$/, '')
type Payload = Record<string, unknown>

function send(res: ServerResponse, status: number, body: Payload) {
  const data = JSON.stringify(body)
  res.writeHead(status, { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(data), 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' })
  res.end(data)
}

async function body(req: IncomingMessage): Promise<Payload> {
  const chunks: Buffer[] = []
  let size = 0
  for await (const chunk of req) {
    const value = Buffer.from(chunk)
    size += value.length
    if (size > 8192) throw new Error('Request too large')
    chunks.push(value)
  }
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) as Payload : {}
}

function equal(left: string, right: string) {
  const a = Buffer.from(left)
  const b = Buffer.from(right)
  return a.length === b.length && timingSafeEqual(a, b)
}

function sign(value: string) {
  return createHmac('sha256', process.env.CODE_SESSION_SECRET || '').update(value).digest('base64url')
}

function authenticated(req: IncomingMessage) {
  if (!process.env.CODE_SESSION_SECRET) return false
  const raw = req.headers.cookie?.split(';').map((item) => item.trim()).find((item) => item.startsWith(`${COOKIE}=`))?.slice(COOKIE.length + 1)
  const parts = raw?.split('.') || []
  if (parts.length !== 3) return false
  const value = `${parts[0]}.${parts[1]}`
  return Number(parts[0]) > Date.now() / 1000 && equal(parts[2], sign(value))
}

function sameOrigin(req: IncomingMessage) {
  if (!req.headers.origin || !req.headers.host) return true
  try { return new URL(req.headers.origin).host === req.headers.host } catch { return false }
}

async function callController(path: '/status' | '/report' | '/run', method: 'GET' | 'POST') {
  if (!CONTROLLER_URL) throw new Error('GPU_CONTROLLER_URL is not configured')
  const token = await getCloudRunIdToken(CONTROLLER_URL)
  if (!token) throw new Error('Vercel workload identity is unavailable')
  const response = await fetch(`${CONTROLLER_URL}${path}`, { method, headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' }, signal: AbortSignal.timeout(25_000) })
  const text = await response.text()
  let payload: Payload
  try { payload = JSON.parse(text) as Payload } catch { payload = { error: 'Controller returned an invalid response' } }
  return { status: response.status, payload }
}

export default async function handler(req: IncomingMessage, res: ServerResponse) {
  res.setHeader('Vary', 'Cookie')
  if (!sameOrigin(req)) return send(res, 403, { error: 'Cross-origin request rejected' })
  const action = new URL(req.url || '/api/code', `https://${req.headers.host || 'localhost'}`).searchParams.get('action') || 'status'

  if (action === 'login' && req.method === 'POST') {
    if (!process.env.CODE_ACCESS_PASSWORD || !process.env.CODE_SESSION_SECRET) return send(res, 503, { error: 'Operator authentication is not configured' })
    try {
      const supplied = String((await body(req)).password || '')
      const actual = createHash('sha256').update(supplied).digest('hex')
      const expected = createHash('sha256').update(process.env.CODE_ACCESS_PASSWORD).digest('hex')
      if (!equal(actual, expected)) return send(res, 401, { error: 'Invalid operator credentials' })
      const value = `${Math.floor(Date.now() / 1000) + SESSION_SECONDS}.${randomBytes(16).toString('base64url')}`
      res.setHeader('Set-Cookie', `${COOKIE}=${value}.${sign(value)}; Path=/; Max-Age=${SESSION_SECONDS}; HttpOnly; Secure; SameSite=Strict`)
      return send(res, 200, { authenticated: true })
    } catch { return send(res, 400, { error: 'Invalid login request' }) }
  }
  if (action === 'logout' && req.method === 'POST') {
    res.setHeader('Set-Cookie', `${COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict`)
    return send(res, 200, { authenticated: false })
  }
  if (!authenticated(req)) return send(res, 401, { authenticated: false, error: 'Operator authentication required' })

  const allowed = { status: ['/status', 'GET'], report: ['/report', 'GET'], run: ['/run', 'POST'] } as const
  const target = allowed[action as keyof typeof allowed]
  if (!target || req.method !== target[1]) return send(res, 405, { error: 'Operation is not allowed' })
  try {
    const result = await callController(target[0], target[1])
    return send(res, result.status, result.payload)
  } catch (error) {
    return send(res, 502, { error: error instanceof Error ? error.message : 'Controller request failed' })
  }
}
