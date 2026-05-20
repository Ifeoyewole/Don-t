import { StatusBadge } from '../components/StatusBadge'
import type { ProjectInspectionSummary } from '../types/domain'

type Props = {
  projectName: string
  projectId: string
  summary: ProjectInspectionSummary | null
  onBack: () => void
  onExport: (format: 'json' | 'pdf' | 'zip') => Promise<void>
  onOpenFlagged: () => void
}

export const InspectionSummaryPage = ({
  projectName,
  projectId,
  summary,
  onBack,
  onExport,
  onOpenFlagged,
}: Props) => (
  <div className="page-grid">
    <section className="section-header compact">
      <button className="button button-ghost" type="button" onClick={onBack}>
        Back
      </button>
    </section>

    <section className="page-intro">
      <div>
        <p className="eyebrow">Project ID: {projectId}</p>
        <h1>Inspection summary</h1>
        <p className="lead">{projectName} aggregate counts, flagged items, and export actions for the frontend review flow.</p>
      </div>
      <div className="export-actions">
        <button className="button button-primary" type="button" onClick={() => void onExport('zip')}>
          Export Evidence Pack
        </button>
        <button className="button button-secondary" type="button" onClick={() => void onExport('pdf')}>
          Export PDF
        </button>
        <button className="button button-ghost" type="button" onClick={() => void onExport('json')}>
          Export JSON
        </button>
      </div>
    </section>

    <section className="stats-grid">
      <article className="stat-card">
        <span className="stat-label">Total joints</span>
        <strong>{summary?.totalJoints ?? 0}</strong>
      </article>
      <article className="stat-card">
        <span className="stat-label">Pass</span>
        <strong>{summary?.passCount ?? 0}</strong>
      </article>
      <article className="stat-card">
        <span className="stat-label">Review</span>
        <strong>{summary?.reviewCount ?? 0}</strong>
      </article>
      <article className="stat-card stat-card-alert">
        <span className="stat-label">Fail</span>
        <strong>{summary?.failCount ?? 0}</strong>
      </article>
    </section>

    <section className="summary-layout">
      <div className="flagged-list">
        <div className="section-header compact">
          <div>
            <h2>Flagged items ({summary?.flaggedJoints.length ?? 0})</h2>
            <p>Non-pass joints surfaced for second-pass review.</p>
          </div>
          <button className="button button-secondary" type="button" onClick={onOpenFlagged}>
            Review Results
          </button>
        </div>

        {summary?.flaggedJoints.length ? (
          summary.flaggedJoints.map((item) => (
            <article className="flagged-card" key={item.inspectionId}>
              <div className="upload-title-row">
                <div>
                  <strong>{item.jointLabel}</strong>
                  <span>{item.finalGapMm.toFixed(1)} mm final gap</span>
                </div>
                <StatusBadge status={item.status} />
              </div>
              <p>{item.note}</p>
            </article>
          ))
        ) : (
          <article className="empty-state">
            <strong>No flagged items</strong>
            <p>All current joint measurements sit inside the pass band.</p>
          </article>
        )}
      </div>

      <aside className="summary-sidebar">
        <div className="summary-card dark-card">
          <h2>Evidence pack contents</h2>
          <ul className="feature-list">
            <li>Project and manhole details</li>
            <li>Queued images and measured results</li>
            <li>Override metadata and inspector notes</li>
            <li>Required disclaimer footer text</li>
          </ul>
        </div>
        <div className="tip-card">
          <strong>Disclaimer</strong>
          <p>Guidance only — not a formal adoption assessment.</p>
        </div>
      </aside>
    </section>
  </div>
)
