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

    const manhole = await db.manholes.get(existing.manholeId)
    const classification = classifyGap(input.overrideValueMm, manhole?.pipeDiameterMm)
    const updated: InspectionResult = {
      ...existing,
      finalGapMm: input.overrideValueMm,
      status: classification.status,
      measurementSource: 'manual',
      overrideApplied: true,
      overrideReason: input.overrideReason.trim(),
      overrideValueMm: input.overrideValueMm,
      overrideAt: createTimestamp(),
      measurementAudit: {
        originalSource: existing.measurementAudit?.originalSource ?? existing.measurementSource ?? 'cv',
        finalSource: 'manual',
        cvConfidence: existing.measurementAudit?.cvConfidence ?? existing.confidence,
        aiConfidence: existing.measurementAudit?.aiConfidence,
        cvGapMm: existing.measurementAudit?.cvGapMm ?? existing.originalGapMm,
        aiEstimatedGapMm: existing.measurementAudit?.aiEstimatedGapMm,
        enhancementUsed: existing.measurementAudit?.enhancementUsed,
        decision: 'Inspector manually overrode the AI/CV measurement.',
      },
    }

    await db.inspectionResults.put(updated)
    return updated
  },

  async clearOverride(inspectionId: string): Promise<InspectionResult> {
    const existing = await db.inspectionResults.get(inspectionId)
    if (!existing) {
      throw new Error(`Inspection result not found: ${inspectionId}`)
    }

    const manhole = await db.manholes.get(existing.manholeId)
    const classification = classifyGap(existing.originalGapMm, manhole?.pipeDiameterMm)
    const updated: InspectionResult = {
      ...existing,
      finalGapMm: existing.originalGapMm,
      status: classification.status,
      measurementSource: existing.measurementAudit?.originalSource ?? 'cv',
      overrideApplied: false,
      overrideReason: undefined,
      overrideValueMm: undefined,
      overrideAt: undefined,
      measurementAudit: existing.measurementAudit
        ? {
            ...existing.measurementAudit,
            finalSource: existing.measurementAudit.originalSource,
            decision: 'Manual override was cleared; result returned to the original measurement source.',
          }
        : existing.measurementAudit,
    }

    await db.inspectionResults.put(updated)
    return updated
  },
}
