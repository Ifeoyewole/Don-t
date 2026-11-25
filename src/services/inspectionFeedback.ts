import { db } from '../db'
import { createId } from '../utils/identity'
import type { InspectionFeedback } from '../types/feedback'

export async function saveOptionalFeedback(inspectionId:string,input:{notes:string;defect:string;gap:string;method:string}):Promise<InspectionFeedback>{
  const value=input.gap.trim()===''?null:Number(input.gap)
  if(value!==null&&(!Number.isFinite(value)||value<0||value>5000))throw Error('Enter a finite site measurement from 0 to 5000 mm, or leave it blank.')
  if(!input.notes.trim()&&!input.defect&&value===null)throw Error('Add an observation, correction or measurement, or leave review unsubmitted.')
  return db.transaction('rw',db.inspectionResults,db.inspectionFeedback,async()=>{
    const result=await db.inspectionResults.get(inspectionId)
    if(!result)throw Error('Inspection record not found.')
    const previous=await db.inspectionFeedback.where('inspectionId').equals(inspectionId).toArray()
    const record:InspectionFeedback={id:createId(),inspectionId,imageId:result.imageId,
      imageSha256:result.unifiedEvidence?.image_sha256??null,revision:Math.max(0,...previous.map(r=>r.revision))+1,
      createdAt:new Date().toISOString(),notes:input.notes.trim().slice(0,2000),defect:input.defect,
      siteMeasuredGapMm:value,measurementMethod:input.method.trim().slice(0,300),
      verification:'OPERATOR_REPORTED_UNVERIFIED',trainingEligible:false,
      originalEvidence:{unified:result.unifiedEvidence??null,gapMm:result.originalGapMm,condition:result.condition??null}}
    await db.inspectionFeedback.add(record)
    return record
  })
}
