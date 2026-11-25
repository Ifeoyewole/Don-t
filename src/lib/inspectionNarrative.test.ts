import {expect,it} from 'vitest'
import {inspectionNarrative} from './inspectionNarrative'
import type {UnifiedEvidence} from '../types/unified'
it('keeps candidate pixels distinct from physical mm and normal-joint acceptance',()=>{
 const e:Pick<UnifiedEvidence,'physical_gap_mm'|'joint_measurement'|'preliminary_findings'>={physical_gap_mm:null,joint_measurement:{status:'PRELIMINARY_PIXEL_EVIDENCE',physical_gap_mm:null,candidates:[{value:158.5,units:'px',meaning:'candidate'},{value:146,units:'px',meaning:'candidate'}]},preliminary_findings:[]}
 const text=inspectionNarrative(e)
 expect(text).toContain('146.0–158.5 px');expect(text).toContain('does not establish a normal joint or PASS');expect(text).toContain('optional')
})
it('does not call an unverified physical value calibrated',()=>{
 const e:Pick<UnifiedEvidence,'physical_gap_mm'|'joint_measurement'|'preliminary_findings'>={physical_gap_mm:4,joint_measurement:{status:'REVIEW',physical_gap_mm:4,calibration_authority_verified:true,calibration_status:'UNVERIFIED',candidates:[]},preliminary_findings:[]}
 expect(inspectionNarrative(e)).not.toContain('Calibrated research gap estimate:')
})
