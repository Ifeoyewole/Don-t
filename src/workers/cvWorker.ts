import { runCvMeasurement, type CvWorkerRequest, type CvWorkerResponse } from '../lib/cvMeasurement'
import { loadOpenCv } from '../lib/opencv'

interface CvWorkerErrorResponse {
  kind: 'error'
  imageId: string
  error: string
}

interface CvWorkerReadyResponse {
  kind: 'ready'
}

type CvWorkerMessage =
  | {
      kind: 'warmup'
    }
  | {
      kind: 'measure'
      request: CvWorkerRequest
    }

self.onmessage = async (event: MessageEvent<CvWorkerMessage>) => {
  if (event.data.kind === 'warmup') {
    try {
      await loadOpenCv()
      const response: CvWorkerReadyResponse = { kind: 'ready' }
      self.postMessage(response)
    } catch (error) {
      const response: CvWorkerErrorResponse = {
        kind: 'error',
        imageId: '__worker__',
        error: error instanceof Error ? error.message : 'CV worker warmup failed',
      }
      self.postMessage(response)
    }
    return
  }

  try {
    const response: CvWorkerResponse & { kind: 'measure' } = {
      kind: 'measure',
      ...(await runCvMeasurement(event.data.request)),
    }
    self.postMessage(response)
  } catch (error) {
    const response: CvWorkerErrorResponse = {
      kind: 'error',
      imageId: event.data.request.imageId,
      error: error instanceof Error ? error.message : 'CV worker failed',
    }
    self.postMessage(response)
  }
}
