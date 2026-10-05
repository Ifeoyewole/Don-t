import { useState } from 'react'
import type { CreateProjectInput, Project } from '../types/domain'

type Props = {
  todayValue: string
  project?: Project | null
  onBack: () => void
  onSave: (input: CreateProjectInput) => Promise<void>
}

export const CreateProjectPage = ({ todayValue, project, onBack, onSave }: Props) => {
  const editing = Boolean(project)
  const [form, setForm] = useState<CreateProjectInput>({ name: project?.name ?? '', siteName: project?.siteName ?? '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      setError('Project name is required.')
      return
    }

    setSaving(true)
    setError('')
    try {
      await onSave(form)
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : 'Could not save project.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page-grid create-project-page">
      <button className="page-back-link" type="button" onClick={onBack}>
        ← Back to Projects
      </button>

      <header className="page-hero left-aligned">
        <div>
          <h1>{editing ? 'Edit Project' : 'Create New Project'}</h1>
          <p className="lead">
            {editing
              ? 'Update the project record, then return to the inspection summary.'
              : 'Create a project record before adding manholes and uploading joint inspection photos.'}
          </p>
        </div>
      </header>

      <section className="split-page-shell">
        <div className="split-main-column">
          <section className="stitch-form-card">
            <div className="stitch-section-head">
              <div>
                <h2>Project Details</h2>
                <p className="form-section-subtitle">Primary metadata used for reporting and tracking across all inspection runs.</p>
              </div>
              <span className="form-step-badge">Step 1 of 4</span>
            </div>

            <label className="field">
              <span>Project Name <strong className="required-star">*</strong></span>
              <input
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="e.g., Riverside Plot A"
                autoFocus
              />
            </label>

            <div className="stitch-two-up">
              <label className="field">
                <span>Site Name</span>
                <input
                  value={form.siteName}
                  onChange={(event) => setForm((current) => ({ ...current, siteName: event.target.value }))}
                  placeholder="e.g., Sector 4 - North Corridor"
                />
              </label>

              <label className="field">
                <span>Inspection Date</span>
                <input type="text" value={todayValue} readOnly className="input-readonly" />
              </label>
            </div>

            {error ? <p className="form-error">{error}</p> : null}

            <div className="form-action-divider" />

            <footer className="page-footer-actions">
              <button className="button button-ghost" type="button" onClick={onBack}>
                {editing ? 'Cancel Edit' : 'Discard Draft'}
              </button>
              <button className="button button-primary button-wide-on-desktop" type="button" onClick={handleSubmit} disabled={saving}>
                {saving ? 'Saving Project...' : editing ? 'Update Project' : 'Save Project'}
              </button>
            </footer>
          </section>
        </div>

        <aside className="split-side-column">
          <div className="setup-guide-card">
            <div className="setup-guide-head">
              <span className="setup-guide-tag">Workflow</span>
              <h3>Inspection Setup</h3>
              <p>Standardized pipeline for field capture and sub-pixel optical measurement.</p>
            </div>

            <ol className="setup-steps-list">
              <li className="setup-step is-current">
                <div className="step-num">1</div>
                <div className="step-body">
                  <strong>Project Setup</strong>
                  <span>Establish project identifier, site location, and inspection baseline.</span>
                </div>
              </li>
              <li className="setup-step">
                <div className="step-num">2</div>
                <div className="step-body">
                  <strong>Manhole & Pipe Spec</strong>
                  <span>Configure pipe diameter, material class, and section meter run.</span>
                </div>
              </li>
              <li className="setup-step">
                <div className="step-num">3</div>
                <div className="step-body">
                  <strong>Joint Photo Acquisition</strong>
                  <span>Capture macro joint openings with automated quality validation.</span>
                </div>
              </li>
              <li className="setup-step">
                <div className="step-num">4</div>
                <div className="step-body">
                  <strong>Sub-Pixel Optical QA</strong>
                  <span>Radial annular gap measurement and tolerance compliance verification.</span>
                </div>
              </li>
            </ol>

            <div className="setup-spec-box">
              <div className="spec-item">
                <span className="spec-label">Optical Accuracy</span>
                <strong>±0.2 mm / ray</strong>
              </div>
              <div className="spec-item">
                <span className="spec-label">Storage Mode</span>
                <strong>Local-First + Sync</strong>
              </div>
            </div>
          </div>
        </aside>
      </section>
    </div>
  )
}
