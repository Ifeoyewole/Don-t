import { describe, expect, it } from 'vitest'
import { normalizeLegacyInspectionResult } from '../db/migrations'

const base = {
  id: 'result-1', imageId: 'image-1', projectId: 'project-1', manholeId: 'mh-1',
  jointLabel: 'Joint 1', processedAt: '2026-01-01T00:00:00Z',
}

describe('legacy inspection migration', () => {
  it('normalizes unavailable physical values to null and never preserves a legacy PASS', () => {
    const migrated = normalizeLegacyInspectionResult({ ...base, status: 'PASS', overrideApplied: false })
    expect(migrated.originalGapMm).toBeNull()
    expect(migrated.finalGapMm).toBeNull()
    expect(migrated.status).toBe('REVIEW')
    expect(migrated.jointType).toBe('CIRCULAR_OPENING')
    expect(migrated.geometrySelectionProvenance).toBe('LEGACY_DEFAULT')
  })

  it('preserves a genuine measured zero', () => {
    const migrated = normalizeLegacyInspectionResult({
      ...base, originalGapMm: 0, finalGapMm: 0, status: 'PASS', overrideApplied: false,
    })
    expect(migrated.originalGapMm).toBe(0)
    expect(migrated.finalGapMm).toBe(0)
    expect(migrated.status).toBe('PASS')
  })

  it('forces rejected evidence to REVIEW while retaining an authorized override value', () => {
    const rejected = normalizeLegacyInspectionResult({
      ...base, originalGapMm: 4, finalGapMm: 4, status: 'PASS', overrideApplied: false,
      resultStatus: 'REJECTED_UNRELIABLE',
    })
    expect(rejected.status).toBe('REVIEW')
    const overridden = normalizeLegacyInspectionResult({
      ...base, status: 'PASS', overrideApplied: true, overrideValueMm: 3.5,
    })
    expect(overridden.finalGapMm).toBe(3.5)
    expect(overridden.overrideApplied).toBe(true)
  })
})
