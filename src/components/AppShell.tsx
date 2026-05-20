import type { ReactNode } from 'react'

type NavKey = 'dashboard' | 'projects'

type Props = {
  children: ReactNode
  online: boolean
  navKey: NavKey
  onNavigateHome: () => void
  onNavigateProjects: () => void
}

export const AppShell = ({
  children,
  online,
  navKey,
  onNavigateHome,
  onNavigateProjects,
}: Props) => (
  <div className="app-shell">
    <header className="topbar">
      <button className="brand" type="button" onClick={onNavigateHome}>
        <span className="brand-mark" aria-hidden="true" />
        <span>JointInspect</span>
      </button>
      <div className={`sync-pill ${online ? 'is-online' : 'is-offline'}`}>
        <span className="sync-dot" aria-hidden="true" />
        <span>{online ? 'Online - Changes cached locally' : 'Offline - Changes cached locally'}</span>
      </div>
    </header>

    <div className={`offline-banner ${online ? 'is-hidden' : ''}`}>
      Connection lost. Inspection edits stay on this device until sync is restored.
    </div>

    <main className="app-content">{children}</main>

    <nav className="bottom-nav" aria-label="Primary">
      <button
        className={navKey === 'dashboard' ? 'nav-item is-active' : 'nav-item'}
        type="button"
        onClick={onNavigateHome}
      >
        <span className="nav-icon" aria-hidden="true" />
        Dashboard
      </button>
      <button
        className={navKey === 'projects' ? 'nav-item is-active' : 'nav-item'}
        type="button"
        onClick={onNavigateProjects}
      >
        <span className="nav-icon nav-icon-box" aria-hidden="true" />
        Projects
      </button>
    </nav>
  </div>
)
