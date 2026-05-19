import { db } from '../db'

export const storageMaintenanceService = {
  async cleanupOrphanedBlobs(): Promise<number> {
    const blobs = await db.inspectionBlobs.toArray()
    let removed = 0

    for (const blob of blobs) {
      const image = await db.inspectionImages.get(blob.imageId)
      if (!image) {
        await db.inspectionBlobs.delete(blob.id)
        removed += 1
      }
    }

    return removed
  },

  async cleanupOrphanedResults(): Promise<number> {
    const results = await db.inspectionResults.toArray()
    let removed = 0

    for (const result of results) {
      const image = await db.inspectionImages.get(result.imageId)
      if (!image) {
        await db.inspectionResults.delete(result.id)
        removed += 1
      }
    }

    return removed
  },

  async resetStuckProcessingImages(): Promise<number> {
    const stuckImages = await db.inspectionImages
      .filter((image) => image.queueStatus === 'processing')
      .toArray()

    for (const image of stuckImages) {
      await db.inspectionImages.update(image.id, { queueStatus: 'failed' })
    }

    return stuckImages.length
  },

  async runMaintenanceSweep(): Promise<{
    orphanedBlobsRemoved: number
    orphanedResultsRemoved: number
    resetProcessingCount: number
  }> {
    const orphanedBlobsRemoved = await this.cleanupOrphanedBlobs()
    const orphanedResultsRemoved = await this.cleanupOrphanedResults()
    const resetProcessingCount = await this.resetStuckProcessingImages()

    return {
      orphanedBlobsRemoved,
      orphanedResultsRemoved,
      resetProcessingCount,
    }
  },
}
