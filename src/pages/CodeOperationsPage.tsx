import { useCallback, useEffect, useState } from 'react'

type Job = { name: string; region: string; state: string }
type PipelineStep = { id: string; label: string; state: string; kind?: string; job?: string; updated_at?: string; detail?: string }
type Status = { state?: string; action?: string; reason?: string; stage?: string; submission_enabled?: boolean; global_gpu_quota?: number; max_active_gpu_jobs?: number; required_global_gpu_quota?: number; scheduler_interval_minutes?: number; last_controller_execution?: string; next_scheduled_execution?: string; jobs?: Job[]; checkpoint?: string | null; pipeline?: { campaign?: string; state?: string; approval_gate?: string; steps?: PipelineStep[]; updated_at?: string }; error?: string }

async function api(action: string, method: 'GET' | 'POST' = 'GET', body?: object) {
  const response = await fetch(`/api/code?action=${action}`, { method, credentials: 'same-origin', headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined })
  const payload = await response.json() as Status
  if (!response.ok) throw Object.assign(new Error(payload.error || `Request failed (${response.status})`), { status: response.status })
  return payload
}

const when = (value?: string) => value ? new Date(value).toLocaleString() : 'Not reported'

export function CodeOperationsPage() {
  const [authorized, setAuthorized] = useState<boolean | null>(null)
  const [password, setPassword] = useState('')
  const [status, setStatus] = useState<Status | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    try { setStatus(await api('status')); setAuthorized(true); setError('') }
    catch (cause) { const failure = cause as Error & { status?: number }; if (failure.status === 401) setAuthorized(false); else setError(failure.message) }
  }, [])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(), 30_000)
    return () => window.clearInterval(timer)
  }, [refresh])

  const run = async () => {
    setBusy(true)
    try { setStatus(await api('run', 'POST')); setError('') }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Controller run failed') }
    finally { setBusy(false) }
  }

  const report = async () => {
    setBusy(true)
    try {
      const data = await api('report')
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
      const link = document.createElement('a'); link.href = url; link.download = `jointinspect-report-${new Date().toISOString().replace(/[:.]/g, '-')}.json`; link.click(); URL.revokeObjectURL(url)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Report failed') }
    finally { setBusy(false) }
  }

  if (authorized !== true) return (
    <div className="code-auth-shell"><form className="code-auth-card" onSubmit={async (event) => {
      event.preventDefault(); setBusy(true)
      try { await api('login', 'POST', { password }); setPassword(''); setAuthorized(true); await refresh() }
      catch (cause) { setError(cause instanceof Error ? cause.message : 'Authentication failed') }
      finally { setBusy(false) }
    }}>
      <span className="code-eyebrow">Restricted operations</span><h1>JointInspect Control Room</h1><p>Authenticate to view cloud builds, training jobs, failures and campaign controls.</p>
      <label className="field"><span>Operator access password</span><input autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
      {error && <div className="code-alert code-alert-error" role="alert">{error}</div>}
      <button className="button button-primary" disabled={busy}>{busy ? 'Authenticating…' : 'Open control room'}</button>
    </form></div>
  )

  const jobs = status?.jobs || []
  const active = jobs.filter((job) => !['SUCCEEDED', 'FAILED', 'CANCELLED', 'DELETION_IN_PROGRESS'].includes(job.state))
  const steps = status?.pipeline?.steps || []
  const blocked = ['BUDGET_PAUSED', 'MANUAL_REVIEW_REQUIRED', 'FAILED'].includes(status?.state || '')
  return <div className="code-page">
    <header className="code-hero"><div><span className="code-eyebrow">Cloud operations · protected</span><h1>Training control room</h1><p>Monitor staging, builds, GPU training, failures and checkpoints from any device.</p></div><div className="code-actions"><button className="button button-secondary" onClick={() => void refresh()} disabled={busy}>Refresh</button><button className="button button-secondary" onClick={() => void report()} disabled={busy}>Download report</button><button className="button button-ghost" onClick={async () => { await api('logout', 'POST'); setAuthorized(false); setStatus(null) }}>Lock</button></div></header>
    {error && <div className="code-alert code-alert-error" role="alert"><strong>Connection error</strong><span>{error}</span></div>}
    {status?.reason && <div className={`code-alert ${blocked ? 'code-alert-warning' : 'code-alert-info'}`}><strong>{status.state || 'Controller update'}</strong><span>{status.reason}</span></div>}
    <section className="code-metrics"><article><span>Stage</span><strong>{status?.stage || 'Unknown'}</strong><small>{status?.action || 'No action reported'}</small></article><article><span>Active GPU jobs</span><strong>{active.length}</strong><small>GCP limit: {status?.max_active_gpu_jobs ?? '—'}</small></article><article><span>Global GPU quota</span><strong>{status?.global_gpu_quota ?? '—'}</strong><small>GCP requirement: {status?.required_global_gpu_quota ?? '—'}</small></article><article><span>Scheduler</span><strong>{status?.submission_enabled ? 'Enabled' : 'Safe mode'}</strong><small>{status?.scheduler_interval_minutes ? `Every ${status.scheduler_interval_minutes} min` : when(status?.next_scheduled_execution)}</small></article></section>
    {steps.length > 0 && <section className="code-panel code-pipeline"><div className="code-panel-heading"><div><span className="code-eyebrow">GCP campaign</span><h2>{status?.pipeline?.campaign || 'Concurrent model campaign'}</h2></div><span className={`code-state code-state-${(status?.pipeline?.state || 'pending').toLowerCase()}`}>{status?.pipeline?.state || 'PENDING'}</span></div><div className="code-step-grid">{steps.map((step) => <article key={step.id}><div className="code-step-marker" aria-hidden="true" /><div><strong>{step.label}</strong><span>{step.detail || step.kind || step.job || 'Reported by GCP'}</span></div><span className={`code-state code-state-${step.state.toLowerCase()}`}>{step.state}</span></article>)}</div>{status?.pipeline?.approval_gate && <div className="code-approval-gate"><span>Final gate</span><strong>{status.pipeline.approval_gate}</strong></div>}</section>}
    <div className="code-grid"><section className="code-panel code-panel-wide"><div className="code-panel-heading"><div><span className="code-eyebrow">Live workload</span><h2>Batch jobs</h2></div><span className="code-live">Updates every 30s</span></div>{jobs.length ? <div className="code-job-list">{jobs.map((job) => <article key={job.name}><div><strong>{job.name.split('/').at(-1)}</strong><span>{job.region}</span></div><span className={`code-state code-state-${job.state.toLowerCase()}`}>{job.state}</span></article>)}</div> : <div className="code-empty"><strong>No campaign jobs detected</strong><span>An approved job will appear here automatically.</span></div>}</section>
      <section className="code-panel"><span className="code-eyebrow">Guarded action</span><h2>Run controller now</h2><p>Re-check quota, active jobs, capacity and financial gates. It cannot bypass the campaign cap or create parallel GPU work.</p><button className="button button-primary" onClick={() => void run()} disabled={busy}>{busy ? 'Checking safeguards…' : 'Run approved sequence'}</button></section>
      <section className="code-panel"><span className="code-eyebrow">Recovery</span><h2>Checkpoint</h2><p className="code-mono">{status?.checkpoint || 'No checkpoint reported yet.'}</p><small>Last controller run: {when(status?.last_controller_execution)}</small></section></div>
  </div>
}
