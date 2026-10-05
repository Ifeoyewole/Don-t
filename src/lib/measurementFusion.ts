import type { AiMeasurementReview, MeasurementAudit, MeasurementOverlayHints } from '../types'
import type { CvWorkerResponse } from './cvMeasurement'

export interface FusedMeasurementResult extends CvWorkerResponse {
  aiReview?: AiMeasurementReview
  measurementAudit: MeasurementAudit
}

function chooseOverlayHints(aiHints: MeasurementOverlayHints | undefined, cvHints: MeasurementOverlayHints | undefined): MeasurementOverlayHints | undefined {
  if (aiHints?.jointTrace?.length || !cvHints?.jointTrace?.length) {
    return aiHints ?? cvHints
  }

  return {
    ...aiHints,
    jointTrace: cvHints.jointTrace,
  }
}

function isCloseUpJointMeasurement(cvResult: CvWorkerResponse): boolean {
  return (
    cvResult.cvDebug?.failureStage === 'linear-close-up-joint' ||
    Boolean(cvResult.cvDebug?.overlayHints?.jointTrace?.length && !cvResult.cvDebug.pipeDetected)
  )
}

function hasVisibleScaleReference(cvResult: CvWorkerResponse): boolean {
  return Boolean(cvResult.cvDebug?.pipeDetected && cvResult.cvDebug.mmPerPixel && cvResult.cvDebug.mmPerPixel > 0)
}

export function fuseMeasurementWithAi(cvResult: CvWorkerResponse, aiReview?: AiMeasurementReview): FusedMeasurementResult {
  if (cvResult.resultStatus === 'REJECTED_UNRELIABLE') {
    return {
      ...cvResult,
      originalGapMm: 0,
      status: 'REVIEW',
      resultStatus: 'REJECTED_UNRELIABLE',
      measurementNote: cvResult.rejectionReason
        ? `Rejected: ${cvResult.rejectionReason}`
        : cvResult.measurementNote,
      aiReview,
      measurementAudit: {
        originalSource: cvResult.measurementSource,
        finalSource: cvResult.measurementSource,
        cvConfidence: cvResult.confidence,
        aiConfidence: aiReview?.confidence,
        cvGapMm: 0,
        resultStatus: 'REJECTED_UNRELIABLE',
        rejectionReason: cvResult.rejectionReason,
        enhancementUsed: cvResult.cvDebug?.enhancementUsed,
        decision: 'Measurement rejected as unreliable; LLM fallback strictly disallowed for physical dimensions.',
      },
    }
  }

  const closeUpJoint = isCloseUpJointMeasurement(cvResult)

  if (!aiReview) {
    if (closeUpJoint && !hasVisibleScaleReference(cvResult)) {
      return {
        ...cvResult,
        originalGapMm: 0,
        status: 'REVIEW',
        confidence: Number(Math.min(cvResult.confidence, 0.62).toFixed(2)),
        measurementSource: 'ai-review',
        measurementNote:
          'Physical millimetre measurement requires a verified pipe diameter or calibration reference.',
        measurementAudit: {
          originalSource: cvResult.measurementSource,
          finalSource: 'ai-review',
          cvConfidence: cvResult.confidence,
          cvGapMm: cvResult.originalGapMm,
          enhancementUsed: cvResult.cvDebug?.enhancementUsed,
          decision: 'Close-up geometry was recorded in pixels only; uncalibrated millimetres were blocked.',
        },
      }
    }

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
  // AI is visual/contextual assistance only. It can never supply, blend, or replace
  // a physical millimetre result, even when a model emits a plausible number.
  if (cvResult.measurementSource === 'fallback') {
    return {
      ...cvResult,
      originalGapMm: 0,
      status: 'REVIEW',
      measurementSource: 'ai-review',
      measurementNote: aiReview.retakeMessage ?? 'OpenCV geometry was unavailable. AI observations are advisory and cannot create a millimetre measurement.',
      aiReview,
      overlayHints: chooseOverlayHints(aiReview.overlayHints, cvResult.overlayHints),
      measurementAudit: {
        originalSource: cvResult.measurementSource, finalSource: 'ai-review', cvConfidence,
        aiConfidence: aiReview.confidence, cvGapMm: cvResult.originalGapMm,
        enhancementUsed: cvResult.cvDebug?.enhancementUsed,
        decision: 'OpenCV did not produce physical geometry; AI estimate was blocked.',
      },
    }
  }

  if (closeUpJoint && !hasVisibleScaleReference(cvResult)) {
    return {
      ...cvResult, originalGapMm: 0, status: 'REVIEW', measurementSource: 'ai-review', aiReview,
      measurementNote: 'Physical millimetre measurement requires a verified pipe diameter or calibration reference.',
      overlayHints: chooseOverlayHints(aiReview.overlayHints, cvResult.overlayHints),
      measurementAudit: { originalSource: cvResult.measurementSource, finalSource: 'ai-review', cvConfidence, aiConfidence: aiReview.confidence, cvGapMm: cvResult.originalGapMm, enhancementUsed: cvResult.cvDebug?.enhancementUsed, decision: 'Uncalibrated close-up image retained pixel evidence only; AI measurement was blocked.' },
    }
  }

  return {
    ...cvResult,
    measurementSource: cvResult.measurementSource === 'ai-assisted' ? 'cv' : cvResult.measurementSource,
    aiReview,
    overlayHints: chooseOverlayHints(aiReview.overlayHints, cvResult.overlayHints),
    measurementAudit: {
      originalSource: cvResult.measurementSource,
      finalSource: cvResult.measurementSource === 'ai-assisted' ? 'cv' : cvResult.measurementSource,
      cvConfidence,
      aiConfidence: aiReview.confidence,
      cvGapMm: cvResult.originalGapMm,
      enhancementUsed: cvResult.cvDebug?.enhancementUsed,
      decision: 'AI visual review was recorded as advisory; the CV result was not altered.',
    },
  }
}
