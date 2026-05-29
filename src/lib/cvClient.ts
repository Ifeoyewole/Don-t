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

const CV_WORKER_WARMUP_TIMEOUT_MS = 30000
const CV_WORKER_MEASURE_TIMEOUT_MS = 30000

function isBrowserWorkerAvailable(): boolean {
  return typeof Worker !== 'undefined'
}

function createCvWorker(): Worker {
  return new Worker('/workers/cv-worker.js?v=ai-assisted-debug-1')
}

function appendDebugStage(debugTrail: string[], stage: string): string[] {
  const nextTrail = [...debugTrail, stage].slice(-30)
  console.info(`[cv-worker] ${stage}`)
  return nextTrail
}

function formatTrail(debugTrail: string[]): string {
  return debugTrail.join(' > ')
}

export async function measureWithCv(request: CvWorkerRequest): Promise<CvWorkerResponse> {
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
