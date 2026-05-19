import cv from '@techstark/opencv-js'

let cvReadyPromise: Promise<typeof cv> | null = null

function isOpenCvReady(instance: typeof cv): boolean {
  return typeof instance?.Mat === 'function'
}

export function loadOpenCv(): Promise<typeof cv> {
  if (cvReadyPromise) {
    return cvReadyPromise
  }

  cvReadyPromise = new Promise((resolve, reject) => {
    try {
      if (isOpenCvReady(cv)) {
        resolve(cv)
        return
      }

      const onRuntimeInitialized = () => {
        resolve(cv)
      }

      const moduleLike = cv as typeof cv & {
        onRuntimeInitialized?: () => void
      }

      moduleLike.onRuntimeInitialized = onRuntimeInitialized

      setTimeout(() => {
        if (isOpenCvReady(cv)) {
          resolve(cv)
          return
        }

        reject(new Error('OpenCV runtime initialization timed out'))
      }, 15000)
    } catch (error) {
      reject(error)
    }
  })

  return cvReadyPromise
}
