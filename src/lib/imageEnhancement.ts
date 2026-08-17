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

/**
 * Build a grayscale luminance map from RGBA image data.
 */
function buildLuminanceMap(data: Uint8ClampedArray, pixelCount: number): Float32Array {
  const lum = new Float32Array(pixelCount)
  for (let i = 0; i < pixelCount; i++) {
    const base = i * 4
    lum[i] = data[base] * 0.299 + data[base + 1] * 0.587 + data[base + 2] * 0.114
  }
  return lum
}

/**
 * CLAHE-style local contrast enhancement.
 * Divides the image into tiles and equalises locally so dark manhole
 * shadows get lifted without washing out bright pipe surfaces.
 * Does NOT move edge positions — only changes intensity values.
 */
function applyClaheContrast(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  tileCountX = 8,
  tileCountY = 8,
  clipLimit = 3.0,
): void {
  const pixelCount = width * height
  const lum = buildLuminanceMap(data, pixelCount)

  const tileW = Math.ceil(width / tileCountX)
  const tileH = Math.ceil(height / tileCountY)
  const bins = 256

  // Build a CDF for each tile
  const tileCdfs: Float32Array[][] = []
  for (let ty = 0; ty < tileCountY; ty++) {
    tileCdfs[ty] = []
    for (let tx = 0; tx < tileCountX; tx++) {
      const hist = new Float32Array(bins)
      let count = 0
      const startX = tx * tileW
      const startY = ty * tileH
      const endX = Math.min(startX + tileW, width)
      const endY = Math.min(startY + tileH, height)

      for (let y = startY; y < endY; y++) {
        for (let x = startX; x < endX; x++) {
          const bin = clamp(Math.round(lum[y * width + x]), 0, 255)
          hist[bin]++
          count++
        }
      }

      // Clip histogram and redistribute
      const limit = Math.max(1, Math.round((clipLimit * count) / bins))
      let excess = 0
      for (let b = 0; b < bins; b++) {
        if (hist[b] > limit) {
          excess += hist[b] - limit
          hist[b] = limit
        }
      }
      const increment = excess / bins
      for (let b = 0; b < bins; b++) {
        hist[b] += increment
      }

      // Build CDF
      const cdf = new Float32Array(bins)
      cdf[0] = hist[0]
      for (let b = 1; b < bins; b++) {
        cdf[b] = cdf[b - 1] + hist[b]
      }
      const cdfMin = cdf.find((v) => v > 0) ?? 0
      const denom = Math.max(1, count - cdfMin)
      for (let b = 0; b < bins; b++) {
        cdf[b] = ((cdf[b] - cdfMin) / denom) * 255
      }

      tileCdfs[ty][tx] = cdf
    }
  }

  // Apply with bilinear interpolation between tile CDFs
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = y * width + x
      const L = lum[idx]
      const bin = clamp(Math.round(L), 0, 255)

      // Find the 4 nearest tile centres and bilinear weight
      const txf = (x - tileW / 2) / tileW
      const tyf = (y - tileH / 2) / tileH
      const tx0 = clamp(Math.floor(txf), 0, tileCountX - 1)
      const ty0 = clamp(Math.floor(tyf), 0, tileCountY - 1)
      const tx1 = clamp(tx0 + 1, 0, tileCountX - 1)
      const ty1 = clamp(ty0 + 1, 0, tileCountY - 1)
      const wx = clamp(txf - tx0, 0, 1)
      const wy = clamp(tyf - ty0, 0, 1)

      const v00 = tileCdfs[ty0][tx0][bin]
      const v10 = tileCdfs[ty0][tx1][bin]
      const v01 = tileCdfs[ty1][tx0][bin]
      const v11 = tileCdfs[ty1][tx1][bin]
      const mapped = v00 * (1 - wx) * (1 - wy) + v10 * wx * (1 - wy) + v01 * (1 - wx) * wy + v11 * wx * wy

      // Apply the mapping to RGB channels proportionally
      const scale = L > 0.5 ? mapped / L : 1
      const base = idx * 4
      data[base] = clamp(Math.round(data[base] * scale), 0, 255)
      data[base + 1] = clamp(Math.round(data[base + 1] * scale), 0, 255)
      data[base + 2] = clamp(Math.round(data[base + 2] * scale), 0, 255)
    }
  }
}

/**
 * Unsharp mask — sharpens existing edges without moving them.
 * Subtracts a blurred copy from the original to amplify edges.
 */
function applyUnsharpMask(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  radius = 2,
  amount = 0.4,
): void {
  const copy = new Uint8ClampedArray(data)

  // Simple box blur as the "blurred" reference
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      let rSum = 0, gSum = 0, bSum = 0, count = 0
      for (let dy = -radius; dy <= radius; dy++) {
        for (let dx = -radius; dx <= radius; dx++) {
          const sx = clamp(x + dx, 0, width - 1)
          const sy = clamp(y + dy, 0, height - 1)
          const si = (sy * width + sx) * 4
          rSum += copy[si]
          gSum += copy[si + 1]
          bSum += copy[si + 2]
          count++
        }
      }
      const i = (y * width + x) * 4
      // original + amount * (original - blurred)
      data[i] = clamp(Math.round(copy[i] + amount * (copy[i] - rSum / count)), 0, 255)
      data[i + 1] = clamp(Math.round(copy[i + 1] + amount * (copy[i + 1] - gSum / count)), 0, 255)
      data[i + 2] = clamp(Math.round(copy[i + 2] + amount * (copy[i + 2] - bSum / count)), 0, 255)
    }
  }
}

/**
 * Edge-preserving denoise (bilateral-style).
 * Smooths noise while keeping sharp edges intact — handles
 * GoPro MAX / iPhone noise in low-light underground conditions.
 */
function applyEdgePreservingDenoise(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  radius = 2,
  intensityRange = 25,
): void {
  const copy = new Uint8ClampedArray(data)

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const ci = (y * width + x) * 4
      const cR = copy[ci], cG = copy[ci + 1], cB = copy[ci + 2]
      let rSum = 0, gSum = 0, bSum = 0, wSum = 0

      for (let dy = -radius; dy <= radius; dy++) {
        for (let dx = -radius; dx <= radius; dx++) {
          const sx = clamp(x + dx, 0, width - 1)
          const sy = clamp(y + dy, 0, height - 1)
          const si = (sy * width + sx) * 4
          const sR = copy[si], sG = copy[si + 1], sB = copy[si + 2]

          const colorDist = Math.abs(sR - cR) + Math.abs(sG - cG) + Math.abs(sB - cB)
          const weight = Math.exp(-(colorDist * colorDist) / (2 * intensityRange * intensityRange * 3))

          rSum += sR * weight
          gSum += sG * weight
          bSum += sB * weight
          wSum += weight
        }
      }

      if (wSum > 0) {
        data[ci] = clamp(Math.round(rSum / wSum), 0, 255)
        data[ci + 1] = clamp(Math.round(gSum / wSum), 0, 255)
        data[ci + 2] = clamp(Math.round(bSum / wSum), 0, 255)
      }
    }
  }
}

/**
 * Measurement-focused image enhancement pipeline.
 * Improves edge visibility for gap measurement WITHOUT distorting
 * or moving pixel geometry. Works for both iPhone and GoPro MAX images.
 *
 * Steps:
 * 1. Edge-preserving denoise → reduce sensor noise while keeping gap edges sharp
 * 2. CLAHE local contrast → reveal detail in dark shadows without washing out bright areas
 * 3. Unsharp mask → sharpen existing edges to make gap boundaries crisper
 */
function enhancePixels(imageData: ImageData): ImageData {
  const enhanced = new ImageData(new Uint8ClampedArray(imageData.data), imageData.width, imageData.height)
  const { width, height, data } = enhanced

  // Step 1: Denoise first (before sharpening, so we don't sharpen noise)
  applyEdgePreservingDenoise(data, width, height, 2, 25)

  // Step 2: Local contrast enhancement
  applyClaheContrast(data, width, height, 8, 8, 3.0)

  // Step 3: Sharpen edges
  applyUnsharpMask(data, width, height, 2, 0.4)

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
    return [{
      base64: await readBlobAsBase64(blob),
      mimeType: blob.type || mimeType,
      enhanced: false,
      label: 'original',
    }]
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

  const variants: (EnhancedImageVariant | null)[] = []
  for (const [label, sx, sy, sw, sh] of cropSpecs) {
    variants.push(await encodeCanvasVariant(canvas, label, sx, sy, sw, sh, outputMimeType))
  }

  return variants.filter((variant): variant is EnhancedImageVariant => Boolean(variant))
}
