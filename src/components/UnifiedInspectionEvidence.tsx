import type { UnifiedEvidence } from '../types/unified'

export function UnifiedInspectionEvidence({ evidence }: { evidence: UnifiedEvidence }) {
  return <section className="unified-inspection-evidence">
    <h3>Unified AI engineering preview</h3>
    <p>{evidence.summary}</p>
    <p><strong>{evidence.physical_gap_mm != null ? `${evidence.physical_gap_mm.toFixed(2)} mm — calibrated research estimate` : 'Measurement unavailable — calibration or reliable joint boundaries required'}</strong></p>
    <p>Calibration: {evidence.joint_measurement.calibration_status ?? 'UNVERIFIED'} · {evidence.joint_measurement.status}</p>
    {evidence.overlay_png_base64 && <img className="unified-evidence-overlay" src={`data:image/png;base64,${evidence.overlay_png_base64}`} alt="Unified inspection segmentation and joint-edge evidence" />}
    <h4>Measurement evidence</h4>
    <p>Scene validation: {evidence.joint_measurement.scene_status ?? 'Not recorded'}. Boundary detection does not confirm a defect or engineering acceptance.</p>
    {Boolean(evidence.joint_measurement.rejection_reasons?.length) && <details open><summary>Why physical mm are unavailable</summary><ul>{evidence.joint_measurement.rejection_reasons?.map(reason=><li key={reason}>{reason.replaceAll('_',' ')}</li>)}</ul></details>}
    <p>Inspect View: {evidence.components.inspect_view?.status ?? 'Not recorded'} · Specialist: {evidence.components.sewer_detector?.status ?? 'Not recorded'}</p>
    <h4>Preliminary defect candidates</h4>
    {!evidence.preliminary_findings.length && <p>No defect candidate reported. This does not establish a normal joint or PASS.</p>}
    <ul>{evidence.preliminary_findings.map((f, i) => <li key={i}>{f.label}: {f.explanation ?? f.status}{f.detector_score != null ? ` · detector score ${f.detector_score.toFixed(3)}` : ''}</li>)}</ul>
    <p>Gemini: {evidence.gemini.model ?? 'not reported'} · {evidence.gemini.status}</p>
    {evidence.regions.map(region => <details key={region.region_id} open={region.boundary_evidence?.gap_estimate_px != null}><summary>Region {region.region_id}: {region.geometry.status}</summary>
      {region.mask_png_base64 && <img className="unified-evidence-mask" src={`data:image/png;base64,${region.mask_png_base64}`} alt={`Actual SAM2 region ${region.region_id} mask`} />}
      <p>{region.boundary_evidence?.reason ?? region.mask_status}</p>
      {region.boundary_evidence?.accepted_cross_sections != null && <p>{region.boundary_evidence.accepted_cross_sections} cross-sections · variation (MAD): {region.boundary_evidence.width_mad_px?.toFixed(2) ?? 'unavailable'} px · method: {region.boundary_evidence.method}</p>}
      {region.boundary_evidence?.limitation && <p>{region.boundary_evidence.limitation}</p>}
      <p>{region.geometry.pixel_candidate != null ? `${region.geometry.pixel_candidate.toFixed(2)} px — image-plane opening candidate` : 'No supported joint-gap estimate'}</p>
    </details>)}
    <details><summary>Independent confidence evidence and disagreements</summary>
      <ul>{Object.entries(evidence.components.inspect_view?.evidence?.classes ?? {}).map(([label, value]) => <li key={label}>{label}: {value.probability?.toFixed(4) ?? 'unavailable'} · {value.status}</li>)}</ul>
      <ul>{evidence.components.sewer_detector?.detections?.map((d, i) => <li key={i}>{d.source_label}: detector score {d.score.toFixed(3)}</li>)}</ul>
      <ul>{evidence.disagreements_and_limits.map((s, i) => <li key={i}>{s}</li>)}</ul>
    </details>
    <p>{evidence.latency_seconds?.total != null ? `Inference ${evidence.latency_seconds.total.toFixed(1)} s. ` : ''}Research evidence; no engineering acceptance.</p>
  </section>
}
