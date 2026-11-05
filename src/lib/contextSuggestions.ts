import type { JointGeometryType } from '../types/domain'

/** Advisory-only contract from the existing backend context_suggestions endpoint. */
export interface InspectionContextSuggestion {
  model: string
  domain_status: string
  processing_allowed: boolean
  image_quality_usable: boolean
  suggested_joint_type: JointGeometryType | null
  suggested_inspection_context: string | null
  possible_gap_visible: boolean | null
  calibration: {
    pipe_diameter_mm: number | null
    source: string | null
    calibration_reference_id: null
    verified: false
    authority: 'UNVERIFIED_METADATA'
  }
  review_required: true
  reason: string
}

const ALLOWED_GEOMETRIES: JointGeometryType[] = [
  'CIRCULAR_OPENING',
  'HORIZONTAL_SEAM',
  'VERTICAL_SEAM',
]

export function validateInspectionContextSuggestion(
  value: unknown,
  expectedManholeDiameterMm?: number,
): InspectionContextSuggestion {
  if (value === null || typeof value !== 'object') {
    throw new Error('The backend returned invalid advisory context.')
  }
  const result = value as Partial<InspectionContextSuggestion>
  const cal = result.calibration
  if (
    typeof result.model !== 'string' ||
    typeof result.domain_status !== 'string' ||
    typeof result.processing_allowed !== 'boolean' ||
    typeof result.image_quality_usable !== 'boolean' ||
    typeof result.reason !== 'string' ||
    result.review_required !== true ||
    (result.suggested_joint_type != null && !ALLOWED_GEOMETRIES.includes(result.suggested_joint_type)) ||
    (result.suggested_inspection_context != null &&
      (typeof result.suggested_inspection_context !== 'string' || result.suggested_inspection_context.length > 1000)) ||
    (result.possible_gap_visible != null && typeof result.possible_gap_visible !== 'boolean') ||
    !cal || cal.verified !== false || cal.calibration_reference_id != null ||
    cal.authority !== 'UNVERIFIED_METADATA' ||
    (cal.pipe_diameter_mm != null &&
      (typeof cal.pipe_diameter_mm !== 'number' || !Number.isFinite(cal.pipe_diameter_mm) ||
        cal.pipe_diameter_mm <= 0 || cal.pipe_diameter_mm > 5000)) ||
    (expectedManholeDiameterMm != null &&
      cal.pipe_diameter_mm != null && cal.pipe_diameter_mm !== expectedManholeDiameterMm) ||
    (!result.processing_allowed &&
      (result.suggested_joint_type != null || result.suggested_inspection_context != null ||
        result.possible_gap_visible != null))
  ) {
    throw new Error('The backend returned invalid or non-advisory context. Enter inspection details manually.')
  }
  return result as InspectionContextSuggestion
}

/**
 * Photo-only AI suggestions via the existing FastAPI/Vercel gateway.
 * No previous inspection histories, operator notes or other customers' records
 * are passed. Optional nominal diameter is trusted manhole metadata, not AI.
 */
export async function requestInspectionContextSuggestions(
  photo: File,
  signal: AbortSignal,
  manholeDiameterMm?: number,
): Promise<InspectionContextSuggestion> {
  const formData = new FormData()
  formData.append('file', photo, photo.name)
  if (manholeDiameterMm && Number.isFinite(manholeDiameterMm)) {
    formData.append('metadata_pipe_diameter_mm', String(manholeDiameterMm))
    formData.append('metadata_source', 'MANHOLE_METADATA')
  }
  const response = await fetch('/api/v1/cv/context-suggestions', {
    method: 'POST',
    body: formData,
    signal,
  })
  if (!response.ok) {
    throw new Error(`Gemini inspection suggestions unavailable (HTTP ${response.status}). Manual entry remains available.`)
  }
  return validateInspectionContextSuggestion(await response.json(), manholeDiameterMm)
}
