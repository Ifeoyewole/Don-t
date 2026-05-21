import { useMemo, useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import type { ProjectSummary } from '../types/domain'

type Props = {
  projects: ProjectSummary[]
  showAllProjects: boolean
  onToggleProjects: () => void
  onNewProject: () => void
  onOpenProject: (projectId: string) => void
}

const formatRelativeTime = (iso: string) =>
  new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(
    new Date(iso),
  )

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

export const DashboardPage = ({
  projects,
  showAllProjects,
  onToggleProjects,
  onNewProject,
  onOpenProject,
}: Props) => {
  const [search, setSearch] = useState('')

  const filteredProjects = useMemo(() => {
    const query = search.trim().toLowerCase()
    if (!query) return projects
    return projects.filter((project) =>
      [project.name, project.siteName, project.id].some((value) => value?.toLowerCase().includes(query)),
    )
  }, [projects, search])

  const visibleProjects = showAllProjects ? filteredProjects : filteredProjects.slice(0, 3)
  const totalFailures = projects.reduce((sum, project) => sum + project.failCount + project.reviewCount, 0)
  const totalInspections = projects.reduce((sum, project) => sum + (project.completedInspections ?? 0), 0)
  const completionRate = projects.length
    ? Math.round(
        (projects.reduce((sum, project) => sum + (project.completedInspections ?? 0), 0) /
          Math.max(projects.reduce((sum, project) => sum + (project.totalJoints ?? 0), 0), 1)) *
          100,
      )
    : 0

  const recentActivity = [...projects]
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
    .slice(0, 3)

  return (
    <div className="page-grid dashboard-page">
      <section className="page-hero">
        <div>
          <h1>Projects</h1>
          <p className="lead">Create a project, add a manhole, upload joint photos, and review measured gaps.</p>
        </div>
        <button className="button button-primary dashboard-cta" type="button" onClick={onNewProject}>
          + New Project
        </button>
      </section>

      <section className="stats-grid dashboard-stats">
        <article className="dashboard-stat-card">
          <div className="dashboard-stat-icon">A</div>
          <div>
            <span className="stat-label">Projects</span>
            <strong>{projects.length}</strong>
            <p className="success-copy">Current records</p>
          </div>
        </article>

        <article className="dashboard-stat-card">
          <div className="dashboard-stat-icon">I</div>
          <div>
            <span className="stat-label">Inspected Joints</span>
            <strong>{totalInspections}</strong>
            <p>{completionRate}% completion</p>
          </div>
        </article>

        <article className="dashboard-stat-card is-alert">
          <div className="dashboard-stat-icon is-alert">!</div>
          <div>
            <span className="stat-label">Review / Fail</span>
            <strong>{totalFailures.toString().padStart(2, '0')}</strong>
            <p className="danger-copy">Flagged results</p>
          </div>
        </article>
      </section>

      <section className="dashboard-table-card">
        <div className="dashboard-table-header">
          <div>
            <h2>Recent Projects</h2>
            <p>{filteredProjects.length} project{filteredProjects.length === 1 ? '' : 's'} stored on this device.</p>
          </div>
          <div className="dashboard-controls">
            <label className="dashboard-search">
              <span aria-hidden="true">⌕</span>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search projects..."
              />
            </label>
            <button className="button button-secondary" type="button" onClick={onToggleProjects}>
              {showAllProjects ? 'Show Less' : 'Show All'}
            </button>
          </div>
        </div>

        <div className="dashboard-table">
          <div className="dashboard-table-head">
            <span>Project Name</span>
            <span>Location</span>
            <span>Status</span>
            <span>Joint Count</span>
            <span>Last Inspected</span>
            <span>Actions</span>
          </div>

          {visibleProjects.map((project) => (
            <button
              key={project.id}
              className="dashboard-table-row"
              type="button"
              onClick={() => onOpenProject(project.id)}
            >
              <div className="dashboard-project-cell">
                <div className="dashboard-project-thumb" aria-hidden="true">
                  {project.name.slice(0, 1)}
                </div>
                <div className="dashboard-project-copy">
                  <strong>{project.name}</strong>
                  <span>{project.id}</span>
                </div>
              </div>
              <span>{project.siteName || 'Site pending'}</span>
              <div className="dashboard-status-cell">
                <StatusBadge status={project.status ?? 'IN PROGRESS'} />
                <small>{statusCopy(project.status)}</small>
              </div>
              <div className="dashboard-count-cell">
                <strong>{project.totalJoints ?? 0}</strong>
                <span>{project.completedInspections ?? 0} inspected</span>
              </div>
              <span>{formatRelativeTime(project.updatedAt)}</span>
              <span className="dashboard-arrow" aria-hidden="true">
                ›
              </span>
            </button>
          ))}
        </div>

        <div className="dashboard-table-footer">
          <span>
            Showing {visibleProjects.length} of {filteredProjects.length} projects
          </span>
          <div className="dashboard-pagination">
            <button className="button button-secondary" type="button" onClick={onToggleProjects}>
              {showAllProjects ? 'Previous' : 'Next'}
            </button>
          </div>
        </div>
      </section>

      <section className="dashboard-lower-grid">
        <article className="dashboard-trends-card">
          <div className="dashboard-panel-head">
            <h2>Inspection Progress</h2>
          </div>
          <div className="trend-bars">
            {projects.slice(0, 4).map((project) => {
              const total = Math.max(project.totalJoints ?? 0, 1)
              const percent = Math.round(((project.completedInspections ?? 0) / total) * 100)
              return (
                <div className="trend-row" key={project.id}>
                  <div>
                    <strong>{project.name}</strong>
                    <span>{project.siteName || 'Site pending'}</span>
                  </div>
                  <div className="trend-meter">
                    <div style={{ width: `${percent}%` }} />
                  </div>
                  <strong>{percent}%</strong>
                </div>
              )
            })}
          </div>
        </article>

        <article className="dashboard-activity-card">
          <h2>Recent Updates</h2>
          <div className="activity-list">
            {recentActivity.map((project) => (
              <div className="activity-row" key={project.id}>
                <div className={activityTone(project.status)} />
                <div>
                  <strong>{project.name}</strong>
                  <p>{statusCopy(project.status)}</p>
                  <span>{formatRelativeTime(project.updatedAt)}</span>
                </div>
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  )
}
