import type { CvMeasurementDebug, InspectionStatus, MeasurementOverlayHints } from '../types'
import type { CvWorkerRequest, CvWorkerResponse } from './cvMeasurement'

type WarmupDebugMessage = {
  imageId?: string
  stage: string
  type: 'DEBUG'
}

type WarmupOkMessage = {
  stage: string
  type: 'WARMUP_OK'
}

type WarmupErrorMessage = {
  imageId?: string
  message: string
  stage: string
  type: 'WARMUP_ERROR'
}

type MeasureOkMessage = {
  result: CvWorkerResponse
  stage: string
  type: 'MEASURE_OK'
}

type MeasureErrorMessage = {
  imageId: string
  message: string
  stage: string
  type: 'MEASURE_ERROR'
}

type CvWorkerMessage =
  | WarmupDebugMessage
  | WarmupOkMessage
  | WarmupErrorMessage
  | MeasureOkMessage
  | MeasureErrorMessage

interface FastApiPoint2D {
  x: number
  y: number
}

interface FastApiRaySample {
  angle_deg: number
  inner_point: FastApiPoint2D
  outer_point: FastApiPoint2D
  gap_px: number
  gap_mm: number
  status: string
}

interface FastApiDetectedCircle {
  center_x: number
  center_y: number
  radius_px: number
  radius_mm?: number
  confidence?: number
}

interface FastApiOverlayHints {
  inner_circle?: FastApiDetectedCircle
  outer_circle?: FastApiDetectedCircle
  center?: FastApiPoint2D
  ray_samples?: FastApiRaySample[]
  gap_lines?: Array<{ start: FastApiPoint2D; end: FastApiPoint2D; gap_px: number; gap_mm: number; status: string }>
  seam_left_edge?: FastApiPoint2D[]
  seam_right_edge?: FastApiPoint2D[]
  bounding_box?: number[]
}

interface FastApiCvDebug {
  pixels_per_mm?: number
  inner_radius_px?: number
  outer_radius_px?: number
  num_samples?: number
  raw_min_gap_mm?: number
  raw_max_gap_mm?: number
  raw_mean_gap_mm?: number
  std_gap_mm?: number
  processing_time_ms?: number
  debug_image_base64?: string
}

interface FastApiMeasurementPayload {
  joint_type?: string
  pipe_diameter_mm?: number
  pixels_per_mm?: number
  mean_gap_mm?: number
  min_gap_mm?: number
  max_gap_mm?: number
  overall_status?: 'PASS' | 'WARNING' | 'FAIL' | 'REVIEW'
  overlay_hints?: FastApiOverlayHints
  debug_info?: FastApiCvDebug
  timestamp?: string
}

const FASTAPI_MEASURE_TIMEOUT_MS = 10000
const CV_WORKER_WARMUP_TIMEOUT_MS = 30000
const CV_WORKER_MEASURE_TIMEOUT_MS = 30000

function isBrowserWorkerAvailable(): boolean {
  return typeof Worker !== 'undefined'
}

function createCvWorker(): Worker {
  return new Worker('/workers/cv-worker.js?v=pipe-aware-tolerance-150-cal-3')
}

function appendDebugStage(debugTrail: string[], stage: string): string[] {
  const nextTrail = [...debugTrail, stage].slice(-30)
  console.info(`[cv-worker] ${stage}`)
  return nextTrail
}

function formatTrail(debugTrail: string[]): string {
  return debugTrail.join(' > ')
}

export async function measureWithFastApi(request: CvWorkerRequest): Promise<CvWorkerResponse> {
  if (!request.blob) {
    throw new Error('No image blob provided for FastAPI measurement.')
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), FASTAPI_MEASURE_TIMEOUT_MS)

  try {
    const formData = new FormData()
    formData.append('file', request.blob, request.fileName || 'inspection.jpg')
    if (request.pipeDiameterMm) {
      formData.append('pipe_diameter_mm', String(request.pipeDiameterMm))
    }
    formData.append('joint_type', 'CIRCULAR_OPENING')
    formData.append('return_debug_image', 'false')

    const response = await fetch('/api/v1/cv/measure', {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    })

    if (!response.ok) {
      const errorText = await response.text().catch(() => '')
      throw new Error(`FastAPI measurement endpoint returned HTTP ${response.status}: ${errorText || response.statusText}`)
    }

    const data: FastApiMeasurementPayload = await response.json()
    const gapMm = Number((data.mean_gap_mm ?? data.debug_info?.raw_mean_gap_mm ?? 0).toFixed(1))
    const status: InspectionStatus =
      data.overall_status === 'PASS' ? 'PASS' : data.overall_status === 'FAIL' ? 'FAIL' : 'REVIEW'

    const stdGap = data.debug_info?.std_gap_mm ?? 0
    const confidence =
      typeof data.debug_info?.std_gap_mm === 'number'
        ? Math.max(0.72, Math.min(0.98, Number((1 - stdGap / Math.max(1, gapMm)).toFixed(2))))
        : 0.9

    const overlayHints: MeasurementOverlayHints = {
      pipeCenter: data.overlay_hints?.center
        ? { x: data.overlay_hints.center.x, y: data.overlay_hints.center.y }
        : data.overlay_hints?.inner_circle
          ? { x: data.overlay_hints.inner_circle.center_x, y: data.overlay_hints.inner_circle.center_y }
          : undefined,
      innerRadiusPx: data.overlay_hints?.inner_circle?.radius_px ?? data.debug_info?.inner_radius_px,
      outerRadiusPx: data.overlay_hints?.outer_circle?.radius_px ?? data.debug_info?.outer_radius_px,
      gapLine: data.overlay_hints?.ray_samples?.[0]
        ? {
            x1: data.overlay_hints.ray_samples[0].inner_point.x,
            y1: data.overlay_hints.ray_samples[0].inner_point.y,
            x2: data.overlay_hints.ray_samples[0].outer_point.x,
            y2: data.overlay_hints.ray_samples[0].outer_point.y,
          }
        : undefined,
      jointTrace: data.overlay_hints?.seam_left_edge?.map((p) => ({ x: p.x, y: p.y })),
      jointEdgeA: data.overlay_hints?.seam_left_edge?.map((p) => ({ x: p.x, y: p.y })),
      jointEdgeB: data.overlay_hints?.seam_right_edge?.map((p) => ({ x: p.x, y: p.y })),
    }

    const cvDebug: CvMeasurementDebug = {
      pipeDetected: true,
      pipeDiameterMm: data.pipe_diameter_mm ?? request.pipeDiameterMm,
      mmPerPixel: data.pixels_per_mm ? Number((1 / data.pixels_per_mm).toFixed(4)) : undefined,
      innerRadiusPx: data.debug_info?.inner_radius_px ?? data.overlay_hints?.inner_circle?.radius_px,
      outerRadiusPx: data.debug_info?.outer_radius_px ?? data.overlay_hints?.outer_circle?.radius_px,
      visibleSectors: data.debug_info?.num_samples,
      gapPixels:
        data.debug_info?.inner_radius_px && data.debug_info?.outer_radius_px
          ? Number((data.debug_info.outer_radius_px - data.debug_info.inner_radius_px).toFixed(1))
          : undefined,
      overlayHints,
    }

    return {
      imageId: request.imageId,
      originalGapMm: gapMm,
      status,
      confidence,
      measurementSource: 'fastapi',
      measurementNote: `FastAPI OpenCV: gap ${gapMm.toFixed(1)} mm (${data.debug_info?.num_samples ?? 0} samples, ${(data.debug_info?.processing_time_ms ?? 0).toFixed(0)}ms)`,
      cvDebug,
      overlayHints,
    }
  } finally {
    clearTimeout(timeoutId)
  }
}

export async function measureWithWebWorker(request: CvWorkerRequest): Promise<CvWorkerResponse> {
  if (!isBrowserWorkerAvailable()) {
    throw new Error('Web workers are unavailable in this browser.')
  }

  const worker = createCvWorker()

  return new Promise<CvWorkerResponse>((resolve, reject) => {
    let debugTrail = ['worker-created']
    let phase: 'warming' | 'measuring' = 'warming'

    const timeoutId = setTimeout(() => {
      cleanup()
      const timeoutLabel =
        phase === 'warming'
          ? `OpenCV worker warmup timed out. Trail: ${formatTrail(debugTrail)}`
          : `OpenCV worker measurement timed out after ${Math.round(CV_WORKER_MEASURE_TIMEOUT_MS / 1000)} seconds. Trail: ${formatTrail(debugTrail)}`
      reject(new Error(timeoutLabel))
    }, CV_WORKER_WARMUP_TIMEOUT_MS + CV_WORKER_MEASURE_TIMEOUT_MS)

    const cleanup = (): void => {
      clearTimeout(timeoutId)
      worker.removeEventListener('message', handleMessage)
      worker.removeEventListener('error', handleError)
      worker.terminate()
    }

    const handleError = (event: ErrorEvent): void => {
      cleanup()
      reject(new Error(`Worker crashed: ${event.message}. Trail: ${formatTrail(debugTrail)}`))
    }

    const handleMessage = (event: MessageEvent<CvWorkerMessage>): void => {
      const data = event.data

      if (data.type === 'DEBUG') {
        if (!data.imageId || data.imageId === request.imageId || data.imageId === '__worker__') {
          debugTrail = appendDebugStage(debugTrail, data.stage)
        }
        return
      }

      if (data.type === 'WARMUP_ERROR') {
        cleanup()
        reject(new Error(`${data.message}. Last stage: ${data.stage}. Trail: ${formatTrail(debugTrail)}`))
        return
      }

      if (data.type === 'MEASURE_ERROR' && data.imageId === request.imageId) {
        cleanup()
        reject(new Error(`${data.message}. Last stage: ${data.stage}. Trail: ${formatTrail(debugTrail)}`))
        return
      }

      if (data.type === 'WARMUP_OK') {
        phase = 'measuring'
        worker.postMessage({ type: 'MEASURE', request })
        return
      }

      if (data.type === 'MEASURE_OK') {
        cleanup()
        resolve(data.result)
      }
    }

    worker.addEventListener('message', handleMessage)
    worker.addEventListener('error', handleError)
    worker.postMessage({ type: 'WARMUP' })
  })
}

export async function measureWithCv(request: CvWorkerRequest): Promise<CvWorkerResponse> {
  try {
    return await measureWithFastApi(request)
  } catch (error) {
    console.warn('[cvClient] FastAPI unavailable, falling back to in-browser Web Worker', error)
    return await measureWithWebWorker(request)
  }
}
