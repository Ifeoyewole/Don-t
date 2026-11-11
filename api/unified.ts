/** No-sign-in PREVIEW website -> private IAM-authenticated, quota-metered worker. */
import type { IncomingMessage, ServerResponse } from 'node:http'
import { getCloudRunIdToken } from './_lib/gcp-oidc.js'
import { checkRateLimit } from './_lib/rate-limiter.js'
import { readStreamWithLimit, PayloadTooLargeError } from './_lib/gateway-guard.js'

export default async function unified(req: IncomingMessage, res: ServerResponse) {
  const send = (status: number, body: unknown) => {
    res.writeHead(status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', Vary: 'Cookie', 'X-Content-Type-Options': 'nosniff' })
    res.end(JSON.stringify(body))
  }
  if (!['GET', 'POST'].includes(req.method || '')) return send(405, { detail: 'Method not allowed' })
  if (process.env.UNIFIED_ENGINEERING_PREVIEW_ENABLED !== 'true') return send(404, { available: false })
  if (process.env.UNIFIED_PREVIEW_MODE !== 'PREVIEW') return send(503, {available:false, detail:'Engineering preview is paused'})
  const url = process.env.UNIFIED_PREVIEW_URL?.replace(/\/$/, '')
  if (!url || !/^https:\/\/[a-z0-9-]+\.[a-z0-9.-]*run\.app$/.test(url)) return send(503, { detail: 'Private unified worker is not configured', available: false })
  const action = new URL(req.url || '/api/unified','https://localhost').searchParams.get('action') || 'inspect'
  const routes: Record<string,string> = {inspect:'unified',suggestions:'context-suggestions',calibration:'check-reference'}
  if (!routes[action]) return send(404,{detail:'Unknown inspection operation'})
  if (req.method === 'GET') return send(200, { available: true, mode: 'PREVIEW', user_sign_in_required: false, max_file_bytes: 3*1024*1024 })
  const origin = req.headers.origin
  const authority = req.headers.host ?? req.headers[':authority']
  let sameOrigin = false
  try { sameOrigin = Boolean(origin && typeof authority === 'string' && new URL(origin).host === authority) } catch { /* reject malformed origin */ }
  if (!sameOrigin) return send(403, { detail: 'Same-origin engineering request required' })
  const rate = await checkRateLimit(req, action === 'inspect' ? 'multi-frame' : action === 'calibration' ? 'calibration-read' : 'validation')
  if (!rate.allowed) return send(429, { detail: 'Engineering preview request limit reached; no automatic retry.' })
  const contentType = req.headers['content-type'] || ''
  if (!(action === 'calibration' ? contentType.startsWith('application/json') : contentType.startsWith('multipart/form-data;'))) return send(415, { detail: 'Supported inspection request body required' })
  try {
    const bytes = await readStreamWithLimit(req, action === 'calibration' ? 16*1024 : 4*1024*1024)
    const token = await getCloudRunIdToken(url)
    if (!token) return send(503, { detail: 'Private worker identity unavailable' })
    const response = await fetch(url+'/api/v1/cv/sewer-research/'+routes[action], {
      method: 'POST', headers: { Authorization: 'Bearer '+token, 'Content-Type': contentType },
      body: new Uint8Array(bytes), signal: AbortSignal.timeout(240_000), redirect: 'error',
    })
    if (!response.ok) return send(response.status, { detail: 'Inspection service or research spending allowance unavailable. No automatic retry.' })
    const data = await response.json()
    return send(200, data)
  } catch (error) {
    return send(error instanceof PayloadTooLargeError ? 413 : 502, { detail: 'Unified preview request failed. No automatic retry.' })
  }
}
