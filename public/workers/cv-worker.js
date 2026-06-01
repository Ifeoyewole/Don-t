let cvReady = null
let cvModule = null
let lastStage = 'worker-created'

const DEFAULT_PIPE_DIAMETER_MM = 225
const MAX_PROCESS_DIMENSION = 720
const ANGLE_STEPS = 48
const BASE_CLOSE_UP_MM_PER_PIXEL = 0.075
const VERTICAL_BLACK_GAP_SCALE = [
  { maxDiameterMm: 150, mmPerPixel: 0.389 },
  { maxDiameterMm: 225, mmPerPixel: 0.18 },
  { maxDiameterMm: 300, mmPerPixel: 0.24 },
  { maxDiameterMm: 450, mmPerPixel: 0.34 },
  { maxDiameterMm: 600, mmPerPixel: 0.44 },
  { maxDiameterMm: Number.POSITIVE_INFINITY, mmPerPixel: 0.55 },
]
const CLOSE_UP_PIPE_SCALE = [
  { maxDiameterMm: 150, scale: 5.18 },
  { maxDiameterMm: 225, scale: 1 },
  { maxDiameterMm: 300, scale: 1.08 },
  { maxDiameterMm: 450, scale: 1.16 },
  { maxDiameterMm: 600, scale: 1.24 },
  { maxDiameterMm: Number.POSITIVE_INFINITY, scale: 1.34 },
]

function debug(stage, imageId = '__worker__') {
  lastStage = stage
  self.postMessage({ type: 'DEBUG', imageId, stage })
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}

function average(values) {
  return values.reduce((sum, value) => sum + value, 0) / Math.max(values.length, 1)
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b)
  const midpoint = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0 ? (sorted[midpoint - 1] + sorted[midpoint]) / 2 : sorted[midpoint]
}

function standardDeviation(values) {
  if (!values.length) {
    return 0
  }

  const mean = average(values)
  const variance = average(values.map((value) => (value - mean) ** 2))
  return Math.sqrt(variance)
}

function classifyGap(gapMm, pipeDiameterMm = DEFAULT_PIPE_DIAMETER_MM) {
  const scale = Math.max(0.5, pipeDiameterMm / DEFAULT_PIPE_DIAMETER_MM)
  const tooSmallMax = 3 * scale
  const passMax = 15 * scale
  const reviewMax = 25 * scale

  if (gapMm < tooSmallMax) {
    return 'REVIEW'
  }

  if (gapMm <= passMax) {
    return 'PASS'
  }

  if (gapMm <= reviewMax) {
    return 'REVIEW'
  }

  return 'FAIL'
}

function estimateCloseUpMmPerPixel(pipeDiameterMm) {
  const pipeScale = CLOSE_UP_PIPE_SCALE.find((entry) => pipeDiameterMm <= entry.maxDiameterMm)?.scale || 1
  return Number((BASE_CLOSE_UP_MM_PER_PIXEL * pipeScale).toFixed(4))
}

function estimateVerticalBlackGapMmPerPixel(pipeDiameterMm) {
  return VERTICAL_BLACK_GAP_SCALE.find((entry) => pipeDiameterMm <= entry.maxDiameterMm)?.mmPerPixel || 0.55
}

function buildGrayMap(imageData) {
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

function enhanceImageData(imageData) {
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

function getPixel(gray, width, height, x, y) {
  const clampedX = clamp(Math.round(x), 0, width - 1)
  const clampedY = clamp(Math.round(y), 0, height - 1)
  return gray[clampedY * width + clampedX]
}

function sampleRayProfile(gray, width, height, centerX, centerY, angle, maxRadius) {
  const profile = []
  const cos = Math.cos(angle)
  const sin = Math.sin(angle)

  for (let radius = 0; radius <= maxRadius; radius += 1) {
    profile.push(getPixel(gray, width, height, centerX + cos * radius, centerY + sin * radius))
  }

  return profile
}

function smoothProfile(profile) {
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

function detectHorizontalJointGap(gray, width, height, pipeDiameterMm) {
  const startX = Math.floor(width * 0.08)
  const endX = Math.ceil(width * 0.92)
  const startY = Math.floor(height * 0.12)
  const endY = Math.ceil(height * 0.88)
  const rowDarkness = []

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
  const assumedMmPerPixel = estimateCloseUpMmPerPixel(pipeDiameterMm)
  const gapMm = Number((gapPixels * assumedMmPerPixel).toFixed(1))
  const rawTracePoints = []
  const columnStep = Math.max(10, Math.floor((endX - startX) / 34))
  const searchRadius = Math.max(10, Math.round(gapPixels * 2.5))
  let previousY = centerY

  for (let x = startX; x <= endX; x += columnStep) {
    let bestY = centerY
    let bestTrackedScore = Number.NEGATIVE_INFINITY
    const localStartY = Math.max(startY + 2, centerY - searchRadius)
    const localEndY = Math.min(endY - 2, centerY + searchRadius)

    for (let y = localStartY; y <= localEndY; y += 1) {
      let darkness = 0
      let count = 0

      for (let offset = -3; offset <= 3; offset += 1) {
        const sampleX = clamp(x + offset, startX, endX - 1)
        darkness += 255 - gray[y * width + sampleX]
        count += 1
      }

      const localScore = darkness / Math.max(1, count)
      const continuityPenalty = Math.abs(y - previousY) * 1.35
      const trackedScore = localScore - continuityPenalty
      if (trackedScore > bestTrackedScore) {
        bestTrackedScore = trackedScore
        bestY = y
      }
    }

    previousY = bestY
    rawTracePoints.push({ x, y: bestY })
  }

  const tracePoints = rawTracePoints.map((point, index, points) => {
    const neighbors = points.slice(Math.max(0, index - 2), Math.min(points.length, index + 3))
    const smoothedY = average(neighbors.map((neighbor) => neighbor.y))
    return { x: point.x, y: Number(smoothedY.toFixed(1)) }
  })

  if (gapMm <= 0.5 || gapMm > 80) {
    return null
  }

  return {
    gapMm,
    confidence: Number(clamp(0.42 + bestScore / 140, 0.45, 0.68).toFixed(2)),
    note: `Linear close-up joint seam detected. Estimate uses the selected ${pipeDiameterMm}mm pipe size and detected pixels; calibrate for measurement-grade accuracy.`,
    debug: {
      pipeDetected: false,
      imageWidth: width,
      imageHeight: height,
      pipeDiameterMm,
      gapPixels,
      mmPerPixel: assumedMmPerPixel,
      edgeStrength: Number(bestScore.toFixed(1)),
      enhancementUsed: true,
      failureStage: 'linear-close-up-joint',
      overlayHints: {
        jointTrace: tracePoints,
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

function detectVerticalJointGap(gray, width, height, pipeDiameterMm) {
  const startX = Math.floor(width * 0.08)
  const endX = Math.ceil(width * 0.92)
  const startY = Math.floor(height * 0.12)
  const endY = Math.ceil(height * 0.88)
  const columnDarkness = []

  for (let x = startX; x < endX; x += 1) {
    let sum = 0
    for (let y = startY; y < endY; y += 1) {
      sum += 255 - gray[y * width + x]
    }
    columnDarkness.push(sum / Math.max(1, endY - startY))
  }

  let bestScore = 0
  let bestIndex = -1
  let leftEdge = -1
  let rightEdge = -1

  for (let index = 3; index < columnDarkness.length - 3; index += 1) {
    const local = average(columnDarkness.slice(index - 2, index + 3))
    const left = average(columnDarkness.slice(Math.max(0, index - 24), Math.max(1, index - 8)))
    const right = average(columnDarkness.slice(Math.min(columnDarkness.length - 1, index + 8), Math.min(columnDarkness.length, index + 24)))
    const score = local - Math.max(left, right)
    if (score > bestScore) {
      bestScore = score
      bestIndex = index
    }
  }

  if (bestScore < 18 || bestIndex < 0) {
    const baseline = average(columnDarkness)
    const darkThreshold = baseline * 1.18
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

        if (widthOk && contrast > bestScore) {
          bestScore = contrast
          bestIndex = Math.round((runStart + runEnd) / 2)
          leftEdge = startX + runStart
          rightEdge = startX + runEnd
        }
        runStart = -1
      }
    }
  }

  if (bestScore < 12 || bestIndex < 0) {
    return null
  }

  const centerX = startX + bestIndex
  const threshold = columnDarkness[bestIndex] - bestScore * 0.45

  if (leftEdge < 0 || rightEdge < 0) {
    leftEdge = centerX
    rightEdge = centerX

    while (leftEdge > startX && columnDarkness[leftEdge - startX] > threshold) {
      leftEdge -= 1
    }

    while (rightEdge < endX - 1 && columnDarkness[rightEdge - startX] > threshold) {
      rightEdge += 1
    }
  }

  const fallbackGapPixels = Math.max(2, rightEdge - leftEdge)
  const rawCenterTrace = []
  const rawLeftEdge = []
  const rawRightEdge = []
  const gapPixelSamples = []
  const rowStep = Math.max(10, Math.floor((endY - startY) / 34))
  const searchRadius = Math.max(18, Math.round(fallbackGapPixels * 2.8))
  let previousX = centerX

  for (let y = startY; y <= endY; y += rowStep) {
    let bestX = centerX
    let bestTrackedScore = Number.NEGATIVE_INFINITY
    const localStartX = Math.max(startX + 2, centerX - searchRadius)
    const localEndX = Math.min(endX - 2, centerX + searchRadius)

    for (let x = localStartX; x <= localEndX; x += 1) {
      let darkness = 0
      let count = 0

      for (let offset = -3; offset <= 3; offset += 1) {
        const sampleY = clamp(y + offset, startY, endY - 1)
        darkness += 255 - gray[sampleY * width + x]
        count += 1
      }

      const localScore = darkness / Math.max(1, count)
      const continuityPenalty = Math.abs(x - previousX) * 1.35
      const trackedScore = localScore - continuityPenalty
      if (trackedScore > bestTrackedScore) {
        bestTrackedScore = trackedScore
        bestX = x
      }
    }

    const localDarkness = []
    for (let x = localStartX; x <= localEndX; x += 1) {
      let darkness = 0
      let count = 0

      for (let offset = -3; offset <= 3; offset += 1) {
        const sampleY = clamp(y + offset, startY, endY - 1)
        darkness += 255 - gray[sampleY * width + x]
        count += 1
      }

      localDarkness.push(darkness / Math.max(1, count))
    }

    const peakDarkness = Math.max(...localDarkness)
    const baselineDarkness = average([
      ...localDarkness.slice(0, Math.min(6, localDarkness.length)),
      ...localDarkness.slice(Math.max(0, localDarkness.length - 6)),
    ])
    const edgeThreshold = Math.max(baselineDarkness + 10, peakDarkness * 0.48)
    const localBestIndex = clamp(Math.round(bestX - localStartX), 0, localDarkness.length - 1)
    let localLeft = localBestIndex
    let localRight = localBestIndex

    while (localLeft > 0 && localDarkness[localLeft] >= edgeThreshold) {
      localLeft -= 1
    }

    while (localRight < localDarkness.length - 1 && localDarkness[localRight] >= edgeThreshold) {
      localRight += 1
    }

    const detectedLeft = localStartX + localLeft
    const detectedRight = localStartX + localRight
    const detectedWidth = detectedRight - detectedLeft

    if (detectedWidth >= 2 && detectedWidth <= width * 0.36) {
      const center = (detectedLeft + detectedRight) / 2
      previousX = center
      rawLeftEdge.push({ x: detectedLeft, y })
      rawRightEdge.push({ x: detectedRight, y })
      rawCenterTrace.push({ x: center, y })
      gapPixelSamples.push(detectedWidth)
    } else {
      previousX = bestX
      rawLeftEdge.push({ x: leftEdge, y })
      rawRightEdge.push({ x: rightEdge, y })
      rawCenterTrace.push({ x: bestX, y })
      gapPixelSamples.push(fallbackGapPixels)
    }
  }

  const smoothXTrace = (points) => points.map((point, index) => {
    const neighbors = points.slice(Math.max(0, index - 2), Math.min(points.length, index + 3))
    const smoothedX = average(neighbors.map((neighbor) => neighbor.x))
    return { x: Number(smoothedX.toFixed(1)), y: point.y }
  })
  const tracePoints = smoothXTrace(rawCenterTrace)
  const leftTrace = smoothXTrace(rawLeftEdge)
  const rightTrace = smoothXTrace(rawRightEdge)
  const sampledGapPixels = median(gapPixelSamples)
  const gapPixels = Number(Math.max(sampledGapPixels, fallbackGapPixels).toFixed(1))
  const assumedMmPerPixel = estimateVerticalBlackGapMmPerPixel(pipeDiameterMm)
  const gapMm = Number((gapPixels * assumedMmPerPixel).toFixed(1))

  if (gapMm <= 0.5 || gapMm > 80) {
    return null
  }

  return {
    gapMm,
    confidence: Number(clamp(0.42 + bestScore / 140, 0.45, 0.68).toFixed(2)),
    note: `Vertical close-up joint seam detected. Estimate uses the two detected black-gap edges with the restored vertical-slot pixel scale; selected pipe size is ${pipeDiameterMm}mm.`,
    debug: {
      pipeDetected: false,
      imageWidth: width,
      imageHeight: height,
      pipeDiameterMm,
      gapPixels,
      gapPixelSamples: gapPixelSamples.map((sample) => Number(sample.toFixed(1))),
      mmPerPixel: assumedMmPerPixel,
      edgeStrength: Number(bestScore.toFixed(1)),
      enhancementUsed: true,
      failureStage: 'linear-close-up-joint',
      overlayHints: {
        jointTrace: tracePoints,
        jointEdgeA: leftTrace,
        jointEdgeB: rightTrace,
        gapLine: {
          x1: Number(centerX.toFixed(1)),
          y1: startY,
          x2: Number(centerX.toFixed(1)),
          y2: endY,
        },
      },
    },
  }
}

function measureGapFromKnownCircle(gray, width, height, pipeDiameterMm, centerX, centerY, innerRadiusPx, enhancementUsed = false) {
  const gapWidths = []
  const brightThresholdSamples = []
  const coveredSectors = new Set()
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
      pipeDiameterMm,
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

function loadOpenCv() {
  if (cvReady) {
    return cvReady
  }

  cvReady = new Promise((resolve, reject) => {
    let settled = false
    const timeout = setTimeout(() => {
      cleanupTimers()
      reject(new Error(`OpenCV timeout at stage: ${lastStage}`))
    }, 25000)
    const pollInterval = setInterval(() => {
      if (settled) {
        return
      }

      const candidate = cvModule || self.cv
      if (candidate && candidate.Mat) {
        debug('runtime-ready-via-poll')
        finalizeReady(candidate)
      }
    }, 100)

    const cleanupTimers = () => {
      clearTimeout(timeout)
      clearInterval(pollInterval)
    }

    const finalizeReady = (cvInstance) => {
      if (settled) {
        return
      }
      if (!cvInstance || !cvInstance.Mat) {
        cleanupTimers()
        reject(new Error('OpenCV runtime initialized but cv.Mat missing'))
        return
      }

      const mat = new cvInstance.Mat()
      mat.delete()

      settled = true
      cvModule = cvInstance
      self.cv = cvInstance
      debug('mat-warmup-ok')
      cleanupTimers()
      resolve()
    }

    try {
      debug('loading-opencv-script')

      const runtimeConfig = {
        locateFile(path) {
          if (path.endsWith('.wasm')) {
            return '/opencv/opencv_js.wasm'
          }
          return path
        },
        onRuntimeInitialized() {
          debug('runtime-initialized')
          finalizeReady(cvModule || self.cv)
        },
        onAbort(message) {
          cleanupTimers()
          reject(new Error(`OpenCV aborted: ${message}`))
        },
      }

      self.Module = runtimeConfig
      delete self.cv
      importScripts('/opencv/opencv.js')
      debug('opencv-script-imported')

      if (!self.cv) {
        debug('opencv-global-missing')
        clearTimeout(timeout)
        reject(new Error('OpenCV script imported but did not expose self.cv'))
        return
      }

      debug(`opencv-global-ready:${typeof self.cv}`)

      if (typeof self.cv.then === 'function') {
        debug('awaiting-cv-promise')
        self.cv.then(
          (resolvedCv) => {
            debug('runtime-initialized')
            finalizeReady(resolvedCv)
          },
          (error) => {
            cleanupTimers()
            reject(error instanceof Error ? error : new Error(String(error)))
          },
        )
        return
      }

      if (self.cv.Mat) {
        debug('runtime-already-ready')
        finalizeReady(self.cv)
        return
      }

      debug('opencv-global-present-without-mat-or-then')
    } catch (error) {
      cleanupTimers()
      reject(error)
    }
  })

  return cvReady
}

async function measureGap(request) {
  const pipeDiameterMm = request.pipeDiameterMm || DEFAULT_PIPE_DIAMETER_MM

  if (!request.blob || typeof createImageBitmap !== 'function' || typeof OffscreenCanvas === 'undefined') {
    throw new Error('Image processing APIs are unavailable in this worker.')
  }

  debug('measure-request-received', request.imageId)
  await loadOpenCv()
  const cv = cvModule
  debug('opencv-ready-for-measure', request.imageId)

  const bitmap = await createImageBitmap(request.blob)
  const scale = Math.min(1, MAX_PROCESS_DIMENSION / Math.max(bitmap.width, bitmap.height))
  const width = Math.max(1, Math.round(bitmap.width * scale))
  const height = Math.max(1, Math.round(bitmap.height * scale))
  const canvas = new OffscreenCanvas(width, height)
  const context = canvas.getContext('2d')

  if (!context) {
    bitmap.close()
    throw new Error('Could not create worker canvas context.')
  }

  context.drawImage(bitmap, 0, 0, width, height)
  const imageData = enhanceImageData(context.getImageData(0, 0, width, height))
  const grayMap = buildGrayMap(imageData)
  const source = cv.matFromImageData(imageData)
  const gray = new cv.Mat()
  const blurred = new cv.Mat()
  const circles = new cv.Mat()

  try {
    debug('running-hough-circles', request.imageId)
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
      const linearMeasured =
        detectHorizontalJointGap(grayMap, width, height, pipeDiameterMm) ||
        detectVerticalJointGap(grayMap, width, height, pipeDiameterMm)
      if (linearMeasured) {
        debug('linear-joint-measurement-completed', request.imageId)
        return {
          imageId: request.imageId,
          originalGapMm: linearMeasured.gapMm,
          status: classifyGap(linearMeasured.gapMm, pipeDiameterMm),
          confidence: linearMeasured.confidence,
          measurementSource: 'cv',
          measurementNote: linearMeasured.note,
          cvDebug: linearMeasured.debug,
          overlayHints: linearMeasured.debug.overlayHints,
        }
      }
      throw new Error('OpenCV did not detect a valid pipe opening.')
    }

    let bestCircle = null
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
      throw new Error('OpenCV circle scoring returned no usable opening.')
    }

    debug('measuring-gap-from-circle', request.imageId)
    const measured = measureGapFromKnownCircle(grayMap, width, height, pipeDiameterMm, bestCircle.x, bestCircle.y, bestCircle.r, true)

    if (!measured) {
      const linearMeasured =
        detectHorizontalJointGap(grayMap, width, height, pipeDiameterMm) ||
        detectVerticalJointGap(grayMap, width, height, pipeDiameterMm)
      if (linearMeasured) {
        debug('linear-joint-measurement-completed-after-circle-fallback', request.imageId)
        return {
          imageId: request.imageId,
          originalGapMm: linearMeasured.gapMm,
          status: classifyGap(linearMeasured.gapMm, pipeDiameterMm),
          confidence: linearMeasured.confidence,
          measurementSource: 'cv',
          measurementNote: linearMeasured.note,
          cvDebug: linearMeasured.debug,
          overlayHints: linearMeasured.debug.overlayHints,
        }
      }
      throw new Error('Pipe opening was detected, but joint gap extraction failed.')
    }

    debug('measurement-completed', request.imageId)
    return {
      imageId: request.imageId,
      originalGapMm: measured.gapMm,
      status: classifyGap(measured.gapMm, pipeDiameterMm),
      confidence: measured.confidence,
      measurementSource: 'cv',
      measurementNote: measured.note,
      cvDebug: measured.debug,
      overlayHints: measured.debug.overlayHints,
    }
  } finally {
    circles.delete()
    blurred.delete()
    gray.delete()
    source.delete()
    bitmap.close()
  }
}

self.onmessage = async (event) => {
  try {
    if (event.data.type === 'WARMUP') {
      debug('warmup-requested')
      await loadOpenCv()
      debug('warmup-ok-posting')
      self.postMessage({
        type: 'WARMUP_OK',
        stage: lastStage,
      })
      return
    }

    if (event.data.type === 'MEASURE') {
      const result = await measureGap(event.data.request)
      self.postMessage({
        type: 'MEASURE_OK',
        result,
        stage: lastStage,
      })
    }
  } catch (error) {
    self.postMessage({
      type: event.data.type === 'MEASURE' ? 'MEASURE_ERROR' : 'WARMUP_ERROR',
      imageId: event.data.request?.imageId ?? '__worker__',
      message: error instanceof Error ? error.message : 'OpenCV worker failed',
      stage: lastStage,
    })
  }
}
