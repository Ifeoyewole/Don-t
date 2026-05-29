import type { AiMeasurementReview, CvMeasurementDebug } from '../types'
import { createEnhancedImagePayload } from '../lib/imageEnhancement'
import { createTimestamp } from '../utils/identity'

export interface AiMeasurementRequest {
  imageId: string
  fileName: string
  mimeType?: string
  blob?: Blob
  pipeDiameterMm?: number
  gapMm: number
  confidence: number
  measurementSource: string
  cvDebug?: CvMeasurementDebug
}

function createMockReview(request: AiMeasurementRequest): AiMeasurementReview {
  const cvDebug = request.cvDebug
  const hasPipeGeometry = Boolean(cvDebug?.pipeDetected && cvDebug.innerRadiusPx && cvDebug.gapPixels)
  const lowConfidence = request.confidence < 0.74
  const fallbackResult = request.measurementSource === 'fallback'
  const estimatedGapMm = fallbackResult ? null : Number(request.gapMm.toFixed(1))
  const confidence = fallbackResult ? 0.42 : lowConfidence ? 0.68 : 0.84

  return {
    provider: 'mock-gemini',
    model: 'gemini-2.5-flash-mock',
    usable: hasPipeGeometry || !fallbackResult,
    jointVisible: hasPipeGeometry || !fallbackResult,
    pipeOpeningVisible: Boolean(cvDebug?.pipeDetected),
    cvPlausible: !fallbackResult && request.gapMm > 0.5 && request.gapMm < 80,
    estimatedGapMm,
    confidence,
    reason: fallbackResult
      ? 'AI review placeholder found insufficient CV geometry, so the photo should be retaken or reviewed.'
      : lowConfidence
        ? 'AI review placeholder accepts the CV result with caution because the visible joint evidence is partial.'
        : 'AI review placeholder confirms the CV geometry is suitable for calculation.',
    retakeMessage: fallbackResult
      ? 'Retake photo: keep the pipe opening centered and make the full joint ring edge visible.'
      : undefined,
    overlayHints: cvDebug?.overlayHints,
    reviewedAt: createTimestamp(),
  }
}

function shouldUseGeminiEndpoint(): boolean {
  return import.meta.env.VITE_AI_REVIEW_MODE === 'gemini'
}

async function reviewWithGeminiEndpoint(request: AiMeasurementRequest): Promise<AiMeasurementReview> {
  if (!request.blob) {
    throw new Error('Image blob is required for Gemini review.')
  }

  const image = await createEnhancedImagePayload(request.blob, request.mimeType ?? request.blob.type ?? 'image/jpeg')
  const response = await fetch('/api/ai/measure-photo', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      imageBase64: image.base64,
      mimeType: image.mimeType,
      enhancedForAi: image.enhanced,
      fileName: request.fileName,
      pipeDiameterMm: request.pipeDiameterMm,
      cv: {
        gapMm: request.gapMm,
        confidence: request.confidence,
        measurementSource: request.measurementSource,
        debug: request.cvDebug,
      },
    }),
  })

  if (!response.ok) {
    throw new Error(`Gemini review failed with status ${response.status}.`)
  }

  return (await response.json()) as AiMeasurementReview
}

export async function reviewMeasurementWithAi(request: AiMeasurementRequest): Promise<AiMeasurementReview> {
  if (!shouldUseGeminiEndpoint()) {
    return createMockReview(request)
  }

  try {
    return await reviewWithGeminiEndpoint(request)
  } catch (error) {
    console.warn(error instanceof Error ? error.message : 'Gemini review failed; using mock review.')
    return createMockReview(request)
  }
}
