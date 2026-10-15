import { afterEach, describe, expect, it, vi } from 'vitest'
import { measureWithFastApi } from '../lib/cvClient'

const request = {
  imageId: 'image-1',
  fileName: 'joint.jpg',
  orderIndex: 0,
  blob: new Blob(['image'], { type: 'image/jpeg' }),
  jointType: 'VERTICAL_SEAM' as const,
}

afterEach(() => vi.unstubAllGlobals())

describe('authoritative cloud response mapper', () => {
  it('preserves semantic, geometry, pixel gap, classifier and explanation evidence', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      joint_type: 'VERTICAL_SEAM',
      confidence_breakdown: { overall_confidence: 0.78 },
      mean_gap_px: 0,
      min_gap_px: 0,
      max_gap_px: 2,
      authoritative_gap_mm: null,
      overall_status: 'CALIBRATION_REQUIRED',
      result_status: 'REVIEW_REQUIRED',
      geometry_tier: 'ACCEPTABLE_GEOMETRY',
      engineering_result: 'REVIEW',
      authoritative_reason: 'Calibration required.',
      ai_explanation: 'Backend composed explanation.',
      semantic_gate: {
        domain_status: 'PIPE_JOINT_INSPECTION', processing_allowed: true,
        confidence: 0.91, model: 'gemini-2.5-flash', observation: 'A visible pipe joint.', user_message: 'Continue.',
      },
      classifier_evidence: {
        classifier: 'WRc InceptionResNetV2', model_id: 'wrc-v1', raw_prediction: 'Water', raw_code: 'W',
        confidence: 0.31, mapped_condition: null, mapping_status: 'UNMAPPED_OR_AMBIGUOUS', top_k: [], classification_status: 'REVIEW_REQUIRED',
      },
      overlay_hints: {},
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await measureWithFastApi(request)

    expect(result.executionSource).toBe('CLOUD_AUTHORITATIVE')
    expect(result.jointType).toBe('VERTICAL_SEAM')
    expect(result.cvDebug?.gapPixels).toBe(0)
    expect(result.cvDebug?.maxGapPixels).toBe(2)
    expect(result.authoritativeGapMm).toBeNull()
    expect(result.originalGapMm).toBeNull()
    expect(result.confidence).toBe(0.78)
    expect(result.semanticGate).toMatchObject({ domainStatus: 'PIPE_JOINT_INSPECTION', processingAllowed: true, confidence: 0.91 })
    expect(result.classifierEvidence?.mapping_status).toBe('UNMAPPED_OR_AMBIGUOUS')
    expect(result.aiExplanation).toBe('Backend composed explanation.')
    expect((fetchMock.mock.calls[0][1]?.body as FormData).get('joint_type')).toBe('VERTICAL_SEAM')
  })

  it('preserves a genuine zero-millimetre authoritative measurement', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      authoritative_gap_mm: 0,
      overall_status: 'PASS',
      result_status: 'ACCEPTED_MEASUREMENT',
      confidence_breakdown: { overall_confidence: 0.81 },
    }), { status: 200 })))
    const result = await measureWithFastApi(request)
    expect(result.originalGapMm).toBe(0)
    expect(result.authoritativeGapMm).toBe(0)
  })

  it('rejects missing or invalid confidence instead of manufacturing 90 percent', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      authoritative_gap_mm: 3.5,
      overall_status: 'PASS',
      result_status: 'ACCEPTED_MEASUREMENT',
    }), { status: 200 })))
    await expect(measureWithFastApi(request)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      authoritative_gap_mm: 3.5,
      confidence_breakdown: { overall_confidence: 1.5 },
    }), { status: 200 })))
    await expect(measureWithFastApi(request)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
  })

  it.each([
    [401, 'AUTHENTICATION_ERROR'], [403, 'AUTHENTICATION_ERROR'], [429, 'RATE_LIMITED'],
    [500, 'SERVER_ERROR'], [502, 'SERVER_ERROR'], [503, 'SERVER_ERROR'], [504, 'SERVER_ERROR'],
  ])('classifies HTTP %i without local fallback', async (status, code) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('failed', { status })))
    await expect(measureWithFastApi(request)).rejects.toMatchObject({ code })
  })

  it('classifies network failures without fabricating a result', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('network down')))
    await expect(measureWithFastApi(request)).rejects.toMatchObject({ code: 'CONNECTION_ERROR' })
  })
})
