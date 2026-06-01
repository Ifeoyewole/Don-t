import type { GuidedPhotoStatus } from '../types'

const MAX_VALIDATION_DIMENSION = 640

export interface GuidedPhotoValidationResult {
  status: GuidedPhotoStatus
  message: string
  score: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
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

function getPixel(gray: Uint8Array, width: number, height: number, x: number, y: number): number {
  const clampedX = clamp(Math.round(x), 0, width - 1)
  const clampedY = clamp(Math.round(y), 0, height - 1)
  return gray[clampedY * width + clampedX]
}

function average(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / Math.max(values.length, 1)
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const midpoint = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0 ? (sorted[midpoint - 1] + sorted[midpoint]) / 2 : sorted[midpoint]
}

function detectOpeningCenter(gray: Uint8Array, width: number, height: number) {
  const startX = Math.floor(width * 0.15)
  const endX = Math.ceil(width * 0.85)
  const startY = Math.floor(height * 0.08)
  const endY = Math.ceil(height * 0.72)
  let min = 255
  let sum = 0
  let count = 0

  for (let y = startY; y < endY; y += 1) {
    for (let x = startX; x < endX; x += 1) {
      const value = gray[y * width + x]
      min = Math.min(min, value)
      sum += value
      count += 1
    }
  }

  if (!count) {
    return null
  }

  const mean = sum / count
  const darkThreshold = Math.max(min + 18, Math.min(118, mean * 0.64))
  const brightThreshold = clamp(mean * 0.93, darkThreshold + 10, 220)
  let weightedX = 0
  let weightedY = 0
  let weightSum = 0

  for (let y = startY; y < endY; y += 1) {
    for (let x = startX; x < endX; x += 1) {
      const value = gray[y * width + x]
      if (value > darkThreshold) {
        continue
      }

      const weight = darkThreshold - value + 1
      weightedX += x * weight
      weightedY += y * weight
      weightSum += weight
    }
  }

  if (!weightSum) {
    return null
  }

  return {
    x: weightedX / weightSum,
    y: weightedY / weightSum,
    brightThreshold,
  }
}

function sampleRayRadii(gray: Uint8Array, width: number, height: number, centerX: number, centerY: number, brightThreshold: number) {
  const radii: number[] = []
  const maxRadius = Math.floor(Math.min(width, height) * 0.45)

  for (let step = 0; step < 36; step += 1) {
    const angle = (Math.PI * 2 * step) / 36
    const cos = Math.cos(angle)
    const sin = Math.sin(angle)
    let radiusFound = -1

    for (let radius = 4; radius <= maxRadius; radius += 1) {
      const sample = getPixel(gray, width, height, centerX + cos * radius, centerY + sin * radius)
      if (sample >= brightThreshold) {
        radiusFound = radius
        break
      }
    }

    if (radiusFound > 0) {
      radii.push(radiusFound)
    }
  }

  return radii
}

function detectHorizontalLinearJoint(gray: Uint8Array, width: number, height: number): { score: number } | null {
  const startX = Math.floor(width * 0.08)
  const endX = Math.ceil(width * 0.92)
  const startY = Math.floor(height * 0.12)
  const endY = Math.ceil(height * 0.88)
  const rowDarkness: number[] = []

  for (let y = startY; y < endY; y += 1) {
    let sum = 0
    for (let x = startX; x < endX; x += 1) {
      sum += 255 - gray[y * width + x]
    }
    rowDarkness.push(sum / Math.max(1, endX - startX))
  }

  const baseline = average(rowDarkness)
  let bestScore = 0
  let bestY = -1

  for (let index = 2; index < rowDarkness.length - 2; index += 1) {
    const local = average(rowDarkness.slice(index - 2, index + 3))
    const upper = average(rowDarkness.slice(Math.max(0, index - 20), Math.max(1, index - 8)))
    const lower = average(rowDarkness.slice(Math.min(rowDarkness.length - 1, index + 8), Math.min(rowDarkness.length, index + 20)))
    const contrast = local - Math.max(upper, lower, baseline * 0.82)
    if (contrast > bestScore) {
      bestScore = contrast
      bestY = startY + index
    }
  }

  if (bestScore < 18 || bestY < 0) {
    return null
  }

  return {
    score: Number(clamp(bestScore / 70, 0.38, 0.92).toFixed(2)),
  }
}

function detectVerticalLinearJoint(gray: Uint8Array, width: number, height: number): { score: number } | null {
  const startX = Math.floor(width * 0.08)
  const endX = Math.ceil(width * 0.92)
  const startY = Math.floor(height * 0.12)
  const endY = Math.ceil(height * 0.88)
  const columnDarkness: number[] = []

  for (let x = startX; x < endX; x += 1) {
    let sum = 0
    for (let y = startY; y < endY; y += 1) {
      sum += 255 - gray[y * width + x]
    }
    columnDarkness.push(sum / Math.max(1, endY - startY))
  }

  const baseline = average(columnDarkness)
  let bestScore = 0

  for (let index = 2; index < columnDarkness.length - 2; index += 1) {
    const local = average(columnDarkness.slice(index - 2, index + 3))
    const left = average(columnDarkness.slice(Math.max(0, index - 20), Math.max(1, index - 8)))
    const right = average(columnDarkness.slice(Math.min(columnDarkness.length - 1, index + 8), Math.min(columnDarkness.length, index + 20)))
    const contrast = local - Math.max(left, right, baseline * 0.82)
    if (contrast > bestScore) {
      bestScore = contrast
    }
  }

  if (bestScore < 18) {
    const darkThreshold = baseline * 1.18
    let bestRunScore = 0
    let runStart = -1

    for (let index = 0; index <= columnDarkness.length; index += 1) {
      const inDarkRun = index < columnDarkness.length && columnDarkness[index] >= darkThreshold
      if (inDarkRun && runStart < 0) {
        runStart = index
      }

      if ((index === columnDarkness.length || !inDarkRun) && runStart >= 0) {
        const runEnd = index - 1
        const runWidth = runEnd - runStart + 1
        const runMean = average(columnDarkness.slice(runStart, runEnd + 1))
        const leftMean = average(columnDarkness.slice(Math.max(0, runStart - 28), Math.max(1, runStart - 6)))
        const rightMean = average(columnDarkness.slice(Math.min(columnDarkness.length - 1, runEnd + 6), Math.min(columnDarkness.length, runEnd + 28)))
        const contrast = runMean - Math.max(leftMean, rightMean, baseline * 0.82)
        const widthOk = runWidth >= width * 0.02 && runWidth <= width * 0.36
        if (widthOk && contrast > bestRunScore) {
          bestRunScore = contrast
        }
        runStart = -1
      }
    }

    bestScore = bestRunScore
  }

  if (bestScore < 12) {
    return null
  }

  return {
    score: Number(clamp(bestScore / 70, 0.38, 0.92).toFixed(2)),
  }
}

function detectLinearJoint(gray: Uint8Array, width: number, height: number): { score: number } | null {
  const horizontal = detectHorizontalLinearJoint(gray, width, height)
  const vertical = detectVerticalLinearJoint(gray, width, height)

  if (!horizontal) {
    return vertical
  }

  if (!vertical) {
    return horizontal
  }

  return horizontal.score >= vertical.score ? horizontal : vertical
}

export async function validateGuidedPhoto(blob?: Blob): Promise<GuidedPhotoValidationResult> {
  if (!blob || typeof createImageBitmap !== 'function' || typeof OffscreenCanvas === 'undefined') {
    return {
      status: 'ready',
      message: 'Guided capture validation unavailable on this device.',
      score: 0.5,
    }
  }

  const bitmap = await createImageBitmap(blob)
  const scale = Math.min(1, MAX_VALIDATION_DIMENSION / Math.max(bitmap.width, bitmap.height))
  const width = Math.max(1, Math.round(bitmap.width * scale))
  const height = Math.max(1, Math.round(bitmap.height * scale))
  const canvas = new OffscreenCanvas(width, height)
  const context = canvas.getContext('2d')

  if (!context) {
    bitmap.close()
    return {
      status: 'ready',
      message: 'Guided capture validation unavailable on this device.',
      score: 0.5,
    }
  }

  context.drawImage(bitmap, 0, 0, width, height)
  const imageData = context.getImageData(0, 0, width, height)
  const gray = buildGrayMap(imageData)
  bitmap.close()

  const center = detectOpeningCenter(gray, width, height)
  if (!center) {
    const linearJoint = detectLinearJoint(gray, width, height)
    if (linearJoint) {
      return {
        status: 'ready',
        message: 'Linear joint seam detected. Enhanced CV and AI review will confirm the measurement.',
        score: linearJoint.score,
      }
    }

    return {
      status: 'retake',
      message: 'Retake photo: keep the pipe opening visible and centered so the gap can be scaled correctly.',
      score: 0.08,
    }
  }

  const radii = sampleRayRadii(gray, width, height, center.x, center.y, center.brightThreshold)
  if (radii.length < 16) {
    const linearJoint = detectLinearJoint(gray, width, height)
    if (linearJoint) {
      return {
        status: 'ready',
        message: 'Linear joint seam detected. Enhanced CV and AI review will confirm the measurement.',
        score: linearJoint.score,
      }
    }

    return {
      status: 'retake',
      message: 'Retake photo: the pipe opening is not clear enough for reliable gap measurement.',
      score: 0.18,
    }
  }

  const radius = median(radii)
  const centerXRatio = center.x / width
  const centerYRatio = center.y / height
  const radiusRatio = radius / Math.min(width, height)
  const radiusVariance = average(radii.map((value) => Math.abs(value - radius)))
  const centeredEnough = centerXRatio > 0.28 && centerXRatio < 0.72 && centerYRatio > 0.12 && centerYRatio < 0.58
  const openingLargeEnough = radiusRatio > 0.13
  const circleStableEnough = radiusVariance < radius * 0.22

  const score = clamp(
    0.34 +
      (centeredEnough ? 0.22 : 0) +
      (openingLargeEnough ? 0.22 : 0) +
      (circleStableEnough ? 0.18 : 0) +
      Math.min(0.12, radii.length / 300),
    0,
    1,
  )

  if (!centeredEnough || !openingLargeEnough || !circleStableEnough) {
    const linearJoint = detectLinearJoint(gray, width, height)
    if (linearJoint) {
      return {
        status: 'ready',
        message: 'Linear joint seam detected. Enhanced CV and AI review will confirm the measurement.',
        score: linearJoint.score,
      }
    }

    return {
      status: 'retake',
      message: 'Retake photo: use the guided capture angle and keep the full pipe opening steady in frame.',
      score: Number(score.toFixed(2)),
    }
  }

  return {
    status: 'ready',
    message: 'Guided photo check passed.',
    score: Number(score.toFixed(2)),
  }
}
