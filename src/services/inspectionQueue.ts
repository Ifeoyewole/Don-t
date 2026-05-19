import { db } from '../db'
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

    const queuedImages: QueuedInspectionImage[] = []

    await db.transaction('rw', db.inspectionImages, db.inspectionBlobs, async () => {
      for (const [index, file] of input.files.entries()) {
        const timestamp = createTimestamp()
        const imageId = createId()
        const blobKey = createId()
        const queuedImage: QueuedInspectionImage = {
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
        }

        await db.inspectionImages.add(queuedImage)
        await db.inspectionBlobs.add({
          id: blobKey,
          imageId,
          fileName: file.name,
          mimeType: file.type || 'application/octet-stream',
          blob: file,
          createdAt: timestamp,
        })

        queuedImages.push(queuedImage)
      }
    })

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
