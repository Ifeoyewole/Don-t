import { describe, expect, it } from 'vitest'
import { validateInspectionContextSuggestion } from './contextSuggestions'

const advisory = () => ({
  model: 'gemini-3.1-pro-preview',
  domain_status: 'PIPE_JOINT_INSPECTION',
  processing_allowed: true,
  image_quality_usable: true,
  suggested_joint_type: 'CIRCULAR_OPENING',
  suggested_inspection_context: 'Visible circular interface. Inspector review required.',
  possible_gap_visible: true,
  calibration: {
    pipe_diameter_mm: 900,
    source: 'MANHOLE_METADATA',
    calibration_reference_id: null,
    verified: false,
    authority: 'UNVERIFIED_METADATA',
  },
  review_required: true,
  reason: 'Image-only suggestions; not a measurement',
})

describe('editable AI context suggestion safety contract', () => {
  it('accepts image hints and nominal diameter only as unverified metadata', () => {
    const result = validateInspectionContextSuggestion(advisory(), 900)
    expect(result.suggested_joint_type).toBe('CIRCULAR_OPENING')
    expect(result.calibration.verified).toBe(false)
    expect(result.review_required).toBe(true)
  })

  it('refuses AI-claimed verified calibration or references', () => {
    expect(() => validateInspectionContextSuggestion({
      ...advisory(),
      calibration: { ...advisory().calibration, verified: true },
    }, 900)).toThrow()
    expect(() => validateInspectionContextSuggestion({
      ...advisory(),
      calibration: { ...advisory().calibration, calibration_reference_id: 'INVENTED' },
    }, 900)).toThrow()
  })

  it('rejects mismatched manhole diameter', () => {
    expect(() => validateInspectionContextSuggestion(advisory(), 600)).toThrow()
  })

  it('rejects suggestions when the image fails domain validation', () => {
    expect(() => validateInspectionContextSuggestion({
      ...advisory(),
      processing_allowed: false,
    }, 900)).toThrow()
  })
})
