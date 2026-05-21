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
  online,
  projectName,
  projectId,
  projectSiteName,
  manholes,
  lastUpdatedAt,
  summary,
  onBack,
  onExport,
  onOpenFlagged,
}: Props) => {
  const flagged = summary?.flaggedJoints ?? []
  const latestManhole = manholes[0]?.manholeId ?? 'No manholes yet'

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
          <h1>{projectName}</h1>
          <p className="lead">
            Last updated: {formatDateTime(lastUpdatedAt)}
            {projectSiteName ? ` • Site: ${projectSiteName}` : ''}
          </p>
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

      <section className="summary-kpi-grid">
        <article className="summary-kpi-card">
          <span>Total Joints</span>
          <strong>{summary?.totalJoints ?? 0}</strong>
          <p>100% inspected</p>
        </article>
        <article className="summary-kpi-card is-pass">
          <span>Pass</span>
          <strong>{summary?.passCount ?? 0}</strong>
          <p>Within tolerance</p>
        </article>
        <article className="summary-kpi-card is-review">
          <span>Review</span>
          <strong>{summary?.reviewCount ?? 0}</strong>
          <p>Action required</p>
        </article>
        <article className="summary-kpi-card is-fail">
          <span>Fail</span>
          <strong>{summary?.failCount ?? 0}</strong>
          <p>Critical issues</p>
        </article>
      </section>

      <section className="summary-bento-grid">
        <div className="flagged-anomalies-card">
          <div className="flagged-card-head">
            <h2>Flagged Anomalies</h2>
            <div className="flagged-head-actions">
              <button className="button button-secondary" type="button">
                Filter
              </button>
              <button className="button button-secondary" type="button">
                Search
              </button>
            </div>
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
                        <strong>Joint #{item.jointLabel}</strong>
                        <span>
                          {item.manholeLabel || latestManhole}
                          {projectSiteName ? ` • ${projectSiteName}` : ''}
                        </span>
                      </div>
                      <span className={`mini-status-pill is-${item.status.toLowerCase()}`}>{item.status}</span>
                    </div>
                    <p>
                      {item.note ||
                        `${item.finalGapMm.toFixed(1)} mm measured gap ${
                          item.measurementSource === 'fallback' ? 'estimated from fallback measurement.' : 'recorded from CV measurement.'
                        }`}
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
                <strong>No flagged anomalies</strong>
                <p>All measured joints are currently inside the pass band.</p>
              </article>
            )}
          </div>

          <div className="flagged-footer">
            <button className="button button-ghost" type="button" onClick={() => onOpenFlagged()}>
              View All Flagged Items ({flagged.length})
            </button>
          </div>
        </div>

        <aside className="summary-side-panels">
          <article className="location-panel">
            <div className="location-panel-head">
              <h3>Location</h3>
              <span>⌖</span>
            </div>
            <div className="location-map">
              <div className="location-map-badge">{latestManhole}</div>
            </div>
            <div className="location-details">
              <p>
                <strong>Project:</strong> {projectId}
              </p>
              <p>
                <strong>Site:</strong> {projectSiteName || 'Not provided'}
              </p>
              <p>
                <strong>Manholes:</strong> {manholes.length}
              </p>
            </div>
          </article>

          <article className="session-log-panel">
            <h3>Session Log</h3>
            <div className="session-log-timeline">
              <div className="session-log-item is-good">
                <strong>Session Finalized</strong>
                <span>{formatDateTime(lastUpdatedAt)}</span>
              </div>
              <div className="session-log-item is-primary">
                <strong>{summary?.totalJoints ?? 0} Joints Recorded</strong>
                <span>{formatDateTime(flagged[0]?.processedAt ?? lastUpdatedAt)}</span>
              </div>
              <div className="session-log-item">
                <strong>Inspection Started</strong>
                <span>{formatDateTime(manholes[0]?.createdAt)}</span>
              </div>
            </div>
            <div className="session-log-meta">
              <div>
                <span>Project ID</span>
                <strong>{projectId}</strong>
              </div>
              <div>
                <span>Manhole Count</span>
                <strong>{manholes.length}</strong>
              </div>
              <div>
                <span>Flagged Joints</span>
                <strong>{flagged.length}</strong>
              </div>
              <div>
                <span>Overrides</span>
                <strong>{summary?.overriddenCount ?? 0}</strong>
              </div>
            </div>
          </article>
        </aside>
      </section>

      <div className="summary-bottom-sync">
        <span>{online ? 'Online - local inspection data ready for export' : 'Offline - local inspection data preserved'}</span>
        <button className="button button-ghost" type="button" onClick={() => void onExport('zip')}>
          Export Again
        </button>
      </div>
    </div>
  )
}
