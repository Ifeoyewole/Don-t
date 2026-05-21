import { db } from '../db'
import type {
  InspectionResult,
  ProcessBatchResult,
  ProcessingEvent,
  ProcessOptions,
} from '../types'
import { measureWithCv } from '../lib'
import { createId, createTimestamp } from '../utils/identity'

const listeners = new Set<(event: ProcessingEvent) => void>()

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

  if (image.validationStatus === 'retake') {
    await db.inspectionImages.put({
      ...image,
      queueStatus: 'failed',
      errorMessage: image.validationMessage ?? 'Retake photo before measurement.',
    })
    emit({
      type: 'failed',
      imageId,
      message: image.validationMessage ?? 'Retake photo before measurement.',
    })
    return null
  }

  await db.inspectionImages.put({
    ...image,
    queueStatus: 'processing',
  })

  emit({ type: 'progress', imageId, progress: 25, message: 'Preparing image' })
  await wait(20)
  emit({ type: 'progress', imageId, progress: 60, message: 'Running CV pipeline' })
  await wait(20)

  const measurement = await measureWithCv({
    imageId: image.id,
    fileName: image.fileName,
    orderIndex: image.orderIndex,
    blob: blobRecord?.blob,
    pipeDiameterMm: manhole?.pipeDiameterMm,
  })

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
            await db.inspectionImages.update(image.id, {
              queueStatus: 'failed',
              errorMessage: message,
            })
            emit({
              type: 'failed',
              imageId: image.id,
              message,
            })
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
      manholeId,
      total: queuedImages.length,
      completed,
      failed,
      inspectionIds,
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

    const measurement = await measureWithCv({
      imageId: image.id,
      fileName: image.fileName,
      orderIndex: image.orderIndex,
      blob: blobRecord?.blob,
      pipeDiameterMm: manhole?.pipeDiameterMm,
    })

    const updated: InspectionResult = {
      ...existing,
      originalGapMm: measurement.originalGapMm,
      finalGapMm: existing.overrideApplied ? existing.finalGapMm : measurement.originalGapMm,
      status: existing.overrideApplied ? existing.status : measurement.status,
      processedAt: createTimestamp(),
      confidence: measurement.confidence,
      measurementSource: measurement.measurementSource,
      measurementNote: measurement.measurementNote,
    }

    await db.inspectionResults.put(updated)

    emit({ type: 'progress', imageId: image.id, inspectionId, progress: 100, message: 'Re-measure complete' })
    emit({ type: 'completed', imageId: image.id, inspectionId })

    return updated
  },
}
