import type { InspectionResult } from '../types'

type LegacyInspectionResult = Partial<InspectionResult> & Pick<InspectionResult, 'id'>

function finiteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

/** Normalize records written before physical measurements became nullable.
 * Explicit numeric zero is preserved; only absent/non-finite values become null.
 */
export function normalizeLegacyInspectionResult(record: LegacyInspectionResult): InspectionResult {
  const originalGapMm = finiteNumber(record.originalGapMm) ? record.originalGapMm : null
  const validOverride = record.overrideApplied === true && finiteNumber(record.overrideValueMm)
  const finalGapMm = validOverride
    ? record.overrideValueMm!
    : originalGapMm == null
      ? null
      : finiteNumber(record.finalGapMm) ? record.finalGapMm : originalGapMm
  const unreliable = record.resultStatus === 'REJECTED_UNRELIABLE' || Boolean(record.rejectionReason)

  return {
    ...record,
    originalGapMm,
    finalGapMm,
    status: unreliable || (finalGapMm == null && !validOverride) ? 'REVIEW' : (record.status ?? 'REVIEW'),
    overrideApplied: validOverride,
    jointType: record.jointType ?? 'CIRCULAR_OPENING',
    geometrySelectionProvenance: record.geometrySelectionProvenance ?? 'LEGACY_DEFAULT',
  } as InspectionResult
}
