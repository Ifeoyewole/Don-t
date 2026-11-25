export interface InspectionFeedback {
  id:string
  inspectionId:string
  imageId:string
  imageSha256:string|null
  revision:number
  createdAt:string
  notes:string
  defect:string
  siteMeasuredGapMm:number|null
  measurementMethod:string
  verification:'OPERATOR_REPORTED_UNVERIFIED'
  trainingEligible:false
  originalEvidence:unknown
}
