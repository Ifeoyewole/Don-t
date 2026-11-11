import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { Readable } from 'node:stream'
import type { IncomingMessage, ServerResponse } from 'node:http'
import session from '../../api/engineering-session'
import retired from '../../api/code'
import { authenticated } from '../../api/_lib/operator-session'

vi.mock('../../api/_lib/rate-limiter', () => ({ checkRateLimit: vi.fn(async () => ({ allowed: true })) }))
beforeEach(() => { vi.stubEnv('CODE_SESSION_SECRET', 'synthetic-session-only'); vi.stubEnv('CODE_ACCESS_PASSWORD', 'synthetic-password') })
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals() })
async function invoke(action: string, password: string, origin = 'https://inspection.test') {
  const req = Object.assign(Readable.from([JSON.stringify({ password })]), { method: 'POST', url: '/api/engineering-session?action='+action,
    headers: { origin, ':authority': 'inspection.test' } }) as unknown as IncomingMessage
  let status = 0; let cookie = ''
  const res = { writeHead: (s: number) => { status = s }, end: () => {}, setHeader: (name: string, value: string) => { if (name === 'Set-Cookie') cookie = value } } as unknown as ServerResponse
  await session(req, res)
  return { status, cookie }
}
it('moves sign-in to inspections while preserving the existing signed Secure session', async () => {
  const result = await invoke('login', 'synthetic-password')
  expect(result.status).toBe(200)
  expect(result.cookie).toContain('HttpOnly; Secure; SameSite=Strict')
  expect(authenticated({ headers: { cookie: result.cookie } } as IncomingMessage)).toBe(true)
  expect((await invoke('logout', '')).cookie).toContain('Max-Age=0')
})
it('rejects incorrect credentials and cross-origin login without issuing a session', async () => {
  expect(await invoke('login', 'wrong')).toEqual({ status: 401, cookie: '' })
  expect(await invoke('login', 'synthetic-password', 'https://foreign.test')).toEqual({ status: 403, cookie: '' })
  expect(await invoke('login', 'synthetic-password', '')).toEqual({ status: 403, cookie: '' })
})
it('retires all console commands without contacting GitHub or GCP', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  for (const action of ['login', 'run', 'command', 'github_dispatch', 'status']) {
    let status = 0
    retired({ method: 'POST', url: '/api/code?action='+action } as IncomingMessage,
      { writeHead: (s: number) => { status = s }, end: () => {} } as unknown as ServerResponse)
    expect(status).toBe(410)
  }
  expect(fetch).not.toHaveBeenCalled()
})
