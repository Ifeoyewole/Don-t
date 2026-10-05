import type { AiMeasurementReview, CvMeasurementDebug } from '../types'
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

function createDevMockReview(request: AiMeasurementRequest): AiMeasurementReview {
  const cvDebug = request.cvDebug
  const hasPipeGeometry = Boolean(cvDebug?.pipeDetected && cvDebug.innerRadiusPx && cvDebug.gapPixels)
  const fallbackResult = request.measurementSource === 'fallback'

  return {
    provider: 'mock-dev',
    model: 'mock-dev-stub',
    usable: hasPipeGeometry || !fallbackResult,
    jointVisible: hasPipeGeometry || !fallbackResult,
    pipeOpeningVisible: Boolean(cvDebug?.pipeDetected),
    cvPlausible: !fallbackResult && request.gapMm > 0.5 && request.gapMm < 80,
    estimatedGapMm: null, // Strictly null: AI is visual assistance only, no physical mm authority
    confidence: fallbackResult ? 0.40 : 0.75,
    reason: 'Dev mock visual observation (non-authoritative test stub).',
    retakeMessage: undefined,
    overlayHints: cvDebug?.overlayHints,
    reviewedAt: createTimestamp(),
  }
}

function createUnavailableReview(): AiMeasurementReview {
  return {
    provider: 'unavailable',
    model: 'AI_SEMANTIC_UNAVAILABLE',
    usable: false,
    jointVisible: false,
    pipeOpeningVisible: false,
    cvPlausible: false,
    estimatedGapMm: null,
    confidence: 0.0,
    reason: 'AI_SEMANTIC_UNAVAILABLE: Semantic visual review is unavailable in current mode.',
    retakeMessage: 'AI semantic review is unavailable. Please verify connection to inspection service.',
    reviewedAt: createTimestamp(),
  }
}

export async function reviewMeasurementWithAi(request: AiMeasurementRequest): Promise<AiMeasurementReview> {
  const isDev = import.meta.env.DEV

  // In production, frontend client does NOT make direct untrusted calls to external Gemini APIs.
  // All authoritative AI domain validation and explanation occurs on Cloud Run via Vertex AI.
  if (!isDev) {
    return createUnavailableReview()
  }

  // Explicit dev mode fallback only
  return createDevMockReview(request)
}
