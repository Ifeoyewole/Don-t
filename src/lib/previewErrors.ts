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
