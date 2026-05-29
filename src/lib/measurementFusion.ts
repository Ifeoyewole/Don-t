import type { AiMeasurementReview, MeasurementAudit, MeasurementSource } from '../types'
import type { CvWorkerResponse } from './cvMeasurement'
import { classifyGap } from '../utils'

export interface FusedMeasurementResult extends CvWorkerResponse {
  aiReview?: AiMeasurementReview
  measurementAudit: MeasurementAudit
}

function buildNote(source: MeasurementSource, cvNote: string | undefined, aiReview: AiMeasurementReview): string {
  if (source === 'ai-assisted') {
    return cvNote
      ? `${cvNote} AI review confirmed the joint geometry.`
      : 'AI review confirmed the CV joint geometry before final classification.'
  }

  if (source === 'ai-estimated') {
    return aiReview.reason
  }

  if (source === 'ai-review') {
    return 'AI can see inspection geometry, but a reliable millimetre value still needs manual confirmation.'
  }

  return cvNote ?? aiReview.reason
}

export function fuseMeasurementWithAi(cvResult: CvWorkerResponse, aiReview?: AiMeasurementReview): FusedMeasurementResult {
  if (!aiReview) {
    return {
      ...cvResult,
      measurementAudit: {
        originalSource: cvResult.measurementSource,
        finalSource: cvResult.measurementSource,
        cvConfidence: cvResult.confidence,
        cvGapMm: cvResult.originalGapMm,
        enhancementUsed: cvResult.cvDebug?.enhancementUsed,
        decision: 'OpenCV confidence was high enough; AI review was not required.',
      },
    }
  }

  const cvConfidence = cvResult.confidence
  const aiGap = aiReview.estimatedGapMm
  const gapDelta = typeof aiGap === 'number' ? Math.abs(aiGap - cvResult.originalGapMm) : Number.POSITIVE_INFINITY
  const aiAgrees = aiReview.cvPlausible && gapDelta <= 3.5

  if (cvResult.measurementSource !== 'fallback' && cvConfidence >= 0.82) {
    return {
      ...cvResult,
      aiReview,
      measurementAudit: {
        originalSource: cvResult.measurementSource,
        finalSource: 'cv',
        cvConfidence,
        aiConfidence: aiReview.confidence,
        cvGapMm: cvResult.originalGapMm,
        aiEstimatedGapMm: aiGap,
        enhancementUsed: cvResult.cvDebug?.enhancementUsed,
        decision: 'CV confidence stayed high; AI review was recorded for audit only.',
      },
    }
  }

  if (cvResult.measurementSource !== 'fallback' && aiAgrees) {
    const fusedGap = Number(((cvResult.originalGapMm * 0.7 + Number(aiGap) * 0.3)).toFixed(1))
    return {
      ...cvResult,
      originalGapMm: fusedGap,
      status: classifyGap(fusedGap).status,
      confidence: Number(Math.min(0.94, Math.max(cvConfidence, aiReview.confidence) + 0.04).toFixed(2)),
      measurementSource: 'ai-assisted',
      measurementNote: buildNote('ai-assisted', cvResult.measurementNote, aiReview),
      aiReview,
      overlayHints: aiReview.overlayHints ?? cvResult.overlayHints,
      measurementAudit: {
        originalSource: cvResult.measurementSource,
        finalSource: 'ai-assisted',
        cvConfidence,
        aiConfidence: aiReview.confidence,
        cvGapMm: cvResult.originalGapMm,
        aiEstimatedGapMm: aiGap,
        enhancementUsed: cvResult.cvDebug?.enhancementUsed,
        decision: 'CV confidence was moderate and AI agreed within tolerance, so the result was fused.',
      },
    }
  }

  if (cvResult.measurementSource === 'fallback' && aiReview.usable && typeof aiGap === 'number' && aiGap > 0.5 && aiReview.confidence >= 0.45) {
    return {
      ...cvResult,
      originalGapMm: aiGap,
      status: classifyGap(aiGap).status,
      confidence: Number(Math.max(0.5, aiReview.confidence).toFixed(2)),
      measurementSource: 'ai-estimated',
      measurementNote: buildNote('ai-estimated', cvResult.measurementNote, aiReview),
      aiReview,
      overlayHints: aiReview.overlayHints ?? cvResult.overlayHints,
      measurementAudit: {
        originalSource: cvResult.measurementSource,
        finalSource: 'ai-estimated',
        cvConfidence,
        aiConfidence: aiReview.confidence,
        cvGapMm: cvResult.originalGapMm,
        aiEstimatedGapMm: aiGap,
        enhancementUsed: cvResult.cvDebug?.enhancementUsed,
        decision: 'CV fell back, but AI produced a high-confidence usable estimate.',
      },
    }
  }

  if (cvResult.measurementSource === 'fallback' && aiReview.usable && (aiReview.jointVisible || aiReview.pipeOpeningVisible)) {
    return {
      ...cvResult,
      originalGapMm: 0,
      status: 'REVIEW',
      confidence: Number(Math.max(0.45, aiReview.confidence).toFixed(2)),
      measurementSource: 'ai-review',
      measurementNote: buildNote('ai-review', cvResult.measurementNote, aiReview),
      aiReview,
      overlayHints: aiReview.overlayHints ?? cvResult.overlayHints,
      measurementAudit: {
        originalSource: cvResult.measurementSource,
        finalSource: 'ai-review',
        cvConfidence,
        aiConfidence: aiReview.confidence,
        cvGapMm: cvResult.originalGapMm,
        aiEstimatedGapMm: aiGap,
        enhancementUsed: cvResult.cvDebug?.enhancementUsed,
        decision: 'AI found visible inspection geometry, but the final millimetre value needs manual confirmation.',
      },
    }
  }

  return {
    ...cvResult,
    aiReview,
    measurementNote: aiReview.retakeMessage ?? buildNote(cvResult.measurementSource, cvResult.measurementNote, aiReview),
    overlayHints: aiReview.overlayHints ?? cvResult.overlayHints,
    measurementAudit: {
      originalSource: cvResult.measurementSource,
      finalSource: cvResult.measurementSource,
      cvConfidence,
      aiConfidence: aiReview.confidence,
      cvGapMm: cvResult.originalGapMm,
      aiEstimatedGapMm: aiGap,
      enhancementUsed: cvResult.cvDebug?.enhancementUsed,
      decision: 'AI and CV did not agree strongly enough; keep the result cautious and guide review or retake.',
    },
  }
}
