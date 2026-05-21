import type { ReactNode } from 'react'

type NavKey = 'dashboard' | 'projects'

type Props = {
  children: ReactNode
  online: boolean
  navKey: NavKey
  onNavigateHome: () => void
  onNavigateProjects: () => void
}

const CloudIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <path
      d="M8 18H17.2C19.85 18 22 15.93 22 13.38C22 11.01 20.12 9.06 17.72 8.78C17.1 5.75 14.39 3.5 11.14 3.5C7.41 3.5 4.39 6.49 4.39 10.18C4.39 10.35 4.4 10.53 4.41 10.7C2.42 11.24 1 13.03 1 15.12C1 17.66 3.15 19.73 5.8 19.73H8"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path d="M12 10V13.6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    <path d="M10.3 12.4L12 14.1L13.7 12.4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

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
        <img className="brand-logo" src="/logo-jointinspect.svg" alt="JointInspect" />
      </button>

      <nav className="desktop-nav" aria-label="Primary">
        <button className={navKey === 'dashboard' ? 'desktop-nav-item is-active' : 'desktop-nav-item'} type="button" onClick={onNavigateHome}>
          Dashboard
        </button>
        <button className={navKey === 'projects' ? 'desktop-nav-item is-active' : 'desktop-nav-item'} type="button" onClick={onNavigateProjects}>
          Projects
        </button>
      </nav>

      <div className="topbar-actions">
        <div className={`sync-pill ${online ? 'is-online' : 'is-offline'}`}>
          <span className="sync-dot" aria-hidden="true" />
          <span>{online ? 'Online - Synced' : 'Offline'}</span>
        </div>

        <button className="topbar-icon-button" type="button" aria-label="Sync status">
          <span className="sync-cloud">
            <CloudIcon />
          </span>
        </button>

        <div className="user-avatar" aria-hidden="true">
          JD
        </div>
      </div>
    </header>

    <div className={`offline-banner ${online ? 'is-hidden' : ''}`}>
      Connection lost. Inspection edits stay on this device until sync is restored.
    </div>

    <main className="app-content">{children}</main>

    <nav className="bottom-nav" aria-label="Primary mobile">
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
