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
it('rejects large PNG dimensions before allocating a bitmap',async()=>{
 const bytes=new Uint8Array(24);const view=new DataView(bytes.buffer)
 view.setUint32(0,0x89504e47);view.setUint32(16,8000);view.setUint32(20,6000)
 const bitmap=vi.fn();vi.stubGlobal('createImageBitmap',bitmap)
 await expect(validatePreviewImage(new Blob([bytes],{type:'image/png'}))).rejects.toThrow('16 megapixels')
 expect(bitmap).not.toHaveBeenCalled()
})
