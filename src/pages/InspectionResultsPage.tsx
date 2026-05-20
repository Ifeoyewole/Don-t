import { useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import type { InspectionResult, ManholeInspectionSummary } from '../types/domain'

type Props = {
  projectName: string
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

  const toneClass =
    item.status === 'PASS' ? 'result-card pass' : item.status === 'FAIL' ? 'result-card fail' : 'result-card review'

  return (
    <article className={toneClass}>
      <div className="result-media">
        <div className="result-image-placeholder" />
        <span>{item.jointLabel}</span>
      </div>
      <div className="result-body">
        <div className="upload-title-row">
          <h3>{item.jointLabel}</h3>
          <StatusBadge status={item.status} />
        </div>
        <div className="metric-row">
          <div>
            <span>Original</span>
            <strong>{item.originalGapMm.toFixed(1)} mm</strong>
          </div>
          <div>
            <span>Final</span>
            <strong>{item.finalGapMm.toFixed(1)} mm</strong>
          </div>
          <div>
            <span>Confidence</span>
            <strong>{Math.round((item.confidence ?? 0) * 100)}%</strong>
          </div>
        </div>

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
          <button className="button button-secondary" type="button" onClick={() => void onRemeasure(item.id)} disabled={busy}>
            Re-measure
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
    </article>
  )
}

export const InspectionResultsPage = ({
  projectName,
  manholeLabel,
  results,
  summary,
  onBack,
  onSaveNote,
  onRemeasure,
  onApplyOverride,
  onClearOverride,
  onNext,
}: Props) => (
  <div className="page-grid">
    <section className="section-header compact">
      <button className="button button-ghost" type="button" onClick={onBack}>
        Back
      </button>
      <button className="button button-primary" type="button" onClick={onNext}>
        Project Summary
      </button>
    </section>

    <section className="page-intro">
      <div>
        <p className="eyebrow">{projectName}</p>
        <h1>Inspection results</h1>
        <p className="lead">{manholeLabel} result review with notes, overrides, and re-measure actions for the UI flow.</p>
      </div>
    </section>

    <section className="two-column-layout">
      <aside className="summary-sidebar">
        <div className="summary-card">
          <h2>Inspection Summary</h2>
          <div className="summary-metrics">
            <div>
              <span>Total joints</span>
              <strong>{summary?.totalJoints ?? 0}</strong>
            </div>
            <div>
              <span>Pass</span>
              <strong>{summary?.passCount ?? 0}</strong>
            </div>
            <div>
              <span>Review</span>
              <strong>{summary?.reviewCount ?? 0}</strong>
            </div>
            <div>
              <span>Fail</span>
              <strong>{summary?.failCount ?? 0}</strong>
            </div>
          </div>
        </div>
        <div className="side-note-card emphasis">
          <h2>Review rules</h2>
          <p>Original values stay preserved, final values reflect overrides, and every mutation leaves an explicit trace in UI copy.</p>
        </div>
      </aside>

      <section className="results-stack">
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
            <strong>No results yet</strong>
            <p>Process the upload queue first to populate inspection results for this manhole.</p>
          </article>
        )}
      </section>
    </section>
  </div>
)
