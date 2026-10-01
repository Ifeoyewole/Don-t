import type { InspectionStatus } from '../types'

export interface ToleranceClassification {
  status: InspectionStatus
  meaning: string
}

const BASE_PIPE_DIAMETER_MM = 225
const BASE_TOO_SMALL_MM = 3
const BASE_PASS_MAX_MM = 15
const BASE_REVIEW_MAX_MM = 25

export function classifyGap(gapMm: number, pipeDiameterMm = BASE_PIPE_DIAMETER_MM): ToleranceClassification {
  const scale = Math.max(0.5, pipeDiameterMm / BASE_PIPE_DIAMETER_MM)
  const tooSmallMax = BASE_TOO_SMALL_MM * scale
  const passMax = BASE_PASS_MAX_MM * scale
  const reviewMax = BASE_REVIEW_MAX_MM * scale

  if (gapMm < tooSmallMax) {
    return {
      status: 'REVIEW',
      meaning: 'Gap too small',
    }
  }

  if (gapMm <= passMax) {
    return {
      status: 'PASS',
      meaning: 'Within tolerance',
    }
  }

  if (gapMm <= reviewMax) {
    return {
      status: 'REVIEW',
      meaning: 'Larger than typical',
    }
  }

  return {
    status: 'FAIL',
    meaning: 'Excessive gap',
  }
}
