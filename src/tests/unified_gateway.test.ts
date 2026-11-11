import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { Readable } from 'node:stream'
import type { IncomingMessage, ServerResponse } from 'node:http'
import handler from '../../api/unified'

vi.mock('../../api/_lib/gcp-oidc', () => ({getCloudRunIdToken: vi.fn(async () => 'synthetic-id-token')}))
vi.mock('../../api/_lib/rate-limiter', () => ({checkRateLimit: vi.fn(async () => ({allowed:true}))}))
beforeEach(() => {
  vi.stubEnv('UNIFIED_ENGINEERING_PREVIEW_ENABLED','true');vi.stubEnv('UNIFIED_PREVIEW_URL','https://preview-test.a.run.app');vi.stubEnv('UNIFIED_PREVIEW_MODE','PREVIEW')
})
afterEach(() => {vi.unstubAllEnvs();vi.unstubAllGlobals();vi.restoreAllMocks()})
async function invoke(method: string, headers: Record<string,string>, url='/api/unified') {
  const req=Object.assign(Readable.from([Buffer.from('bounded test form')]),{method, headers, url}) as unknown as IncomingMessage
  let status=0, body=''
  const res={writeHead: (code:number)=>{status=code}, end:(value:string)=>{body=value}} as unknown as ServerResponse
  await handler(req,res)
  return {status,body:JSON.parse(body)}
}
it('serves no-sign-in PREVIEW and fails closed when disabled or paused', async()=>{
  expect((await invoke('GET',{})).body).toMatchObject({available:true,mode:'PREVIEW',user_sign_in_required:false})
  vi.stubEnv('UNIFIED_PREVIEW_MODE','PRODUCTION')
  expect((await invoke('GET',{})).status).toBe(503)
  vi.stubEnv('UNIFIED_ENGINEERING_PREVIEW_ENABLED','false')
  expect((await invoke('GET',{})).status).toBe(404)
})
it('rejects cross-origin and malformed-origin posts before requesting a cloud identity',async()=>{
  for(const origin of ['https://foreign.test','not a URL']) {
    expect((await invoke('POST',{host:'jointinspect.test',origin})).status).toBe(403)
  }
})
it('recognizes HTTP/2 authority and waits beyond the observed cloud cold-start latency',async()=>{
  const timeout=vi.spyOn(AbortSignal,'timeout')
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({research_only:true})});vi.stubGlobal('fetch',fetch)
  const result=await invoke('POST',{':authority':'jointinspect.test',origin:'https://jointinspect.test','content-type':'multipart/form-data; boundary=test'})
  expect(result.status).toBe(200)
  expect(fetch).toHaveBeenCalledTimes(1)
  expect(fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer synthetic-id-token')
  expect(timeout).toHaveBeenCalledWith(240_000)
})
it('does not leak internal provider errors or retry failed requests',async()=>{
  const fetch=vi.fn().mockRejectedValue(new Error('private provider detail'));vi.stubGlobal('fetch',fetch)
  const result=await invoke('POST',{host:'jointinspect.test',origin:'https://jointinspect.test','content-type':'multipart/form-data; boundary=test'})
  expect(result.status).toBe(502);expect(JSON.stringify(result.body)).not.toContain('private provider detail');expect(fetch).toHaveBeenCalledTimes(1)
})

it('does not depend on an old or future calendar activation date',async()=>{
  vi.stubEnv('UNIFIED_PREVIEW_EXPIRES_UNIX','1')
  vi.stubEnv('UNIFIED_NO_SIGNIN_WINDOW','1')
  for(const now of [1794393096000,4102444800000]) {
    vi.spyOn(Date,'now').mockReturnValue(now)
    expect((await invoke('GET',{})).status).toBe(200)
  }
})
it('enforces rate limits before contacting the private worker',async()=>{
  const {checkRateLimit}=await import('../../api/_lib/rate-limiter')
  vi.mocked(checkRateLimit).mockResolvedValueOnce({allowed:false} as never)
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch)
  const result=await invoke('POST',{host:'jointinspect.test',origin:'https://jointinspect.test','content-type':'multipart/form-data; boundary=test'})
  expect(result.status).toBe(429);expect(fetch).not.toHaveBeenCalled()
})

it('routes editable suggestions and read-only calibration through the private worker',async()=>{
  const fetch=vi.fn().mockResolvedValue({ok:true,json:async()=>({reference_verified:false,status:'CALIBRATION_REQUIRED'})});vi.stubGlobal('fetch',fetch)
  expect((await invoke('POST',{host:'jointinspect.test',origin:'https://jointinspect.test','content-type':'application/json'},'/api/unified?action=calibration')).status).toBe(200)
  expect(fetch.mock.calls[0][0]).toBe('https://preview-test.a.run.app/api/v1/cv/sewer-research/check-reference')
  expect((await invoke('POST',{host:'jointinspect.test',origin:'https://jointinspect.test','content-type':'multipart/form-data; boundary=test'},'/api/unified?action=suggestions')).status).toBe(200)
  expect(fetch.mock.calls[1][0]).toBe('https://preview-test.a.run.app/api/v1/cv/sewer-research/context-suggestions')
  expect(fetch.mock.calls[1][1].headers.Authorization).toBe('Bearer synthetic-id-token')
  expect((await invoke('GET',{},'/api/unified?action=arbitrary-resource')).status).toBe(404)
})
