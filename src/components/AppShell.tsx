import { useState, type ReactNode } from 'react'
import type { RealtimeHealthState } from '../hooks/useRealtimeHealth'

export type NavKey =
  | 'dashboard'
  | 'projects'
  | 'inspections'
  | 'calibration'
  | 'models'
  | 'reports'
  | 'settings'

interface InspectorProfile {
  name: string
  role: string
}

const DEFAULT_PROFILE: InspectorProfile = {
  name: 'Guest',
  role: 'Field Inspector',
}

const PROFILE_STORAGE_KEY = 'jointinspect:inspector-session'

type Props = {
  children: ReactNode
  online: boolean
  health?: RealtimeHealthState
  onRefreshHealth?: () => void
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
  health,
  onRefreshHealth,
  navKey,
  onNavigateHome,
  onNavigateProjects,
  onNavigateInspections,
  onNavigateReports,
  globalSearchQuery = '',
  onGlobalSearchChange,
}: Props) => {
  const [activeModal, setActiveModal] = useState<'calibration' | 'models' | 'settings' | null>(null)

  // Dynamic Inspector Profile Session
  const [profile, setProfile] = useState<InspectorProfile>(() => {
    try {
      const stored = window.localStorage.getItem(PROFILE_STORAGE_KEY)
      if (stored) {
        const parsed = JSON.parse(stored)
        if (parsed?.name) return parsed
      }
    } catch {}
    return DEFAULT_PROFILE
  })
  const [profileModalOpen, setProfileModalOpen] = useState(false)
  const [editName, setEditName] = useState(profile.name)
  const [editRole, setEditRole] = useState(profile.role)

  const handleSaveProfile = () => {
    const next = {
      name: editName.trim() || 'Guest',
      role: editRole.trim() || 'Field Inspector',
    }
    setProfile(next)
    window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(next))
    setProfileModalOpen(false)
  }

  const handleResetProfile = () => {
    setProfile(DEFAULT_PROFILE)
    setEditName(DEFAULT_PROFILE.name)
    setEditRole(DEFAULT_PROFILE.role)
    window.localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(DEFAULT_PROFILE))
    setProfileModalOpen(false)
  }

  // Real-time status derivations
  const isCloudOnline = health ? health.cloudConnected : online
  const isModelReady = health ? health.modelReady : true

  const cloudPillClass = isCloudOnline
    ? 'is-cloud-online'
    : health?.online
      ? 'is-cloud-local'
      : 'is-cloud-offline'

  const cloudLabel = isCloudOnline
    ? health?.latencyMs
      ? `Cloud Connected (${health.latencyMs}ms)`
      : 'Cloud Connected'
    : health?.online
      ? 'Local Engine'
      : 'Offline'

  const cloudTooltip = isCloudOnline
    ? `Real-time cloud sync active (${health?.latencyMs ?? 0}ms round-trip). Click to ping.`
    : health?.online
      ? 'Connected to local device engine. Click to ping cloud service.'
      : 'Network offline. Inspections stored locally in IndexedDB.'

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
          {/* Cloud Connection Badge (Click to ping) */}
          <button
            type="button"
            className={`status-pill ${cloudPillClass} status-pill-clickable`}
            onClick={() => onRefreshHealth?.()}
            title={cloudTooltip}
          >
            <span className={`status-dot-pulse ${health?.isChecking ? 'is-checking' : ''}`} aria-hidden="true" />
            <span className="status-pill-text">{cloudLabel}</span>
          </button>

          {/* AI Model Status Badge (Click to view model specs) */}
          <button
            type="button"
            className={`status-pill ${isModelReady ? 'is-model-ready' : 'is-model-loading'} status-pill-clickable`}
            onClick={() => setActiveModal('models')}
            title="AI/CV Optical Analysis Pipeline. Click for model telemetry."
          >
            <span className="status-dot-ready" aria-hidden="true">
              <CheckIcon />
            </span>
            <span className="status-pill-text">{isModelReady ? 'Model Ready' : 'Loading Engine'}</span>
          </button>

          {/* Dynamic Inspector Session Profile */}
          <button
            type="button"
            className="user-profile user-profile-btn"
            onClick={() => {
              setEditName(profile.name)
              setEditRole(profile.role)
              setProfileModalOpen(true)
            }}
            title="Active Inspector Session • Click to customize identity"
          >
            <div className="user-avatar" aria-hidden="true">
              {profile.name.charAt(0).toUpperCase() || 'G'}
            </div>
            <div className="user-details">
              <span className="user-name">{profile.name}</span>
              <span className="user-role">{profile.role}</span>
            </div>
          </button>
        </div>
      </header>

      {/* Offline Alert Strip */}
      <div className={`offline-banner ${isCloudOnline || (health?.online ?? online) ? 'is-hidden' : ''}`}>
        <CloudIcon />
        <span>Connection lost. Field measurements are cached locally on IndexedDB and will sync once reconnected.</span>
      </div>

      {/* Body: Slim Desktop Sidebar + Main Content */}
      <div className="app-layout">
        <aside className="desktop-sidebar" aria-label="Main Navigation">
          <div className="sidebar-top-section">
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
          </div>

          <div className="sidebar-footer">
            <div className="sidebar-system-badge">
              <div className="badge-row">
                <span className={`live-dot ${isCloudOnline ? 'is-live' : ''}`} />
                <strong>Inspection Engine v1.0</strong>
              </div>
              <span className="badge-sub">{isCloudOnline ? `Live Cloud (${health?.latencyMs ?? 0}ms)` : 'Local Engine'} • Sub-pixel QA</span>
            </div>
          </div>
        </aside>

        <main className="content-surface">{children}</main>
      </div>

      {/* Inspector Profile Customization Modal */}
      {profileModalOpen && (
        <div className="modal-backdrop" onClick={() => setProfileModalOpen(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <h3>Inspector Session Identity</h3>
              </div>
              <button className="modal-close-btn" type="button" onClick={() => setProfileModalOpen(false)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p className="modal-lead">Configure the inspector identity attached to quality assessments and reports.</p>
              <div className="stitch-two-up" style={{ marginTop: '16px' }}>
                <label className="field">
                  <span>Inspector Name</span>
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    placeholder="Guest"
                  />
                </label>
                <label className="field">
                  <span>Role / Title</span>
                  <input
                    type="text"
                    value={editRole}
                    onChange={(e) => setEditRole(e.target.value)}
                    placeholder="Field Inspector"
                  />
                </label>
              </div>
            </div>
            <div className="modal-footer" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <button className="button button-ghost" type="button" onClick={handleResetProfile}>
                Reset to Guest
              </button>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="button button-secondary" type="button" onClick={() => setProfileModalOpen(false)}>
                  Cancel
                </button>
                <button className="button button-primary" type="button" onClick={handleSaveProfile}>
                  Save Profile
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modals for Engine, Calibration, Models, Settings */}
      {activeModal === 'calibration' && (
        <div className="modal-backdrop" onClick={() => setActiveModal(null)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div className="modal-title-group">
                <CalibrationIcon />
                <h3>Sub-Pixel Geometric Calibration</h3>
              </div>
              <button className="modal-close-btn" type="button" onClick={() => setActiveModal(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p className="modal-lead">
                Sub-pixel radial boundary tracking using annular edge estimation and adaptive contour sampling.
              </p>
              <div className="spec-grid">
                <div className="spec-card">
                  <span className="spec-label">Radial Edge Rays</span>
                  <strong>36 sectors</strong>
                  <span className="spec-note">10° angular step validation</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Sub-Pixel Method</span>
                  <strong>Zernike Moments</strong>
                  <span className="spec-note">Gaussian gradient peak interpolation</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Nominal Joint Gap</span>
                  <strong>12.0 mm</strong>
                  <span className="spec-note">Design tolerance: ±4.0 mm</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Pixel Scale Target</span>
                  <strong>1.000 mm/px</strong>
                  <span className="spec-note">Nominal uncalibrated sensor scale</span>
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
                <h3>AI Inspection Engine & Models</h3>
              </div>
              <button className="modal-close-btn" type="button" onClick={() => setActiveModal(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <p className="modal-lead">
                Sub-pixel optical joint analysis and defect classification pipeline.
              </p>
              <div className="spec-grid">
                <div className="spec-card">
                  <span className="spec-label">Joint Profile Engine</span>
                  <strong>Sub-Pixel Profiler v1.0</strong>
                  <span className="spec-note">Radial contour & annular gap solver</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Defect Classifier</span>
                  <strong>Sewer-ML Deep Classifier</strong>
                  <span className="spec-note">Displaced joint, cracks & intrusion detection</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Measurement Precision</span>
                  <strong>Nominal ±0.2 mm</strong>
                  <span className="spec-note">36-ray angular sub-pixel sampling</span>
                </div>
                <div className="spec-card">
                  <span className="spec-label">Processing Pipeline</span>
                  <strong>{isCloudOnline ? 'Cloud Active' : 'Local Engine'}</strong>
                  <span className="spec-note">{isCloudOnline ? `Live latency: ${health?.latencyMs ?? 0}ms` : 'Offline fallback active'}</span>
                </div>
              </div>
              <div className="modal-callout">
                <strong>Standard Inspection Defect Codes</strong>
                <p>FS (Displaced joint), RO (Roots), AF/BE (Deposits), FO (Obstacle), RB (Fracture/Crack), IS (Intruding seal).</p>
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
