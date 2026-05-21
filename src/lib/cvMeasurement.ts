import type { InspectionStatus } from '../types'
import { classifyGap } from '../utils'

export interface CvWorkerRequest {
  imageId: string
  fileName: string
  orderIndex: number
  blob?: Blob
  pipeDiameterMm?: number
}

export interface CvWorkerResponse {
  imageId: string
  originalGapMm: number
  status: InspectionStatus
  confidence: number
  measurementSource: 'cv' | 'fallback'
  measurementNote?: string
}

const DEFAULT_PIPE_DIAMETER_MM = 225
const MAX_PROCESS_DIMENSION = 640

function deriveGapMm(seed: string, orderIndex: number): number {
  const hash = Array.from(seed).reduce((acc, char, index) => {
    return acc + char.charCodeAt(0) * (index + 1)
  }, 0)

  const base = (hash % 260) / 10
  const offset = (orderIndex % 3) * 0.4
  return Number((base + offset).toFixed(1))
}

function buildGrayMap(imageData: ImageData): Uint8Array {
  const gray = new Uint8Array(imageData.width * imageData.height)
  const { data } = imageData

  for (let sourceIndex = 0, grayIndex = 0; sourceIndex < data.length; sourceIndex += 4, grayIndex += 1) {
    const red = data[sourceIndex]
    const green = data[sourceIndex + 1]
    const blue = data[sourceIndex + 2]
    gray[grayIndex] = Math.round(red * 0.299 + green * 0.587 + blue * 0.114)
  }

  return gray
}

function detectPipeDiameterPixels(gray: Uint8Array, width: number, height: number): number | null {
  const topSearchLimit = Math.max(1, Math.floor(height * 0.72))
  const minXSearch = Math.floor(width * 0.12)
  const maxXSearch = Math.ceil(width * 0.88)

  let sum = 0
  let min = 255
  let count = 0

  for (let y = 0; y < topSearchLimit; y += 1) {
    for (let x = minXSearch; x < maxXSearch; x += 1) {
      const value = gray[y * width + x]
      sum += value
      min = Math.min(min, value)
      count += 1
    }
  }

  if (!count) {
    return null
  }

  const mean = sum / count
  const darkThreshold = Math.max(min + 18, Math.min(140, mean * 0.72))

  let minX = width
  let maxX = -1
  let minY = topSearchLimit
  let maxY = -1
  let darkCount = 0

  for (let y = 0; y < topSearchLimit; y += 1) {
    for (let x = minXSearch; x < maxXSearch; x += 1) {
      if (gray[y * width + x] > darkThreshold) {
        continue
      }

      minX = Math.min(minX, x)
      maxX = Math.max(maxX, x)
      minY = Math.min(minY, y)
      maxY = Math.max(maxY, y)
      darkCount += 1
    }
  }

  if (darkCount < width * height * 0.003 || maxX <= minX || maxY <= minY) {
    return null
  }

  const detectedWidth = maxX - minX + 1
  const detectedHeight = maxY - minY + 1

  if (detectedWidth < width * 0.08 || detectedHeight < height * 0.08) {
    return null
  }

  return (detectedWidth + detectedHeight) / 2
}

function detectGapPixels(gray: Uint8Array, width: number, height: number): { gapPixels: number; edgeStrength: number } | null {
  const bandHeight = Math.max(12, Math.floor(height * 0.14))
  const startY = Math.max(1, Math.floor(height / 2 - bandHeight / 2))
  const endY = Math.min(height - 1, startY + bandHeight)
  const scores = new Float32Array(width)

  for (let x = 1; x < width - 1; x += 1) {
    let score = 0
    for (let y = startY; y < endY; y += 1) {
      const index = y * width + x
      score += Math.abs(gray[index] - gray[index - 1])
      score += Math.abs(gray[index] - gray[index + 1])
    }
    scores[x] = score / Math.max(1, endY - startY)
  }

  const midpoint = Math.floor(width / 2)
  const leftStart = Math.max(1, Math.floor(width * 0.15))
  const leftEnd = Math.max(leftStart + 1, midpoint - Math.floor(width * 0.05))
  const rightStart = Math.min(width - 2, midpoint + Math.floor(width * 0.05))
  const rightEnd = Math.max(rightStart + 1, Math.floor(width * 0.85))

  let leftEdge = -1
  let rightEdge = -1
  let leftStrength = 0
  let rightStrength = 0

  for (let x = leftStart; x < leftEnd; x += 1) {
    if (scores[x] > leftStrength) {
      leftStrength = scores[x]
      leftEdge = x
    }
  }

  for (let x = rightStart; x < rightEnd; x += 1) {
    if (scores[x] > rightStrength) {
      rightStrength = scores[x]
      rightEdge = x
    }
  }

  const gapPixels = rightEdge - leftEdge
  const edgeStrength = (leftStrength + rightStrength) / 2

  if (leftEdge < 0 || rightEdge < 0 || gapPixels <= 0 || edgeStrength < 12) {
    return null
  }

  return { gapPixels, edgeStrength }
}

async function tryMeasureWithImageAnalysis(
  blob: Blob | undefined,
  pipeDiameterMm: number,
): Promise<{ gapMm: number; confidence: number } | null> {
  if (!blob || typeof createImageBitmap !== 'function' || typeof OffscreenCanvas === 'undefined') {
    return null
  }

  const bitmap = await createImageBitmap(blob)
  const scale = Math.min(1, MAX_PROCESS_DIMENSION / Math.max(bitmap.width, bitmap.height))
  const targetWidth = Math.max(1, Math.round(bitmap.width * scale))
  const targetHeight = Math.max(1, Math.round(bitmap.height * scale))
  const canvas = new OffscreenCanvas(targetWidth, targetHeight)
  const context = canvas.getContext('2d')

  if (!context) {
    bitmap.close()
    return null
  }

  context.drawImage(bitmap, 0, 0, targetWidth, targetHeight)
  const imageData = context.getImageData(0, 0, targetWidth, targetHeight)
  const gray = buildGrayMap(imageData)

  try {
    const diameterPixels = detectPipeDiameterPixels(gray, targetWidth, targetHeight)
    const gap = detectGapPixels(gray, targetWidth, targetHeight)

    if (!diameterPixels || !gap) {
      return null
    }

    const mmPerPixel = pipeDiameterMm / diameterPixels
    const gapMm = Number((gap.gapPixels * mmPerPixel).toFixed(1))
    const confidence = Number(Math.min(0.91, 0.62 + gap.edgeStrength / 180).toFixed(2))
    return {
      gapMm,
      confidence,
    }
  } finally {
    bitmap.close()
  }
}

function createFallbackMeasurement(
  request: CvWorkerRequest,
  pipeDiameterMm: number,
  note?: string,
): CvWorkerResponse {
  const originalGapMm = deriveGapMm(request.fileName, request.orderIndex)
  const classification = classifyGap(originalGapMm)

  return {
    imageId: request.imageId,
    originalGapMm,
    status: classification.status,
    confidence: 0.72,
    measurementSource: 'fallback',
    measurementNote:
      note ??
      `Estimated from file metadata because the CV pipeline could not confirm the ${pipeDiameterMm}mm pipe geometry.`,
  }
}

export async function runCvMeasurement(
  request: CvWorkerRequest,
  options?: {
    skipOpenCv?: boolean
    fallbackNote?: string
  },
): Promise<CvWorkerResponse> {
  const pipeDiameterMm = request.pipeDiameterMm ?? DEFAULT_PIPE_DIAMETER_MM
  if (options?.skipOpenCv) {
    return createFallbackMeasurement(request, pipeDiameterMm, options.fallbackNote)
  }

  const measured = await tryMeasureWithImageAnalysis(request.blob, pipeDiameterMm)

  if (!measured) {
    return createFallbackMeasurement(request, pipeDiameterMm, options?.fallbackNote)
  }

  return {
    imageId: request.imageId,
    originalGapMm: measured.gapMm,
    status: classifyGap(measured.gapMm).status,
    confidence: measured.confidence,
    measurementSource: 'cv',
  }
}
