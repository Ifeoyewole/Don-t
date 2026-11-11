import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { Readable } from 'node:stream'
import { createHmac } from 'node:crypto'
import type { IncomingMessage, ServerResponse } from 'node:http'
import handler from '../../api/unified'

vi.mock('../../api/_lib/gcp-oidc', () => ({getCloudRunIdToken: vi.fn(async () => 'synthetic-id-token')}))
vi.mock('../../api/_lib/rate-limiter', () => ({checkRateLimit: vi.fn(async () => ({allowed:true}))}))
beforeEach(() => {
  vi.stubEnv('UNIFIED_ENGINEERING_PREVIEW_ENABLED','true');vi.stubEnv('UNIFIED_PREVIEW_URL','https://preview-test.a.run.app');vi.stubEnv('CODE_SESSION_SECRET','synthetic-session-key-only')
})
afterEach(() => {vi.unstubAllEnvs();vi.unstubAllGlobals()})
function session() {
  const value = `${Math.floor(Date.now()/1000)+600}.test-nonce`
  return '__Host-jointinspect-code='+value+'.'+createHmac('sha256',process.env.CODE_SESSION_SECRET!).update(value).digest('base64url')
}
async function invoke(method: string, headers: Record<string,string>) {
  const req=Object.assign(Readable.from([Buffer.from('bounded test form')]),{method, headers}) as unknown as IncomingMessage
  let status=0, body=''
  const res={writeHead: (code:number)=>{status=code}, end:(value:string)=>{body=value}} as unknown as ServerResponse
  await handler(req,res)
  return {status,body:JSON.parse(body)}
}
it('never exposes the research worker to anonymous product users', async()=>{
  expect((await invoke('GET',{})).status).toBe(401)
  vi.stubEnv('UNIFIED_ENGINEERING_PREVIEW_ENABLED','false')
  expect((await invoke('GET',{cookie:session()})).status).toBe(404)
})
it('rejects cross-origin and malformed-origin posts before requesting a cloud identity',async()=>{
  for(const origin of ['https://foreign.test','not a URL']) {
    expect((await invoke('POST',{cookie:session(),host:'jointinspect.test',origin})).status).toBe(403)
  }
})
it('recognizes HTTP/2 authority without weakening same-origin enforcement',async()=>{
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({research_only:true})});vi.stubGlobal('fetch',fetch)
  const result=await invoke('POST',{cookie:session(),':authority':'jointinspect.test',origin:'https://jointinspect.test','content-type':'multipart/form-data; boundary=test'})
  expect(result.status).toBe(200)
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer synthetic-id-token')
})
it('does not leak internal provider errors or retry failed requests',async()=>{
  const fetch=vi.fn().mockRejectedValue(new Error('private provider detail'));vi.stubGlobal('fetch',fetch)
  const result=await invoke('POST',{cookie:session(),host:'jointinspect.test',origin:'https://jointinspect.test','content-type':'multipart/form-data; boundary=test'})
  expect(result.status).toBe(502);expect(JSON.stringify(result.body)).not.toContain('private provider detail');expect(fetch).toHaveBeenCalledTimes(1)
})
