import { runCvMeasurement, type CvWorkerRequest, type CvWorkerResponse } from './cvMeasurement'

interface CvWorkerErrorResponse {
  imageId: string
  error: string
}

function isBrowserWorkerAvailable(): boolean {
  return typeof Worker !== 'undefined' && typeof URL !== 'undefined'
}

export async function measureWithCv(request: CvWorkerRequest): Promise<CvWorkerResponse> {
  if (!isBrowserWorkerAvailable()) {
    return runCvMeasurement(request)
  }

  return new Promise<CvWorkerResponse>((resolve, reject) => {
    const worker = new Worker(new URL('../workers/cvWorker.ts', import.meta.url), {
      type: 'module',
    })

    const cleanup = () => {
      worker.terminate()
    }

    worker.onmessage = (event: MessageEvent<CvWorkerResponse | CvWorkerErrorResponse>) => {
      const payload = event.data
      cleanup()

      if ('error' in payload) {
        reject(new Error(payload.error))
        return
      }

      resolve(payload)
    }

    worker.onerror = () => {
      cleanup()
      runCvMeasurement(request).then(resolve).catch(reject)
    }

    worker.postMessage(request)
  })
}
