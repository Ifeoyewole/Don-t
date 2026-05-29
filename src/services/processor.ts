import { db } from '../db'
import type {
  InspectionImage,
  InspectionResult,
  ProcessBatchResult,
  ProcessingEvent,
  ProcessOptions,
} from '../types'
import { fuseMeasurementWithAi, measureWithCv } from '../lib'
import type { CvWorkerResponse } from '../lib'
import { reviewMeasurementWithAi } from './aiMeasurement'
import { createId, createTimestamp } from '../utils/identity'

const listeners = new Set<(event: ProcessingEvent) => void>()

function getRetakeMessageFromProcessingError(message: string): string | null {
  if (
    message.includes('Pipe opening was detected, but joint gap extraction failed') ||
    message.includes('OpenCV did not detect a valid pipe opening') ||
    message.includes('OpenCV circle scoring returned no usable opening')
  ) {
    return 'Retake photo: keep the full pipe opening and the joint ring clearly visible so the gap can be measured.'
  }

  if (
    message.includes('measuring-gap-from-circle') ||
    message.includes('running-hough-circles')
  ) {
    return 'Retake photo: use the guided capture angle and keep the full pipe opening steady in frame.'
  }

  return null
}

async function failImageProcessing(imageId: string, message: string): Promise<void> {
  const image = await db.inspectionImages.get(imageId)
  const retakeMessage = getRetakeMessageFromProcessingError(message)

  if (!image) {
    emit({
      type: 'failed',
      imageId,
      message: retakeMessage ?? message,
    })
    return
  }

  await db.inspectionImages.put({
    ...image,
    queueStatus: 'failed',
    progress: 0,
    errorMessage: retakeMessage ?? message,
    validationStatus: retakeMessage ? 'retake' : image.validationStatus,
    validationMessage: retakeMessage ?? image.validationMessage,
    validationScore: retakeMessage ? Math.min(image.validationScore ?? 0.3, 0.28) : image.validationScore,
  })

  emit({
    type: 'failed',
    imageId,
    message: retakeMessage ?? message,
  })
}

function emit(event: ProcessingEvent): void {
  for (const listener of listeners) {
    listener(event)
  }
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

function shouldReviewWithAi(measurement: Awaited<ReturnType<typeof measureWithCv>>): boolean {
  return measurement.measurementSource === 'fallback' || measurement.confidence < 0.82
}

async function runAiAssistedMeasurement(
  image: InspectionImage,
  blob: Blob | undefined,
  pipeDiameterMm: number | undefined,
): Promise<ReturnType<typeof fuseMeasurementWithAi>> {
  try {
    const cvMeasurement = await measureWithCv({
      imageId: image.id,
      fileName: image.fileName,
      orderIndex: image.orderIndex,
      blob,
      pipeDiameterMm,
    })
    const aiReview = shouldReviewWithAi(cvMeasurement)
      ? await reviewMeasurementWithAi({
          imageId: image.id,
          fileName: image.fileName,
          mimeType: image.mimeType,
          blob,
          pipeDiameterMm,
          gapMm: cvMeasurement.originalGapMm,
          confidence: cvMeasurement.confidence,
          measurementSource: cvMeasurement.measurementSource,
          cvDebug: cvMeasurement.cvDebug,
        })
      : undefined

    return fuseMeasurementWithAi(cvMeasurement, aiReview)
  } catch (error) {
    const fallbackMeasurement: CvWorkerResponse = {
      imageId: image.id,
      originalGapMm: 0,
      status: 'REVIEW',
      confidence: 0.2,
      measurementSource: 'fallback',
      measurementNote: error instanceof Error ? error.message : 'OpenCV measurement failed before producing geometry.',
      cvDebug: {
        pipeDetected: false,
        failureStage: 'opencv-measurement-error',
        enhancementUsed: true,
      },
    }
    const aiReview = await reviewMeasurementWithAi({
      imageId: image.id,
      fileName: image.fileName,
      mimeType: image.mimeType,
      blob,
      pipeDiameterMm,
      gapMm: 0,
      confidence: 0.2,
      measurementSource: 'fallback',
      cvDebug: fallbackMeasurement.cvDebug,
    })
    const fused = fuseMeasurementWithAi(fallbackMeasurement, aiReview)

    if (fused.measurementSource === 'fallback' && fused.originalGapMm <= 0 && !aiReview.jointVisible && !aiReview.pipeOpeningVisible) {
      throw new Error(aiReview.retakeMessage ?? fallbackMeasurement.measurementNote ?? 'Retake photo before measurement.', {
        cause: error,
      })
    }

    return fused
  }
}

async function processImage(imageId: string): Promise<string | null> {
  const image = await db.inspectionImages.get(imageId)
  if (!image) {
    emit({
      type: 'failed',
      imageId,
      message: 'Queued image not found',
    })
    return null
  }

  const blobRecord = await db.inspectionBlobs.get(image.blobKey)
  const manhole = await db.manholes.get(image.manholeId)

  emit({ type: 'started', imageId })

  await db.inspectionImages.put({
    ...image,
    queueStatus: 'processing',
  })

  emit({ type: 'progress', imageId, progress: 25, message: 'Preparing image' })
  await wait(20)
  emit({ type: 'progress', imageId, progress: 60, message: image.validationStatus === 'retake' ? 'Running enhanced CV and AI review' : 'Running CV pipeline' })
  await wait(20)

  const measurement = await runAiAssistedMeasurement(image, blobRecord?.blob, manhole?.pipeDiameterMm)

  const resultId = createId()
  const result: InspectionResult = {
    id: resultId,
    imageId: image.id,
    projectId: image.projectId,
    manholeId: image.manholeId,
    jointLabel: image.jointLabel,
    originalGapMm: measurement.originalGapMm,
    finalGapMm: measurement.originalGapMm,
    status: measurement.status,
    confidence: measurement.confidence,
    measurementSource: measurement.measurementSource,
    measurementNote: measurement.measurementNote,
    cvDebug: measurement.cvDebug,
    aiReview: measurement.aiReview,
    overlayHints: measurement.overlayHints,
    measurementAudit: measurement.measurementAudit,
    processedAt: createTimestamp(),
    overrideApplied: false,
  }

  await db.transaction('rw', db.inspectionImages, db.inspectionResults, async () => {
    const existingResults = await db.inspectionResults.where('imageId').equals(image.id).toArray()
    for (const existing of existingResults) {
      await db.inspectionResults.delete(existing.id)
    }

    await db.inspectionResults.add(result)
    await db.inspectionImages.put({
      ...image,
      queueStatus: 'completed',
    })
  })

  emit({
    type: 'progress',
    imageId,
    inspectionId: resultId,
    progress: 100,
    message: measurement.measurementSource === 'fallback' ? 'Completed with estimated fallback' : 'Completed',
  })
  emit({ type: 'completed', imageId, inspectionId: resultId })

  return resultId
}

export const processor = {
  subscribe(listener: (event: ProcessingEvent) => void): () => void {
    listeners.add(listener)
    return () => {
      listeners.delete(listener)
    }
  },

  async processQueuedImages(
    manholeId: string,
    options?: ProcessOptions,
  ): Promise<ProcessBatchResult> {
    const queuedImages = await db.inspectionImages
      .where('manholeId')
      .equals(manholeId)
      .and((image) => image.queueStatus === 'queued' || image.queueStatus === 'failed')
      .sortBy('orderIndex')

    const concurrency = Math.max(1, options?.concurrency ?? 1)
    const inspectionIds: string[] = []
    let completed = 0
    let failed = 0

    for (let index = 0; index < queuedImages.length; index += concurrency) {
      const batch = queuedImages.slice(index, index + concurrency)
      const batchResults = await Promise.all(
        batch.map(async (image) => {
          try {
            return await processImage(image.id)
          } catch (error) {
            const message = error instanceof Error ? error.message : 'Processing failed'
            await failImageProcessing(image.id, message)
            return null
          }
        }),
      )

      for (const resultId of batchResults) {
        if (resultId) {
          inspectionIds.push(resultId)
          completed += 1
        } else {
          failed += 1
        }
      }
    }

    return {
      success: completed > 0,
      manholeId,
      inspectionId: inspectionIds[0],
      resultIds: inspectionIds,
      queueStatus: failed === 0 ? 'completed' : completed > 0 ? 'completed' : 'failed',
      message: completed > 0 ? undefined : 'Inspection processing failed',
      total: queuedImages.length,
      completed,
      failed,
      processed: completed,
    }
  },

  async remeasureInspection(inspectionId: string): Promise<InspectionResult> {
    const existing = await db.inspectionResults.get(inspectionId)
    if (!existing) {
      throw new Error(`Inspection result not found: ${inspectionId}`)
    }

    const image = await db.inspectionImages.get(existing.imageId)
    if (!image) {
      throw new Error(`Queued image not found for inspection: ${inspectionId}`)
    }

    const blobRecord = await db.inspectionBlobs.get(image.blobKey)
    const manhole = await db.manholes.get(image.manholeId)

    emit({ type: 'started', imageId: image.id, inspectionId })
    emit({ type: 'progress', imageId: image.id, inspectionId, progress: 40, message: 'Re-running CV measurement' })
    await wait(20)

    const measurement = await runAiAssistedMeasurement(image, blobRecord?.blob, manhole?.pipeDiameterMm)

    const updated: InspectionResult = {
      ...existing,
      originalGapMm: measurement.originalGapMm,
      finalGapMm: existing.overrideApplied ? existing.finalGapMm : measurement.originalGapMm,
      status: existing.overrideApplied ? existing.status : measurement.status,
      processedAt: createTimestamp(),
      confidence: measurement.confidence,
      measurementSource: measurement.measurementSource,
      measurementNote: measurement.measurementNote,
      cvDebug: measurement.cvDebug,
      aiReview: measurement.aiReview,
      overlayHints: measurement.overlayHints,
      measurementAudit: measurement.measurementAudit,
    }

    await db.inspectionResults.put(updated)

    emit({ type: 'progress', imageId: image.id, inspectionId, progress: 100, message: 'Re-measure complete' })
    emit({ type: 'completed', imageId: image.id, inspectionId })

    return updated
  },
}
