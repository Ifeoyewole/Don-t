import { afterEach, expect, it, vi } from 'vitest'
import { createHmac } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'
import session from '../../api/engineering-session'
import retired from '../../api/code'
import { authenticated } from '../../api/_lib/operator-session'
afterEach(() => { vi.unstubAllEnvs(); vi.unstubAllGlobals() })
it('keeps existing signed sessions verifiable without a user-facing sign-in flow', () => {
  vi.stubEnv('CODE_SESSION_SECRET', 'synthetic-session-only')
  const value = `${Math.floor(Date.now()/1000)+600}.test`
  const signature = createHmac('sha256', 'synthetic-session-only').update(value).digest('base64url')
  expect(authenticated({headers:{cookie:'__Host-jointinspect-code='+value+'.'+signature}} as IncomingMessage)).toBe(true)
  expect(authenticated({headers:{cookie:'__Host-jointinspect-code='+value+'.tampered'}} as IncomingMessage)).toBe(false)
})
it('retires login and console commands without contacting GitHub or GCP', () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
  for (const handler of [session, retired]) for (const action of ['login', 'run', 'command', 'github_dispatch']) {
    let status = 0
    handler({method:'POST',url:'/?action='+action} as IncomingMessage,
      {writeHead:(s:number)=>{status=s},end:()=>{}} as unknown as ServerResponse)
    expect(status).toBe(410)
  }
  expect(fetch).not.toHaveBeenCalled()
})
