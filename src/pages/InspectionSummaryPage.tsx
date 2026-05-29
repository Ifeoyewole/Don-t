import type { Manhole, ProjectInspectionSummary } from '../types/domain'

type Props = {
  online: boolean
  projectName: string
  projectId: string
  projectSiteName?: string
  manholes: Manhole[]
  lastUpdatedAt?: string
  summary: ProjectInspectionSummary | null
  onBack: () => void
  onEditProject: () => void
  onEditManhole: (manholeId: string) => void
  onResumeUpload: (manholeId: string) => void
  onExport: (format: 'json' | 'pdf' | 'zip') => Promise<void>
  onOpenFlagged: (inspectionId?: string) => void
}

const formatDateTime = (value?: string) =>
  value
    ? new Intl.DateTimeFormat('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(new Date(value))
    : 'Not yet processed'

export const InspectionSummaryPage = ({
  projectName,
  projectSiteName,
  manholes,
  lastUpdatedAt,
  summary,
  onBack,
  onEditProject,
  onEditManhole,
  onResumeUpload,
  onExport,
  onOpenFlagged,
}: Props) => {
  const flagged = summary?.flaggedJoints ?? []
  const overallReport =
    (summary?.failCount ?? 0) > 0 ? 'FAIL' : (summary?.reviewCount ?? 0) > 0 ? 'REVIEW' : (summary?.totalJoints ?? 0) > 0 ? 'PASS' : 'NO RESULTS'

  return (
    <div className="page-grid summary-page">
      <section className="page-breadcrumbs">
        <button className="page-back-link" type="button" onClick={onBack}>
          Projects
        </button>
        <span>›</span>
        <span>{projectName.toUpperCase()}</span>
        <span>›</span>
        <strong>Inspection Summary</strong>
      </section>

      <section className="page-hero">
        <div>
          <h1>Inspection Summary</h1>
          <p className="lead">
            {projectName}
            {projectSiteName ? ` • ${projectSiteName}` : ''} • Last updated: {formatDateTime(lastUpdatedAt)}
          </p>
        </div>
        <div className="export-actions">
          <button className="button button-secondary" type="button" onClick={onEditProject}>
            Edit Project
          </button>
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

      <section className="summary-kpi-grid">
        <article className="summary-kpi-card">
          <span>Overall Report</span>
          <strong>{overallReport}</strong>
          <p>Project outcome</p>
        </article>
        <article className="summary-kpi-card is-pass">
          <span>Pass</span>
          <strong>{summary?.passCount ?? 0}</strong>
          <p>Within tolerance</p>
        </article>
        <article className="summary-kpi-card is-review">
          <span>Review</span>
          <strong>{summary?.reviewCount ?? 0}</strong>
          <p>Needs checking</p>
        </article>
        <article className="summary-kpi-card is-fail">
          <span>Fail</span>
          <strong>{summary?.failCount ?? 0}</strong>
          <p>Outside tolerance</p>
        </article>
      </section>

      <section className="summary-bento-grid">
        <div className="flagged-anomalies-card">
          <div className="flagged-card-head">
            <h2>Flagged Joints</h2>
          </div>

          <div className="flagged-anomalies-list">
            {flagged.length ? (
              flagged.map((item) => (
                <button
                  className="flagged-anomaly-row"
                  type="button"
                  key={item.inspectionId}
                  onClick={() => onOpenFlagged(item.inspectionId)}
                >
                  <div className="flagged-anomaly-thumb">
                    {item.previewUrl ? <img src={item.previewUrl} alt={item.fileName ?? item.jointLabel} /> : <div className="preview-placeholder" />}
                  </div>
                  <div className="flagged-anomaly-copy">
                    <div className="flagged-anomaly-top">
                      <div>
                        <strong>Joint {item.jointLabel}</strong>
                        <span>
                          {item.manholeLabel || 'Manhole'}
                          {projectSiteName ? ` • ${projectSiteName}` : ''}
                        </span>
                      </div>
                      <span className={`mini-status-pill is-${item.status.toLowerCase()}`}>{item.status}</span>
                    </div>
                    <p>
                      {item.finalGapMm.toFixed(1)} mm gap
                      {item.note ? ` • ${item.note}` : ''}
                    </p>
                    <div className="flagged-anomaly-meta">
                      <span>Log: {formatDateTime(item.processedAt)}</span>
                      <span>{item.photoCount ?? 1} Photo{(item.photoCount ?? 1) === 1 ? '' : 's'}</span>
                    </div>
                  </div>
                  <span className="dashboard-arrow" aria-hidden="true">
                    ›
                  </span>
                </button>
              ))
            ) : (
              <article className="empty-state">
                <strong>No flagged joints</strong>
                <p>All measured joints are currently inside the pass band.</p>
              </article>
            )}
          </div>

          <div className="flagged-footer">
            <button className="button button-ghost" type="button" onClick={() => onOpenFlagged()}>
              View Flagged Results ({flagged.length})
            </button>
          </div>
        </div>

        <aside className="summary-side-panels">
          <article className="location-panel">
            <div className="location-panel-head">
              <h3>Project Record</h3>
            </div>
            <div className="location-details">
              <p>
                <strong>Project:</strong> {projectName}
              </p>
              <p>
                <strong>Site:</strong> {projectSiteName || 'Not provided'}
              </p>
              <p>
                <strong>Manholes:</strong> {manholes.length}
              </p>
              <p>
                <strong>Joints Captured:</strong> {summary?.totalJoints ?? 0}
              </p>
            </div>
            <div className="summary-action-stack">
              <button className="button button-primary" type="button" onClick={() => onResumeUpload(manholes[0]?.id ?? '')} disabled={!manholes.length}>
                Resume Upload
              </button>
              <button className="button button-secondary" type="button" onClick={() => onOpenFlagged()} disabled={!flagged.length}>
                View Results Again
              </button>
            </div>
          </article>

          <article className="session-log-panel">
            <h3>Edit Inspection Setup</h3>
            <div className="summary-manhole-list">
              {manholes.length ? (
                manholes.map((manhole) => (
                  <div className="summary-manhole-row" key={manhole.id}>
                    <div>
                      <strong>{manhole.manholeId}</strong>
                      <span>{manhole.pipeDiameterMm} mm pipe • {manhole.estimatedJointCount} expected joints</span>
                    </div>
                    <div className="action-row">
                      <button className="button button-secondary" type="button" onClick={() => onEditManhole(manhole.id)}>
                        Edit
                      </button>
                      <button className="button button-ghost" type="button" onClick={() => onResumeUpload(manhole.id)}>
                        Upload
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <p className="lead">No manholes have been added yet.</p>
              )}
            </div>
          </article>

          <article className="session-log-panel">
            <h3>Summary Notes</h3>
            <div className="session-log-timeline">
              <div className="session-log-item">
                <strong>Pass count</strong>
                <span>{summary?.passCount ?? 0}</span>
              </div>
              <div className="session-log-item is-primary">
                <strong>Review count</strong>
                <span>{summary?.reviewCount ?? 0}</span>
              </div>
              <div className="session-log-item is-good">
                <strong>Fail count</strong>
                <span>{summary?.failCount ?? 0}</span>
              </div>
            </div>
            <p className="lead">Guidance only – not a formal adoption assessment.</p>
          </article>
        </aside>
      </section>
    </div>
  )
}
