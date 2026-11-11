import { useEffect, useState } from 'react'

type Props = { available: boolean; onAvailability: (available: boolean) => void; onSignOut: () => void }

/** Sign in inside the inspection workflow; no separate operations portal. */
export function UnifiedPreviewAccess({ available, onAvailability, onSignOut }: Props) {
  const [required, setRequired] = useState(false)
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    void fetch('/api/unified', { credentials: 'same-origin', signal: controller.signal }).then(async response => {
      const result = await response.json()
      onAvailability(response.ok && result.available === true)
      setRequired(response.status === 401)
    }).catch(() => {})
    return () => controller.abort()
  }, [onAvailability])
  if (available) return <section className="card">
    <p>Engineering preview operator signed in.</p>
    <button type="button" disabled={busy} onClick={async () => {
      setBusy(true); setError('')
      try {
        const response = await fetch('/api/engineering-session?action=logout', { method: 'POST', credentials: 'same-origin' })
        if (!response.ok) throw new Error('Sign-out unavailable. Please try again.')
        onAvailability(false); onSignOut(); setRequired(true)
      } catch (reason) { setError(reason instanceof Error ? reason.message : 'Sign-out unavailable.') }
      finally { setBusy(false) }
    }}>Sign out of engineering preview</button>
    {error && <p role="alert">{error}</p>}
  </section>
  if (!required) return null
  return <section className="card">
    <details><summary>Engineering preview sign-in</summary>
      <form onSubmit={async event => {
        event.preventDefault(); setBusy(true); setError('')
        try {
          const response = await fetch('/api/engineering-session?action=login', { method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) })
          if (!response.ok) throw new Error('Sign-in failed. Check your existing operator credentials.')
          const available = await fetch('/api/unified', { credentials: 'same-origin' })
          if (!available.ok || (await available.json()).available !== true) throw new Error('Engineering preview is currently unavailable.')
          onAvailability(true); setRequired(false)
        } catch (reason) { setError(reason instanceof Error ? reason.message : 'Sign-in unavailable.') }
        finally { setPassword(''); setBusy(false) }
      }}>
        <label>Operator password<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required disabled={busy} /></label>
        <button type="submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in to engineering preview'}</button>
        {error && <p role="alert">{error}</p>}
      </form>
      <p>Use your existing operator access. Ordinary inspections do not require this sign-in.</p>
    </details>
  </section>
}
