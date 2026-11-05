import { useEffect, useMemo, useRef, useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import { requestInspectionContextSuggestions } from '../lib/contextSuggestions'
import type { CalibrationProfile, GeometrySelectionProvenance, InspectionImage, JointGeometryType, ProcessBatchResult } from '../types/domain'

type Props = {
  online: boolean
  projectId: string
  projectName: string
  manholeLabel: string
  manholeId: string
  manholePipeDiameterMm?: number
  queue: InspectionImage[]
  events: string[]
  onBack: () => void
  onAddFiles: (files: File[]) => Promise<InspectionImage[]>
  onUpdateImageContext: (imageId: string, patch: Partial<InspectionImage>, origin: 'ai' | 'inspector' | 'system') => Promise<void>
  onRemoveFile: (imageId: string) => Promise<void>
  onClearQueue: () => Promise<void>
  onStartInspection: (operatorContext?: string, calibration?: CalibrationProfile, jointType?: JointGeometryType, provenance?: GeometrySelectionProvenance) => Promise<ProcessBatchResult>
}

const validationTone = (image: InspectionImage) =>
  image.validationStatus === 'retake' && image.queueStatus === 'queued' ? 'AI review needed' : image.validationStatus === 'retake' ? 'Needs retake' : 'Ready for inspection'

const phaseLabel = (image: InspectionImage) => {
  if (image.queueStatus === 'failed') return image.errorMessage ?? 'Needs replacement'
  if (image.queueStatus === 'processing') return `Uploading ${image.progress ?? 0}%`
  if (image.queueStatus === 'completed') return 'Measurement ready for review'
  return `${image.progress ?? 0}% complete`
}

type CalibrationSourceType = 'PROJECT_METADATA' | 'MANHOLE_METADATA' | 'PHYSICAL_REFERENCE' | 'TEST_RIG' | 'CAMERA_CALIBRATION'

function getInitialCalibration(projId: string, manholeId: string) {
  if (!projId || typeof localStorage === 'undefined') {
    return {
      profile: null as CalibrationProfile | null,
      pipeDiameter: '' as number | '',
      source: 'PROJECT_METADATA' as CalibrationSourceType,
      referenceId: '',
      verified: false,
      notes: '',
    }
  }
  try {
    const stored = localStorage.getItem(`jointinspect_cal_${projId}_${manholeId}`)
    if (stored) {
      const parsed = JSON.parse(stored) as CalibrationProfile
      const dia = parsed.pipe_diameter_mm ?? parsed.pipeDiameterMm
      const ref = parsed.calibration_reference_id ?? parsed.calibrationReferenceId
      return {
        profile: parsed,
        pipeDiameter: (dia ? Number(dia) : '') as number | '',
        source: (parsed.source as CalibrationSourceType) || 'PROJECT_METADATA',
        referenceId: ref || '',
        verified: Boolean(parsed.verified),
        notes: parsed.notes || '',
      }
    }
  } catch {
    // ignore
  }
  return {
    profile: null as CalibrationProfile | null,
    pipeDiameter: '' as number | '',
    source: 'PROJECT_METADATA' as CalibrationSourceType,
    referenceId: '',
    verified: false,
    notes: '',
  }
}

export const PhotoUploadPage = ({
  online,
  projectId,
  projectName,
  manholeLabel,
  manholeId,
  manholePipeDiameterMm,
  queue,
  events,
  onBack,
  onAddFiles,
  onUpdateImageContext,
  onRemoveFile,
  onClearQueue,
  onStartInspection,
}: Props) => {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notesDrafts, setNotesDrafts] = useState<Record<string, string>>({})
  const suggestionControllers = useRef(new Map<string, AbortController>())
  const pendingWrites = useRef(new Set<Promise<void>>())
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [reportedDownlink, setReportedDownlink] = useState<number | null>(null)

  // Calibration Profile Setup - Fail-Safe Defaults initialized from project storage
  const [calPipeDiameter, setCalPipeDiameter] = useState<number | ''>(() => getInitialCalibration(projectId, manholeId).pipeDiameter || manholePipeDiameterMm || '')
  const [calSource, setCalSource] = useState<CalibrationSourceType>(() => getInitialCalibration(projectId, manholeId).pipeDiameter ? getInitialCalibration(projectId, manholeId).source : manholePipeDiameterMm ? 'MANHOLE_METADATA' : 'PROJECT_METADATA')
  const [calReferenceId, setCalReferenceId] = useState<string>(() => getInitialCalibration(projectId, manholeId).referenceId)
  const [calNotes, setCalNotes] = useState<string>(() => getInitialCalibration(projectId, manholeId).notes)
  const [calCameraId, setCalCameraId] = useState<string>(() => getInitialCalibration(projectId, manholeId).profile?.camera_id ?? '')
  const [savedProfile, setSavedProfile] = useState<CalibrationProfile | null>(() => getInitialCalibration(projectId, manholeId).profile)
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string>('')
  const [saveErrorMsg, setSaveErrorMsg] = useState<string>('')

  useEffect(() => {
    const init = getInitialCalibration(projectId, manholeId)
    // Defer the state reset so the effect synchronizes the selected project
    // without triggering React's synchronous set-state-in-effect rule.
    queueMicrotask(() => {
      const diameterConflict = Boolean(manholePipeDiameterMm && init.pipeDiameter !== '' && init.pipeDiameter !== manholePipeDiameterMm)
      setCalPipeDiameter(diameterConflict ? manholePipeDiameterMm! : init.pipeDiameter !== '' ? init.pipeDiameter : manholePipeDiameterMm ?? '')
      setCalSource(diameterConflict ? 'MANHOLE_METADATA' : init.pipeDiameter !== '' ? init.source : manholePipeDiameterMm ? 'MANHOLE_METADATA' : init.source)
      setCalReferenceId(diameterConflict ? '' : init.referenceId)
      setCalNotes(diameterConflict ? '' : init.notes)
      setCalCameraId(diameterConflict ? '' : init.profile?.camera_id ?? '')
      setSavedProfile(diameterConflict ? null : init.profile ? { ...init.profile, verified: false, verified_at: null, verifiedAt: null } : null)
      for (const controller of suggestionControllers.current.values()) controller.abort()
      suggestionControllers.current.clear()
      setNotesDrafts({})
    })
  }, [projectId, manholeId, manholePipeDiameterMm])

  useEffect(() => () => { for (const controller of suggestionControllers.current.values()) controller.abort() }, [])

  const handleSaveCalibration = () => {
    setSaveErrorMsg('')
    setSaveSuccessMsg('')

    const refId = calReferenceId.trim()
    const dia = calPipeDiameter !== '' ? Number(calPipeDiameter) : null

    if (dia !== null && dia <= 0) {
      setSaveErrorMsg('Pipe diameter must be greater than zero.')
      return
    }

    const profile: CalibrationProfile = {
      calibration_reference_id: refId || `UNVERIFIED-${Date.now().toString(36).toUpperCase()}`,
      calibrationReferenceId: refId || `UNVERIFIED-${Date.now().toString(36).toUpperCase()}`,
      project_id: projectId,
      projectId,
      source: calSource,
      pipe_diameter_mm: dia,
      pipeDiameterMm: dia,
      verified: false,
      verified_at: null,
      verifiedAt: null,
      notes: calNotes.trim() || undefined,
      camera_id: calCameraId.trim() || null,
      cameraId: calCameraId.trim() || null,
    }
    try {
      localStorage.setItem(`jointinspect_cal_${projectId}_${manholeId}`, JSON.stringify(profile))
      setSavedProfile(profile)
      setSaveSuccessMsg('Calibration reference saved. The server must verify it before authoritative millimetres are available.')
      setTimeout(() => {
        setSaveSuccessMsg('')
        setSaveErrorMsg('')
      }, 4000)
    } catch {
      setSaveErrorMsg('Failed to save profile.')
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
  const needsImageSelection = queue.some((image) => (image.queueStatus === 'queued' || image.queueStatus === 'failed') && image.analysisMode !== 'EVIDENCE_ONLY' && !image.jointType)

  const persistPhotoContext = (imageId: string, patch: Partial<InspectionImage>, origin: 'ai' | 'inspector' | 'system') => {
    const write = onUpdateImageContext(imageId, patch, origin)
    pendingWrites.current.add(write)
    void write.catch((err: unknown) => setError(err instanceof Error ? err.message : 'Could not update image context.'))
      .finally(() => pendingWrites.current.delete(write))
    return write
  }

  const analyzeForSuggestions = async (image: InspectionImage, photo: File) => {
    const controller = new AbortController()
    suggestionControllers.current.set(image.id, controller)
    await persistPhotoContext(image.id, { contextSuggestionStatus: 'pending' }, 'system')
    const timeout = window.setTimeout(() => controller.abort('timeout'), 45000)
    try {
      const result = await requestInspectionContextSuggestions(photo, controller.signal, manholePipeDiameterMm)
      if (controller.signal.aborted) return
      const allowed = result.processing_allowed && result.image_quality_usable
      await persistPhotoContext(image.id, {
        contextSuggestionStatus: allowed ? 'ready' : 'review_required',
        contextSuggestionMessage: result.reason,
        contextSuggestionModel: result.model,
        suggestedJointType: allowed ? result.suggested_joint_type ?? undefined : undefined,
        suggestedInspectionContext: allowed ? result.suggested_inspection_context ?? undefined : undefined,
        possibleGapVisible: allowed ? result.possible_gap_visible : null,
        jointType: allowed ? result.suggested_joint_type ?? undefined : undefined,
        operatorContext: allowed ? result.suggested_inspection_context ?? undefined : undefined,
      }, 'ai')
    } catch (err) {
      if (controller.signal.aborted && controller.signal.reason !== 'timeout') return
      await persistPhotoContext(image.id, {
        contextSuggestionStatus: 'unavailable',
        contextSuggestionMessage: controller.signal.reason === 'timeout' ? 'Suggestion timed out; choose geometry manually.' :
          err instanceof Error ? err.message : 'AI suggestion unavailable. You can still enter context manually.',
      }, 'system')
    } finally {
      window.clearTimeout(timeout)
      suggestionControllers.current.delete(image.id)
    }
  }

  const handleFileSelection = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    setError('')
    try {
      const selected = Array.from(files)
      const added = await onAddFiles(selected)
      if (online) {
        // Two image-only requests at a time, to limit network and Vertex usage.
        void (async () => {
          for (let i = 0; i < added.length; i += 2) {
            await Promise.all(added.slice(i, i + 2).map((image, offset) =>
              analyzeForSuggestions(image, selected[i + offset])))
          }
        })().catch((err: unknown) => setError(err instanceof Error ? err.message : 'Suggestion preflight interrupted.'))
      } else {
        for (const image of added) void persistPhotoContext(image.id, {
          contextSuggestionStatus: 'unavailable',
          contextSuggestionMessage: 'Offline: enter geometry and notes manually.',
        }, 'system')
      }
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : 'Could not add selected files.')
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  const saveNote = (imageId: string, textValue: string) => {
    void persistPhotoContext(imageId, { operatorContext: textValue }, 'inspector')
    setNotesDrafts((current) => {
      const next = { ...current }
      delete next[imageId]
      return next
    })
  }

  const handleStart = async () => {
    setBusy(true)
    setError('')
    try {
      for (const [imageId, note] of Object.entries(notesDrafts)) {
        await persistPhotoContext(imageId, { operatorContext: note }, 'inspector')
      }
      await Promise.all([...pendingWrites.current])
      const readyToMeasure = queue.filter((image) => image.queueStatus === 'queued' || image.queueStatus === 'failed')
      if (readyToMeasure.some((image) => image.analysisMode !== 'EVIDENCE_ONLY' && !image.jointType)) {
        throw new Error('Choose a geometry or evidence-only review for every photo before processing.')
      }
      await onStartInspection(undefined, savedProfile ?? undefined)
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
          disabled={!queue.length || busy || needsImageSelection}
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
              <span className="status-pill is-review">
                {savedProfile ? 'REFERENCE SAVED' : 'CALIBRATION REQUIRED'}
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
                  <strong>Calibration:</strong> SERVER VERIFICATION REQUIRED
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
                    value={calPipeDiameter ? (['150', '225', '300', '450', '600', '900'].includes(String(calPipeDiameter)) ? String(calPipeDiameter) : 'custom') : ''}
                    onChange={(e) => {
                      if (e.target.value === '') {
                        setCalPipeDiameter('')
                      } else if (e.target.value !== 'custom') {
                        setCalPipeDiameter(Number(e.target.value))
                      }
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
                    <option value="">Select diameter...</option>
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
                  onChange={(e) => setCalSource(e.target.value as CalibrationSourceType)}
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
              {saveErrorMsg ? (
                <div style={{ color: '#f87171', fontSize: '0.75rem', textAlign: 'center' }}>
                  {saveErrorMsg}
                </div>
              ) : null}
            </div>
            <p style={{ fontSize: '0.72rem', opacity: 0.7, marginTop: '0.4rem' }}>
              {manholePipeDiameterMm && !getInitialCalibration(projectId, manholeId).pipeDiameter
                ? `Diameter prefilled from manhole specifications (${manholePipeDiameterMm} mm), NOT inferred by AI. `
                : ''}
              Save the calibration reference once for this project. The backend verifies trusted references before issuing authoritative millimetres.
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
              <button className="button button-ghost" type="button" onClick={() => { for (const controller of suggestionControllers.current.values()) controller.abort(); suggestionControllers.current.clear(); void onClearQueue() }} disabled={!queue.length || busy || needsImageSelection}>
                Clear All
              </button>
            </div>
          </section>

          <section className="network-card operator-context-card">
            <div className="network-head"><strong>Photo-specific evidence</strong><span>Editable</span></div>
            <p>Each photo below has its own geometry and inspection note. Gemini suggests them independently; operators can correct or mark unsupported views as evidence-only review.</p>
            <p>Other conditions such as infiltration, deposits, surface damage, intruding connections and unknown features are never silently labelled as open joints.</p>
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
                    <button className="icon-button" type="button" onClick={() => {
                      suggestionControllers.current.get(image.id)?.abort()
                      void onRemoveFile(image.id)
                    }}>
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
                    <div className="photo-context-editor" style={{ marginTop: '0.75rem', paddingTop: '0.75rem', borderTop: '1px solid var(--outline, #cbd5e1)' }}>
                      <label htmlFor={`geometry-${image.id}`} style={{ display: 'block', fontWeight: 700, fontSize: '0.8rem' }}>
                        Photo-specific geometry
                      </label>
                      <select
                        id={`geometry-${image.id}`}
                        value={image.analysisMode === 'EVIDENCE_ONLY' ? 'EVIDENCE_ONLY' : image.jointType ?? ''}
                        disabled={image.queueStatus === 'completed' || image.queueStatus === 'processing'}
                        onChange={(event) => {
                          const selection = event.target.value
                          if (selection === 'EVIDENCE_ONLY') {
                            void persistPhotoContext(image.id, { analysisMode: 'EVIDENCE_ONLY' }, 'inspector')
                          } else if (selection) {
                            void persistPhotoContext(image.id, { jointType: selection as JointGeometryType }, 'inspector')
                          }
                        }}
                        style={{ width: '100%', padding: '0.5rem', marginTop: '0.25rem' }}
                      >
                        <option value="">Select / await AI suggestion</option>
                        <option value="CIRCULAR_OPENING">Circular joint / opening</option>
                        <option value="HORIZONTAL_SEAM">Horizontal seam</option>
                        <option value="VERTICAL_SEAM">Vertical seam</option>
                        <option value="EVIDENCE_ONLY">Other defect, lateral, or uncertain — review only</option>
                      </select>
                      <p style={{ fontSize: '0.72rem', marginTop: '0.3rem' }}>
                        {image.contextSuggestionStatus === 'pending' ? 'Gemini is analyzing this photo…' :
                          image.contextSuggestionStatus === 'ready' ? `AI suggestion: ${image.contextSuggestionModel ?? 'visual model'} — review before trusting.` :
                            image.contextSuggestionMessage ?? 'Select a supported gap geometry or keep evidence for manual review.'}
                      </p>
                      {image.suggestedInspectionContext && (
                        <p style={{ fontSize: '0.74rem', marginTop: '0.35rem' }}>
                          AI observation: {image.suggestedInspectionContext}
                        </p>
                      )}
                      {image.possibleGapVisible === true && <p style={{ fontSize: '0.72rem' }}>Potential gap visible; not a confirmed defect.</p>}
                      {(image.suggestedJointType || image.suggestedInspectionContext) && image.queueStatus !== 'completed' && (
                        <button type="button" className="button button-ghost" style={{ marginTop: '0.4rem' }}
                          onClick={() => void persistPhotoContext(image.id, {
                            ...(image.suggestedJointType ? { jointType: image.suggestedJointType } : {}),
                            ...(image.suggestedInspectionContext ? { operatorContext: image.suggestedInspectionContext } : {}),
                          }, 'inspector')}>
                          Apply this photo's suggestions
                        </button>
                      )}
                      <label htmlFor={`notes-${image.id}`} style={{ display: 'block', fontWeight: 700, fontSize: '0.8rem', marginTop: '0.6rem' }}>
                        Inspection note
                      </label>
                      <textarea
                        id={`notes-${image.id}`}
                        className="operator-context-textarea"
                        rows={2}
                        maxLength={1000}
                        disabled={image.queueStatus === 'completed' || image.queueStatus === 'processing'}
                        value={notesDrafts[image.id] ?? image.operatorContext ?? ''}
                        onChange={(event) => setNotesDrafts((old) => ({ ...old, [image.id]: event.target.value }))}
                        onBlur={() => {
                          if (notesDrafts[image.id] !== undefined) saveNote(image.id, notesDrafts[image.id])
                        }}
                        placeholder="Optional visible observations or inspector findings; never calibration authority."
                        style={{ width: '100%', padding: '0.5rem', boxSizing: 'border-box', marginTop: '0.25rem' }}
                      />
                      <p style={{ fontSize: '0.7rem', opacity: 0.78 }}>
                        {image.analysisMode === 'EVIDENCE_ONLY' ? 'Review only — no fabricated mm or PASS.' :
                          image.geometrySelectionProvenance === 'INSPECTOR_SELECTED' ? 'Geometry confirmed/edited by inspector.' :
                            image.geometrySelectionProvenance === 'EVIDENCE_SUGGESTED' ? 'AI-suggested geometry — remains provisional.' :
                              'Geometry not confirmed; select a mode before processing.'}
                      </p>
                    </div>
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
              <button className="button button-ghost" type="button" onClick={() => { for (const controller of suggestionControllers.current.values()) controller.abort(); suggestionControllers.current.clear(); void onClearQueue() }} disabled={!queue.length || busy || needsImageSelection}>
                Clear all
              </button>
              <button
                className="button button-primary"
                type="button"
                onClick={() => void handleStart()}
                disabled={!queue.length || busy || needsImageSelection}
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
