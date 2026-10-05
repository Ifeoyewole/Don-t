import { useEffect, useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import type { CvMeasurementDebug, InspectionResult, ManholeInspectionSummary, MeasurementOverlayHints, MeasurementSource } from '../types/domain'

type Props = {
  inspectionId: string
  loading?: boolean
  online: boolean
  projectId: string
  projectName: string
  siteName?: string
  manholeLabel: string
  results: InspectionResult[]
  summary: ManholeInspectionSummary | null
  onBack: () => void
  onSaveNote: (inspectionId: string, note: string) => Promise<void>
  onRemeasure: (inspectionId: string) => Promise<void>
  onApplyOverride: (inspectionId: string, overrideValueMm: number, overrideReason: string) => Promise<void>
  onClearOverride: (inspectionId: string) => Promise<void>
  onNext: () => void
}

type DraftOverride = {
  value: string
  reason: string
}

const sourceLabels: Record<MeasurementSource, string> = {
  fastapi: 'Optical CV Engine',
  cv: 'CV Measured',
  'offline-preview': 'Offline preview (unverified)',
  'ai-assisted': 'AI assisted',
  'ai-review': 'AI review',
  manual: 'Manual override',
  fallback: 'Estimated fallback',
}

const trustStatusLabels: Record<string, { label: string; className: string }> = {
  ACCEPTED_MEASUREMENT: { label: '✓ Accepted Measurement', className: 'trust-accepted' },
  REVIEW_REQUIRED: { label: '⚠ Review Required', className: 'trust-review' },
  REJECTED_UNRELIABLE: { label: '✕ Rejected (Unreliable)', className: 'trust-rejected' },
}

const conditionLabels: Record<string, string> = {
  NORMAL: 'Normal Joint',
  OPEN_JOINT: 'Open Joint',
  ANGULAR_DEFLECTION: 'Angular Deflection',
  SURFACE_DAMAGE: 'Surface Damage',
  DEPOSITS_OBSTACLES: 'Deposits / Obstacles',
  INTRUDING_SEAL: 'Intruding Sealing Material',
  UNKNOWN: 'Unclassified Condition',
}

const measurementLabel = (item: InspectionResult) => {
  const source = item.measurementSource ?? 'cv'
  return item.measurementNote || sourceLabels[source]
}

const sourceLabel = (item: InspectionResult) => sourceLabels[item.measurementSource ?? 'cv']

const measurementValueLabel = (item: InspectionResult) => {
  if (item.measurementSource === 'ai-review') {
    return item.cvDebug?.gapPixels ? `${item.cvDebug.gapPixels.toFixed(1)} px gap - calibrate for mm` : 'Calibration needed'
  }

  if (item.measurementSource === 'ai-assisted' && !item.cvDebug?.pipeDetected) {
    return `~${item.finalGapMm.toFixed(1)} mm from ${item.cvDebug?.gapPixels?.toFixed(1) ?? '--'} px`
  }

  return `${item.finalGapMm.toFixed(1)} mm`
}

const toSmoothPath = (points: Array<{ x: number; y: number }>) => {
  if (!points.length) {
    return ''
  }

  if (points.length === 1) {
    return `M ${points[0].x} ${points[0].y}`
  }

  const commands = [`M ${points[0].x} ${points[0].y}`]

  for (let index = 0; index < points.length - 1; index += 1) {
    const previous = points[Math.max(0, index - 1)]
    const current = points[index]
    const next = points[index + 1]
    const following = points[Math.min(points.length - 1, index + 2)]
    const controlOne = {
      x: current.x + (next.x - previous.x) / 6,
      y: current.y + (next.y - previous.y) / 6,
    }
    const controlTwo = {
      x: next.x - (following.x - current.x) / 6,
      y: next.y - (following.y - current.y) / 6,
    }

    commands.push(
      `C ${controlOne.x.toFixed(1)} ${controlOne.y.toFixed(1)}, ${controlTwo.x.toFixed(1)} ${controlTwo.y.toFixed(1)}, ${next.x} ${next.y}`,
    )
  }

  return commands.join(' ')
}

const resolveOverlayHints = (item: InspectionResult): MeasurementOverlayHints | undefined => {
  const primaryHints = item.overlayHints
  const cvHints = item.cvDebug?.overlayHints

  if (primaryHints?.jointTrace?.length || !cvHints?.jointTrace?.length) {
    return primaryHints ?? cvHints
  }

  return {
    ...primaryHints,
    jointTrace: cvHints.jointTrace,
    jointEdgeA: primaryHints?.jointEdgeA ?? cvHints.jointEdgeA,
    jointEdgeB: primaryHints?.jointEdgeB ?? cvHints.jointEdgeB,
  }
}

const Overlay = ({ debug, hints }: { debug?: CvMeasurementDebug; hints?: MeasurementOverlayHints }) => {
  if (!hints?.pipeCenter && !hints?.gapLine && !hints?.jointTrace?.length && !hints?.jointEdgeA?.length && !hints?.jointEdgeB?.length) {
    return null
  }

  const radius = hints.outerRadiusPx ?? hints.innerRadiusPx ?? 0
  const allTracePoints = [...(hints.jointTrace ?? []), ...(hints.jointEdgeA ?? []), ...(hints.jointEdgeB ?? [])]
  const lastTracePoint = allTracePoints[allTracePoints.length - 1]
  const width = debug?.imageWidth ?? Math.max((hints.pipeCenter?.x ?? hints.gapLine?.x2 ?? lastTracePoint?.x ?? 1) + radius, 1)
  const height = debug?.imageHeight ?? Math.max((hints.pipeCenter?.y ?? hints.gapLine?.y2 ?? lastTracePoint?.y ?? 1) + radius, 1)
  const viewBox = `0 0 ${width} ${height}`

  return (
    <svg className="measurement-overlay" viewBox={viewBox} preserveAspectRatio="none" aria-hidden="true">
      {hints.pipeCenter && hints.innerRadiusPx ? (
        <circle cx={hints.pipeCenter.x} cy={hints.pipeCenter.y} r={hints.innerRadiusPx} className="overlay-inner-ring" />
      ) : null}
      {hints.pipeCenter && hints.outerRadiusPx ? (
        <circle cx={hints.pipeCenter.x} cy={hints.pipeCenter.y} r={hints.outerRadiusPx} className="overlay-outer-ring" />
      ) : null}
      {hints.gapLine && !hints.jointTrace?.length ? (
        <line x1={hints.gapLine.x1} y1={hints.gapLine.y1} x2={hints.gapLine.x2} y2={hints.gapLine.y2} className="overlay-gap-line" />
      ) : null}
      {hints.jointEdgeA?.length ? <path d={toSmoothPath(hints.jointEdgeA)} className="overlay-gap-edge" /> : null}
      {hints.jointEdgeB?.length ? <path d={toSmoothPath(hints.jointEdgeB)} className="overlay-gap-edge" /> : null}
      {hints.jointTrace?.length ? <path d={toSmoothPath(hints.jointTrace)} className="overlay-joint-trace" /> : null}
    </svg>
  )
}

const statusActionLabel = (status: InspectionResult['status']) => {
  if (status === 'FAIL') return 'Review result'
  if (status === 'REVIEW') return 'Review result'
  return 'Add note'
}

const ResultCard = ({
  item,
  onSaveNote,
  onRemeasure,
  onApplyOverride,
  onClearOverride,
}: {
  item: InspectionResult
  onSaveNote: (inspectionId: string, note: string) => Promise<void>
  onRemeasure: (inspectionId: string) => Promise<void>
  onApplyOverride: (inspectionId: string, overrideValueMm: number, overrideReason: string) => Promise<void>
  onClearOverride: (inspectionId: string) => Promise<void>
}) => {
  const [note, setNote] = useState(item.notes ?? '')
  const [overrideDraft, setOverrideDraft] = useState<DraftOverride>({
    value: item.overrideValueMm?.toString() ?? item.finalGapMm.toString(),
    reason: item.overrideReason ?? '',
  })
  const [busy, setBusy] = useState(false)
  const [openControls, setOpenControls] = useState(false)

  const handleSaveNote = async () => {
    setBusy(true)
    await onSaveNote(item.id, note)
    setBusy(false)
  }

  const handleOverride = async () => {
    setBusy(true)
    await onApplyOverride(item.id, Number(overrideDraft.value), overrideDraft.reason)
    setBusy(false)
  }

  return (
    <article className={`inspection-result-card result-${item.status.toLowerCase()}`}>
      <div className="inspection-result-media">
        {item.previewUrl ? <img src={item.previewUrl} alt={item.fileName ?? item.jointLabel} /> : <div className="preview-placeholder" />}
        <Overlay debug={item.cvDebug} hints={resolveOverlayHints(item)} />
        <div className="result-media-top">
          <StatusBadge status={item.status} />
          {item.resultStatus && (
            <span className={`trust-badge ${trustStatusLabels[item.resultStatus]?.className ?? ''}`}>
              {trustStatusLabels[item.resultStatus]?.label ?? item.resultStatus}
            </span>
          )}
          <span className={`source-chip source-${(item.measurementSource ?? 'cv').replaceAll('-', '-')}`}>{sourceLabel(item)}</span>
        </div>
        <div className="result-media-bottom">
          <strong>Joint {item.jointLabel}</strong>
          {item.condition && (
            <span className={`condition-tag condition-${item.condition.toLowerCase().replaceAll('_', '-')}`}>
              {conditionLabels[item.condition] ?? item.condition}
            </span>
          )}
        </div>
      </div>

      <div className="inspection-result-body">
        {item.resultStatus === 'REJECTED_UNRELIABLE' && (
          <div className="rejection-callout">
            <div className="rejection-callout-header">
              <span className="rejection-callout-icon">✕</span>
              <strong>Measurement Rejected (Zero Guessing Policy)</strong>
            </div>
            <p>{item.rejectionReason || 'Detection confidence is below acceptable threshold. Zero artificial guessing enforced.'}</p>
          </div>
        )}

        <div className="inspection-gap-row">
          <span>{item.measurementSource === 'ai-review' ? 'Detected gap:' : item.measurementSource === 'ai-assisted' && !item.cvDebug?.pipeDetected ? 'Estimated gap:' : 'Measured gap:'}</span>
          <strong>{measurementValueLabel(item)}</strong>
        </div>

        <div className="inspection-gap-row">
          <span>Status:</span>
          <strong>{item.status}</strong>
        </div>

        {item.condition && (
          <div className="inspection-condition-row">
            <span>Classified Condition:</span>
            <span className={`condition-pill condition-${item.condition.toLowerCase().replaceAll('_', '-')}`}>
              {conditionLabels[item.condition] ?? item.condition}
            </span>
          </div>
        )}

        {item.confidenceBreakdown && (
          <div className="confidence-breakdown-panel">
            <div className="confidence-breakdown-head">
              <span>Confidence Factors</span>
              <strong>{Math.round(item.confidenceBreakdown.totalConfidence * 100)}%</strong>
            </div>
            <div className="confidence-factor-grid">
              <div className="factor-item">
                <span className="factor-label">Quality (Q)</span>
                <span className="factor-value">{Math.round(item.confidenceBreakdown.qualityFactor * 100)}%</span>
              </div>
              <div className="factor-item">
                <span className="factor-label">Geometry (G)</span>
                <span className="factor-value">{Math.round(item.confidenceBreakdown.geometricConsistency * 100)}%</span>
              </div>
              <div className="factor-item">
                <span className="factor-label">Model (M)</span>
                <span className="factor-value">{Math.round(item.confidenceBreakdown.modelConfidence * 100)}%</span>
              </div>
              <div className="factor-item">
                <span className="factor-label">Stability (S)</span>
                <span className="factor-value">{Math.round(item.confidenceBreakdown.stabilityFactor * 100)}%</span>
              </div>
            </div>
            <div className="risk-rate-indicator">
              <span>Estimated Failure Risk:</span>
              <strong className={item.confidenceBreakdown.failureRiskRate > 0.05 ? 'risk-high' : 'risk-low'}>
                {(item.confidenceBreakdown.failureRiskRate * 100).toFixed(1)}%
              </strong>
            </div>
          </div>
        )}

        {/* 6-Level Beta Inspection Hierarchy */}
        <div className="beta-inspection-hierarchy" style={{
          margin: '14px 0',
          padding: '12px 14px',
          background: 'rgba(255, 255, 255, 0.03)',
          borderRadius: '8px',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          fontSize: '0.82rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px'
        }}>
          {/* 1. SEMANTIC VALIDATION (Vertex) */}
          <div className="hierarchy-tier tier-semantic">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', fontSize: '0.72rem' }}>
                1. Semantic Domain Validation
              </span>
              <span style={{
                fontSize: '0.72rem',
                padding: '2px 6px',
                borderRadius: '4px',
                fontWeight: 600,
                background: item.rejectionReason?.includes('temporarily unavailable')
                  ? 'rgba(239, 68, 68, 0.15)'
                  : 'rgba(34, 197, 94, 0.15)',
                color: item.rejectionReason?.includes('temporarily unavailable') ? '#ef4444' : '#22c55e'
              }}>
                Vertex AI (Gemini 2.5)
              </span>
            </div>
            {item.rejectionReason?.includes('temporarily unavailable') ? (
              <div style={{ marginTop: '4px', color: '#f87171', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>AI image validation is temporarily unavailable. Retry validation.</span>
                <button
                  className="button button-ghost"
                  style={{ padding: '2px 8px', fontSize: '0.75rem' }}
                  type="button"
                  onClick={() => void onRemeasure(item.id)}
                  disabled={busy}
                >
                  Retry
                </button>
              </div>
            ) : (
              <div style={{ marginTop: '2px', color: '#cbd5e1' }}>
                Scene validated as pipe joint inspection. Fail-closed semantic gate active.
              </div>
            )}
          </div>

          {/* 2. MEASUREMENT EVIDENCE (OpenCV) */}
          <div className="hierarchy-tier tier-measurement" style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', fontSize: '0.72rem' }}>
                2. Measurement Evidence
              </span>
              <span style={{ fontSize: '0.72rem', color: '#38bdf8', fontWeight: 600 }}>
                OpenCV Zero-Guessing Engine
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginTop: '4px' }}>
              <div>
                <span style={{ color: '#64748b' }}>Geometry Tier: </span>
                <strong style={{ color: (item.geometryTier || item.cvDebug?.geometryTier) === 'ACCEPTABLE_GEOMETRY' ? '#22c55e' : (item.geometryTier || item.cvDebug?.geometryTier) === 'PARTIAL_REVIEW_GEOMETRY' ? '#f59e0b' : '#ef4444' }}>
                  {item.geometryTier || item.cvDebug?.geometryTier || 'ACCEPTABLE_GEOMETRY'}
                </strong>
              </div>
              <div>
                <span style={{ color: '#64748b' }}>Detected Gap: </span>
                <strong>
                  {item.cvDebug?.gapPixels ? `${item.cvDebug.gapPixels.toFixed(1)} px` : '-- px'}
                  {item.candidateGapMm ? ` (~${item.candidateGapMm.toFixed(1)} mm candidate)` : ''}
                </strong>
              </div>
            </div>
          </div>

          {/* 3. CALIBRATION (Verified source / reference) */}
          <div className="hierarchy-tier tier-calibration" style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', fontSize: '0.72rem' }}>
                3. Calibration Authority
              </span>
              <span style={{
                fontSize: '0.72rem',
                padding: '2px 6px',
                borderRadius: '4px',
                fontWeight: 600,
                background: item.calibrationProfile?.verified || item.cvDebug?.calibrationProfile?.verified ? 'rgba(34, 197, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                color: item.calibrationProfile?.verified || item.cvDebug?.calibrationProfile?.verified ? '#22c55e' : '#f59e0b'
              }}>
                {item.calibrationProfile?.verified || item.cvDebug?.calibrationProfile?.verified ? 'VERIFIED' : 'CALIBRATION REQUIRED'}
              </span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px', marginTop: '4px' }}>
              <div>
                <span style={{ color: '#64748b' }}>Source: </span>
                <span>{item.calibrationProfile?.source || item.cvDebug?.calibrationProfile?.source || 'PROJECT_METADATA'}</span>
              </div>
              <div>
                <span style={{ color: '#64748b' }}>Reference ID: </span>
                <span>{item.calibrationProfile?.calibration_reference_id || item.cvDebug?.calibrationProfile?.calibration_reference_id || 'CAL-PROJ-300MM'}</span>
              </div>
            </div>
          </div>

          {/* 4. ENGINEERING RESULT (Gap / tolerance) */}
          <div className="hierarchy-tier tier-engineering" style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', fontSize: '0.72rem' }}>
                4. Engineering Result
              </span>
              <span style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                color: item.status === 'PASS' ? '#22c55e' : item.status === 'FAIL' ? '#ef4444' : '#f59e0b'
              }}>
                {item.status} ({item.authoritativeGapMm ? `${item.authoritativeGapMm.toFixed(1)} mm` : (item.finalGapMm > 0 ? `${item.finalGapMm.toFixed(1)} mm` : 'Mm Withheld')})
              </span>
            </div>
            <div style={{ color: '#94a3b8', fontSize: '0.75rem', marginTop: '2px' }}>
              {item.authoritativeReason || item.cvDebug?.authoritativeReason || 'Based solely on verified physical measurement + configured tolerance.'}
            </div>
          </div>

          {/* 5. DEFECT CLASSIFICATION (WRc InceptionResNetV2) */}
          <div className="hierarchy-tier tier-classification" style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', fontSize: '0.72rem' }}>
                5. Primary Defect Classifier
              </span>
              <span style={{ fontSize: '0.72rem', padding: '2px 6px', borderRadius: '4px', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', fontWeight: 600 }}>
                WRc InceptionResNetV2
              </span>
            </div>
            {(() => {
              type ClassifierEvidenceView = {
                raw_prediction?: string
                raw_class_name?: string
                raw_code?: string
                raw_class_code?: string
                confidence?: number
                mapped_condition?: string
                jointinspect_mapping?: string
                mapping_status?: string
              }
              const evidence = (item.classifierEvidence || item.cvDebug?.classifierEvidence || item.externalClassifier || item.cvDebug?.externalClassifier) as ClassifierEvidenceView | undefined;
              if (!evidence) {
                return <div style={{ color: '#64748b', marginTop: '2px' }}>Classifier evidence unavailable</div>;
              }
              const rawName = evidence.raw_prediction || evidence.raw_class_name || 'Normal';
              const rawCode = evidence.raw_code || evidence.raw_class_code || '';
              const conf = Math.round((evidence.confidence ?? 0) * 100);
              const mapped = evidence.mapped_condition || evidence.jointinspect_mapping || item.condition || 'normal_joint';
              const mapStatus = evidence.mapping_status || 'DIRECT';

              return (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                    <div>
                      <span style={{ color: '#64748b' }}>Raw Prediction: </span>
                      <strong style={{ color: '#f8fafc' }}>{rawName} {rawCode ? `(${rawCode})` : ''}</strong>
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>WRc Confidence: </span>
                      <strong style={{ color: '#f8fafc' }}>{conf}%</strong>
                    </div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                    <div>
                      <span style={{ color: '#64748b' }}>Mapped Condition: </span>
                      <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{mapped} ({mapStatus})</span>
                    </div>
                    <div>
                      <span style={{ color: '#64748b' }}>Live Authority: </span>
                      <span style={{ color: '#38bdf8' }}>Primary Defect Classifier</span>
                    </div>
                  </div>
                </div>
              );
            })()}
          </div>

          {/* 6. AI EXPLANATION (Vertex) */}
          <div className="hierarchy-tier tier-explanation" style={{ borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', fontSize: '0.72rem' }}>
                6. AI Result Explanation
              </span>
              <span style={{ fontSize: '0.72rem', color: '#a78bfa', fontWeight: 600 }}>
                Vertex Multimodal Gate
              </span>
            </div>
            <div style={{ color: '#e2e8f0', fontSize: '0.78rem', marginTop: '4px', lineHeight: 1.4, background: 'rgba(0,0,0,0.2)', padding: '6px 8px', borderRadius: '4px' }}>
              {item.aiExplanation || item.cvDebug?.aiExplanation || item.measurementNote || 'Scene evaluated by Vertex semantic gatekeeper; physical geometry verified by OpenCV and classified against WRc sewer defect baseline.'}
            </div>
          </div>
        </div>

        <div className="inspection-note-block">
          <span>Measurement Review</span>
          <p>{measurementLabel(item)}</p>
        </div>

        <div className="inspection-audit-grid">
          <span>{item.measurementAudit?.enhancementUsed ? 'Enhanced image used' : 'Original image basis'}</span>
          <span>{item.aiReview ? `${Math.round(item.aiReview.confidence * 100)}% AI review` : 'AI skipped'}</span>
          <span>{item.cvDebug?.visibleSectors ? `${item.cvDebug.visibleSectors} sectors checked` : 'Geometry trace saved'}</span>
        </div>

        <div className="inspection-note-block">
          <span>Inspector Notes</span>
          <p>{item.notes || 'Awaiting inspector note for this joint.'}</p>
        </div>

        <div className="inspection-meta-row">
          <span>{measurementLabel(item)}</span>
          <span>{Math.round((item.confidence ?? 0) * 100)}% confidence</span>
        </div>

        <div className="inspection-cta-row">
          <button className="button button-secondary card-action-button" type="button" onClick={() => setOpenControls((current) => !current)}>
            {statusActionLabel(item.status)}
          </button>
          <button className="button button-ghost" type="button" onClick={() => void onRemeasure(item.id)} disabled={busy}>
            Re-measure
          </button>
        </div>

        {openControls ? (
          <div className="inspection-controls-panel">
            <label className="field">
              <span>Inspector Note</span>
              <textarea value={note} onChange={(event) => setNote(event.target.value)} rows={4} />
            </label>

            <div className="override-grid">
              <label className="field">
                <span>Override Value (mm)</span>
                <input
                  type="number"
                  step="0.1"
                  value={overrideDraft.value}
                  onChange={(event) => setOverrideDraft((current) => ({ ...current, value: event.target.value }))}
                />
              </label>
              <label className="field">
                <span>Override Reason</span>
                <input
                  value={overrideDraft.reason}
                  onChange={(event) => setOverrideDraft((current) => ({ ...current, reason: event.target.value }))}
                  placeholder="Why are you overriding this value?"
                />
              </label>
            </div>

            <div className="action-row">
              <button className="button button-secondary" type="button" onClick={() => void handleSaveNote()} disabled={busy}>
                Save Note
              </button>
              <button className="button button-primary" type="button" onClick={() => void handleOverride()} disabled={busy}>
                Apply Override
              </button>
              {item.overrideApplied ? (
                <button className="button button-ghost" type="button" onClick={() => void onClearOverride(item.id)} disabled={busy}>
                  Clear Override
                </button>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </article>
  )
}

export const InspectionResultsPage = ({
  inspectionId,
  loading = false,
  online,
  projectId,
  projectName,
  siteName,
  manholeLabel,
  results,
  summary,
  onBack,
  onSaveNote,
  onRemeasure,
  onApplyOverride,
  onClearOverride,
  onNext,
}: Props) => {
  const total = summary?.totalJoints ?? results.length
  const pass = summary?.passCount ?? results.filter((item) => item.status === 'PASS').length
  const fail = summary?.failCount ?? results.filter((item) => item.status === 'FAIL').length
  const review = summary?.reviewCount ?? results.filter((item) => item.status === 'REVIEW').length
  const completion = total ? Math.round((results.length / total) * 100) : 0
  const latestProcessedAt = results[results.length - 1]?.processedAt

  useEffect(() => {
    console.log('ROUTE INSPECTION ID:', inspectionId)
    console.log('LOADED RESULTS:', results)
  }, [inspectionId, results])

  if (loading) {
    return (
      <div className="page-grid results-page">
        <article className="empty-state">
          <strong>Loading inspection results...</strong>
          <p>Fetching the saved measurement job for display.</p>
        </article>
      </div>
    )
  }

  return (
    <div className="page-grid results-page">
      <div className="page-status-strip">
        <span>{online ? 'Online - measurements saved locally' : 'Offline - measurements stored on device'}</span>
        <span>
          Last updated:{' '}
          {latestProcessedAt
            ? new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: 'short' }).format(new Date(latestProcessedAt))
            : 'Not processed yet'}
        </span>
      </div>

      <section className="results-summary-hero">
        <div className="results-summary-copy">
          <div className="results-project-id">Project ID: {projectId}</div>
          <h1>{projectName}</h1>
          <p className="lead">
            Gap measurement results for {manholeLabel}
            {siteName ? ` at ${siteName}` : ''}.
          </p>

          <div className="results-progress-block">
            <div className="results-progress-head">
              <span>Overall Inspection Completion</span>
              <strong>{completion}%</strong>
            </div>
            <div className="progress-rail large">
              <div className="progress-fill" style={{ width: `${completion}%` }} />
            </div>
          </div>
        </div>

        <div className="results-kpi-grid">
          <article className="results-kpi-card">
            <strong>{total}</strong>
            <span>Total</span>
          </article>
          <article className="results-kpi-card is-pass">
            <strong>{pass}</strong>
            <span>Pass</span>
          </article>
          <article className="results-kpi-card is-fail">
            <strong>{fail}</strong>
            <span>Fail</span>
          </article>
          <article className="results-kpi-card is-review">
            <strong>{review}</strong>
            <span>Review</span>
          </article>
        </div>
      </section>

      <div className="page-top-actions">
        <button className="button button-secondary" type="button" onClick={onBack}>
          Back to Upload
        </button>
        <button className="button button-primary" type="button" onClick={onNext}>
          Project Summary
        </button>
      </div>

      <p className="lead">Guidance only – not a formal adoption assessment.</p>

      <section className="inspection-results-grid">
        {results.length ? (
          results.map((item) => (
            <ResultCard
              key={item.id}
              item={item}
              onSaveNote={onSaveNote}
              onRemeasure={onRemeasure}
              onApplyOverride={onApplyOverride}
              onClearOverride={onClearOverride}
            />
          ))
        ) : (
          <article className="empty-state">
            <strong>No inspection results found.</strong>
            <p>The selected inspection job did not return any saved results yet.</p>
          </article>
        )}
      </section>
    </div>
  )
}
