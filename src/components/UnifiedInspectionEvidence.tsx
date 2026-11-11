import type { UnifiedEvidence } from '../types/unified'

export function UnifiedInspectionEvidence({ evidence }: { evidence: UnifiedEvidence }) {
  return <section className="unified-inspection-evidence">
    <h3>Unified AI engineering preview</h3>
    <p>{evidence.summary}</p>
    <p><strong>{evidence.physical_gap_mm != null ? `${evidence.physical_gap_mm.toFixed(2)} mm — calibrated research estimate` : 'Measurement unavailable — calibration or reliable joint boundaries required'}</strong></p>
    <p>Calibration: {evidence.joint_measurement.calibration_status ?? 'UNVERIFIED'} · {evidence.joint_measurement.status}</p>
    {evidence.overlay_png_base64 && <img className="unified-evidence-overlay" src={`data:image/png;base64,${evidence.overlay_png_base64}`} alt="Unified inspection segmentation and joint-edge evidence" />}
    <h4>Preliminary defect candidates</h4>
    <ul>{evidence.preliminary_findings.map((f, i) => <li key={i}>{f.label}: {f.explanation ?? f.status}{f.detector_score != null ? ` · detector score ${f.detector_score.toFixed(3)}` : ''}</li>)}</ul>
    <p>Gemini: {evidence.gemini.model ?? 'not reported'} · {evidence.gemini.status}</p>
    {evidence.regions.map(region => <details key={region.region_id}><summary>Region {region.region_id}: {region.geometry.status}</summary>
      {region.mask_png_base64 && <img className="unified-evidence-mask" src={`data:image/png;base64,${region.mask_png_base64}`} alt={`Actual SAM2 region ${region.region_id} mask`} />}
      <p>{region.boundary_evidence?.reason ?? region.mask_status}</p>
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
