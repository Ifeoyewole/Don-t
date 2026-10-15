/** Preserve distinct WRc states without inventing a classification or confidence. */
export type WrcEvidenceState =
  | 'MISSING_RESPONSE'
  | 'MODEL_UNAVAILABLE'
  | 'INTEGRITY_FAILURE'
  | 'INFERENCE_FAILED'
  | 'LOW_CONFIDENCE'
  | 'UNMAPPED'
  | 'AMBIGUOUS'
  | 'SUCCESS'

export interface WrcEvidenceLike {
  classification_status?: string | null
  status?: string | null
  mapping_status?: string | null
  confidence?: number | null
  raw_prediction?: string | null
  raw_class_name?: string | null
}

export function classifyWrcEvidence(evidence?: WrcEvidenceLike | null): WrcEvidenceState {
  if (!evidence) return 'MISSING_RESPONSE'
  const status = evidence.classification_status || evidence.status
  if (!status) return 'MISSING_RESPONSE'
  if (status.includes('INTEGRITY')) return 'INTEGRITY_FAILURE'
  if (status.includes('UNAVAILABLE')) return 'MODEL_UNAVAILABLE'
  if (status.includes('ERROR') || status.includes('FAILED')) return 'INFERENCE_FAILED'
  if (status.includes('LOW_CONFIDENCE')) return 'LOW_CONFIDENCE'
  if (!Number.isFinite(evidence.confidence) || evidence.confidence == null) return 'MISSING_RESPONSE'
  if (evidence.mapping_status?.includes('AMBIGUOUS')) return 'AMBIGUOUS'
  if (!evidence.mapping_status || evidence.mapping_status.includes('UNMAPPED')) return 'UNMAPPED'
  if (status === 'SUCCESS') return 'SUCCESS'
  return 'INFERENCE_FAILED'
}
