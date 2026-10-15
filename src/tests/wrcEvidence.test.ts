import { describe, expect, it } from 'vitest'
import { classifyWrcEvidence } from '../lib/wrcEvidence'

describe('WRc evidence states', () => {
  it('does not invent a successful result when evidence is missing', () => {
    expect(classifyWrcEvidence(undefined)).toBe('MISSING_RESPONSE')
  })

  it('distinguishes integrity, unavailability, inference failure and low confidence', () => {
    expect(classifyWrcEvidence({ status: 'EXTERNAL_CLASSIFIER_INTEGRITY_FAILURE' })).toBe('INTEGRITY_FAILURE')
    expect(classifyWrcEvidence({ status: 'EXTERNAL_CLASSIFIER_UNAVAILABLE' })).toBe('MODEL_UNAVAILABLE')
    expect(classifyWrcEvidence({ status: 'INFERENCE_FAILED' })).toBe('INFERENCE_FAILED')
    expect(classifyWrcEvidence({ status: 'LOW_CONFIDENCE_CLASSIFICATION', confidence: 0.2 })).toBe('LOW_CONFIDENCE')
  })

  it('does not reinterpret an unmapped or ambiguous output as normal', () => {
    expect(classifyWrcEvidence({ status: 'SUCCESS', confidence: 0.9, mapping_status: 'UNMAPPED' })).toBe('UNMAPPED')
    expect(classifyWrcEvidence({ status: 'SUCCESS', confidence: 0.9, mapping_status: 'AMBIGUOUS' })).toBe('AMBIGUOUS')
    expect(classifyWrcEvidence({ status: 'SUCCESS', confidence: 0.9, mapping_status: 'DIRECT' })).toBe('SUCCESS')
  })
})
