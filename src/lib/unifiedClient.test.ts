import { afterEach, describe, expect, it, vi } from 'vitest'
import { requestUnified } from './unifiedClient'

afterEach(() => vi.unstubAllGlobals())
describe('unified response identity', () => {
  it('rejects a report for different original bytes', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok:true, json:async()=>({image_sha256:'wrong', decision:'REVIEW_REQUIRED', research_only:true, physical_gap_mm:null, regions:[]})}))
    await expect(requestUnified(new Blob(['original']), {})).rejects.toThrow('identity')
  })
  it('does not retry failed inference', async () => {
    const call = vi.fn().mockResolvedValue({ok:false, status:503});vi.stubGlobal('fetch', call)
    await expect(requestUnified(new Blob(['original']), {})).rejects.toThrow('no automatic retry')
    expect(call).toHaveBeenCalledTimes(1)
  })
  it('rejects unbounded uploads before calling the protected route', async () => {
    const call=vi.fn();vi.stubGlobal('fetch',call)
    await expect(requestUnified(new Blob([new Uint8Array(3*1024*1024+1)]), {})).rejects.toThrow('3 MiB')
    expect(call).not.toHaveBeenCalled()
  })
})
