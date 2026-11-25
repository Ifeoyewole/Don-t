import { useEffect,useState } from 'react'
import { previewFailure,validatePreviewImage } from '../lib/previewErrors'
import { db } from '../db'
import { saveOptionalFeedback } from '../services/inspectionFeedback'
import type { InspectionFeedback } from '../types/feedback'

export function OptionalInspectionReview({inspectionId}:{inspectionId:string}){
 const [notes,setNotes]=useState(''),[defect,setDefect]=useState(''),[gap,setGap]=useState(''),[method,setMethod]=useState('')
 const [history,setHistory]=useState<InspectionFeedback[]>([]),[message,setMessage]=useState(''),[busy,setBusy]=useState(false)
 useEffect(()=>{let active=true;void db.inspectionFeedback.where('inspectionId').equals(inspectionId).toArray().then(rows=>{if(active)setHistory(rows)}).catch(()=>{if(active)setMessage('Review history could not be loaded; inspection remains available.')});return()=>{active=false}},[inspectionId])
 const [interpretation,setInterpretation]=useState<{proposed_label:string;explanation:string;boundary_guidance:string}|null>(null)
 const askGemini=async()=>{setBusy(true);setMessage('');try{
   const row=history.at(-1)
   if(!row)throw Error('Save optional feedback first, or continue without it.')
   const cached=await db.feedbackInterpretations.get(row.id)
   if(cached){setInterpretation((cached.result as {interpretation:NonNullable<typeof interpretation>}).interpretation);return}
   const original=await db.inspectionBlobs.where('imageId').equals(row.imageId).first()
   if(!original)throw Error('Original image is unavailable; saved feedback remains accessible.')
   await validatePreviewImage(original.blob)
   const digest=[...new Uint8Array(await crypto.subtle.digest('SHA-256',await original.blob.arrayBuffer()))].map(v=>v.toString(16).padStart(2,'0')).join('')
   if(row.imageSha256 && row.imageSha256!==digest)throw Error('Original image identity changed. Feedback remains saved; interpretation was not submitted.')
   const form=new FormData();form.append('file',original.blob,'inspection.jpg');form.append('review',JSON.stringify({notes:row.notes,defect:row.defect,siteMeasuredGapMm:row.siteMeasuredGapMm,measurementMethod:row.measurementMethod,revision:row.revision}))
   const response=await fetch('/api/unified?action=review',{method:'POST',body:form,signal:AbortSignal.timeout(180000)})
   if(!response.ok)throw Error(await previewFailure(response))
   const result=await response.json()
   if(result.image_sha256!==digest||result.review_revision!==row.revision||result.authoritative!==false||result.training_eligible!==false||typeof result.interpretation?.explanation!=='string')throw Error('Invalid advisory review response.')
   await db.feedbackInterpretations.add({feedbackId:row.id,result,createdAt:new Date().toISOString()});setInterpretation(result.interpretation)
   setMessage('Interpretation saved separately. No model weights or original findings changed.')
 }catch(e){setMessage(e instanceof Error?e.message:'Interpretation unavailable; inspection preserved.')}finally{setBusy(false)}}
 const save=async()=>{setBusy(true);setMessage('');try{const row=await saveOptionalFeedback(inspectionId,{notes,defect,gap,method});setHistory(old=>[...old,row]);setMessage('Optional feedback saved on this device. Original predictions are unchanged.')}catch(e){setMessage(e instanceof Error?e.message:'Feedback could not be saved.')}finally{setBusy(false)}}
 return <details className="optional-inspection-review"><summary>Optional engineer feedback · {history.length?'feedback recorded':'unreviewed'}</summary>
 <p>Inspection and exports work without review. Corrections are recorded separately; saving does not retrain models or establish calibration.</p>
 <label className="field">Observation or boundary correction<textarea value={notes} maxLength={2000} onChange={e=>setNotes(e.target.value)} rows={4}/></label>
 <label className="field">Reported condition<select value={defect} onChange={e=>setDefect(e.target.value)}><option value="">Not assessed</option>{['NO_DEFECT_OBSERVED','UNCERTAIN','OPEN_JOINT','JOINT_DISPLACEMENT','JOINT_MISALIGNMENT','INFILTRATION','PROTRUDING_LATERAL','BROKEN_PIPE','SURFACE_DAMAGE','OTHER'].map(x=><option key={x}>{x}</option>)}</select></label>
 <label className="field">Site-measured gap (mm), optional<input type="number" min="0" max="5000" step="any" value={gap} onChange={e=>setGap(e.target.value)}/></label>
 <label className="field">Measurement method or source<input value={method} maxLength={300} onChange={e=>setMethod(e.target.value)} placeholder="For example: feeler gauge at the marked cross-section"/></label>
 <button type="button" className="button button-secondary" onClick={()=>void save()} disabled={busy}>{busy?'Saving feedback…':'Save optional feedback'}</button>
 <button type="button" className="button button-ghost" onClick={()=>void askGemini()} disabled={busy||!history.length}>Interpret saved feedback with Gemini (optional)</button>
 <p>This optional action sends the image and saved feedback to Vertex AI and retains a private research copy. It uses the remaining allowance; feedback is not automatically training-approved.</p>
 {interpretation&&<section><strong>AI interpretation — provisional: {interpretation.proposed_label}</strong><p>{interpretation.explanation}</p><p>{interpretation.boundary_guidance}</p></section>}
 <p role="status">{message}</p>
 {history.map(row=><p key={row.id}>Revision {row.revision} · {row.createdAt} · {row.defect||'Condition not assessed'} · {row.siteMeasuredGapMm!==null?`${row.siteMeasuredGapMm} mm, operator reported`:'No site measurement'} · not training-approved</p>)}
 </details>
}
