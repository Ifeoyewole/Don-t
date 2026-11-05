import type { JointGeometryType } from '../types/domain'

export interface InspectionContextSuggestion {
  model: string
  domain_status: string
  processing_allowed: boolean
  source: 'IMAGE_ADVISORY'
  review_required: true
  calibration: { pipe_diameter_mm: number | null; source: string | null; verified: false; calibration_reference_id: null }
  suggested_joint_type: JointGeometryType | null
  suggested_inspection_context: string | null
  possible_gap_visible: boolean | null
  calibration_verified: false
  calibration_reference_id: null
  pipe_diameter_mm: null
  guidance: string
}

const ALLOWED_GEOMETRIES: JointGeometryType[] = [
  'CIRCULAR_OPENING',
  'HORIZONTAL_SEAM',
  'VERTICAL_SEAM',
]

/**
 * Independent, non-authoritative Gemini context hint. Never send operator notes
 * or saved customer history. The photo is processed through the cloud gateway.
 */
export async function requestInspectionContextSuggestions(
  photo: File,
  signal: AbortSignal,
  manholeDiameterMm?: number,
): Promise<InspectionContextSuggestion> {
  const payload = new FormData()
  payload.append('file', photo, photo.name)
  if (manholeDiameterMm && Number.isFinite(manholeDiameterMm)) {
    payload.append('metadata_pipe_diameter_mm', String(manholeDiameterMm))
    payload.append('metadata_source', 'MANHOLE_METADATA')
  }
  const response = await fetch('/api/v1/cv/context-suggestions', {
    method: 'POST',
    body: payload,
    signal,
  })
  if (!response.ok) {
    throw new Error(`Gemini inspection suggestions unavailable (HTTP ${response.status}). You can still enter the context manually.`)
  }
  const result: InspectionContextSuggestion = await response.json()
  if (
    !result || typeof result !== 'object' ||
    typeof result.model !== 'string' ||
    typeof result.processing_allowed !== 'boolean' ||
    (result.suggested_joint_type != null && !ALLOWED_GEOMETRIES.includes(result.suggested_joint_type)) ||
    (result.suggested_inspection_context != null && typeof result.suggested_inspection_context !== 'string') ||
    result.review_required !== true ||
    result.calibration?.verified !== false ||
    result.calibration?.calibration_reference_id != null ||
    result.calibration_verified !== false ||
    result.calibration_reference_id != null ||
    result.pipe_diameter_mm != null
  ) {
    throw new Error('The backend returned an invalid advisory context. Enter inspection context manually.')
  }
  return result
}
