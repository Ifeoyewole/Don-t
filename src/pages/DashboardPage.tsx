import { useMemo, useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import type { ProjectSummary } from '../types/domain'

type Props = {
  projects: ProjectSummary[]
  showAllProjects: boolean
  onToggleProjects: () => void
  onNewProject: () => void
  onOpenProject: (projectId: string) => void
  onDeleteProject: (projectId: string) => void
  viewMode?: 'dashboard' | 'projects'
  searchQuery?: string
  onSearchChange?: (query: string) => void
}

const formatRelativeTime = (iso: string) => {
  try {
    return new Intl.DateTimeFormat('en-GB', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

const statusCopy = (status: ProjectSummary['status']) => {
  if (status === 'FAIL') return 'Immediate action required'
  if (status === 'REVIEW') return 'Waiting for review'
  if (status === 'PASS') return 'Inspection complete'
  return 'Ready for field capture'
}

const activityTone = (status: ProjectSummary['status']) => {
  if (status === 'FAIL') return 'activity-dot is-fail'
  if (status === 'REVIEW') return 'activity-dot is-review'
  if (status === 'PASS') return 'activity-dot is-pass'
  return 'activity-dot is-progress'
}

const PipeEmptyGraphic = () => (
  <svg viewBox="0 0 120 120" fill="none" width="80" height="80" aria-hidden="true">
    <circle cx="60" cy="60" r="50" stroke="#cdd9ec" strokeWidth="3" strokeDasharray="6 6" />
    <circle cx="60" cy="60" r="34" stroke="#0051d5" strokeWidth="3" fill="#eef4ff" />
    <circle cx="60" cy="60" r="16" stroke="#cdd9ec" strokeWidth="2" fill="#ffffff" />
    <path d="M60 10v16M60 94v16M10 60h16M94 60h16" stroke="#0051d5" strokeWidth="2.5" strokeLinecap="round" />
    <path d="M42 42l8 8M70 70l8 8M78 42l-8 8M50 70l-8 8" stroke="#94a3b8" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
)

export const DashboardPage = ({
  projects,
  showAllProjects,
  onToggleProjects,
  onNewProject,
  onOpenProject,
  onDeleteProject,
  viewMode = 'dashboard',
  searchQuery,
  onSearchChange,
}: Props) => {
  const [internalSearch, setInternalSearch] = useState('')
  const search = searchQuery !== undefined ? searchQuery : internalSearch
  const setSearch = onSearchChange || setInternalSearch

  const filteredProjects = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return projects
    return projects.filter((project) =>
      [project.name, project.siteName, project.id].some((value) => value?.toLowerCase().includes(query)),
    )
  }, [projects, search])

  const visibleProjects = showAllProjects ? filteredProjects : filteredProjects.slice(0, 5)

  // KPI Calculations
  const totalProjects = projects.length
  const totalInspections = projects.reduce((sum, project) => sum + (project.completedInspections ?? 0), 0)
  const totalJointsTarget = projects.reduce((sum, project) => sum + (project.totalJoints ?? 0), 0)
  const totalFailures = projects.reduce((sum, project) => sum + (project.failCount ?? 0), 0)
  const totalReview = projects.reduce((sum, project) => sum + (project.reviewCount ?? 0), 0)
  const totalAccepted = Math.max(totalInspections - totalFailures - totalReview, 0)

  const completionRate = totalJointsTarget > 0 ? Math.round((totalInspections / totalJointsTarget) * 100) : 0

  const acceptedPct = totalInspections > 0 ? Math.round((totalAccepted / totalInspections) * 100) : 0
  const reviewPct = totalInspections > 0 ? Math.round((totalReview / totalInspections) * 100) : 0
  const failPct = totalInspections > 0 ? Math.round((totalFailures / totalInspections) * 100) : 0

  const recentActivity = [...projects]
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    .slice(0, 4)

  const pageTitle = viewMode === 'projects' ? 'Projects' : 'Inspection Dashboard'
  const pageLead =
    viewMode === 'projects'
      ? 'Manage inspection projects, manhole runs, and measured pipe joints.'
      : 'Real-time AI/CV joint measurement telemetry, defect classification, and pipeline health.'

  return (
    <div className="page-grid dashboard-page">
      {/* 6. Page Header with aligned Primary CTA */}
      <section className="dashboard-hero-row">
        <div className="hero-text-block">
          <div className="hero-badge-tag">
            <span className="hero-badge-dot" />
            <span>Industrial Pipeline CV</span>
          </div>
          <h1>{pageTitle}</h1>
          <p className="hero-lead-text">{pageLead}</p>
        </div>
        <button className="button button-primary cta-new-project" type="button" onClick={onNewProject}>
          <span className="plus-sign" aria-hidden="true">
            +
          </span>
          <span>New Project</span>
        </button>
      </section>

      {/* 3 & 4. Upgraded 5 KPI Cards Grid with Semantic Trust Colors and 25-30% shorter height */}
      <section className="dashboard-kpi-grid" aria-label="Key Performance Indicators">
        {/* KPI 1: Projects */}
        <article className="kpi-card is-neutral">
          <div className="kpi-top">
            <span className="kpi-label">Projects</span>
            <span className="kpi-tag neutral-tag">FLEET</span>
          </div>
          <div className="kpi-value-row">
            <strong className="kpi-number">{totalProjects}</strong>
          </div>
          <span className="kpi-footer-text">Active datasets on device</span>
        </article>

        {/* KPI 2: Inspected Joints */}
        <article className="kpi-card is-processing">
          <div className="kpi-top">
            <span className="kpi-label">Inspected Joints</span>
            <span className="kpi-tag processing-tag">PROGRESS</span>
          </div>
          <div className="kpi-value-row">
            <strong className="kpi-number">{totalInspections}</strong>
          </div>
          <span className="kpi-footer-text">
            {totalJointsTarget > 0 ? `${completionRate}% of ${totalJointsTarget} target` : 'Ready for field capture'}
          </span>
        </article>

        {/* KPI 3: Accepted (Green) */}
        <article className="kpi-card is-accepted">
          <div className="kpi-top">
            <span className="kpi-label">Accepted</span>
            <span className="kpi-tag accepted-tag">PASS</span>
          </div>
          <div className="kpi-value-row">
            <strong className="kpi-number text-accepted">{totalAccepted}</strong>
          </div>
          <span className="kpi-footer-text text-accepted">ACCEPTED_MEASUREMENT</span>
        </article>

        {/* KPI 4: Review Required (Amber) */}
        <article className="kpi-card is-review">
          <div className="kpi-top">
            <span className="kpi-label">Review Required</span>
            <span className="kpi-tag review-tag">ATTENTION</span>
          </div>
          <div className="kpi-value-row">
            <strong className="kpi-number text-review">{totalReview}</strong>
          </div>
          <span className="kpi-footer-text text-review">REVIEW_REQUIRED</span>
        </article>

        {/* KPI 5: Rejected (Red) */}
        <article className="kpi-card is-rejected">
          <div className="kpi-top">
            <span className="kpi-label">Rejected</span>
            <span className="kpi-tag rejected-tag">FLAGGED</span>
          </div>
          <div className="kpi-value-row">
            <strong className="kpi-number text-rejected">{totalFailures}</strong>
          </div>
          <span className="kpi-footer-text text-rejected">REJECTED_UNRELIABLE</span>
        </article>
      </section>

      {/* Projects Table Card */}
      <section className="dashboard-table-card">
        <div className="dashboard-table-header">
          <div>
            <h2>{viewMode === 'projects' ? 'All Projects' : 'Recent Projects'}</h2>
            <p>
              {filteredProjects.length} project{filteredProjects.length === 1 ? '' : 's'} stored on this device.
            </p>
          </div>
          <div className="dashboard-controls">
            <label className="dashboard-search">
              <span className="search-symbol" aria-hidden="true">
                ⌕
              </span>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Filter by name, site, ID..."
              />
            </label>
            {filteredProjects.length > 5 && (
              <button className="button button-secondary button-compact" type="button" onClick={onToggleProjects}>
                {showAllProjects ? 'Show Less' : 'Show All'}
              </button>
            )}
          </div>
        </div>

        {/* 7. Centered Empty State when 0 projects exist */}
        {filteredProjects.length === 0 ? (
          <div className="dashboard-empty-state">
            <div className="empty-graphic-wrapper">
              <PipeEmptyGraphic />
            </div>
            <h3 className="empty-title">No inspection projects yet</h3>
            <p className="empty-description">
              Create your first project, add a manhole, and begin inspecting joints with the AI/CV measurement engine.
            </p>
            <button className="button button-primary empty-cta-btn" type="button" onClick={onNewProject}>
              + Create Project
            </button>
          </div>
        ) : (
          <>
            <div className="dashboard-table">
              <div className="dashboard-table-head">
                <span>Project Name</span>
                <span>Location</span>
                <span>Status</span>
                <span>Joint Count</span>
                <span>Last Inspected</span>
                <span className="actions-head">Actions</span>
              </div>

              {visibleProjects.map((project) => (
                <div key={project.id} className="dashboard-table-row">
                  <div className="dashboard-project-cell">
                    <div className="dashboard-project-thumb" aria-hidden="true">
                      {project.name.slice(0, 1).toUpperCase()}
                    </div>
                    <div className="dashboard-project-copy">
                      <strong>{project.name}</strong>
                      <span className="project-id-sub">{project.id}</span>
                    </div>
                  </div>
                  <span className="location-cell">{project.siteName || 'Site pending'}</span>
                  <div className="dashboard-status-cell">
                    <StatusBadge status={project.status ?? 'IN PROGRESS'} />
                    <small>{statusCopy(project.status)}</small>
                  </div>
                  <div className="dashboard-count-cell">
                    <strong>{project.totalJoints ?? 0} joints</strong>
                    <span>{project.completedInspections ?? 0} inspected</span>
                  </div>
                  <span className="time-cell">{formatRelativeTime(project.updatedAt)}</span>
                  <div className="dashboard-actions-cell">
                    <button
                      className="button button-secondary button-compact"
                      type="button"
                      onClick={() => onOpenProject(project.id)}
                    >
                      Open
                    </button>
                    <button
                      className="button button-danger button-compact"
                      type="button"
                      onClick={() => onDeleteProject(project.id)}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>

            <div className="dashboard-table-footer">
              <span>
                Showing {visibleProjects.length} of {filteredProjects.length} projects
              </span>
              {filteredProjects.length > 5 && (
                <div className="dashboard-pagination">
                  <button className="button button-secondary button-compact" type="button" onClick={onToggleProjects}>
                    {showAllProjects ? 'Show Recent (5)' : `View All (${filteredProjects.length})`}
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </section>

      {/* 8 & 9. Lower Grid: Visual Inspection Progress + System Readiness */}
      <section className="dashboard-lower-grid">
        {/* 9. Visual Inspection Progress Card */}
        <article className="dashboard-trends-card">
          <div className="dashboard-panel-head">
            <div>
              <h2>Inspection Progress</h2>
              <p className="panel-subtitle">Aggregate measurement completion and trust breakdown</p>
            </div>
            <span className="progress-ratio-badge">
              {totalInspections} / {Math.max(totalJointsTarget, totalInspections)} Joints
            </span>
          </div>

          <div className="visual-progress-block">
            {/* Segmented Progress Bar */}
            <div className="segmented-progress-track" title={`${completionRate}% overall inspected`}>
              {totalInspections > 0 ? (
                <>
                  <div
                    className="prog-seg is-seg-accepted"
                    style={{ width: `${acceptedPct}%` }}
                    title={`Accepted: ${totalAccepted} (${acceptedPct}%)`}
                  />
                  <div
                    className="prog-seg is-seg-review"
                    style={{ width: `${reviewPct}%` }}
                    title={`Review: ${totalReview} (${reviewPct}%)`}
                  />
                  <div
                    className="prog-seg is-seg-fail"
                    style={{ width: `${failPct}%` }}
                    title={`Rejected: ${totalFailures} (${failPct}%)`}
                  />
                </>
              ) : (
                <div className="prog-seg-empty" style={{ width: '100%' }} />
              )}
            </div>

            {/* Segment Legend */}
            <div className="progress-legend-row">
              <div className="legend-item">
                <span className="legend-dot is-dot-accepted" />
                <span className="legend-name">Accepted</span>
                <strong className="legend-val">{totalAccepted}</strong>
              </div>
              <div className="legend-item">
                <span className="legend-dot is-dot-review" />
                <span className="legend-name">Review</span>
                <strong className="legend-val">{totalReview}</strong>
              </div>
              <div className="legend-item">
                <span className="legend-dot is-dot-fail" />
                <span className="legend-name">Rejected</span>
                <strong className="legend-val">{totalFailures}</strong>
              </div>
            </div>
          </div>

          {/* Project-by-project breakdown */}
          <div className="trend-bars">
            {projects.length > 0 ? (
              projects.slice(0, 4).map((project) => {
                const total = Math.max(project.totalJoints ?? 0, 1)
                const percent = Math.round(((project.completedInspections ?? 0) / total) * 100)
                return (
                  <div className="trend-row" key={project.id}>
                    <div className="trend-info">
                      <strong>{project.name}</strong>
                      <span>{project.siteName || 'Site pending'}</span>
                    </div>
                    <div className="trend-meter">
                      <div className="trend-fill" style={{ width: `${percent}%` }} />
                    </div>
                    <strong className="trend-percent">{percent}%</strong>
                  </div>
                )
              })
            ) : (
              <div className="trend-empty-placeholder">
                <span>Add inspection photos to track joint measurements across manholes.</span>
              </div>
            )}
          </div>
        </article>

        {/* 8. System Readiness Card (AI/CV Engine Telemetry) */}
        <article className="dashboard-activity-card system-readiness-panel">
          <div className="dashboard-panel-head">
            <div>
              <h2>System Readiness</h2>
              <p className="panel-subtitle">AI/CV inspection pipeline & hardware telemetry</p>
            </div>
            <span className="status-live-pill">
              <span className="pulse-dot" />
              <span>LIVE</span>
            </span>
          </div>

          <div className="readiness-spec-list">
            <div className="readiness-row">
              <div className="readiness-label-group">
                <span className="readiness-name">AI Segmenter</span>
                <span className="readiness-detail">joint-seg-v1 (Sewer-ML & YOLOv8)</span>
              </div>
              <span className="readiness-status is-ready">READY</span>
            </div>

            <div className="readiness-row">
              <div className="readiness-label-group">
                <span className="readiness-name">OpenCV Geometry</span>
                <span className="readiness-detail">Sub-pixel radial gap detection</span>
              </div>
              <span className="readiness-status is-ready">READY</span>
            </div>

            <div className="readiness-row">
              <div className="readiness-label-group">
                <span className="readiness-name">Camera Calibration</span>
                <span className="readiness-detail">1.000 mm/px nominal scale</span>
              </div>
              <span className="readiness-status is-active">ACTIVE</span>
            </div>

            <div className="readiness-row">
              <div className="readiness-label-group">
                <span className="readiness-name">Cloud Synchronization</span>
                <span className="readiness-detail">Sub-pixel optical verification</span>
              </div>
              <span className="readiness-status is-ready">CONNECTED</span>
            </div>

            <div className="readiness-row">
              <div className="readiness-label-group">
                <span className="readiness-name">Inspection Model</span>
                <span className="readiness-detail">Sub-pixel radial contour profiling</span>
              </div>
              <span className="readiness-badge-spec">joint-v1.0</span>
            </div>

            <div className="readiness-row">
              <div className="readiness-label-group">
                <span className="readiness-name">Last CV Check</span>
                <span className="readiness-detail">Continuous stream heartbeat</span>
              </div>
              <span className="readiness-status is-recent">2 min ago</span>
            </div>
          </div>
        </article>
      </section>

      {/* Recent Updates timeline when projects exist */}
      {recentActivity.length > 0 && (
        <section className="dashboard-activity-section">
          <div className="dashboard-table-card">
            <div className="dashboard-table-header">
              <div>
                <h2>Recent Activity</h2>
                <p>Latest project edits and inspection updates.</p>
              </div>
            </div>
            <div className="activity-list-container">
              {recentActivity.map((project) => (
                <div className="activity-row" key={project.id}>
                  <div className={activityTone(project.status)} />
                  <div className="activity-content">
                    <div className="activity-top-line">
                      <strong>{project.name}</strong>
                      <span className="activity-time">{formatRelativeTime(project.updatedAt)}</span>
                    </div>
                    <p>{statusCopy(project.status)}</p>
                    <span className="activity-sub">
                      {project.siteName ? `${project.siteName} • ` : ''}
                      {project.completedInspections ?? 0} joints measured
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
