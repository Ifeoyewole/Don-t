import { useEffect, useMemo, useRef, useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import type { CalibrationProfile, InspectionImage, ProcessBatchResult } from '../types/domain'

type Props = {
  online: boolean
  projectId: string
  projectName: string
  manholeLabel: string
  queue: InspectionImage[]
  events: string[]
  onBack: () => void
  onAddFiles: (files: File[]) => Promise<void>
  onLoadSample: () => Promise<void>
  onRemoveFile: (imageId: string) => Promise<void>
  onClearQueue: () => Promise<void>
  onStartInspection: (operatorContext?: string, calibration?: CalibrationProfile) => Promise<ProcessBatchResult>
}

const validationTone = (image: InspectionImage) =>
  image.validationStatus === 'retake' && image.queueStatus === 'queued' ? 'AI review needed' : image.validationStatus === 'retake' ? 'Needs retake' : 'Ready for inspection'

const phaseLabel = (image: InspectionImage) => {
  if (image.queueStatus === 'failed') return image.errorMessage ?? 'Needs replacement'
  if (image.queueStatus === 'processing') return `Uploading ${image.progress ?? 0}%`
  if (image.queueStatus === 'completed') return 'Measurement ready for review'
  return `${image.progress ?? 0}% complete`
}

export const PhotoUploadPage = ({
  online,
  projectId,
  projectName,
  manholeLabel,
  queue,
  events,
  onBack,
  onAddFiles,
  onLoadSample,
  onRemoveFile,
  onClearQueue,
  onStartInspection,
}: Props) => {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [operatorContext, setOperatorContext] = useState('')
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [reportedDownlink, setReportedDownlink] = useState<number | null>(null)

  // Calibration Profile Setup
  const [calPipeDiameter, setCalPipeDiameter] = useState<number | ''>(300)
  const [calSource, setCalSource] = useState<'PROJECT_METADATA' | 'MANHOLE_METADATA' | 'PHYSICAL_REFERENCE' | 'TEST_RIG' | 'CAMERA_CALIBRATION'>('PROJECT_METADATA')
  const [calReferenceId, setCalReferenceId] = useState<string>('')
  const [calVerified, setCalVerified] = useState<boolean>(true)
  const [calNotes, setCalNotes] = useState<string>('')
  const [savedProfile, setSavedProfile] = useState<CalibrationProfile | null>(null)
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string>('')

  // Load saved calibration profile for this project
  useEffect(() => {
    if (!projectId) return
    const key = `jointinspect_cal_${projectId}`
    try {
      const stored = localStorage.getItem(key)
      if (stored) {
        const parsed = JSON.parse(stored) as CalibrationProfile
        setSavedProfile(parsed)
        const dia = parsed.pipe_diameter_mm ?? parsed.pipeDiameterMm
        if (dia) setCalPipeDiameter(dia)
        if (parsed.source) setCalSource(parsed.source as any)
        const ref = parsed.calibration_reference_id ?? parsed.calibrationReferenceId
        if (ref) setCalReferenceId(ref)
        setCalVerified(Boolean(parsed.verified))
        if (parsed.notes) setCalNotes(parsed.notes)
      } else {
        // Default unverified/blank profile for new project
        const defaultRef = `CAL-${projectId.slice(0, 8).toUpperCase()}`
        setCalReferenceId(defaultRef)
      }
    } catch {
      // ignore JSON parse error
    }
  }, [projectId])

  const handleSaveCalibration = () => {
    const refId = calReferenceId.trim() || `CAL-${Date.now().toString(36).toUpperCase()}`
    const dia = calPipeDiameter ? Number(calPipeDiameter) : null
    const verifiedTimestamp = calVerified ? new Date().toISOString() : null
    const profile: CalibrationProfile = {
      calibration_reference_id: refId,
      calibrationReferenceId: refId,
      project_id: projectId,
      projectId,
      source: calSource,
      pipe_diameter_mm: dia,
      pipeDiameterMm: dia,
      verified: calVerified,
      verified_at: verifiedTimestamp,
      verifiedAt: verifiedTimestamp,
      notes: calNotes.trim() || undefined,
    }
    try {
      localStorage.setItem(`jointinspect_cal_${projectId}`, JSON.stringify(profile))
      setSavedProfile(profile)
      setSaveSuccessMsg('Calibration profile saved!')
      setTimeout(() => setSaveSuccessMsg(''), 3000)
    } catch {
      setSaveSuccessMsg('Failed to save profile.')
    }
  }

  const completedCount = useMemo(() => queue.filter((image) => image.queueStatus === 'completed').length, [queue])
  const processingCount = useMemo(() => queue.filter((image) => image.queueStatus === 'processing').length, [queue])
  const aiReviewCount = useMemo(() => queue.filter((image) => image.validationStatus === 'retake' && image.queueStatus === 'queued').length, [queue])
  const queueCompletion = useMemo(() => {
    if (!queue.length) return 0
    const weighted = queue.reduce((sum, image) => sum + (image.progress ?? 0), 0)
    return Math.round(weighted / queue.length)
  }, [queue])

  useEffect(() => {
    const connection = (navigator as Navigator & { connection?: { downlink?: number; addEventListener?: (type: string, listener: () => void) => void; removeEventListener?: (type: string, listener: () => void) => void } }).connection
    const syncConnection = () => setReportedDownlink(typeof connection?.downlink === 'number' ? connection.downlink : null)
    syncConnection()
    connection?.addEventListener?.('change', syncConnection)
    return () => connection?.removeEventListener?.('change', syncConnection)
  }, [])

  const networkLabel = !online
    ? 'Offline'
    : busy || processingCount > 0
      ? 'Processing'
      : queue.length
        ? 'Ready'
        : 'Idle'

  const throughputValue = reportedDownlink !== null ? `${reportedDownlink.toFixed(1)} Mbps` : `${queueCompletion}% queue progress`
  const throughputCaption = reportedDownlink !== null ? 'Reported device link' : 'Live queue throughput'

  const handleFileSelection = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    setError('')
    try {
      await onAddFiles(Array.from(files))
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Could not add selected files.')
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const handleStart = async () => {
    setBusy(true)
    setError('')
    try {
      await onStartInspection(operatorContext.trim() || undefined, savedProfile ?? undefined)
    } catch (processingError) {
      setError(processingError instanceof Error ? processingError.message : 'Processing failed.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page-grid upload-page">
      <section className="page-breadcrumbs">
        <button className="page-back-link" type="button" onClick={onBack}>
          Projects
        </button>
        <span>›</span>
        <span>{projectName}</span>
        <span>›</span>
        <strong>Evidence Upload</strong>
      </section>

      <section className="page-hero">
        <div>
          <h1>Upload Inspection Evidence</h1>
          <p className="lead">
            Ensure each joint is clearly visible. Upload photos in order so the app can measure each gap and assign a tolerance status.
          </p>
        </div>
        <button
          className="button button-primary dashboard-cta"
          type="button"
          onClick={() => void handleStart()}
          disabled={!queue.length || busy}
        >
          {busy ? 'Processing...' : 'Start Inspection'}
        </button>
      </section>

      <section className="upload-shell">
        <aside className="upload-sidebar">
          <section className="upload-drop-card">
            <input
              ref={inputRef}
              className="sr-only"
              id="upload-input"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              onChange={(event) => void handleFileSelection(event.target.files)}
            />
            <label className="upload-drop-target" htmlFor="upload-input">
              <div className="upload-drop-icon" aria-hidden="true">
                ⌁
              </div>
              <strong>Drag photos here</strong>
              <span>Or tap to browse photos. Supported formats: JPG, PNG, WEBP (max 15 MB).</span>
              <button className="button button-secondary" type="button" onClick={() => inputRef.current?.click()} disabled={busy}>
                Browse Photos
              </button>
              <div className="upload-tag-row">
                <span>Photos only</span>
                <span>Upload order kept</span>
              </div>
            </label>
          </section>

          {/* Project Reusable Calibration Profile */}
          <section className="network-card calibration-setup-card">
            <div className="network-head">
              <strong>Calibration</strong>
              <span className={`status-pill ${savedProfile?.verified ? 'is-pass' : 'is-review'}`}>
                {savedProfile?.verified ? 'VERIFIED' : 'CALIBRATION REQUIRED'}
              </span>
            </div>

            {savedProfile ? (
              <div
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  borderRadius: '6px',
                  padding: '0.6rem 0.75rem',
                  marginTop: '0.5rem',
                  fontSize: '0.8rem',
                  lineHeight: '1.4',
                }}
              >
                <div>
                  <strong>Calibration:</strong> {savedProfile.verified ? 'VERIFIED' : 'UNVERIFIED'}
                </div>
                <div>
                  <strong>Source:</strong> {savedProfile.source}
                </div>
                <div>
                  <strong>Pipe diameter:</strong>{' '}
                  {(savedProfile.pipeDiameterMm ?? savedProfile.pipe_diameter_mm)
                    ? `${savedProfile.pipeDiameterMm ?? savedProfile.pipe_diameter_mm} mm`
                    : 'Not specified'}
                </div>
                <div>
                  <strong>Reference:</strong>{' '}
                  {savedProfile.calibrationReferenceId ?? savedProfile.calibration_reference_id}
                </div>
              </div>
            ) : null}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginTop: '0.75rem' }}>
              <div>
                <label style={{ fontSize: '0.75rem', opacity: 0.85, display: 'block', marginBottom: '0.2rem' }}>
                  Pipe diameter
                </label>
                <div style={{ display: 'flex', gap: '0.4rem' }}>
                  <select
                    value={['150', '225', '300', '450', '600', '900'].includes(String(calPipeDiameter)) ? String(calPipeDiameter) : 'custom'}
                    onChange={(e) => {
                      if (e.target.value !== 'custom') setCalPipeDiameter(Number(e.target.value))
                    }}
                    style={{
                      flex: 1,
                      padding: '0.4rem',
                      borderRadius: '4px',
                      background: 'rgba(0, 0, 0, 0.3)',
                      color: 'inherit',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                    }}
                  >
                    <option value="150">150 mm</option>
                    <option value="225">225 mm</option>
                    <option value="300">300 mm</option>
                    <option value="450">450 mm</option>
                    <option value="600">600 mm</option>
                    <option value="900">900 mm</option>
                    <option value="custom">Custom</option>
                  </select>
                  <input
                    type="number"
                    min="1"
                    max="5000"
                    placeholder="mm"
                    value={calPipeDiameter}
                    onChange={(e) => setCalPipeDiameter(e.target.value ? Number(e.target.value) : '')}
                    style={{
                      width: '80px',
                      padding: '0.4rem',
                      borderRadius: '4px',
                      background: 'rgba(0, 0, 0, 0.3)',
                      color: 'inherit',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                    }}
                  />
                </div>
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', opacity: 0.85, display: 'block', marginBottom: '0.2rem' }}>
                  Source
                </label>
                <select
                  value={calSource}
                  onChange={(e) => setCalSource(e.target.value as any)}
                  style={{
                    width: '100%',
                    padding: '0.4rem',
                    borderRadius: '4px',
                    background: 'rgba(0, 0, 0, 0.3)',
                    color: 'inherit',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                  }}
                >
                  <option value="PROJECT_METADATA">Project Metadata</option>
                  <option value="MANHOLE_METADATA">Manhole Metadata</option>
                  <option value="PHYSICAL_REFERENCE">Physical Reference</option>
                  <option value="TEST_RIG">Test Rig</option>
                  <option value="CAMERA_CALIBRATION">Camera Calibration</option>
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.75rem', opacity: 0.85, display: 'block', marginBottom: '0.2rem' }}>
                  Reference ID
                </label>
                <input
                  type="text"
                  placeholder="e.g. DWG-2026-04, MH-402-SPEC"
                  value={calReferenceId}
                  onChange={(e) => setCalReferenceId(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.4rem',
                    borderRadius: '4px',
                    background: 'rgba(0, 0, 0, 0.3)',
                    color: 'inherit',
                    border: '1px solid rgba(255, 255, 255, 0.15)',
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.2rem' }}>
                <input
                  type="checkbox"
                  id="cal-verified-chk"
                  checked={calVerified}
                  onChange={(e) => setCalVerified(e.target.checked)}
                />
                <label htmlFor="cal-verified-chk" style={{ fontSize: '0.8rem', cursor: 'pointer' }}>
                  Verified by operator / metadata
                </label>
              </div>

              <button
                type="button"
                className="button button-secondary"
                style={{ marginTop: '0.35rem', width: '100%' }}
                onClick={handleSaveCalibration}
              >
                Save Calibration Profile
              </button>
              {saveSuccessMsg ? (
                <div style={{ color: '#4ade80', fontSize: '0.75rem', textAlign: 'center' }}>
                  {saveSuccessMsg}
                </div>
              ) : null}
            </div>
            <p style={{ fontSize: '0.72rem', opacity: 0.7, marginTop: '0.4rem' }}>
              Calibrate once: saved profile applies automatically to all subsequent photos in this project.
            </p>
          </section>

          <section className="network-card">
            <div className="network-head">
              <strong>Inspection Run</strong>
              <span>{networkLabel}</span>
            </div>
            <div className="network-meter-row">
              <span>{throughputCaption}</span>
              <strong>{throughputValue}</strong>
            </div>
            <div className="progress-rail">
              <div className="progress-fill" style={{ width: `${Math.max(queueCompletion, online ? 12 : 4)}%` }} />
            </div>
            <p>
              Project records persist in local storage. Inspection photos undergo ephemeral server-side computer vision &amp; Vertex AI domain gating; images are not retained on servers and training consent is disabled by default.
            </p>
            <p>{aiReviewCount ? `${aiReviewCount} photo(s) will use enhanced CV and AI review before a retake decision.` : 'All queued photos are eligible for measurement.'}</p>
            <div className="action-row">
              <button className="button button-secondary" type="button" onClick={() => void onLoadSample()} disabled={busy}>
                Load Sample
              </button>
              <button className="button button-ghost" type="button" onClick={() => void onClearQueue()} disabled={!queue.length || busy}>
                Clear All
              </button>
            </div>
          </section>

          <section className="network-card operator-context-card">
            <div className="network-head">
              <strong>Inspection context</strong>
              <span>Optional</span>
            </div>
            <textarea
              id="operator-context-input"
              className="operator-context-textarea"
              rows={3}
              maxLength={1000}
              value={operatorContext}
              onChange={(e) => setOperatorContext(e.target.value)}
              placeholder='Add useful context for this inspection, for example: "Possible gasket extrusion near the upper-right edge. Focus on joint alignment."'
              style={{
                width: '100%',
                padding: '0.6rem',
                borderRadius: '6px',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                background: 'rgba(0, 0, 0, 0.25)',
                color: 'inherit',
                fontSize: '0.85rem',
                resize: 'vertical',
                marginTop: '0.5rem',
                boxSizing: 'border-box',
              }}
            />
            <p style={{ fontSize: '0.75rem', opacity: 0.75, marginTop: '0.35rem' }}>
              Optional. This helps AI interpret the inspection and tailor its explanation. It does not override measurements, calibration, tolerance rules, or safety checks.
            </p>
          </section>
        </aside>

        <section className="upload-assets-card">
          <div className="upload-assets-head">
            <div>
              <h2>Uploaded Assets</h2>
              <span className="assets-count-pill">{queue.length} Files</span>
            </div>
            <div className="assets-view-icons" aria-hidden="true">
              <span>◫</span>
              <span>☰</span>
            </div>
          </div>

          {error ? <p className="form-error upload-error">{error}</p> : null}

          <div className="upload-assets-grid">
            {queue.length ? (
              queue.map((image) => (
                <article
                  className={`asset-card asset-${image.queueStatus} ${image.validationStatus === 'retake' ? 'asset-invalid-capture' : ''}`}
                  key={image.id}
                >
                  <div className="asset-image-wrap">
                    {image.previewUrl ? <img src={image.previewUrl} alt={image.fileName} /> : <div className="preview-placeholder" />}
                    <button className="icon-button" type="button" onClick={() => void onRemoveFile(image.id)}>
                      Remove
                    </button>
                    {image.queueStatus === 'completed' ? <span className="asset-check">✓</span> : null}
                    {image.queueStatus === 'processing' ? <div className="asset-overlay">{phaseLabel(image)}</div> : null}
                  </div>
                  <div className="asset-body">
                    <div className="upload-title-row">
                      <strong>{image.fileName}</strong>
                      <span className="segment-pill">{image.jointLabel}</span>
                    </div>
                    <div className="asset-meta-row">
                      <StatusBadge status={image.queueStatus} />
                      <span>{manholeLabel}</span>
                    </div>
                    <div className="asset-validation-row">
                      <span className={image.validationStatus === 'retake' && image.queueStatus === 'queued' ? 'mini-status-pill is-review' : image.validationStatus === 'retake' ? 'mini-status-pill is-fail' : 'mini-status-pill is-pass'}>
                        {validationTone(image)}
                      </span>
                    </div>
                    <div className="progress-rail">
                      <div className="progress-fill" style={{ width: `${image.progress ?? 0}%` }} />
                    </div>
                    <p>{phaseLabel(image)}</p>
                    {image.validationMessage ? <p className="asset-validation-message">{image.validationMessage}</p> : null}
                  </div>
                </article>
              ))
            ) : (
              <article className="empty-state">
                <strong>No uploaded assets yet</strong>
                <p>Select or drag field photos to begin this inspection run.</p>
              </article>
            )}
          </div>

          <div className="upload-assets-footer">
            <span>
              Showing {queue.length} of {queue.length} assets for current inspection run.
            </span>
            <div className="action-row">
              <button className="button button-ghost" type="button" onClick={() => void onClearQueue()} disabled={!queue.length || busy}>
                Clear all
              </button>
              <button
                className="button button-primary"
                type="button"
                onClick={() => void handleStart()}
                disabled={!queue.length || busy}
              >
                {busy ? 'Processing Queue...' : 'Start Inspection'}
              </button>
            </div>
          </div>
        </section>
      </section>

      <section className="event-panel upload-events-panel">
        <div className="section-header compact">
          <div>
            <h2>Processing Feed</h2>
            <p>{completedCount} item(s) completed in the current run.</p>
          </div>
        </div>
        <div className="event-list">
          {events.length ? events.map((event) => <p key={event}>{event}</p>) : <p>Waiting for queue activity.</p>}
        </div>
      </section>
    </div>
  )
}
