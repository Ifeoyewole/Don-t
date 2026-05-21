import { useState } from 'react'
import type { CreateProjectInput } from '../types/domain'

type Props = {
  todayLabel: string
  onBack: () => void
  onSave: (input: CreateProjectInput) => Promise<void>
}

export const CreateProjectPage = ({ todayLabel, onBack, onSave }: Props) => {
  const [form, setForm] = useState<CreateProjectInput>({ name: '', siteName: '' })
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
    <div className="page-grid">
      <section className="section-header compact">
        <button className="button button-ghost" type="button" onClick={onBack}>
          Back
        </button>
      </section>

      <section className="editor-hero">
        <div className="editor-hero-copy">
          <p className="eyebrow">Setup phase</p>
          <h1>New project</h1>
          <p className="lead">Set up the project details before adding manholes, evidence, and inspection results.</p>
        </div>
      </section>

      <section className="form-card">
        <label className="field">
          <span>Project Name</span>
          <input
            value={form.name}
            onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
            placeholder="e.g. North Basin Relief Main"
          />
        </label>

        <label className="field">
          <span>Site Name</span>
          <input
            value={form.siteName}
            onChange={(event) => setForm((current) => ({ ...current, siteName: event.target.value }))}
            placeholder="Enter site or corridor name"
          />
        </label>

        <div className="readonly-field">
          <span>Created Date</span>
          <div>{todayLabel}</div>
        </div>

        {error ? <p className="form-error">{error}</p> : null}
      </section>

      <footer className="sticky-actions">
        <button className="button button-primary button-wide" type="button" onClick={handleSubmit} disabled={saving}>
          {saving ? 'Saving Project...' : 'Save Project'}
        </button>
      </footer>
    </div>
  )
}
