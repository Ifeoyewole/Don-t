import { describe, expect, it } from 'vitest'
import {
  formatGapForUnit,
  getAuthorizedMillimetres,
  type GapDisplayEvidence,
} from './measurementUnits'

const verified: GapDisplayEvidence = {
  executionSource: 'CLOUD_AUTHORITATIVE',
  measurementSource: 'fastapi',
  authoritativeGapMm: 134,
  cvDebug: { pipeDetected: true, gapPixels: 127 },
}

describe('physical gap unit display', () => {
  it('uses actual pixel evidence instead of implying a physical scale', () => {
    expect(formatGapForUnit(verified, 'px')).toBe('127.0 px (image evidence)')
  })

  it('converts only existing authoritative millimetres into metres', () => {
    expect(formatGapForUnit(verified, 'mm')).toBe('134.0 mm')
    expect(formatGapForUnit(verified, 'm')).toBe('0.1340 m')
    expect(getAuthorizedMillimetres(verified)).toBe(134)
  })

  it('does not convert 134 image pixels to physical units', () => {
    const uncalibrated: GapDisplayEvidence = {
      executionSource: 'CLOUD_AUTHORITATIVE',
      measurementSource: 'fastapi',
      authoritativeGapMm: null,
      cvDebug: { pipeDetected: true, gapPixels: 134 },
    }
    expect(formatGapForUnit(uncalibrated, 'px')).toContain('134.0 px')
    expect(formatGapForUnit(uncalibrated, 'mm')).toContain('verified calibration required')
    expect(formatGapForUnit(uncalibrated, 'm')).toContain('verified calibration required')
  })

  it('blocks non-cloud, manual, model-only and provisional values', () => {
    for (const partial of [
      { executionSource: 'LOCAL_PREVIEW_UNVERIFIED' as const },
      { executionSource: undefined },
      { measurementSource: 'manual' as const },
      { measurementSource: 'ai-review' as const },
      { measurementSource: 'fallback' as const },
    ]) {
      const item = { ...verified, ...partial }
      expect(getAuthorizedMillimetres(item)).toBeNull()
      expect(formatGapForUnit(item, 'm')).toContain('verified calibration required')
    }
  })

  it('rejects non-finite and negative values', () => {
    for (const value of [NaN, Number.POSITIVE_INFINITY, -5]) {
      const item = { ...verified, authoritativeGapMm: value }
      expect(getAuthorizedMillimetres(item)).toBeNull()
    }
  })

  it('does not derive pixels from physical values when none were reported', () => {
    const item = { ...verified, cvDebug: undefined }
    expect(formatGapForUnit(item, 'px')).toBe('Pixel width unavailable')
  })
})
