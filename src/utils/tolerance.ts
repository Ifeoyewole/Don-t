import type { InspectionStatus } from '../types'

export interface ToleranceClassification {
  status: InspectionStatus
  meaning: string
}

export function classifyGap(gapMm: number): ToleranceClassification {
  if (gapMm < 3) {
    return {
      status: 'REVIEW',
      meaning: 'Gap too small',
    }
  }

  if (gapMm <= 15) {
    return {
      status: 'PASS',
      meaning: 'Within tolerance',
    }
  }

  if (gapMm <= 25) {
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
