let cvReady = null
let cvModule = null
let lastStage = 'worker-created'

const DEFAULT_PIPE_DIAMETER_MM = 225
const MAX_PROCESS_DIMENSION = 720
const ANGLE_STEPS = 48

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

function classifyGap(gapMm) {
  if (gapMm < 3) {
    return 'REVIEW'
  }

  if (gapMm <= 15) {
    return 'PASS'
  }

  if (gapMm <= 25) {
    return 'REVIEW'
  }

  return 'FAIL'
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

function measureGapFromKnownCircle(gray, width, height, pipeDiameterMm, centerX, centerY, innerRadiusPx) {
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
  const imageData = context.getImageData(0, 0, width, height)
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
    const measured = measureGapFromKnownCircle(grayMap, width, height, pipeDiameterMm, bestCircle.x, bestCircle.y, bestCircle.r)

    if (!measured) {
      throw new Error('Pipe opening was detected, but joint gap extraction failed.')
    }

    debug('measurement-completed', request.imageId)
    return {
      imageId: request.imageId,
      originalGapMm: measured.gapMm,
      status: classifyGap(measured.gapMm),
      confidence: measured.confidence,
      measurementSource: 'cv',
      measurementNote: measured.note,
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
