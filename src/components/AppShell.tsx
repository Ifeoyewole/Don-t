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
        <img className="brand-logo" src="/logo-jointinspect.svg" alt="JointInspect" />
      </button>
      <div className={`sync-pill ${online ? 'is-online' : 'is-offline'}`}>
        <span className="sync-cloud" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path
              d="M7 18.5H17.2C19.85 18.5 22 16.43 22 13.88C22 11.51 20.12 9.56 17.72 9.28C17.1 6.25 14.39 4 11.14 4C7.41 4 4.39 6.99 4.39 10.68C4.39 10.85 4.4 11.03 4.41 11.2C2.42 11.74 1 13.53 1 15.62C1 18.16 3.15 20.23 5.8 20.23H7"
              stroke="currentColor"
              strokeWidth="1.9"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M12 10.5V14.2"
              stroke="currentColor"
              strokeWidth="1.9"
              strokeLinecap="round"
            />
            <path
              d="M10.3 12.8L12 14.5L13.7 12.8"
              stroke="currentColor"
              strokeWidth="1.9"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </span>
        <span>{online ? 'Online' : 'Offline'}</span>
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
