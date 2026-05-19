import { db } from '../db'
import type {
  ApplyOverrideInput,
  InspectionResult,
} from '../types'
import { classifyGap } from '../utils'
import { createTimestamp } from '../utils/identity'

export const inspectionService = {
  async listByManhole(manholeId: string): Promise<InspectionResult[]> {
    return db.inspectionResults.where('manholeId').equals(manholeId).sortBy('processedAt')
  },

  async getInspection(inspectionId: string): Promise<InspectionResult | null> {
    return (await db.inspectionResults.get(inspectionId)) ?? null
  },

  async saveInspectorNote(
    inspectionId: string,
    note: string,
  ): Promise<InspectionResult> {
    const existing = await db.inspectionResults.get(inspectionId)
    if (!existing) {
      throw new Error(`Inspection result not found: ${inspectionId}`)
    }

    const updated: InspectionResult = {
      ...existing,
      notes: note.trim() || undefined,
    }

    await db.inspectionResults.put(updated)
    return updated
  },

  async applyOverride(input: ApplyOverrideInput): Promise<InspectionResult> {
    const existing = await db.inspectionResults.get(input.inspectionId)
    if (!existing) {
      throw new Error(`Inspection result not found: ${input.inspectionId}`)
    }

    const classification = classifyGap(input.overrideValueMm)
    const updated: InspectionResult = {
      ...existing,
      finalGapMm: input.overrideValueMm,
      status: classification.status,
      overrideApplied: true,
      overrideReason: input.overrideReason.trim(),
      overrideValueMm: input.overrideValueMm,
      overrideAt: createTimestamp(),
    }

    await db.inspectionResults.put(updated)
    return updated
  },

  async clearOverride(inspectionId: string): Promise<InspectionResult> {
    const existing = await db.inspectionResults.get(inspectionId)
    if (!existing) {
      throw new Error(`Inspection result not found: ${inspectionId}`)
    }

    const classification = classifyGap(existing.originalGapMm)
    const updated: InspectionResult = {
      ...existing,
      finalGapMm: existing.originalGapMm,
      status: classification.status,
      overrideApplied: false,
      overrideReason: undefined,
      overrideValueMm: undefined,
      overrideAt: undefined,
    }

    await db.inspectionResults.put(updated)
    return updated
  },
}
