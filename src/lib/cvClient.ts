import { runCvMeasurement, type CvWorkerRequest, type CvWorkerResponse } from './cvMeasurement'

interface CvWorkerErrorResponse {
  kind: 'error'
  imageId: string
  error: string
}

interface CvWorkerReadyResponse {
  kind: 'ready'
}

interface CvWorkerMeasureResponse extends CvWorkerResponse {
  kind: 'measure'
}

type CvWorkerMessage = CvWorkerReadyResponse | CvWorkerMeasureResponse | CvWorkerErrorResponse

function isBrowserWorkerAvailable(): boolean {
  return typeof Worker !== 'undefined' && typeof URL !== 'undefined'
}

const CV_WORKER_TIMEOUT_MS = 15000
const CV_WORKER_WARMUP_TIMEOUT_MS = 30000
let sharedWorker: Worker | null = null
let workerReadyPromise: Promise<void> | null = null
let workerReadyState: 'idle' | 'warming' | 'ready' = 'idle'
let resolveWorkerReady: (() => void) | null = null
let rejectWorkerReady: ((reason?: unknown) => void) | null = null
let workerWarmupTimeoutId: ReturnType<typeof setTimeout> | null = null

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
}

function ensureWorker(): Worker {
  if (sharedWorker) {
    return sharedWorker
  }

  sharedWorker = new Worker(new URL('../workers/cvWorker.ts', import.meta.url), {
    type: 'module',
  })

  sharedWorker.onmessage = (event: MessageEvent<CvWorkerMessage>) => {
    const payload = event.data

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
        rejectWorkerReady?.(new Error(payload.error))
        destroySharedWorker()
      }
      return
    }

    clearTimeout(pending.timeoutId)
    pendingRequests.delete(payload.imageId)

    if (payload.kind === 'error') {
      runCvMeasurement(
        pending.request,
        {
          skipOpenCv: true,
          fallbackNote: `Estimated result shown because the CV worker failed: ${payload.error}`,
        },
      ).then(pending.resolve).catch(pending.reject)
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
      pending.reject(new Error('CV worker could not continue processing.'))
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
      reject(new Error(`CV worker warmup timed out after ${Math.round(CV_WORKER_WARMUP_TIMEOUT_MS / 1000)} seconds.`))
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
    return runCvMeasurement(request, {
      skipOpenCv: true,
      fallbackNote:
        error instanceof Error
          ? `Estimated result shown because the CV engine could not warm up: ${error.message}`
          : 'Estimated result shown because the CV engine could not warm up.',
    })
  }

  return new Promise<CvWorkerResponse>((resolve, reject) => {
    const worker = ensureWorker()
    const timeoutId: ReturnType<typeof setTimeout> = setTimeout(() => {
      pendingRequests.delete(request.imageId)
      runCvMeasurement(request, {
        skipOpenCv: true,
        fallbackNote: `Estimated result shown after the CV worker timed out at ${Math.round(CV_WORKER_TIMEOUT_MS / 1000)} seconds.`,
      }).then(resolve).catch(reject)
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
      runCvMeasurement(request, {
        skipOpenCv: true,
        fallbackNote: 'Estimated result shown because the CV worker could not start.',
      }).then(resolve).catch(reject)
    }
  })
}
