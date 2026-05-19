import { db } from '../db'
import type {
  InspectionResult,
  ProcessBatchResult,
  ProcessingEvent,
  ProcessOptions,
} from '../types'
import { classifyGap } from '../utils'
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

function deriveGapMm(seed: string, orderIndex: number): number {
  const hash = Array.from(seed).reduce((acc, char, index) => {
    return acc + char.charCodeAt(0) * (index + 1)
  }, 0)

  const base = (hash % 260) / 10
  const offset = (orderIndex % 3) * 0.4
  return Number((base + offset).toFixed(1))
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

  emit({ type: 'started', imageId })

  await db.inspectionImages.put({
    ...image,
    queueStatus: 'processing',
  })

  emit({ type: 'progress', imageId, progress: 25, message: 'Preparing image' })
  await wait(20)
  emit({ type: 'progress', imageId, progress: 60, message: 'Measuring joint gap' })
  await wait(20)

  const originalGapMm = deriveGapMm(image.fileName, image.orderIndex)
  const classification = classifyGap(originalGapMm)
  const resultId = createId()
  const result: InspectionResult = {
    id: resultId,
    imageId: image.id,
    projectId: image.projectId,
    manholeId: image.manholeId,
    jointLabel: image.jointLabel,
    originalGapMm,
    finalGapMm: originalGapMm,
    status: classification.status,
    confidence: 0.72,
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

  emit({ type: 'progress', imageId, inspectionId: resultId, progress: 100, message: 'Completed' })
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
            await db.inspectionImages.update(image.id, { queueStatus: 'failed' })
            emit({
              type: 'failed',
              imageId: image.id,
              message: error instanceof Error ? error.message : 'Processing failed',
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

    emit({ type: 'started', imageId: image.id, inspectionId })
    emit({ type: 'progress', imageId: image.id, inspectionId, progress: 40, message: 'Re-measuring joint gap' })
    await wait(20)

    const originalGapMm = Number((deriveGapMm(image.fileName, image.orderIndex) + 0.2).toFixed(1))
    const classification = classifyGap(originalGapMm)
    const updated: InspectionResult = {
      ...existing,
      originalGapMm,
      finalGapMm: existing.overrideApplied ? existing.finalGapMm : originalGapMm,
      status: existing.overrideApplied ? existing.status : classification.status,
      processedAt: createTimestamp(),
      confidence: 0.78,
    }

    await db.inspectionResults.put(updated)

    emit({ type: 'progress', imageId: image.id, inspectionId, progress: 100, message: 'Re-measure complete' })
    emit({ type: 'completed', imageId: image.id, inspectionId })

    return updated
  },
}
