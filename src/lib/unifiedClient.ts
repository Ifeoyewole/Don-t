import type { UnifiedEvidence } from '../types/unified'

export async function unifiedPreviewAvailable(signal?: AbortSignal): Promise<boolean> {
  const response = await fetch('/api/unified', { credentials: 'same-origin', signal })
  return response.ok && (await response.json()).available === true
}

export async function requestUnified(blob: Blob, options: Record<string, unknown>): Promise<UnifiedEvidence> {
  if (blob.size > 3*1024*1024) throw new Error('Engineering preview images must be at most 3 MiB.')
  const original = await blob.arrayBuffer()
  const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', original))].map(v => v.toString(16).padStart(2, '0')).join('')
  const body = new FormData(); body.append('file', blob, 'inspection.jpg'); body.append('options', JSON.stringify(options))
  const response = await fetch('/api/unified', { method: 'POST', credentials: 'same-origin', body, signal: AbortSignal.timeout(245_000) })
  if (!response.ok) throw new Error(`Protected unified preview failed (${response.status}); no automatic retry.`)
  const evidence = await response.json() as UnifiedEvidence
  const validMm = evidence.physical_gap_mm === null || (typeof evidence.physical_gap_mm === 'number' && Number.isFinite(evidence.physical_gap_mm) && evidence.physical_gap_mm > 0 && evidence.joint_measurement?.calibration_authority_verified === true && evidence.joint_measurement.physical_gap_mm === evidence.physical_gap_mm)
  if (evidence.image_sha256 !== digest || evidence.decision !== 'REVIEW_REQUIRED' || evidence.research_only !== true || !validMm || !Array.isArray(evidence.regions)) {
    throw new Error('Unified response identity or research safety contract is invalid.')
  }
  return evidence
}
