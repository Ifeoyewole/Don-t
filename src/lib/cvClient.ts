import { runCvMeasurement, type CvWorkerRequest, type CvWorkerResponse } from './cvMeasurement'

interface CvWorkerErrorResponse {
  imageId: string
  error: string
}

function isBrowserWorkerAvailable(): boolean {
  return typeof Worker !== 'undefined' && typeof URL !== 'undefined'
}

const CV_WORKER_TIMEOUT_MS = 15000

export async function measureWithCv(request: CvWorkerRequest): Promise<CvWorkerResponse> {
  if (!isBrowserWorkerAvailable()) {
    return runCvMeasurement(request)
  }

  return new Promise<CvWorkerResponse>((resolve, reject) => {
    const worker = new Worker(new URL('../workers/cvWorker.ts', import.meta.url), {
      type: 'module',
    })
    let settled = false
    const timeoutId: ReturnType<typeof setTimeout> = setTimeout(() => {
      if (settled) {
        return
      }

      cleanup()
      runCvMeasurement(request, {
        skipOpenCv: true,
        fallbackNote: `Estimated result shown after the CV worker timed out at ${Math.round(CV_WORKER_TIMEOUT_MS / 1000)} seconds.`,
      }).then(resolve).catch(reject)
    }, CV_WORKER_TIMEOUT_MS)

    const cleanup = () => {
      settled = true
      clearTimeout(timeoutId)
      worker.terminate()
    }

    worker.onmessage = (event: MessageEvent<CvWorkerResponse | CvWorkerErrorResponse>) => {
      if (settled) {
        return
      }

      const payload = event.data
      cleanup()

      if ('error' in payload) {
        runCvMeasurement(request, {
          skipOpenCv: true,
          fallbackNote: `Estimated result shown because the CV worker failed: ${payload.error}`,
        }).then(resolve).catch(reject)
        return
      }

      resolve(payload)
    }

    worker.onerror = () => {
      if (settled) {
        return
      }

      cleanup()
      runCvMeasurement(request, {
        skipOpenCv: true,
        fallbackNote: 'Estimated result shown because the CV worker could not start.',
      }).then(resolve).catch(reject)
    }

    worker.postMessage(request)
  })
}
