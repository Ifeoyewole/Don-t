type OpenCvModule = typeof import('@techstark/opencv-js')

let cvReadyPromise: Promise<OpenCvModule> | null = null

function isOpenCvReady(instance: OpenCvModule): boolean {
  return typeof (instance as { Mat?: unknown })?.Mat === 'function'
}

export async function loadOpenCv(): Promise<OpenCvModule> {
  if (cvReadyPromise) {
    return cvReadyPromise
  }

  cvReadyPromise = new Promise(async (resolve, reject) => {
    try {
      const importedModule = await import('@techstark/opencv-js')
      const cv = (
        'default' in importedModule ? importedModule.default : importedModule
      ) as OpenCvModule

      if (isOpenCvReady(cv)) {
        resolve(cv)
        return
      }

      const moduleLike = cv as OpenCvModule & {
        onRuntimeInitialized?: () => void
      }

      moduleLike.onRuntimeInitialized = () => {
        resolve(cv)
      }

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
