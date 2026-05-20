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
  manholeId: manhole?.manholeId ?? 'MH-',
  type: manhole?.type ?? 'surface-water',
  meterRun: manhole?.meterRun ?? 18,
  pipeType: manhole?.pipeType ?? '225mm-clay',
})

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

  const handleReset = () => {
    const next = defaultForm(projectId, manhole)
    setForm(next)
    void refreshEstimate(next)
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
    <div className="page-grid">
      <section className="section-header compact">
        <button className="button button-ghost" type="button" onClick={onBack}>
          Back
        </button>
      </section>

      <section className="page-intro">
        <div>
          <p className="eyebrow">{projectName}</p>
          <h1>Manhole setup</h1>
          <p className="lead">Configure run length and pipe type, then use the live estimator before image capture.</p>
        </div>
      </section>

      <section className="two-column-layout">
        <div className="form-card">
          <label className="field">
            <span>Manhole ID</span>
            <input
              value={form.manholeId}
              onChange={(event) => updateForm((current) => ({ ...current, manholeId: event.target.value }))}
              placeholder="Enter ID"
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

          <label className="field">
            <span>Meter Run</span>
            <input
              type="number"
              min="1"
              step="0.1"
              value={form.meterRun}
              onChange={(event) => updateForm((current) => ({ ...current, meterRun: Number(event.target.value) || 0 }))}
            />
          </label>

          <label className="field">
            <span>Pipe Type</span>
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
                  {spec.label} - {spec.unitLengthM}m
                </option>
              ))}
            </select>
          </label>

          {error ? <p className="form-error">{error}</p> : null}

          <div className="action-row">
            <button className="button button-primary" type="button" onClick={handleSave} disabled={saving}>
              {saving ? 'Saving...' : 'Save Configuration'}
            </button>
            <button className="button button-secondary" type="button" onClick={handleReset}>
              Reset
            </button>
          </div>
        </div>

        <aside className="estimate-panel">
          <div className="estimate-header">
            <h2>Materials Estimate</h2>
            <span>{loadingEstimate ? 'Refreshing...' : 'Live'}</span>
          </div>
          <div className="estimate-card">
            <span>Pipes needed</span>
            <strong>{estimate?.pipesNeeded ?? '--'}</strong>
          </div>
          <div className="estimate-card">
            <span>Joints needed</span>
            <strong>{estimate?.jointsNeeded ?? '--'}</strong>
          </div>
          <div className="estimate-card">
            <span>Unit length</span>
            <strong>{estimate?.unitLengthM ?? '--'}m</strong>
          </div>
          <p className="estimate-note">
            Live UI estimate using the plan formula: pipes = ceil(run / unit length), joints = pipes + 2.
          </p>
        </aside>
      </section>
    </div>
  )
}
