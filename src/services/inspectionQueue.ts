import { db } from '../db'
import { validateGuidedPhoto } from '../lib/photoValidation'
import type { QueueFilesInput, QueuedInspectionImage } from '../types'
import { createJointLabels } from '../utils'
import { createId, createTimestamp } from '../utils/identity'

function inferCaptureSource(file: File): 'camera' | 'upload' {
  return file.type.startsWith('image/') ? 'upload' : 'upload'
}

export const inspectionQueue = {
  async addFiles(input: QueueFilesInput): Promise<QueuedInspectionImage[]> {
    const existingCount = await db.inspectionImages.where('manholeId').equals(input.manholeId).count()
    const labels = createJointLabels(input.files.length, existingCount + 1)
    const validations = await Promise.all(input.files.map((file) => validateGuidedPhoto(file)))
    const queuedImages: QueuedInspectionImage[] = input.files.map((file, index) => {
      const timestamp = createTimestamp()
      const imageId = createId()
      const blobKey = createId()
      const validation = validations[index]

      return {
        id: imageId,
        projectId: input.projectId,
        manholeId: input.manholeId,
        fileName: file.name,
        mimeType: file.type || 'application/octet-stream',
        blobKey,
        orderIndex: existingCount + index,
        jointLabel: labels[index],
        captureSource: inferCaptureSource(file),
        queueStatus: 'queued',
        createdAt: timestamp,
        progress: 0,
        validationStatus: validation.status,
        validationMessage: validation.message,
        validationScore: validation.score,
      }
    })

    const blobRecords = input.files.map((file, index) => ({
      id: queuedImages[index].blobKey,
      imageId: queuedImages[index].id,
      fileName: file.name,
      mimeType: file.type || 'application/octet-stream',
      blob: file,
      createdAt: queuedImages[index].createdAt,
    }))

    try {
      await db.inspectionImages.bulkAdd(queuedImages)
      await db.inspectionBlobs.bulkAdd(blobRecords)
    } catch (error) {
      await Promise.allSettled(queuedImages.map((image) => db.inspectionImages.delete(image.id)))
      await Promise.allSettled(blobRecords.map((record) => db.inspectionBlobs.delete(record.id)))
      throw error
    }

    return queuedImages
  },

  async removeFile(imageId: string): Promise<void> {
    await db.transaction('rw', db.inspectionImages, db.inspectionBlobs, db.inspectionResults, async () => {
      const image = await db.inspectionImages.get(imageId)
      if (!image) {
        return
      }

      await db.inspectionImages.delete(imageId)
      await db.inspectionBlobs.delete(image.blobKey)

      const results = await db.inspectionResults.where('imageId').equals(imageId).toArray()
      for (const result of results) {
        await db.inspectionResults.delete(result.id)
      }
    })
  },

  async clearManholeQueue(manholeId: string): Promise<void> {
    await db.transaction('rw', db.inspectionImages, db.inspectionBlobs, db.inspectionResults, async () => {
      const images = await db.inspectionImages.where('manholeId').equals(manholeId).toArray()
      for (const image of images) {
        await db.inspectionImages.delete(image.id)
        await db.inspectionBlobs.delete(image.blobKey)
      }

      const results = await db.inspectionResults.where('manholeId').equals(manholeId).toArray()
      for (const result of results) {
        await db.inspectionResults.delete(result.id)
      }
    })
  },

  async listQueue(manholeId: string): Promise<QueuedInspectionImage[]> {
    const images = await db.inspectionImages.where('manholeId').equals(manholeId).sortBy('orderIndex')
    return images.map((image) => ({ ...image, progress: image.queueStatus === 'completed' ? 100 : 0 }))
  },
}
