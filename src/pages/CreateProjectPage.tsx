import { useState } from 'react'
import type { CreateProjectInput } from '../types/domain'

type Props = {
  todayValue: string
  onBack: () => void
  onSave: (input: CreateProjectInput) => Promise<void>
}

export const CreateProjectPage = ({ todayValue, onBack, onSave }: Props) => {
  const [form, setForm] = useState<CreateProjectInput>({ name: '', siteName: '' })
  const [startDate, setStartDate] = useState(todayValue)
  const [focusAreas, setFocusAreas] = useState(['Joint Integrity'])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const toggleFocus = (label: string) => {
    setFocusAreas((current) =>
      current.includes(label) ? current.filter((item) => item !== label) : [...current, label],
    )
  }

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
      <div className="projects-sync-banner">Online - synced workspace ready for field capture</div>

      <section className="split-page-shell">
        <div className="split-main-column">
          <button className="page-back-link" type="button" onClick={onBack}>
            ← Back to Projects
          </button>

          <header className="page-hero left-aligned">
            <div>
              <h1>Create New Project</h1>
              <p className="lead">Initialize a new structural inspection framework for site-wide monitoring.</p>
            </div>
          </header>

          <section className="stitch-form-card">
            <div className="stitch-section-head">
              <h2>General Information</h2>
            </div>

            <label className="field">
              <span>Project Name</span>
              <input
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="e.g., Terminal 4 Expansion"
              />
            </label>

            <div className="stitch-two-up">
              <label className="field">
                <span>Site Name / ID</span>
                <input
                  value={form.siteName}
                  onChange={(event) => setForm((current) => ({ ...current, siteName: event.target.value }))}
                  placeholder="Zone B-12"
                />
              </label>

              <label className="field">
                <span>Inspection Start Date</span>
                <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
              </label>
            </div>
          </section>

          <section className="stitch-form-card">
            <div className="stitch-section-head">
              <h2>Inspection Parameters</h2>
            </div>

            <div className="focus-grid">
              {['Joint Integrity', 'Material Grade', 'Surface Finish'].map((label) => (
                <button
                  key={label}
                  className={focusAreas.includes(label) ? 'focus-chip is-selected' : 'focus-chip'}
                  type="button"
                  onClick={() => toggleFocus(label)}
                >
                  <span className="focus-chip-box" aria-hidden="true" />
                  {label}
                </button>
              ))}
            </div>

            {error ? <p className="form-error">{error}</p> : null}
          </section>

          <footer className="page-footer-actions">
            <button className="button button-ghost" type="button" onClick={onBack}>
              Discard Draft
            </button>
            <button className="button button-primary button-wide-on-desktop" type="button" onClick={handleSubmit} disabled={saving}>
              {saving ? 'Saving Project...' : 'Save Project'}
            </button>
          </footer>
        </div>

        <aside className="split-side-column">
          <article className="info-visual-card">
            <div className="info-visual-image" />
            <div className="info-visual-copy">
              <strong>Global Coordinates</strong>
              <p>Location data will be attached once the first manhole and image capture are saved.</p>
            </div>
          </article>

          <article className="info-note-card is-blue">
            <strong>Precision Sync</strong>
            <p>Every joint entry is timestamped and linked to the project workspace for reporting continuity.</p>
          </article>

          <article className="info-note-card is-gold">
            <strong>Compliance Ready</strong>
            <p>Exported evidence packs stay aligned with inspection records and override history.</p>
          </article>

          <article className="info-tip-card">
            <strong>Field Tip</strong>
            <p>Use clear Site IDs so uploaded inspection images stay easy to match during review.</p>
          </article>
        </aside>
      </section>
    </div>
  )
}
