import { db } from '../db'
import type {
  CreateManholeInput,
  Manhole,
  UpdateManholeInput,
} from '../types'
import { estimateMaterials, getPipeSpec } from '../utils'
import { createId, createTimestamp } from '../utils/identity'

export const manholeService = {
  async listByProject(projectId: string): Promise<Manhole[]> {
    return db.manholes.where('projectId').equals(projectId).sortBy('createdAt')
  },

  async getManhole(manholeId: string): Promise<Manhole | null> {
    return (await db.manholes.get(manholeId)) ?? null
  },

  async createManhole(input: CreateManholeInput): Promise<Manhole> {
    const timestamp = createTimestamp()
    const estimate = estimateMaterials({
      meterRun: input.meterRun,
      pipeType: input.pipeType,
    })
    const spec = getPipeSpec(input.pipeType)

    const manhole: Manhole = {
      id: createId(),
      projectId: input.projectId,
      manholeId: input.manholeId.trim(),
      type: input.type,
      meterRun: input.meterRun,
      pipeType: input.pipeType,
      pipeDiameterMm: spec.diameterMm,
      unitLengthM: spec.unitLengthM,
      estimatedPipeCount: estimate.pipesNeeded,
      estimatedJointCount: estimate.jointsNeeded,
      createdAt: timestamp,
      updatedAt: timestamp,
    }

    await db.manholes.add(manhole)
    return manhole
  },

  async updateManhole(manholeId: string, input: UpdateManholeInput): Promise<Manhole> {
    const existing = await db.manholes.get(manholeId)
    if (!existing) {
      throw new Error(`Manhole not found: ${manholeId}`)
    }

    const nextPipeType = input.pipeType ?? existing.pipeType
    const nextMeterRun = input.meterRun ?? existing.meterRun
    const estimate = estimateMaterials({
      meterRun: nextMeterRun,
      pipeType: nextPipeType,
    })
    const spec = getPipeSpec(nextPipeType)

    const updated: Manhole = {
      ...existing,
      manholeId: input.manholeId?.trim() ?? existing.manholeId,
      type: input.type ?? existing.type,
      meterRun: nextMeterRun,
      pipeType: nextPipeType,
      pipeDiameterMm: spec.diameterMm,
      unitLengthM: spec.unitLengthM,
      estimatedPipeCount: estimate.pipesNeeded,
      estimatedJointCount: estimate.jointsNeeded,
      updatedAt: createTimestamp(),
    }

    await db.manholes.put(updated)
    return updated
  },

  async deleteManhole(manholeId: string): Promise<void> {
    await db.transaction('rw', db.manholes, db.inspectionImages, db.inspectionResults, async () => {
      await db.manholes.delete(manholeId)

      const images = await db.inspectionImages.where('manholeId').equals(manholeId).toArray()
      for (const image of images) {
        await db.inspectionImages.delete(image.id)
      }

      const results = await db.inspectionResults.where('manholeId').equals(manholeId).toArray()
      for (const result of results) {
        await db.inspectionResults.delete(result.id)
      }
    })
  },
}
