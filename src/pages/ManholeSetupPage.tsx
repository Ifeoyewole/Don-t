import { useState } from 'react'
import { pipeSpecs } from '../services/mockData'
import type { CreateManholeInput, EstimateMaterialsResult, Manhole, PipeType } from '../types/domain'

type Props = {
  projectName: string
  manhole?: Manhole | null
  projectId: string
  onBack: () => void
  onEstimate: (input: { meterRun: number; pipeType: PipeType }) => Promise<EstimateMaterialsResult>
  onSave: (input: CreateManholeInput, existingManholeId?: string) => Promise<void>
}

const defaultForm = (projectId: string, manhole?: Manhole | null): CreateManholeInput => ({
  projectId,
  manholeId: manhole?.manholeId ?? 'MH-882-NORTH',
  type: manhole?.type ?? 'surface-water',
  meterRun: manhole?.meterRun ?? 45.5,
  pipeType: manhole?.pipeType ?? '450mm-concrete',
})

const structureLabel = (type: CreateManholeInput['type']) =>
  type === 'surface-water' ? 'Surface Water' : 'Foul Water'

export const ManholeSetupPage = ({ projectName, manhole, projectId, onBack, onEstimate, onSave }: Props) => {
  const [form, setForm] = useState<CreateManholeInput>(() => defaultForm(projectId, manhole))
  const [estimate, setEstimate] = useState<EstimateMaterialsResult | null>(() => {
    const initialForm = defaultForm(projectId, manhole)
    const spec = pipeSpecs[initialForm.pipeType]
    const pipesNeeded = Math.max(1, Math.ceil(initialForm.meterRun / spec.unitLengthM))
    return {
      unitLengthM: spec.unitLengthM,
      pipesNeeded,
      jointsNeeded: pipesNeeded + 2,
      pipeDiameterMm: spec.diameterMm,
    }
  })
  const [loadingEstimate, setLoadingEstimate] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const refreshEstimate = async (nextForm: CreateManholeInput) => {
    setLoadingEstimate(true)
    try {
      const result = await onEstimate({ meterRun: nextForm.meterRun, pipeType: nextForm.pipeType })
      setEstimate(result)
    } catch {
      setError('Could not calculate the current materials estimate.')
    } finally {
      setLoadingEstimate(false)
    }
  }

  const updateForm = (updater: (current: CreateManholeInput) => CreateManholeInput) => {
    setForm((current) => {
      const next = updater(current)
      void refreshEstimate(next)
      return next
    })
  }

  const handleSave = async () => {
    if (!form.manholeId.trim()) {
      setError('Manhole ID is required.')
      return
    }

    setSaving(true)
    setError('')
    try {
      await onSave(form, manhole?.id)
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : 'Could not save manhole configuration.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="page-grid manhole-page">
      <section className="page-hero left-aligned">
        <div>
          <p className="eyebrow">{projectName}</p>
          <h1>Manhole Setup</h1>
          <p className="lead">Set the manhole details used for photo ordering, joint measurement, and summary reporting.</p>
        </div>
      </section>

      <section className="split-page-shell">
        <div className="split-main-column">
          <article className="stitch-form-card">
            <div className="stitch-two-up">
              <label className="field">
                <span>Manhole ID</span>
                <input
                  value={form.manholeId}
                  onChange={(event) => updateForm((current) => ({ ...current, manholeId: event.target.value }))}
                />
              </label>

              <label className="field">
                <span>Type</span>
                <select
                  value={form.type}
                  onChange={(event) =>
                    updateForm((current) => ({
                      ...current,
                      type: event.target.value as CreateManholeInput['type'],
                    }))
                  }
                >
                  <option value="surface-water">Surface Water</option>
                  <option value="foul-water">Foul Water</option>
                </select>
              </label>
            </div>

            <div className="stitch-two-up">
              <label className="field">
                <span>Meter Run (m)</span>
                <input
                  type="number"
                  min="1"
                  step="0.1"
                  value={form.meterRun}
                  onChange={(event) => updateForm((current) => ({ ...current, meterRun: Number(event.target.value) || 0 }))}
                />
              </label>

              <label className="field">
                <span>Pipe Diameter (mm)</span>
                <select
                  value={form.pipeType}
                  onChange={(event) =>
                    updateForm((current) => ({
                      ...current,
                      pipeType: event.target.value as PipeType,
                    }))
                  }
                >
                  {Object.entries(pipeSpecs).map(([value, spec]) => (
                    <option key={value} value={value}>
                      {spec.diameterMm} mm
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="context-photo-card">
              <span>Site Context Photo</span>
              <div className="context-photo-placeholder">
                <div className="context-photo-overlay">
                  <strong>{structureLabel(form.type)}</strong>
                  <p>Capture photos in upload order for this manhole.</p>
                </div>
              </div>
            </div>

            {error ? <p className="form-error">{error}</p> : null}

            <div className="page-footer-actions align-right">
              <button className="button button-secondary" type="button" onClick={onBack}>
                Back
              </button>
              <button className="button button-primary button-wide-on-desktop" type="button" onClick={handleSave} disabled={saving}>
                {saving ? 'Saving...' : 'Confirm Setup'}
              </button>
            </div>
          </article>
        </div>

        <aside className="split-side-column">
          <article className="estimate-sidebar">
            <div className="estimate-sidebar-head">
              <h2>Live Materials Estimate</h2>
              <span>{loadingEstimate ? 'Refreshing' : 'Verified'}</span>
            </div>
            <div className="estimate-highlight">
              <span>Estimated Joints</span>
              <strong>{estimate?.jointsNeeded ?? '--'}</strong>
              <p>Based on {estimate?.unitLengthM ?? '--'}m standard lengths</p>
            </div>
            <div className="estimate-mini-grid">
              <div className="estimate-mini-card">
                <span>Pipe Sections</span>
                <strong>{estimate?.pipesNeeded ?? '--'}</strong>
              </div>
              <div className="estimate-mini-card">
                <span>Sealing Kit</span>
                <strong>{estimate?.pipeDiameterMm ? `${estimate.pipeDiameterMm}-SK` : '--'}</strong>
              </div>
            </div>
            <div className="estimate-message">
              Estimates update automatically as you modify the meter run and selected diameter.
            </div>
          </article>

          <article className="specification-card">
            <h3>Specification Overview</h3>
            <div className="spec-list">
              <div className="spec-row">
                <div>
                  <strong>Precision Alignment</strong>
                  <p>Pipe geometry remains mapped to joint labels.</p>
                </div>
                <span className="spec-check is-good">✓</span>
              </div>
              <div className="spec-row">
                <div>
                  <strong>Hydrostatic Test</strong>
                  <p>Field verification required during review.</p>
                </div>
                <span className="spec-check">•</span>
              </div>
              <div className="spec-row">
                <div>
                  <strong>Corrosion Grade</strong>
                  <p>Recorded together with pipe material selection.</p>
                </div>
                <span className="spec-check is-good">✓</span>
              </div>
            </div>
          </article>
        </aside>
      </section>
    </div>
  )
}
