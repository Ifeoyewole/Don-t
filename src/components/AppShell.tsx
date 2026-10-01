import { useState, type ReactNode } from 'react'

export type NavKey =
  | 'dashboard'
  | 'projects'
  | 'inspections'
  | 'calibration'
  | 'models'
  | 'reports'
  | 'settings'

type Props = {
  children: ReactNode
  online: boolean
  navKey: NavKey
  onNavigateHome: () => void
  onNavigateProjects: () => void
  onNavigateInspections?: () => void
  onNavigateReports?: () => void
  globalSearchQuery?: string
  onGlobalSearchChange?: (query: string) => void
}

const CloudIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" width="16" height="16" aria-hidden="true">
    <path
      d="M8 18H17.2C19.85 18 22 15.93 22 13.38C22 11.01 20.12 9.06 17.72 8.78C17.1 5.75 14.39 3.5 11.14 3.5C7.41 3.5 4.39 6.49 4.39 10.18C4.39 10.35 4.4 10.53 4.41 10.7C2.42 11.24 1 13.03 1 15.12C1 17.66 3.15 19.73 5.8 19.73H8"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const CheckIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" width="14" height="14" aria-hidden="true">
    <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

const DashboardIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" width="18" height="18" aria-hidden="true">
    <rect x="3" y="3" width="7" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
    <rect x="14" y="3" width="7" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
    <rect x="14" y="12" width="7" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
    <rect x="3" y="16" width="7" height="5" rx="1.5" stroke="currentColor" strokeWidth="1.8" />
  </svg>
)

const ProjectsIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" width="18" height="18" aria-hidden="true">
    <path
      d="M3 7.5A2.5 2.5 0 015.5 5h3.6c.7 0 1.35.3 1.8.85l1.2 1.5c.45.55 1.1.85 1.8.85H18.5A2.5 2.5 0 0121 10.7v7.8a2.5 2.5 0 01-2.5 2.5h-13A2.5 2.5 0 013 18.5v-11z"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinejoin="round"
    />
  </svg>
)

const InspectionsIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" width="18" height="18" aria-hidden="true">
    <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.8" />
    <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
)

const CalibrationIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" width="18" height="18" aria-hidden="true">
    <path
      d="M4 20l4.5-4.5m0 0l2 2m-2-2l7-7a2.12 2.12 0 013 3l-7 7m-2-2l2 2M15 5l4 4"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
)

const ModelsIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" width="18" height="18" aria-hidden="true">
    <rect x="5" y="5" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.8" />
    <path d="M9 9h6v6H9z" stroke="currentColor" strokeWidth="1.8" />
    <path d="M9 1v4M15 1v4M9 19v4M15 19v4M1 9h4M1 15h4M19 9h4M19 15h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
)

const ReportsIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" width="18" height="18" aria-hidden="true">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
  </svg>
)

const SettingsIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" width="18" height="18" aria-hidden="true">
    <path
      d="M12 15a3 3 0 100-6 3 3 0 000 6z"
      stroke="currentColor"
      strokeWidth="1.8"
    />
    <path
      d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"
      stroke="currentColor"
      strokeWidth="1.8"
    />
  </svg>
)

const SearchIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" width="16" height="16" aria-hidden="true">
    <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
    <path d="M20 20l-4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
  </svg>
)

export const AppShell = ({
  children,
  online,
  navKey,
  onNavigateHome,
  onNavigateProjects,
  onNavigateInspections,
  onNavigateReports,
  globalSearchQuery = '',
  onGlobalSearchChange,
}: Props) => {
  const [activeModal, setActiveModal] = useState<'calibration' | 'models' | 'settings' | null>(null)

  const handleSidebarClick = (key: NavKey) => {
    if (key === 'dashboard') {
      onNavigateHome()
      return
    }
    if (key === 'projects') {
      onNavigateProjects()
      return
    }
    if (key === 'inspections') {
      if (onNavigateInspections) {
        onNavigateInspections()
      } else {
        onNavigateProjects()
      }
      return
    }
    if (key === 'reports') {
      if (onNavigateReports) {
        onNavigateReports()
      } else {
        onNavigateProjects()
      }
      return
    }
    if (key === 'calibration' || key === 'models' || key === 'settings') {
      setActiveModal(key)
    }
  }

  return (
    <div className="app-shell">
      {/* Upgraded Industrial Header */}
      <header className="topbar">
        <div className="topbar-left">
          <button className="brand" type="button" onClick={onNavigateHome}>
            <img className="brand-logo" src="/logo-jointinspect.svg" alt="JointInspect" />
            <span className="brand-tag">AI/CV</span>
          </button>
        </div>

        <div className="topbar-center">
          <div className="topbar-search-box">
            <span className="topbar-search-icon">
              <SearchIcon />
            </span>
            <input
              type="search"
              className="topbar-search-input"
              placeholder="Search projects, joints, manholes... (Ctrl+K)"
              value={globalSearchQuery}
              onChange={(e) => onGlobalSearchChange?.(e.target.value)}
            />
          </div>
        </div>

        <div className="topbar-actions">
          {/* Cloud Connection Badge */}
          <div className={`status-pill ${online ? 'is-cloud-online' : 'is-cloud-offline'}`} title="Google Cloud Run (europe-west2)">
            <span className="status-dot-pulse" aria-hidden="true" />
            <span className="status-pill-text">
              {online ? 'Cloud Connected' : 'Offline Mode'}
            </span>
          </div>

          {/* AI Model Status Badge */}
          <div className="status-pill is-model-ready" title="YOLOv8-seg + Sewer-ML Defect Model Ready">
            <span className="status-dot-ready" aria-hidden="true">
              <CheckIcon />
            </span>
            <span className="status-pill-text">Model Ready</span>
          </div>

          {/* User Profile */}
          <div className="user-profile" title="Active Inspector Session">
            <div className="user-avatar" aria-hidden="true">
              JD
            </div>
            <div className="user-details">
              <span className="user-name">J. Doe</span>
              <span className="user-role">Lead Inspector</span>
            </div>
          </div>
        </div>
      </header>

      {/* Offline Alert Strip */}
      <div className={`offline-banner ${online ? 'is-hidden' : ''}`}>
        <CloudIcon />
        <span>Connection lost. Field measurements are cached locally on IndexedDB and will sync once reconnected.</span>
      </div>

      {/* Body: Slim Desktop Sidebar + Main Content */}
      <div className="app-layout">
        <aside className="desktop-sidebar" aria-label="Main Navigation">
          <div className="sidebar-section-title">Operations</div>
          <nav className="sidebar-nav">
            <button
              className={navKey === 'dashboard' ? 'sidebar-item is-active' : 'sidebar-item'}
              type="button"
              onClick={() => handleSidebarClick('dashboard')}
            >
              <DashboardIcon />
              <span>Dashboard</span>
            </button>
            <button
              className={navKey === 'projects' ? 'sidebar-item is-active' : 'sidebar-item'}
              type="button"
              onClick={() => handleSidebarClick('projects')}
            >
              <ProjectsIcon />
              <span>Projects</span>
            </button>
            <button
              className={navKey === 'inspections' ? 'sidebar-item is-active' : 'sidebar-item'}
              type="button"
              onClick={() => handleSidebarClick('inspections')}
            >
              <InspectionsIcon />
              <span>Inspections</span>
            </button>
          </nav>

          <div className="sidebar-section-title">Engine & Specs</div>
          <nav className="sidebar-nav">
            <button
              className={navKey === 'calibration' ? 'sidebar-item is-active' : 'sidebar-item'}
              type="button"
              onClick={() => handleSidebarClick('calibration')}
            >
              <CalibrationIcon />
              <span>Calibration</span>
            </button>
            <button
              className={navKey === 'models' ? 'sidebar-item is-active' : 'sidebar-item'}
              type="button"
              onClick={() => handleSidebarClick('models')}
            >
              <ModelsIcon />
              <span>Models</span>
            </button>
            <button
              className={navKey === 'reports' ? 'sidebar-item is-active' : 'sidebar-item'}
              type="button"
              onClick={() => handleSidebarClick('reports')}
            >
              <ReportsIcon />
              <span>Reports</span>
            </button>
            <button
              className={navKey === 'settings' ? 'sidebar-item is-active' : 'sidebar-item'}
              type="button"
              onClick={() => handleSidebarClick('settings')}
            >
              <SettingsIcon />
              <span>Settings</span>
            </button>
          </nav>

          <div className="sidebar-footer">
            <div className="sidebar-system-badge">
              <div className="badge-row">
                <span className="live-dot" />
                <strong>CV Engine v1.0</strong>
              </div>
              <span className="badge-sub">europe-west2 • ADC/IAM</span>
            </div>
          </div>
        </aside>

        {/* Primary Page Content */}
        <main className="app-content">{children}</main>
      </div>

      {/* Mobile Bottom Navigation */}
      <nav className="bottom-nav" aria-label="Primary mobile">
        <button
          className={navKey === 'dashboard' ? 'nav-item is-active' : 'nav-item'}
          type="button"
          onClick={onNavigateHome}
        >
          <DashboardIcon />
          <span>Dashboard</span>
        </button>
        <button
          className={navKey === 'projects' ? 'nav-item is-active' : 'nav-item'}
          type="button"
          onClick={onNavigateProjects}
        >
          <ProjectsIcon />
          <span>Projects</span>
        </button>
        <button
          className={navKey === 'inspections' ? 'nav-item is-active' : 'nav-item'}
          type="button"
          onClick={() => handleSidebarClick('inspections')}
        >
          <InspectionsIcon />
          <span>Inspect</span>
        </button>
        <button
          className={navKey === 'settings' ? 'nav-item is-active' : 'nav-item'}
          type="button"
          onClick={() => setActiveModal('settings')}
        >
          <SettingsIcon />
          <span>Settings</span>
        </button>
      </nav>

      {/* Interactive Engine Modals (Calibration, Models, Settings) */}
      {activeModal === 'calibration' && (
        <div className="modal-backdrop" onClick={() => setActiveModal(null)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <CalibrationIcon />
                <h3>Optical Calibration Engine</h3>
              </div>
              <button className="modal-close-btn" type="button" onClick={() => setActiveModal(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p className="modal-lead">
                Sub-pixel geometric scaling and radial distortion correction for CCTV pipe cameras.
              </p>
              <div className="spec-grid">
                <div className="spec-card">
                  <span className="spec-label">Nominal Scale</span>
                  <strong>1.000 mm/px</strong>
                  <span className="spec-note">Empirically calibrated from pipe ring</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Supported Diameters</span>
                  <strong>150mm – 900mm</strong>
                  <span className="spec-note">Clay & Concrete circular geometries</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Pass Tolerance</span>
                  <strong>3.0 – 15.0 mm</strong>
                  <span className="spec-note">ACCEPTED_MEASUREMENT</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Review Tolerance</span>
                  <strong>15.0 – 25.0 mm</strong>
                  <span className="spec-note">REVIEW_REQUIRED</span>
                </div>
              </div>
              <div className="modal-callout">
                <strong>Sub-Pixel Radial Edge Tracing: ACTIVE</strong>
                <p>Calculates orthogonal gap distances across visible angular sectors while excluding shadows and debris.</p>
              </div>
            </div>
            <div className="modal-footer">
              <button className="button button-primary" type="button" onClick={() => setActiveModal(null)}>
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {activeModal === 'models' && (
        <div className="modal-backdrop" onClick={() => setActiveModal(null)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <ModelsIcon />
                <h3>AI Inspection Models & Telemetry</h3>
              </div>
              <button className="modal-close-btn" type="button" onClick={() => setActiveModal(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p className="modal-lead">
                Hybrid AI segmentation and OpenCV computer vision pipeline deployed on Google Cloud.
              </p>
              <div className="spec-grid">
                <div className="spec-card">
                  <span className="spec-label">Joint Segmenter</span>
                  <strong>joint-seg-v1</strong>
                  <span className="spec-note">YOLOv8-seg • Sewer-ML Benchmark</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">CV Engine</span>
                  <strong>OpenCV 4.12</strong>
                  <span className="spec-note">Radial edge fitting & validation</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Container Image</span>
                  <strong>pipe-joint-api:v1</strong>
                  <span className="spec-note">Artifact Registry (europe-west2)</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Training Pipeline</span>
                  <strong>Vertex AI Custom Job</strong>
                  <span className="spec-note">joint-inspection-trainer (ADC/IAM)</span>
                </div>
              </div>
              <div className="modal-callout">
                <strong>Sewer-ML Multi-Defect Classifier</strong>
                <p>Standard codes: FS (Displaced joint), RO (Roots), AF/BE (Deposits), FO (Obstacle), RB (Fracture/Crack), IS (Intruding seal).</p>
              </div>
            </div>
            <div className="modal-footer">
              <button className="button button-primary" type="button" onClick={() => setActiveModal(null)}>
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {activeModal === 'settings' && (
        <div className="modal-backdrop" onClick={() => setActiveModal(null)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <SettingsIcon />
                <h3>Inspection Quality & Cache Settings</h3>
              </div>
              <button className="modal-close-btn" type="button" onClick={() => setActiveModal(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <div className="spec-grid">
                <div className="spec-card">
                  <span className="spec-label">Min Blur Threshold</span>
                  <strong>100.0</strong>
                  <span className="spec-note">Laplacian variance threshold</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Brightness Bounds</span>
                  <strong>45 – 215</strong>
                  <span className="spec-note">Standardized 8-bit dynamic range</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Max Glare Percentage</span>
                  <strong>4.0%</strong>
                  <span className="spec-note">Specular reflection rejection</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Local Storage</span>
                  <strong>IndexedDB (Dexie)</strong>
                  <span className="spec-note">Offline persistent storage active</span>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="button button-primary" type="button" onClick={() => setActiveModal(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
