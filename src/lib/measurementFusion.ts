import type { AiMeasurementReview, MeasurementAudit, MeasurementOverlayHints, MeasurementSource } from '../types'
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

function classifyMeasurement(gapMm: number, cvResult: CvWorkerResponse) {
  return classifyGap(gapMm, cvResult.cvDebug?.pipeDiameterMm)
}

export function fuseMeasurementWithAi(cvResult: CvWorkerResponse, aiReview?: AiMeasurementReview): FusedMeasurementResult {
  const closeUpJoint = isCloseUpJointMeasurement(cvResult)

  if (!aiReview) {
    if (closeUpJoint && !hasVisibleScaleReference(cvResult)) {
      return {
        ...cvResult,
        status: classifyMeasurement(cvResult.originalGapMm, cvResult).status,
        confidence: Number(Math.min(cvResult.confidence, 0.62).toFixed(2)),
        measurementSource: 'ai-estimated',
        measurementNote:
          'Estimated from the pixel distance between the two detected black-gap edges. Add calibration for measurement-grade millimetres.',
        measurementAudit: {
          originalSource: cvResult.measurementSource,
          finalSource: 'ai-estimated',
          cvConfidence: cvResult.confidence,
          cvGapMm: cvResult.originalGapMm,
          enhancementUsed: cvResult.cvDebug?.enhancementUsed,
          decision: 'Close-up joint used the two detected black-gap edges and an uncalibrated pixel-to-mm estimate.',
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
  const aiGap = aiReview.estimatedGapMm
  const gapDelta = typeof aiGap === 'number' ? Math.abs(aiGap - cvResult.originalGapMm) : Number.POSITIVE_INFINITY
  const aiAgrees = aiReview.cvPlausible && gapDelta <= 3.5

  if (
    closeUpJoint &&
    hasVisibleScaleReference(cvResult) &&
    aiReview.usable &&
    aiReview.jointVisible &&
    typeof aiGap === 'number' &&
    aiGap > 0.5 &&
    aiReview.confidence >= 0.35
  ) {
    return {
      ...cvResult,
      originalGapMm: aiGap,
      status: classifyMeasurement(aiGap, cvResult).status,
      confidence: Number(Math.max(0.5, aiReview.confidence).toFixed(2)),
      measurementSource: 'ai-estimated',
      measurementNote: aiReview.reason,
      aiReview,
      overlayHints: chooseOverlayHints(aiReview.overlayHints, cvResult.overlayHints),
      measurementAudit: {
        originalSource: cvResult.measurementSource,
        finalSource: 'ai-estimated',
        cvConfidence,
        aiConfidence: aiReview.confidence,
        cvGapMm: cvResult.originalGapMm,
        aiEstimatedGapMm: aiGap,
        enhancementUsed: cvResult.cvDebug?.enhancementUsed,
        decision: 'Close-up joint image used CV for seam tracing and Gemini for the final millimetre estimate.',
      },
    }
  }

  if (closeUpJoint && !hasVisibleScaleReference(cvResult)) {
    if (cvResult.originalGapMm > 0.5) {
      return {
        ...cvResult,
        status: classifyMeasurement(cvResult.originalGapMm, cvResult).status,
        confidence: Number(Math.max(0.35, Math.min(aiReview.confidence, 0.68)).toFixed(2)),
        measurementSource: 'ai-estimated',
        measurementNote:
          `${aiReview.reason} Estimated mm is calculated from the pixel distance between the two detected black-gap edges; calibration will make it more accurate.`,
        aiReview,
        overlayHints: chooseOverlayHints(aiReview.overlayHints, cvResult.overlayHints),
        measurementAudit: {
          originalSource: cvResult.measurementSource,
          finalSource: 'ai-estimated',
          cvConfidence,
          aiConfidence: aiReview.confidence,
          cvGapMm: cvResult.originalGapMm,
          aiEstimatedGapMm: aiGap,
          enhancementUsed: cvResult.cvDebug?.enhancementUsed,
          decision: 'Close-up black gap used the two CV edge traces for a rough uncalibrated millimetre estimate; Gemini provided visual review only.',
        },
      }
    }

    return {
      ...cvResult,
      originalGapMm: 0,
      status: 'REVIEW',
      confidence: Number(Math.max(0.45, Math.min(aiReview.confidence, 0.62)).toFixed(2)),
      measurementSource: 'ai-review',
      measurementNote:
        'The black joint gap was detected and traced, but this close-up crop has no calibrated scale reference. Add a ruler/calibration target or use manual confirmation for millimetres.',
      aiReview,
      overlayHints: chooseOverlayHints(aiReview.overlayHints, cvResult.overlayHints),
      measurementAudit: {
        originalSource: cvResult.measurementSource,
        finalSource: 'ai-review',
        cvConfidence,
        aiConfidence: aiReview.confidence,
        cvGapMm: cvResult.originalGapMm,
        aiEstimatedGapMm: aiGap,
        enhancementUsed: cvResult.cvDebug?.enhancementUsed,
        decision: 'Close-up joint was visible, but no visible scale reference was available, so AI millimetres were not accepted.',
      },
    }
  }

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
      status: classifyMeasurement(fusedGap, cvResult).status,
      confidence: Number(Math.min(0.94, Math.max(cvConfidence, aiReview.confidence) + 0.04).toFixed(2)),
      measurementSource: 'ai-assisted',
      measurementNote: buildNote('ai-assisted', cvResult.measurementNote, aiReview),
      aiReview,
      overlayHints: chooseOverlayHints(aiReview.overlayHints, cvResult.overlayHints),
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

  if (
    cvResult.measurementSource === 'fallback' &&
    aiReview.usable &&
    aiReview.pipeOpeningVisible &&
    typeof aiGap === 'number' &&
    aiGap > 0.5 &&
    aiReview.confidence >= 0.45
  ) {
    return {
      ...cvResult,
      originalGapMm: aiGap,
      status: classifyMeasurement(aiGap, cvResult).status,
      confidence: Number(Math.max(0.5, aiReview.confidence).toFixed(2)),
      measurementSource: 'ai-estimated',
      measurementNote: buildNote('ai-estimated', cvResult.measurementNote, aiReview),
      aiReview,
      overlayHints: chooseOverlayHints(aiReview.overlayHints, cvResult.overlayHints),
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
      overlayHints: chooseOverlayHints(aiReview.overlayHints, cvResult.overlayHints),
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
    overlayHints: chooseOverlayHints(aiReview.overlayHints, cvResult.overlayHints),
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
