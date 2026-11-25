import type { UnifiedEvidence } from '../types/unified'
export function inspectionNarrative(e:Pick<UnifiedEvidence,'physical_gap_mm'|'joint_measurement'|'preliminary_findings'>):string {
 const px=e.joint_measurement.candidates.map(c=>c.value).filter(v=>Number.isFinite(v)&&v>=0)
 const mm=e.physical_gap_mm
 const measured=typeof mm==='number'&&Number.isFinite(mm)&&e.joint_measurement.calibration_authority_verified===true&&e.joint_measurement.calibration_status==='VERIFIED_IMAGE_JOINT_PLANE'&&e.joint_measurement.physical_gap_mm===mm
 const finding=measured?`Calibrated research gap estimate: ${mm.toFixed(2)} mm.`:px.length?`Boundary evidence found: ${Math.min(...px).toFixed(1)}${Math.max(...px)!==Math.min(...px)?`–${Math.max(...px).toFixed(1)}`:''} px across the analysed regions. Physical gap in mm is unavailable because a verified scale and suitable measurement geometry are required.`:'No stable joint-gap estimate was established for this image. The available image and model evidence are retained for inspection.'
 return finding+' '+(e.preliminary_findings.length?'Defect suggestions are preliminary and remain separate from the measurement.':'No defect candidate was reported; this does not establish a normal joint or PASS.')+' Engineer feedback is optional. No engineering acceptance has been issued.'
}
