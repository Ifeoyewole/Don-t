/** Stable public failures; never render raw provider errors or credentials. */
export async function previewFailure(response: Response): Promise<string> {
  const messages:Record<number,string>={
    401:'The private inspection connection could not authenticate. Your image was not processed.',
    403:'The inspection connection is not authorized. Your image was not processed.',
    413:'This preview accepts images up to 3 MiB and 16 megapixels. Choose a smaller original capture.',
    422:'The image or inspection settings are unsupported. Check the format, dimensions and selected geometry.',
    429:'The request rate or remaining research allowance was reached. No automatic retry was made.',
    502:'The AI response could not be validated. Your editable notes remain available.',
    503:'The inspection component is temporarily unavailable. Your editable notes remain available.',
    504:'Cloud analysis timed out. No automatic retry was made.',
  }
  return messages[response.status] ?? `Inspection request failed (HTTP ${response.status}). Your existing evidence is preserved.`
}

export async function validatePreviewImage(photo: Blob): Promise<void> {
  if(photo.size>3*1024*1024)throw Error('Preview images must be at most 3 MiB; the original was not submitted.')
  if(photo.type && !['image/jpeg','image/png','image/webp'].includes(photo.type))throw Error('Use a JPG, PNG or WEBP original for this preview.')
  // Read dimensions before allocating a potentially huge phone-image bitmap.
  const header=new DataView(await photo.arrayBuffer())
  let dimensions:[number,number]|undefined
  if(header.byteLength>=24&&header.getUint32(0)===0x89504e47)dimensions=[header.getUint32(16),header.getUint32(20)]
  else if(header.byteLength>=4&&header.getUint16(0)===0xffd8){
    for(let i=2;i+9<=header.byteLength;){
      if(header.getUint8(i)!==255){i++;continue}
      const marker=header.getUint8(i+1)
      if(marker===255){i++;continue}
      if(marker===0xda||marker===0xd9)break
      const length=header.getUint16(i+2)
      if(length<2||i+2+length>header.byteLength)break
      if([0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf].includes(marker)){dimensions=[header.getUint16(i+7),header.getUint16(i+5)];break}
      i+=2+length
    }
  }
  if(dimensions&&dimensions[0]*dimensions[1]>16_000_000)throw Error('Preview images must be at most 16 megapixels. The original was not decoded or submitted.')
  let image:{width:number;height:number;close:()=>void}
  try{
    if(typeof createImageBitmap==='function')image=await createImageBitmap(photo)
    else image=await new Promise((resolve,reject)=>{
      const url=URL.createObjectURL(photo),element=new Image()
      element.onload=()=>{URL.revokeObjectURL(url);resolve({width:element.naturalWidth,height:element.naturalHeight,close:()=>{}})}
      element.onerror=()=>{URL.revokeObjectURL(url);reject(Error('Decode failed'))}
      element.src=url
    })
  }catch{throw Error('This browser could not decode the image. Use a JPG, PNG or WEBP original.')}
  try {if(image.width*image.height>16_000_000)throw Error('Preview images must be at most 16 megapixels. Choose a lower-resolution capture; the original was not submitted.')}
  finally {image.close()}
}
