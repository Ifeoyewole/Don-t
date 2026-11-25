import {afterEach,expect,it,vi} from 'vitest'
import {previewFailure,validatePreviewImage} from './previewErrors'
afterEach(()=>vi.unstubAllGlobals())
it('distinguishes invalid images from unavailable AI and budget errors',async()=>{
 expect(await previewFailure({status:422} as Response)).toContain('unsupported')
 expect(await previewFailure({status:503} as Response)).toContain('temporarily unavailable')
 expect(await previewFailure({status:429} as Response)).toContain('allowance')
})
it('rejects 48MP before upload and closes the decoded image',async()=>{
 const close=vi.fn();vi.stubGlobal('createImageBitmap',vi.fn().mockResolvedValue({width:8000,height:6000,close}))
 await expect(validatePreviewImage(new Blob(['test']))).rejects.toThrow('16 megapixels');expect(close).toHaveBeenCalledOnce()
})
