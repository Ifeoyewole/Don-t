import type { CalibrationProfile } from '../types/domain'

export interface CalibrationReferenceStatus {
  reference_verified: boolean
  status: 'REFERENCE_MATCHED' | 'CALIBRATION_REQUIRED'
  guidance: string
}

/** A read-only match against the server registry, not a claim that photo scale is valid. */
export async function checkCalibrationReference(profile: CalibrationProfile): Promise<CalibrationReferenceStatus> {
  const ref = profile.calibration_reference_id || profile.calibrationReferenceId
  const diameter = profile.pipe_diameter_mm ?? profile.pipeDiameterMm
  if (!ref || !diameter || !Number.isFinite(diameter) || diameter <= 0) {
    return { reference_verified: false, status: 'CALIBRATION_REQUIRED', guidance: 'An official reference and known diameter are required. A nominal diameter alone is not calibration.' }
  }
  const response = await fetch('/api/v1/cv/calibration/check-reference', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      reference_id: ref,
      project_id: profile.project_id || profile.projectId,
      source: profile.source,
      pipe_diameter_mm: diameter,
      camera_id: profile.camera_id || profile.cameraId || null,
    }),
  })
  if (!response.ok) throw new Error('Calibration verification service is unavailable. Millimetres remain unverified.')
  const data: CalibrationReferenceStatus = await response.json()
  if (typeof data.reference_verified !== 'boolean' ||
      !['REFERENCE_MATCHED', 'CALIBRATION_REQUIRED'].includes(data.status) ||
      typeof data.guidance !== 'string') {
    throw new Error('Invalid calibration verification response. Millimetres remain unverified.')
  }
  return data
}
