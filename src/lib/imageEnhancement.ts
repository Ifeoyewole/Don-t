export type EnhancedImagePayload = {
  base64: string
  mimeType: string
  enhanced: boolean
}

export type EnhancedImageVariant = EnhancedImagePayload & {
  label: string
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function readBlobAsBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = typeof reader.result === 'string' ? reader.result : ''
      resolve(result.includes(',') ? result.split(',')[1] : result)
    }
    reader.onerror = () => reject(new Error('Could not read image for AI review.'))
    reader.readAsDataURL(blob)
  })
}

function canvasToBlob(canvas: HTMLCanvasElement | OffscreenCanvas, mimeType: string): Promise<Blob> {
  if ('convertToBlob' in canvas) {
    return canvas.convertToBlob({ type: mimeType, quality: 0.9 })
  }

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob)
      } else {
        reject(new Error('Could not encode enhanced image.'))
      }
    }, mimeType, 0.9)
  })
}

function createCanvas(width: number, height: number): HTMLCanvasElement | OffscreenCanvas {
  if (typeof OffscreenCanvas !== 'undefined') {
    return new OffscreenCanvas(width, height)
  }

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  return canvas
}

function getCanvas2dContext(canvas: HTMLCanvasElement | OffscreenCanvas): CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | null {
  return canvas.getContext('2d') as CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | null
}

function enhancePixels(imageData: ImageData): ImageData {
  const enhanced = new ImageData(new Uint8ClampedArray(imageData.data), imageData.width, imageData.height)
  const { data } = enhanced
  let luminanceSum = 0

  for (let index = 0; index < data.length; index += 4) {
    luminanceSum += data[index] * 0.299 + data[index + 1] * 0.587 + data[index + 2] * 0.114
  }

  const mean = luminanceSum / Math.max(1, data.length / 4)
  const exposureLift = clamp(132 - mean, -34, 54)
  const contrast = mean < 112 ? 1.24 : 1.12

  for (let index = 0; index < data.length; index += 4) {
    const red = data[index]
    const green = data[index + 1]
    const blue = data[index + 2]

    data[index] = clamp((red - 128) * contrast + 128 + exposureLift, 0, 255)
    data[index + 1] = clamp((green - 128) * contrast + 128 + exposureLift, 0, 255)
    data[index + 2] = clamp((blue - 128) * contrast + 128 + exposureLift, 0, 255)
  }

  return enhanced
}

export async function createEnhancedImagePayload(blob: Blob, mimeType = 'image/jpeg'): Promise<EnhancedImagePayload> {
  const variants = await createEnhancedImageVariants(blob, mimeType)
  const primary = variants[0]
  return {
    base64: primary.base64,
    mimeType: primary.mimeType,
    enhanced: primary.enhanced,
  }
}

async function encodeCanvasVariant(
  source: HTMLCanvasElement | OffscreenCanvas,
  label: string,
  sx: number,
  sy: number,
  sw: number,
  sh: number,
  mimeType: string,
): Promise<EnhancedImageVariant | null> {
  const width = Math.max(1, Math.round(sw))
  const height = Math.max(1, Math.round(sh))
  const canvas = createCanvas(width, height)
  const context = getCanvas2dContext(canvas)

  if (!context) {
    return null
  }

  context.drawImage(source, sx, sy, sw, sh, 0, 0, width, height)
  const blob = await canvasToBlob(canvas, mimeType)

  return {
    label,
    base64: await readBlobAsBase64(blob),
    mimeType,
    enhanced: true,
  }
}

export async function createEnhancedImageVariants(blob: Blob, mimeType = 'image/jpeg'): Promise<EnhancedImageVariant[]> {
  if (typeof createImageBitmap !== 'function') {
    return {
      base64: await readBlobAsBase64(blob),
      mimeType: blob.type || mimeType,
      enhanced: false,
      label: 'original',
    } satisfies EnhancedImageVariant[]
  }

  const bitmap = await createImageBitmap(blob)
  const maxDimension = 1280
  const scale = Math.min(1, maxDimension / Math.max(bitmap.width, bitmap.height))
  const width = Math.max(1, Math.round(bitmap.width * scale))
  const height = Math.max(1, Math.round(bitmap.height * scale))
  const canvas = createCanvas(width, height)
  const context = getCanvas2dContext(canvas)

  if (!context) {
    bitmap.close()
    return [{
      base64: await readBlobAsBase64(blob),
      mimeType: blob.type || mimeType,
      enhanced: false,
      label: 'original',
    }]
  }

  context.drawImage(bitmap, 0, 0, width, height)
  bitmap.close()

  const imageData = context.getImageData(0, 0, width, height)
  context.putImageData(enhancePixels(imageData), 0, 0)

  const outputMimeType = mimeType === 'image/png' ? 'image/png' : 'image/jpeg'
  const cropSpecs: Array<[string, number, number, number, number]> = [
    ['full-enhanced', 0, 0, width, height],
    ['center-zoom', width * 0.18, height * 0.18, width * 0.64, height * 0.64],
    ['upper-strip', 0, 0, width, height * 0.42],
    ['middle-strip', 0, height * 0.29, width, height * 0.42],
    ['lower-strip', 0, height * 0.58, width, height * 0.42],
    ['left-band', 0, 0, width * 0.5, height],
    ['right-band', width * 0.5, 0, width * 0.5, height],
  ]

  const variants = await Promise.all(
    cropSpecs.map(([label, sx, sy, sw, sh]) => encodeCanvasVariant(canvas, label, sx, sy, sw, sh, outputMimeType)),
  )

  return variants.filter((variant): variant is EnhancedImageVariant => Boolean(variant))
}
