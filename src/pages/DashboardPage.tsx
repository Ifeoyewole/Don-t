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
  new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(
    new Date(iso),
  )

export const DashboardPage = ({
  projects,
  showAllProjects,
  onToggleProjects,
  onNewProject,
  onOpenProject,
}: Props) => {
  const visibleProjects = showAllProjects ? projects : projects.slice(0, 3)
  const totalFailures = projects.reduce((sum, project) => sum + project.failCount + project.reviewCount, 0)
  const totalInspections = projects.reduce((sum, project) => sum + project.completedInspections, 0)

  return (
    <div className="page-grid">
      <section className="hero-row">
        <div>
          <p className="eyebrow">Field overview</p>
          <h1>Pipe joint inspection command view</h1>
          <p className="lead">
            Use the stitch flow as a field-ready workspace for project intake, manhole setup, evidence capture,
            inspection review, and evidence export.
          </p>
        </div>
        <button className="button button-primary" type="button" onClick={onNewProject}>
          New Project
        </button>
      </section>

      <section className="stats-grid">
        <article className="stat-card">
          <span className="stat-label">Active projects</span>
          <strong>{projects.length}</strong>
          <p>UI-only project cards for the dashboard route.</p>
        </article>
        <article className="stat-card">
          <span className="stat-label">Inspections completed</span>
          <strong>{totalInspections}</strong>
          <p>Finished evidence items across seeded and new manholes.</p>
        </article>
        <article className="stat-card stat-card-alert">
          <span className="stat-label">Review required</span>
          <strong>{totalFailures}</strong>
          <p>Combined `REVIEW` and `FAIL` statuses needing attention.</p>
        </article>
      </section>

      <section className="feature-panel">
        <div className="map-card">
          <div className="map-grid" />
          <div className="map-overlay">
            <span className="map-kicker">Current field focus</span>
            <strong>Drainage runs, manholes, and flagged joint sequences</strong>
          </div>
        </div>
        <div className="side-note-card">
          <h2>Frontend plan coverage</h2>
          <ul className="feature-list">
            <li>Dashboard and project intake use real navigation handlers.</li>
            <li>Offline banner, touch target sizing, and contrast rules are preserved.</li>
            <li>All visible CTA buttons are wired to local UI actions.</li>
          </ul>
        </div>
      </section>

      <section className="section-header">
        <div>
          <h2>Recent Projects</h2>
          <p>Frontend-only project summaries and status chips.</p>
        </div>
        <button className="button button-ghost" type="button" onClick={onToggleProjects}>
          {showAllProjects ? 'Show Recent' : 'View All Projects'}
        </button>
      </section>

      <section className="project-list">
        {visibleProjects.map((project) => (
          <button key={project.id} className="project-row" type="button" onClick={() => onOpenProject(project.id)}>
            <div className="project-icon" aria-hidden="true" />
            <div className="project-copy">
              <strong>{project.name}</strong>
              <span>{project.siteName || 'Site name pending'}</span>
              <span>Updated {formatRelativeTime(project.updatedAt)}</span>
            </div>
            <div className="project-meta">
              <StatusBadge status={project.status} />
              <span>{project.completedInspections}/{Math.max(project.totalJoints, 1)} measured</span>
            </div>
          </button>
        ))}
      </section>
    </div>
  )
}
