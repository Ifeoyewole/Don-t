import { runCvMeasurement, type CvWorkerRequest, type CvWorkerResponse } from './cvMeasurement'

interface CvWorkerErrorResponse {
  kind: 'error'
  imageId: string
  error: string
}

interface CvWorkerReadyResponse {
  kind: 'ready'
}

interface CvWorkerDebugResponse {
  kind: 'debug'
  imageId: string
  message: string
}

interface CvWorkerMeasureResponse extends CvWorkerResponse {
  kind: 'measure'
}

type CvWorkerMessage = CvWorkerReadyResponse | CvWorkerMeasureResponse | CvWorkerErrorResponse | CvWorkerDebugResponse

function isBrowserWorkerAvailable(): boolean {
  return typeof Worker !== 'undefined' && typeof URL !== 'undefined'
}

const CV_WORKER_TIMEOUT_MS = 8000
const CV_WORKER_WARMUP_TIMEOUT_MS = 5000
let sharedWorker: Worker | null = null
let workerReadyPromise: Promise<void> | null = null
let workerReadyState: 'idle' | 'warming' | 'ready' = 'idle'
let resolveWorkerReady: (() => void) | null = null
let rejectWorkerReady: ((reason?: unknown) => void) | null = null
let workerWarmupTimeoutId: ReturnType<typeof setTimeout> | null = null
let latestWorkerDebugMessage = 'worker not started'

type PendingRequest = {
  reject: (reason?: unknown) => void
  request: CvWorkerRequest
  resolve: (value: CvWorkerResponse | PromiseLike<CvWorkerResponse>) => void
  timeoutId: ReturnType<typeof setTimeout>
}

const pendingRequests = new Map<string, PendingRequest>()

function destroySharedWorker(): void {
  if (sharedWorker) {
    sharedWorker.terminate()
    sharedWorker = null
  }

  if (workerWarmupTimeoutId) {
    clearTimeout(workerWarmupTimeoutId)
    workerWarmupTimeoutId = null
  }

  workerReadyPromise = null
  workerReadyState = 'idle'
  resolveWorkerReady = null
  rejectWorkerReady = null
  latestWorkerDebugMessage = 'worker not started'
}

function ensureWorker(): Worker {
  if (sharedWorker) {
    return sharedWorker
  }

  latestWorkerDebugMessage = 'worker constructed'
  sharedWorker = new Worker(new URL('../workers/cvWorker.ts', import.meta.url), {
    type: 'module',
  })

  sharedWorker.onmessage = (event: MessageEvent<CvWorkerMessage>) => {
    const payload = event.data

    if (payload.kind === 'debug') {
      latestWorkerDebugMessage = payload.message
      console.info(`[cv-worker] ${payload.imageId}: ${payload.message}`)
      return
    }

    if (payload.kind === 'ready') {
      if (workerWarmupTimeoutId) {
        clearTimeout(workerWarmupTimeoutId)
        workerWarmupTimeoutId = null
      }
      workerReadyState = 'ready'
      resolveWorkerReady?.()
      resolveWorkerReady = null
      rejectWorkerReady = null
      return
    }

    const pending = pendingRequests.get(payload.imageId)

    if (!pending) {
      if (payload.kind === 'error' && payload.imageId === '__worker__') {
        if (workerWarmupTimeoutId) {
          clearTimeout(workerWarmupTimeoutId)
          workerWarmupTimeoutId = null
        }
        rejectWorkerReady?.(new Error(`${payload.error} | debug trail: ${latestWorkerDebugMessage}`))
        destroySharedWorker()
      }
      return
    }

    clearTimeout(pending.timeoutId)
    pendingRequests.delete(payload.imageId)

    if (payload.kind === 'error') {
      pending.reject(new Error(`OpenCV worker failed: ${payload.error} | debug trail: ${latestWorkerDebugMessage}`))
      return
    }

    pending.resolve(payload)
  }

  sharedWorker.onerror = () => {
    const inflight = Array.from(pendingRequests.entries())
    pendingRequests.clear()
    destroySharedWorker()

    for (const [, pending] of inflight) {
      clearTimeout(pending.timeoutId)
      pending.reject(new Error(`CV worker could not continue processing. Last stage: ${latestWorkerDebugMessage}`))
    }
  }

  return sharedWorker
}

async function warmUpWorker(): Promise<void> {
  if (workerReadyState === 'ready') {
    return
  }

  const worker = ensureWorker()

  if (workerReadyPromise) {
    return workerReadyPromise
  }

  workerReadyState = 'warming'
  workerReadyPromise = new Promise<void>((resolve, reject) => {
    resolveWorkerReady = resolve
    rejectWorkerReady = reject
    workerWarmupTimeoutId = setTimeout(() => {
      reject(
        new Error(
          `CV worker warmup timed out after ${Math.round(CV_WORKER_WARMUP_TIMEOUT_MS / 1000)} seconds. Last stage: ${latestWorkerDebugMessage}`,
        ),
      )
      destroySharedWorker()
    }, CV_WORKER_WARMUP_TIMEOUT_MS)
  })

  worker.postMessage({ kind: 'warmup' })
  return workerReadyPromise
}

export async function measureWithCv(request: CvWorkerRequest): Promise<CvWorkerResponse> {
  if (!isBrowserWorkerAvailable()) {
    return runCvMeasurement(request)
  }

  try {
    await warmUpWorker()
  } catch (error) {
    throw new Error(error instanceof Error ? `OpenCV warmup failed: ${error.message}` : 'OpenCV warmup failed.', {
      cause: error,
    })
  }

  return new Promise<CvWorkerResponse>((resolve, reject) => {
    const worker = ensureWorker()
    const timeoutId: ReturnType<typeof setTimeout> = setTimeout(() => {
      pendingRequests.delete(request.imageId)
      reject(
        new Error(
          `OpenCV processing timed out after ${Math.round(CV_WORKER_TIMEOUT_MS / 1000)} seconds. Last stage: ${latestWorkerDebugMessage}`,
        ),
      )
    }, CV_WORKER_TIMEOUT_MS)

    pendingRequests.set(request.imageId, {
      request,
      resolve,
      reject,
      timeoutId,
    })

    try {
      worker.postMessage({ kind: 'measure', request })
    } catch {
      clearTimeout(timeoutId)
      pendingRequests.delete(request.imageId)
      destroySharedWorker()
      reject(new Error(`OpenCV worker could not start. Last stage: ${latestWorkerDebugMessage}`))
    }
  })
}
