import { useRef, useState } from 'react'
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
    <div className="page-grid">
      <section className="section-header compact">
        <button className="button button-ghost" type="button" onClick={onBack}>
          Back
        </button>
      </section>

      <section className="page-intro">
        <div>
          <p className="eyebrow">{projectName}</p>
          <h1>Upload joint evidence</h1>
          <p className="lead">{manholeLabel} photo queue with explicit empty, queued, processing, completed, and failed states.</p>
        </div>
      </section>

      <section className="upload-dropzone">
        <input
          ref={inputRef}
          className="sr-only"
          id="upload-input"
          type="file"
          accept="image/*"
          multiple
          onChange={(event) => void handleFileSelection(event.target.files)}
        />
        <label className="upload-target" htmlFor="upload-input">
          <span className="upload-icon" aria-hidden="true" />
          <strong>Tap to capture or upload</strong>
          <span>JPG or PNG, multi-select supported for field efficiency.</span>
        </label>
        <div className="action-row">
          <button className="button button-secondary" type="button" onClick={() => void onLoadSample()} disabled={busy}>
            Load Sample Queue
          </button>
          <button className="button button-ghost" type="button" onClick={() => void onClearQueue()} disabled={!queue.length || busy}>
            Clear All
          </button>
        </div>
      </section>

      {error ? <p className="form-error">{error}</p> : null}

      <section className="section-header compact">
        <div>
          <h2>Current uploads ({queue.length})</h2>
          <p>UI queue cards with local progress, remove, clear, and start actions.</p>
        </div>
      </section>

      <section className="upload-grid">
        {queue.length ? (
          queue.map((image) => (
            <article className="upload-card" key={image.id}>
              <div className="upload-preview">
                {image.previewUrl ? <img src={image.previewUrl} alt={image.fileName} /> : <div className="preview-placeholder" />}
                <button className="icon-button" type="button" onClick={() => void onRemoveFile(image.id)}>
                  Remove
                </button>
              </div>
              <div className="upload-copy">
                <div className="upload-title-row">
                  <strong>{image.jointLabel}</strong>
                  <StatusBadge status={image.queueStatus} />
                </div>
                <span>{image.fileName}</span>
                <div className="progress-rail">
                  <div className="progress-fill" style={{ width: `${image.progress ?? 0}%` }} />
                </div>
                <span>{image.errorMessage ?? `${image.progress ?? 0}% complete`}</span>
              </div>
            </article>
          ))
        ) : (
          <article className="empty-state">
            <strong>No queued photos yet</strong>
            <p>Add field images or load the sample queue to validate the full inspection flow.</p>
          </article>
        )}
      </section>

      <section className="event-panel">
        <h2>Processing feed</h2>
        <div className="event-list">
          {events.length ? events.map((event) => <p key={event}>{event}</p>) : <p>Waiting for queue activity.</p>}
        </div>
      </section>

      <footer className="sticky-actions">
        <button
          className="button button-primary button-wide"
          type="button"
          onClick={handleStart}
          disabled={!queue.length || busy}
        >
          {busy ? 'Processing Queue...' : 'Start Inspection'}
        </button>
      </footer>
    </div>
  )
}
