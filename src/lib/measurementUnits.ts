import type { InspectionResult } from '../types/domain'

export type GapDisplayUnit = 'px' | 'mm' | 'm'

export type GapDisplayEvidence = Pick<
  InspectionResult,
  'authoritativeGapMm' | 'executionSource' | 'measurementSource' | 'cvDebug' | 'unifiedEvidence'
>

const safeNonNegative = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0

/** Never convert nominal pipe diameter, model guesses or research pixels to physical units. */
export function getAuthorizedMillimetres(item: GapDisplayEvidence): number | null {
  const mm = item.authoritativeGapMm
  if (
    item.executionSource !== 'CLOUD_AUTHORITATIVE' ||
    ['manual', 'offline-preview', 'fallback', 'ai-review'].includes(item.measurementSource ?? '') ||
    !safeNonNegative(mm)
  ) {
    return null
  }
  return mm
}

export function getPixelEvidence(item: GapDisplayEvidence): number | null {
  const pixels = item.cvDebug?.gapPixels
  return safeNonNegative(pixels) ? pixels : null
}

/** Presentation only. Changing display units cannot change inspection status or stored measurements. */
export function formatGapForUnit(item: GapDisplayEvidence, unit: GapDisplayUnit): string {
  if (unit === 'px') {
    const pixels = getPixelEvidence(item)
    return pixels === null ? 'Pixel width unavailable' : `${pixels.toFixed(1)} px (image evidence)`
  }

  const research = item.executionSource === 'CLOUD_RESEARCH_UNVERIFIED' ? item.unifiedEvidence : undefined
  const researchMm = research?.joint_measurement.calibration_authority_verified === true &&
    research.joint_measurement.calibration_status === 'VERIFIED_IMAGE_JOINT_PLANE' &&
    research.physical_gap_mm === research.joint_measurement.physical_gap_mm && safeNonNegative(research.physical_gap_mm)
    ? research.physical_gap_mm : null
  const mm = getAuthorizedMillimetres(item) ?? researchMm
  if (mm === null) {
    return 'Measurement unavailable — calibration or reliable joint boundaries required'
  }
  return unit === 'mm'
    ? `${mm.toLocaleString('en-GB', { minimumFractionDigits: 1, maximumFractionDigits: 2 })} mm`
    : `${(mm / 1000).toLocaleString('en-GB', { minimumFractionDigits: 3, maximumFractionDigits: 6 })} m`
}
