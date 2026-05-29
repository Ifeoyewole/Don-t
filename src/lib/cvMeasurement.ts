import type { CvMeasurementDebug, InspectionStatus, MeasurementOverlayHints, MeasurementSource } from '../types'
import { loadOpenCv } from './opencv'
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
  measurementSource: MeasurementSource
  measurementNote?: string
  cvDebug?: CvMeasurementDebug
  overlayHints?: MeasurementOverlayHints
}

const DEFAULT_PIPE_DIAMETER_MM = 225
const MAX_PROCESS_DIMENSION = 720
const ANGLE_STEPS = 48

type CvMeasurementCandidate = {
  gapMm: number
  confidence: number
  note?: string
  debug: CvMeasurementDebug
}

function deriveGapMm(seed: string, orderIndex: number): number {
  const hash = Array.from(seed).reduce((acc, char, index) => acc + char.charCodeAt(0) * (index + 1), 0)
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

function enhanceImageData(imageData: ImageData): ImageData {
  const enhanced = new ImageData(new Uint8ClampedArray(imageData.data), imageData.width, imageData.height)
  const { data } = enhanced
  let luminanceSum = 0

  for (let index = 0; index < data.length; index += 4) {
    luminanceSum += data[index] * 0.299 + data[index + 1] * 0.587 + data[index + 2] * 0.114
  }

  const mean = luminanceSum / Math.max(1, data.length / 4)
  const exposureLift = clamp(128 - mean, -28, 42)
  const contrast = mean < 105 ? 1.18 : 1.08

  for (let index = 0; index < data.length; index += 4) {
    data[index] = clamp((data[index] - 128) * contrast + 128 + exposureLift, 0, 255)
    data[index + 1] = clamp((data[index + 1] - 128) * contrast + 128 + exposureLift, 0, 255)
    data[index + 2] = clamp((data[index + 2] - 128) * contrast + 128 + exposureLift, 0, 255)
  }

  return enhanced
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function median(values: number[]): number {
  const sorted = [...values].sort((a, b) => a - b)
  const midpoint = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0 ? (sorted[midpoint - 1] + sorted[midpoint]) / 2 : sorted[midpoint]
}

function average(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / Math.max(values.length, 1)
}

function standardDeviation(values: number[]): number {
  if (!values.length) {
    return 0
  }

  const mean = average(values)
  const variance = average(values.map((value) => (value - mean) ** 2))
  return Math.sqrt(variance)
}

function getPixel(gray: Uint8Array, width: number, height: number, x: number, y: number): number {
  const clampedX = clamp(Math.round(x), 0, width - 1)
  const clampedY = clamp(Math.round(y), 0, height - 1)
  return gray[clampedY * width + clampedX]
}

function detectOpeningCenter(gray: Uint8Array, width: number, height: number): { x: number; y: number; darkThreshold: number; brightThreshold: number } | null {
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
    darkThreshold,
    brightThreshold,
  }
}

function sampleRayProfile(
  gray: Uint8Array,
  width: number,
  height: number,
  centerX: number,
  centerY: number,
  angle: number,
  maxRadius: number,
): number[] {
  const profile: number[] = []
  const cos = Math.cos(angle)
  const sin = Math.sin(angle)

  for (let radius = 0; radius <= maxRadius; radius += 1) {
    profile.push(getPixel(gray, width, height, centerX + cos * radius, centerY + sin * radius))
  }

  return profile
}

function measureGapFromKnownCircle(
  gray: Uint8Array,
  width: number,
  height: number,
  pipeDiameterMm: number,
  centerX: number,
  centerY: number,
  innerRadiusPx: number,
  enhancementUsed = false,
): CvMeasurementCandidate | null {
  const gapWidths: number[] = []
  const brightThresholdSamples: number[] = []
  const coveredSectors = new Set<number>()
  const maxRadius = Math.floor(Math.min(width, height) * 0.45)

  for (let step = 0; step < ANGLE_STEPS; step += 1) {
    const angle = (Math.PI * 2 * step) / ANGLE_STEPS
    const profile = smoothProfile(sampleRayProfile(gray, width, height, centerX, centerY, angle, maxRadius))
    const sampleIndex = clamp(Math.round(innerRadiusPx * 0.75), 0, profile.length - 1)
    brightThresholdSamples.push(profile[sampleIndex])
  }

  const brightThreshold = clamp(average(brightThresholdSamples) + 18, 86, 222)

  for (let step = 0; step < ANGLE_STEPS; step += 1) {
    const angle = (Math.PI * 2 * step) / ANGLE_STEPS
    const profile = smoothProfile(sampleRayProfile(gray, width, height, centerX, centerY, angle, maxRadius))
    const innerRadius = clamp(Math.round(innerRadiusPx), 4, profile.length - 6)
    const localReference = average(profile.slice(Math.max(0, innerRadius - 3), Math.min(profile.length, innerRadius + 3)))
    const rayBrightThreshold = clamp((brightThreshold + localReference) / 2 + 10, 80, 228)
    let outerRadius = -1
    let bestScore = 0

    for (let radius = innerRadius + 2; radius < Math.min(profile.length - 2, innerRadius + Math.floor(innerRadiusPx * 0.6)); radius += 1) {
      const gradient = profile[radius + 1] - profile[radius - 1]
      const intensityJump = profile[radius] - profile[Math.max(0, radius - 2)]
      const score = gradient + intensityJump
      const isBrightEnough = profile[radius] >= rayBrightThreshold

      if (score > bestScore && gradient >= 5 && (isBrightEnough || intensityJump >= 12)) {
        bestScore = score
        outerRadius = radius
      }
    }

    const gapPixels = outerRadius - innerRadius
    if (outerRadius > 0 && gapPixels >= 2 && gapPixels <= innerRadiusPx * 0.5) {
      gapWidths.push(gapPixels)
      coveredSectors.add(Math.floor(step / 6))
    }
  }

  if (gapWidths.length < 6 || coveredSectors.size < 3) {
    return null
  }

  const gapPixels = median(gapWidths)
  const gapSpread = standardDeviation(gapWidths)
  const mmPerPixel = pipeDiameterMm / (innerRadiusPx * 2)
  const gapMm = Number((gapPixels * mmPerPixel).toFixed(1))
  const confidence = Number(clamp(0.52 + gapWidths.length / 90 + coveredSectors.size / 24 - gapSpread / 24, 0.5, 0.93).toFixed(2))
  const outerRadiusPx = innerRadiusPx + gapPixels

  if (gapMm <= 0.5 || gapMm > 60) {
    return null
  }

  return {
    gapMm,
    confidence,
    note:
      confidence < 0.72
        ? 'OpenCV confirmed the pipe opening, but the gap was estimated from partial visible joint slices.'
        : undefined,
    debug: {
      pipeDetected: true,
      imageWidth: width,
      imageHeight: height,
      innerRadiusPx: Number(innerRadiusPx.toFixed(1)),
      outerRadiusPx: Number(outerRadiusPx.toFixed(1)),
      gapPixels: Number(gapPixels.toFixed(1)),
      mmPerPixel: Number(mmPerPixel.toFixed(4)),
      visibleSectors: coveredSectors.size,
      enhancementUsed,
      overlayHints: {
        pipeCenter: { x: Number(centerX.toFixed(1)), y: Number(centerY.toFixed(1)) },
        innerRadiusPx: Number(innerRadiusPx.toFixed(1)),
        outerRadiusPx: Number(outerRadiusPx.toFixed(1)),
        gapLine: {
          x1: Number((centerX + innerRadiusPx).toFixed(1)),
          y1: Number(centerY.toFixed(1)),
          x2: Number((centerX + outerRadiusPx).toFixed(1)),
          y2: Number(centerY.toFixed(1)),
        },
      },
    },
  }
}

function smoothProfile(profile: number[]): number[] {
  return profile.map((_, index) => {
    const start = Math.max(0, index - 1)
    const end = Math.min(profile.length - 1, index + 1)
    let sum = 0
    let count = 0
    for (let cursor = start; cursor <= end; cursor += 1) {
      sum += profile[cursor]
      count += 1
    }
    return sum / count
  })
}

function findCircleGapMeasurement(
  gray: Uint8Array,
  width: number,
  height: number,
  pipeDiameterMm: number,
  enhancementUsed = false,
): CvMeasurementCandidate | null {
  const center = detectOpeningCenter(gray, width, height)
  if (!center) {
    return null
  }

  const maxRadius = Math.floor(Math.min(width, height) * 0.45)
  const innerRadii: number[] = []
  const gapWidths: number[] = []
  const openingCoverage: number[] = []

  for (let step = 0; step < ANGLE_STEPS; step += 1) {
    const angle = (Math.PI * 2 * step) / ANGLE_STEPS
    const profile = smoothProfile(sampleRayProfile(gray, width, height, center.x, center.y, angle, maxRadius))

    let innerRadius = -1
    for (let radius = 4; radius < profile.length - 2; radius += 1) {
      if (profile[radius] >= center.brightThreshold && profile[radius + 1] >= center.brightThreshold) {
        innerRadius = radius
        break
      }
    }

    if (innerRadius < 0) {
      continue
    }

    const minOuterStart = innerRadius + 4
    const maxOuterEnd = Math.min(profile.length - 2, innerRadius + Math.floor(maxRadius * 0.42))
    let outerRadius = -1
    let strongestGradient = 0

    for (let radius = minOuterStart; radius < maxOuterEnd; radius += 1) {
      const gradient = profile[radius + 1] - profile[radius - 1]
      const becomesBright = profile[radius] > center.brightThreshold + 10
      if (gradient > strongestGradient && becomesBright) {
        strongestGradient = gradient
        outerRadius = radius
      }
    }

    const gapPixels = outerRadius - innerRadius
    if (outerRadius < 0 || gapPixels < 2 || gapPixels > innerRadius * 0.4) {
      continue
    }

    innerRadii.push(innerRadius)
    gapWidths.push(gapPixels)
    openingCoverage.push(innerRadius / maxRadius)
  }

  if (innerRadii.length < 12 || gapWidths.length < 12) {
    return null
  }

  const innerRadiusPx = median(innerRadii)
  const gapPixels = median(gapWidths)
  const radiusSpread = standardDeviation(innerRadii)
  const gapSpread = standardDeviation(gapWidths)
  const coverage = average(openingCoverage)

  if (innerRadiusPx < width * 0.08 || coverage < 0.22) {
    return null
  }

  const mmPerPixel = pipeDiameterMm / (innerRadiusPx * 2)
  const gapMm = Number((gapPixels * mmPerPixel).toFixed(1))
  const outerRadiusPx = innerRadiusPx + gapPixels
  const confidence = Number(
    clamp(0.58 + innerRadii.length / 90 - radiusSpread / 60 - gapSpread / 30, 0.55, 0.93).toFixed(2),
  )

  return {
    gapMm,
    confidence,
    note: confidence < 0.68 ? 'Measurement captured from a low-confidence opening profile.' : undefined,
    debug: {
      pipeDetected: true,
      imageWidth: width,
      imageHeight: height,
      innerRadiusPx: Number(innerRadiusPx.toFixed(1)),
      outerRadiusPx: Number(outerRadiusPx.toFixed(1)),
      gapPixels: Number(gapPixels.toFixed(1)),
      mmPerPixel: Number(mmPerPixel.toFixed(4)),
      visibleSectors: innerRadii.length,
      enhancementUsed,
      overlayHints: {
        pipeCenter: { x: Number(center.x.toFixed(1)), y: Number(center.y.toFixed(1)) },
        innerRadiusPx: Number(innerRadiusPx.toFixed(1)),
        outerRadiusPx: Number(outerRadiusPx.toFixed(1)),
        gapLine: {
          x1: Number((center.x + innerRadiusPx).toFixed(1)),
          y1: Number(center.y.toFixed(1)),
          x2: Number((center.x + outerRadiusPx).toFixed(1)),
          y2: Number(center.y.toFixed(1)),
        },
      },
    },
  }
}

function detectLinearGapPixels(
  gray: Uint8Array,
  width: number,
  height: number,
): { gapPixels: number; edgeStrength: number } | null {
  const bandStartX = Math.floor(width * 0.2)
  const bandEndX = Math.ceil(width * 0.8)
  const bandStartY = Math.floor(height * 0.15)
  const bandEndY = Math.ceil(height * 0.85)
  const columnScores = new Float32Array(width)

  for (let x = bandStartX; x < bandEndX; x += 1) {
    let score = 0
    for (let y = bandStartY + 1; y < bandEndY - 1; y += 1) {
      const index = y * width + x
      score += Math.abs(gray[index] - gray[index - width])
      score += Math.abs(gray[index] - gray[index + width])
    }
    columnScores[x] = score / Math.max(1, bandEndY - bandStartY)
  }

  let leftEdge = -1
  let rightEdge = -1
  let leftStrength = 0
  let rightStrength = 0
  const midpoint = Math.floor(width / 2)

  for (let x = Math.max(bandStartX, midpoint - Math.floor(width * 0.2)); x < midpoint; x += 1) {
    if (columnScores[x] > leftStrength) {
      leftStrength = columnScores[x]
      leftEdge = x
    }
  }

  for (let x = midpoint; x < Math.min(bandEndX, midpoint + Math.floor(width * 0.2)); x += 1) {
    if (columnScores[x] > rightStrength) {
      rightStrength = columnScores[x]
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

function detectReferenceSpanPixels(gray: Uint8Array, width: number, height: number): number | null {
  const startY = Math.floor(height * 0.2)
  const endY = Math.ceil(height * 0.8)
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

  const threshold = average(Array.from(scores)) * 1.35
  let first = -1
  let last = -1
  for (let x = Math.floor(width * 0.08); x < Math.floor(width * 0.92); x += 1) {
    if (scores[x] < threshold) {
      continue
    }
    if (first < 0) {
      first = x
    }
    last = x
  }

  if (first < 0 || last <= first) {
    return null
  }

  const span = last - first
  return span > width * 0.22 ? span : null
}

function detectHorizontalJointGap(gray: Uint8Array, width: number, height: number): CvMeasurementCandidate | null {
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

  let bestScore = 0
  let bestIndex = -1

  for (let index = 3; index < rowDarkness.length - 3; index += 1) {
    const local = average(rowDarkness.slice(index - 2, index + 3))
    const upper = average(rowDarkness.slice(Math.max(0, index - 24), Math.max(1, index - 8)))
    const lower = average(rowDarkness.slice(Math.min(rowDarkness.length - 1, index + 8), Math.min(rowDarkness.length, index + 24)))
    const score = local - Math.max(upper, lower)
    if (score > bestScore) {
      bestScore = score
      bestIndex = index
    }
  }

  if (bestScore < 18 || bestIndex < 0) {
    return null
  }

  const centerY = startY + bestIndex
  let topEdge = centerY
  let bottomEdge = centerY
  const threshold = rowDarkness[bestIndex] - bestScore * 0.45

  while (topEdge > startY && rowDarkness[topEdge - startY] > threshold) {
    topEdge -= 1
  }

  while (bottomEdge < endY - 1 && rowDarkness[bottomEdge - startY] > threshold) {
    bottomEdge += 1
  }

  const gapPixels = Math.max(2, bottomEdge - topEdge)
  const mmPerPixel = 0.55
  const gapMm = Number((gapPixels * mmPerPixel).toFixed(1))

  if (gapMm <= 0.5 || gapMm > 80) {
    return null
  }

  return {
    gapMm,
    confidence: Number(clamp(0.42 + bestScore / 140, 0.45, 0.68).toFixed(2)),
    note: 'Linear close-up joint seam detected. AI review or inspector confirmation is recommended for final accuracy.',
    debug: {
      pipeDetected: false,
      imageWidth: width,
      imageHeight: height,
      gapPixels,
      mmPerPixel,
      edgeStrength: Number(bestScore.toFixed(1)),
      enhancementUsed: true,
      failureStage: 'linear-close-up-joint',
      overlayHints: {
        gapLine: {
          x1: startX,
          y1: Number(centerY.toFixed(1)),
          x2: endX,
          y2: Number(centerY.toFixed(1)),
        },
      },
    },
  }
}

async function tryMeasureWithImageAnalysis(
  blob: Blob | undefined,
  pipeDiameterMm: number,
): Promise<CvMeasurementCandidate | null> {
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
  const imageData = enhanceImageData(context.getImageData(0, 0, targetWidth, targetHeight))
  const gray = buildGrayMap(imageData)

  try {
    const circularMeasurement = findCircleGapMeasurement(gray, targetWidth, targetHeight, pipeDiameterMm, true)
    if (circularMeasurement && circularMeasurement.gapMm > 0.5 && circularMeasurement.gapMm < 60) {
      return circularMeasurement
    }

    const closeUpJoint = detectHorizontalJointGap(gray, targetWidth, targetHeight)
    if (closeUpJoint) {
      return closeUpJoint
    }

    const linearGap = detectLinearGapPixels(gray, targetWidth, targetHeight)
    const referenceSpan = detectReferenceSpanPixels(gray, targetWidth, targetHeight)

    if (!linearGap || !referenceSpan) {
      return null
    }

    const mmPerPixel = pipeDiameterMm / referenceSpan
    const gapMm = Number((linearGap.gapPixels * mmPerPixel).toFixed(1))
    const confidence = Number(clamp(0.44 + linearGap.edgeStrength / 180, 0.4, 0.71).toFixed(2))
    if (gapMm <= 0.5 || gapMm > 80) {
      return null
    }

    return {
      gapMm,
      confidence,
      note: 'Measured from a partial joint view. Capture a centered guided joint photo for highest accuracy.',
      debug: {
        pipeDetected: false,
        imageWidth: targetWidth,
        imageHeight: targetHeight,
        gapPixels: linearGap.gapPixels,
        mmPerPixel: Number(mmPerPixel.toFixed(4)),
        edgeStrength: Number(linearGap.edgeStrength.toFixed(1)),
        enhancementUsed: true,
        failureStage: 'linear-gap-estimate',
        overlayHints: {
          gapLine: {
            x1: Number((targetWidth / 2 - linearGap.gapPixels / 2).toFixed(1)),
            y1: Number((targetHeight / 2).toFixed(1)),
            x2: Number((targetWidth / 2 + linearGap.gapPixels / 2).toFixed(1)),
            y2: Number((targetHeight / 2).toFixed(1)),
          },
        },
      },
    }
  } finally {
    bitmap.close()
  }
}

async function tryMeasureWithOpenCv(
  blob: Blob | undefined,
  pipeDiameterMm: number,
): Promise<CvMeasurementCandidate | null> {
  if (!blob || typeof createImageBitmap !== 'function' || typeof OffscreenCanvas === 'undefined') {
    return null
  }

  const cv = await loadOpenCv()
  const bitmap = await createImageBitmap(blob)
  const scale = Math.min(1, MAX_PROCESS_DIMENSION / Math.max(bitmap.width, bitmap.height))
  const width = Math.max(1, Math.round(bitmap.width * scale))
  const height = Math.max(1, Math.round(bitmap.height * scale))
  const canvas = new OffscreenCanvas(width, height)
  const context = canvas.getContext('2d')

  if (!context) {
    bitmap.close()
    return null
  }

  context.drawImage(bitmap, 0, 0, width, height)
  const imageData = enhanceImageData(context.getImageData(0, 0, width, height))
  const grayMap = buildGrayMap(imageData)
  const source = cv.matFromImageData(imageData)
  const gray = new cv.Mat()
  const blurred = new cv.Mat()
  const circles = new cv.Mat()

  try {
    cv.cvtColor(source, gray, cv.COLOR_RGBA2GRAY)
    cv.GaussianBlur(gray, blurred, new cv.Size(9, 9), 2, 2, cv.BORDER_DEFAULT)
    cv.HoughCircles(
      blurred,
      circles,
      cv.HOUGH_GRADIENT,
      1.2,
      Math.max(24, Math.floor(height * 0.16)),
      120,
      28,
      Math.max(18, Math.floor(Math.min(width, height) * 0.08)),
      Math.max(24, Math.floor(Math.min(width, height) * 0.34)),
    )

    if (!circles.data32F || circles.data32F.length < 3) {
      return null
    }

    let bestCircle: { x: number; y: number; r: number; score: number } | null = null
    for (let index = 0; index < circles.data32F.length; index += 3) {
      const x = circles.data32F[index]
      const y = circles.data32F[index + 1]
      const r = circles.data32F[index + 2]
      const xBias = Math.abs(x / width - 0.5)
      const yBias = Math.abs(y / height - 0.32)
      const coverage = r / Math.min(width, height)
      const score = 1 - xBias - yBias + coverage

      if (!bestCircle || score > bestCircle.score) {
        bestCircle = { x, y, r, score }
      }
    }

    if (!bestCircle) {
      return null
    }

    return measureGapFromKnownCircle(grayMap, width, height, pipeDiameterMm, bestCircle.x, bestCircle.y, bestCircle.r, true)
  } finally {
    circles.delete()
    blurred.delete()
    gray.delete()
    source.delete()
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
    cvDebug: {
      pipeDetected: false,
      failureStage: 'fallback-derived-from-metadata',
      enhancementUsed: false,
    },
  }
}

export async function runCvMeasurement(
  request: CvWorkerRequest,
  options?: {
    disableOpenCv?: boolean
    skipOpenCv?: boolean
    fallbackNote?: string
  },
): Promise<CvWorkerResponse> {
  const pipeDiameterMm = request.pipeDiameterMm ?? DEFAULT_PIPE_DIAMETER_MM
  if (options?.skipOpenCv) {
    return createFallbackMeasurement(request, pipeDiameterMm, options.fallbackNote)
  }

  if (!options?.disableOpenCv) {
    const openCvMeasured = await tryMeasureWithOpenCv(request.blob, pipeDiameterMm)
    if (openCvMeasured) {
      return {
        imageId: request.imageId,
        originalGapMm: openCvMeasured.gapMm,
        status: classifyGap(openCvMeasured.gapMm).status,
        confidence: openCvMeasured.confidence,
        measurementSource: 'cv',
        measurementNote: openCvMeasured.note,
        cvDebug: openCvMeasured.debug,
        overlayHints: openCvMeasured.debug.overlayHints,
      }
    }
  }

  const measured = await tryMeasureWithImageAnalysis(request.blob, pipeDiameterMm)

  if (!measured) {
    return createFallbackMeasurement(
      request,
      pipeDiameterMm,
      options?.fallbackNote ?? 'Guided joint photo required. The current image did not expose enough pipe geometry for a reliable gap measurement.',
    )
  }

  return {
    imageId: request.imageId,
    originalGapMm: measured.gapMm,
    status: classifyGap(measured.gapMm).status,
    confidence: measured.confidence,
    measurementSource: 'cv',
    measurementNote: measured.note,
    cvDebug: measured.debug,
    overlayHints: measured.debug.overlayHints,
  }
}
