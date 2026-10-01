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
      <section className="split-page-shell">
        <div className="split-main-column">
          <button className="page-back-link" type="button" onClick={onBack}>
            ← Back to Projects
          </button>

          <header className="page-hero left-aligned">
            <div>
              <h1>{editing ? 'Edit Project' : 'Create New Project'}</h1>
              <p className="lead">{editing ? 'Update the project record, then return to the inspection summary.' : 'Create a project record before adding manholes and uploading joint inspection photos.'}</p>
            </div>
          </header>

          <section className="stitch-form-card">
            <div className="stitch-section-head">
              <h2>Project Details</h2>
            </div>

            <label className="field">
              <span>Project Name</span>
              <input
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="e.g., Riverside Plot A"
              />
            </label>

            <div className="stitch-two-up">
              <label className="field">
                <span>Site Name</span>
                <input
                  value={form.siteName}
                  onChange={(event) => setForm((current) => ({ ...current, siteName: event.target.value }))}
                  placeholder="Optional"
                />
              </label>

              <label className="field">
                <span>Date</span>
                <input type="text" value={todayValue} readOnly />
              </label>
            </div>

            {error ? <p className="form-error">{error}</p> : null}
          </section>

          <footer className="page-footer-actions">
            <button className="button button-ghost" type="button" onClick={onBack}>
              {editing ? 'Cancel Edit' : 'Discard Draft'}
            </button>
            <button className="button button-primary button-wide-on-desktop" type="button" onClick={handleSubmit} disabled={saving}>
              {saving ? 'Saving Project...' : editing ? 'Update Project' : 'Save Project'}
            </button>
          </footer>
        </div>

        <aside className="split-side-column">
          <article className="info-visual-card">
            <div className="info-visual-image" />
            <div className="info-visual-copy">
              <strong>Project First</strong>
              <p>Create the project first, then add manholes and start capturing joint photos.</p>
            </div>
          </article>

          <article className="info-note-card is-blue">
            <strong>Required Field</strong>
            <p>Project Name is required before you can continue to manhole setup.</p>
          </article>

          <article className="info-note-card is-gold">
            <strong>Optional Field</strong>
            <p>Site Name is optional and can be left blank.</p>
          </article>

          <article className="info-tip-card">
            <strong>Auto Date</strong>
            <p>The date is generated automatically for the project record.</p>
          </article>
        </aside>
      </section>
    </div>
  )
}
