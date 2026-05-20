import { runCvMeasurement, type CvWorkerRequest, type CvWorkerResponse } from '../lib/cvMeasurement'

interface CvWorkerErrorResponse {
  imageId: string
  error: string
}

self.onmessage = async (event: MessageEvent<CvWorkerRequest>) => {
  try {
    const response: CvWorkerResponse = await runCvMeasurement(event.data)
    self.postMessage(response)
  } catch (error) {
    const response: CvWorkerErrorResponse = {
      imageId: event.data.imageId,
      error: error instanceof Error ? error.message : 'CV worker failed',
    }
    self.postMessage(response)
  }
}
