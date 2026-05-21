import { useMemo, useRef, useState } from 'react'
import { StatusBadge } from '../components/StatusBadge'
import type { InspectionImage, ProcessBatchResult } from '../types/domain'

type Props = {
  projectName: string
  manholeLabel: string
  queue: InspectionImage[]
  events: string[]
  onBack: () => void
  onAddFiles: (files: File[]) => Promise<void>
  onLoadSample: () => Promise<void>
  onRemoveFile: (imageId: string) => Promise<void>
  onClearQueue: () => Promise<void>
  onStartInspection: () => Promise<ProcessBatchResult>
}

const phaseLabel = (image: InspectionImage) => {
  if (image.queueStatus === 'failed') return image.errorMessage ?? 'Needs replacement'
  if (image.queueStatus === 'processing') return `Uploading ${image.progress ?? 0}%`
  if (image.queueStatus === 'completed') return `AI analysis ${(Math.round((image.progress ?? 100) * 0.98) || 98)}% confidence`
  return `${image.progress ?? 0}% complete`
}

export const PhotoUploadPage = ({
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
  const inputRef = useRef<HTMLInputElement | null>(null)

  const completedCount = useMemo(() => queue.filter((image) => image.queueStatus === 'completed').length, [queue])

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
      await onStartInspection()
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
            Ensure all joint segments are clearly visible. High-resolution photos are required for structural integrity
            validation and AI-assisted defect detection.
          </p>
        </div>
        <button className="button button-primary dashboard-cta" type="button" onClick={() => void handleStart()} disabled={!queue.length || busy}>
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
              accept="image/*"
              multiple
              onChange={(event) => void handleFileSelection(event.target.files)}
            />
            <label className="upload-drop-target" htmlFor="upload-input">
              <div className="upload-drop-icon" aria-hidden="true">
                ⌁
              </div>
              <strong>Drag photos here</strong>
              <span>Or click to browse your workstation. Support JPG, PNG up to 25MB.</span>
              <div className="upload-tag-row">
                <span>4K Resolution</span>
                <span>Geo-tagged</span>
              </div>
            </label>
          </section>

          <section className="network-card">
            <div className="network-head">
              <strong>Network Integrity</strong>
              <span>Stable</span>
            </div>
            <div className="network-meter-row">
              <span>Upload Bandwidth</span>
              <strong>45 MB/s</strong>
            </div>
            <div className="progress-rail">
              <div className="progress-fill" style={{ width: '75%' }} />
            </div>
            <p>Offline caching stays enabled, so inspection data persists locally if connection drops.</p>
            <div className="action-row">
              <button className="button button-secondary" type="button" onClick={() => void onLoadSample()} disabled={busy}>
                Load Sample
              </button>
              <button className="button button-ghost" type="button" onClick={() => void onClearQueue()} disabled={!queue.length || busy}>
                Clear All
              </button>
            </div>
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
                <article className={`asset-card asset-${image.queueStatus}`} key={image.id}>
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
                      <span className="segment-pill">{image.jointLabel} SEG</span>
                    </div>
                    <div className="asset-meta-row">
                      <StatusBadge status={image.queueStatus} />
                      <span>{manholeLabel}</span>
                    </div>
                    <div className="progress-rail">
                      <div className="progress-fill" style={{ width: `${image.progress ?? 0}%` }} />
                    </div>
                    <p>{phaseLabel(image)}</p>
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
              <button className="button button-primary" type="button" onClick={() => void handleStart()} disabled={!queue.length || busy}>
                {busy ? 'Processing Queue...' : 'Verify All'}
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
