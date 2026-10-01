import { runCvMeasurement, type CvWorkerRequest, type CvWorkerResponse } from '../lib/cvMeasurement'
import { loadOpenCv } from '../lib/opencv'

interface CvWorkerErrorResponse {
  kind: 'error'
  imageId: string
  error: string
}

interface CvWorkerDebugResponse {
  kind: 'debug'
  imageId: string
  message: string
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

let lastDebugMessage = 'worker booted'

function postDebug(imageId: string, message: string): void {
  lastDebugMessage = message
  const response: CvWorkerDebugResponse = {
    kind: 'debug',
    imageId,
    message,
  }
  self.postMessage(response)
}

self.onmessage = async (event: MessageEvent<CvWorkerMessage>) => {
  if (event.data.kind === 'warmup') {
    try {
      postDebug('__worker__', 'warmup requested')
      await loadOpenCv({
        onStage: (message) => postDebug('__worker__', message),
      })
      postDebug('__worker__', 'warmup completed')
      const response: CvWorkerReadyResponse = { kind: 'ready' }
      self.postMessage(response)
    } catch (error) {
      const response: CvWorkerErrorResponse = {
        kind: 'error',
        imageId: '__worker__',
        error:
          error instanceof Error
            ? `${error.message} | last stage: ${lastDebugMessage}`
            : `CV worker warmup failed | last stage: ${lastDebugMessage}`,
      }
      self.postMessage(response)
    }
    return
  }

  try {
    postDebug(event.data.request.imageId, 'measure request received')
    const response: CvWorkerResponse & { kind: 'measure' } = {
      kind: 'measure',
      ...(await runCvMeasurement(event.data.request)),
    }
    postDebug(event.data.request.imageId, 'measurement completed')
    self.postMessage(response)
  } catch (error) {
    const response: CvWorkerErrorResponse = {
      kind: 'error',
      imageId: event.data.request.imageId,
      error:
        error instanceof Error
          ? `${error.message} | last stage: ${lastDebugMessage}`
          : `CV worker failed | last stage: ${lastDebugMessage}`,
    }
    self.postMessage(response)
  }
}
