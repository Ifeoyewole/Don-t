type OpenCvModule = typeof import('@techstark/opencv-js')

let cvReadyPromise: Promise<OpenCvModule> | null = null

type LoadOpenCvOptions = {
  onStage?: (message: string) => void
}

function isOpenCvReady(instance: OpenCvModule): boolean {
  return typeof (instance as { Mat?: unknown })?.Mat === 'function'
}

export async function loadOpenCv(options?: LoadOpenCvOptions): Promise<OpenCvModule> {
  options?.onStage?.('loadOpenCv called')

  if (cvReadyPromise) {
    options?.onStage?.('reusing existing OpenCV promise')
    return cvReadyPromise
  }

  options?.onStage?.('starting OpenCV module import')
  cvReadyPromise = import('@techstark/opencv-js')
    .then(
      (importedModule) =>
        new Promise<OpenCvModule>((resolve, reject) => {
          options?.onStage?.('OpenCV module import resolved')
          const cv = (
            'default' in importedModule ? importedModule.default : importedModule
          ) as OpenCvModule

          if (isOpenCvReady(cv)) {
            options?.onStage?.('OpenCV runtime already ready')
            resolve(cv)
            return
          }

          options?.onStage?.('waiting for OpenCV runtime initialization callback')
          const moduleLike = cv as OpenCvModule & {
            onRuntimeInitialized?: () => void
          }

          moduleLike.onRuntimeInitialized = () => {
            options?.onStage?.('OpenCV runtime initialization callback fired')
            resolve(cv)
          }

          setTimeout(() => {
            if (isOpenCvReady(cv)) {
              options?.onStage?.('OpenCV runtime became ready before timeout check ended')
              resolve(cv)
              return
            }

            options?.onStage?.('OpenCV runtime initialization timed out')
            reject(new Error('OpenCV runtime initialization timed out'))
          }, 15000)
        }),
    )
    .catch((error) => {
      options?.onStage?.(error instanceof Error ? `OpenCV import failed: ${error.message}` : 'OpenCV import failed')
      cvReadyPromise = null
      throw error
    })

  return cvReadyPromise
}
