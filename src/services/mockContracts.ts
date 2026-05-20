import { pipeSpecs, makeId } from './mockData'
import type {
  AppStore,
  ApplyOverrideInput,
  CreateManholeInput,
  CreateProjectInput,
  EstimateMaterialsInput,
  EstimateMaterialsResult,
  InspectionImage,
  InspectionResult,
  InspectionStatus,
  Manhole,
  ManholeInspectionSummary,
  ProcessBatchResult,
  ProcessingEvent,
  ProcessOptions,
  ProjectInspectionSummary,
  ProjectSummary,
  QueueFilesInput,
  UpdateManholeInput,
  UpdateProjectInput,
} from '../types/domain'

type StoreContext = {
  getStore: () => AppStore
  updateStore: (updater: (current: AppStore) => AppStore) => void
  emit: (event: ProcessingEvent) => void
}

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

const classifyGap = (value: number): InspectionStatus => {
  if (value < 3) return 'REVIEW'
  if (value <= 15) return 'PASS'
  if (value <= 25) return 'REVIEW'
  return 'FAIL'
}

const summarizeInspections = (inspections: InspectionResult[]): Omit<ProjectInspectionSummary, 'projectId'> => {
  const passCount = inspections.filter((item) => item.status === 'PASS').length
  const reviewCount = inspections.filter((item) => item.status === 'REVIEW').length
  const failCount = inspections.filter((item) => item.status === 'FAIL').length
  const overriddenCount = inspections.filter((item) => item.overrideApplied).length
  const flaggedJoints = inspections
    .filter((item) => item.status !== 'PASS')
    .map((item) => ({
      inspectionId: item.id,
      jointLabel: item.jointLabel,
      status: item.status,
      finalGapMm: item.finalGapMm,
      note: item.notes || 'No inspector note recorded yet.',
    }))

  return {
    totalJoints: inspections.length,
    passCount,
    reviewCount,
    failCount,
    overriddenCount,
    flaggedJoints,
  }
}

const buildProjectSummary = (store: AppStore, projectId: string): ProjectInspectionSummary => {
  const scoped = store.inspections.filter((inspection) => inspection.projectId === projectId)
  return {
    projectId,
    ...summarizeInspections(scoped),
  }
}

const buildManholeSummary = (store: AppStore, manholeId: string): ManholeInspectionSummary => {
  const scoped = store.inspections.filter((inspection) => inspection.manholeId === manholeId)
  const projectId = scoped[0]?.projectId ?? store.manholes.find((item) => item.id === manholeId)?.projectId ?? ''

  return {
    manholeId,
    projectId,
    ...summarizeInspections(scoped),
  }
}

const jointLabelForIndex = (index: number) => `${index + 1}-${index + 2}`

const formatProjectSummary = (store: AppStore, projectId: string): ProjectSummary => {
  const project = store.projects.find((item) => item.id === projectId)
  if (!project) {
    throw new Error('Project not found')
  }

  const manholes = store.manholes.filter((item) => item.projectId === projectId)
  const summary = buildProjectSummary(store, projectId)
  const completedInspections = store.queueImages.filter(
    (item) => item.projectId === projectId && item.queueStatus === 'completed',
  ).length

  let status: ProjectSummary['status'] = 'IN PROGRESS'
  if (summary.failCount > 0) status = 'FAIL'
  else if (summary.reviewCount > 0) status = 'REVIEW'
  else if (summary.totalJoints > 0) status = 'PASS'

  return {
    id: project.id,
    name: project.name,
    siteName: project.siteName,
    createdAt: project.createdAt,
    updatedAt: project.updatedAt,
    totalManholes: manholes.length,
    totalJoints: summary.totalJoints,
    completedInspections,
    failCount: summary.failCount,
    reviewCount: summary.reviewCount,
    status,
  }
}

const calculateEstimate = ({ meterRun, pipeType }: EstimateMaterialsInput): EstimateMaterialsResult => {
  const spec = pipeSpecs[pipeType]
  const pipesNeeded = Math.max(1, Math.ceil((meterRun || 0) / spec.unitLengthM))
  return {
    unitLengthM: spec.unitLengthM,
    pipesNeeded,
    jointsNeeded: pipesNeeded + 2,
  }
}

const mutateQueueImage = (queueImages: InspectionImage[], imageId: string, updates: Partial<InspectionImage>) =>
  queueImages.map((image) => (image.id === imageId ? { ...image, ...updates } : image))

const upsertInspection = (inspections: InspectionResult[], result: InspectionResult) => {
  const existingIndex = inspections.findIndex((item) => item.id === result.id)
  if (existingIndex === -1) {
    return [...inspections, result]
  }

  return inspections.map((item, index) => (index === existingIndex ? result : item))
}

const createMeasurement = (imageId: string) => {
  const seed = imageId
    .split('')
    .reduce((sum, character) => sum + character.charCodeAt(0), 0)
  const mm = Number((((seed % 33) + 2) / 1.4).toFixed(1))
  return {
    value: mm,
    confidence: Number((0.76 + ((seed % 20) / 100)).toFixed(2)),
  }
}

export const createMockServices = ({ getStore, updateStore, emit }: StoreContext) => {
  const projectService = {
    async listProjects() {
      await wait(180)
      return getStore().projects.map((project) => formatProjectSummary(getStore(), project.id))
    },
    async getProject(projectId: string) {
      await wait(120)
      return getStore().projects.find((project) => project.id === projectId) ?? null
    },
    async createProject(input: CreateProjectInput) {
      await wait(240)
      const timestamp = new Date().toISOString()
      const project = {
        id: makeId('project'),
        name: input.name.trim(),
        siteName: input.siteName?.trim(),
        createdAt: timestamp,
        updatedAt: timestamp,
      }
      updateStore((current) => ({
        ...current,
        projects: [project, ...current.projects],
      }))
      return project
    },
    async updateProject(projectId: string, input: UpdateProjectInput) {
      await wait(180)
      let updated
      updateStore((current) => {
        updated = current.projects.find((item) => item.id === projectId)
        if (!updated) return current
        const nextProject = {
          ...updated,
          ...input,
          updatedAt: new Date().toISOString(),
        }
        updated = nextProject
        return {
          ...current,
          projects: current.projects.map((item) => (item.id === projectId ? nextProject : item)),
        }
      })
      if (!updated) throw new Error('Project not found')
      return updated
    },
    async deleteProject(projectId: string) {
      await wait(180)
      updateStore((current) => ({
        projects: current.projects.filter((item) => item.id !== projectId),
        manholes: current.manholes.filter((item) => item.projectId !== projectId),
        queueImages: current.queueImages.filter((item) => item.projectId !== projectId),
        inspections: current.inspections.filter((item) => item.projectId !== projectId),
      }))
    },
  }

  const manholeService = {
    async listByProject(projectId: string) {
      await wait(150)
      return getStore().manholes.filter((manhole) => manhole.projectId === projectId)
    },
    async getManhole(manholeId: string) {
      await wait(100)
      return getStore().manholes.find((manhole) => manhole.id === manholeId) ?? null
    },
    async createManhole(input: CreateManholeInput) {
      await wait(240)
      const estimate = calculateEstimate({ meterRun: input.meterRun, pipeType: input.pipeType })
      const timestamp = new Date().toISOString()
      const spec = pipeSpecs[input.pipeType]
      const manhole: Manhole = {
        id: makeId('manhole'),
        projectId: input.projectId,
        manholeId: input.manholeId.trim(),
        type: input.type,
        meterRun: input.meterRun,
        pipeType: input.pipeType,
        pipeDiameterMm: spec.diameterMm,
        unitLengthM: estimate.unitLengthM,
        estimatedPipeCount: estimate.pipesNeeded,
        estimatedJointCount: estimate.jointsNeeded,
        createdAt: timestamp,
        updatedAt: timestamp,
      }
      updateStore((current) => ({
        ...current,
        manholes: [...current.manholes.filter((item) => item.id !== manhole.id), manhole],
      }))
      return manhole
    },
    async updateManhole(manholeId: string, input: UpdateManholeInput) {
      await wait(220)
      let updated: Manhole | undefined
      updateStore((current) => {
        const existing = current.manholes.find((item) => item.id === manholeId)
        if (!existing) return current
        const nextPipeType = input.pipeType ?? existing.pipeType
        const nextMeterRun = input.meterRun ?? existing.meterRun
        const estimate = calculateEstimate({ meterRun: nextMeterRun, pipeType: nextPipeType })
        const spec = pipeSpecs[nextPipeType]
        updated = {
          ...existing,
          ...input,
          pipeType: nextPipeType,
          meterRun: nextMeterRun,
          pipeDiameterMm: spec.diameterMm,
          unitLengthM: estimate.unitLengthM,
          estimatedPipeCount: estimate.pipesNeeded,
          estimatedJointCount: estimate.jointsNeeded,
          updatedAt: new Date().toISOString(),
        }
        return {
          ...current,
          manholes: current.manholes.map((item) => (item.id === manholeId ? updated! : item)),
        }
      })
      if (!updated) throw new Error('Manhole not found')
      return updated
    },
    async deleteManhole(manholeId: string) {
      await wait(180)
      updateStore((current) => ({
        ...current,
        manholes: current.manholes.filter((item) => item.id !== manholeId),
        queueImages: current.queueImages.filter((item) => item.manholeId !== manholeId),
        inspections: current.inspections.filter((item) => item.manholeId !== manholeId),
      }))
    },
  }

  const estimatorService = {
    async calculate(input: EstimateMaterialsInput) {
      await wait(80)
      return calculateEstimate(input)
    },
  }

  const inspectionQueue = {
    async addFiles(input: QueueFilesInput) {
      await wait(120)
      const store = getStore()
      const existing = store.queueImages.filter((item) => item.manholeId === input.manholeId)
      const queued = input.files.map((file, index) => {
        const orderIndex = existing.length + index + 1
        const item: InspectionImage = {
          id: makeId('image'),
          projectId: input.projectId,
          manholeId: input.manholeId,
          fileName: file.name,
          mimeType: file.type || 'image/jpeg',
          blobKey: makeId('blob'),
          orderIndex,
          jointLabel: jointLabelForIndex(orderIndex - 1),
          captureSource: 'upload',
          queueStatus: 'queued',
          createdAt: new Date().toISOString(),
          previewUrl: file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined,
          progress: 0,
        }
        emit({ type: 'queued', imageId: item.id, progress: 0, message: `${item.fileName} added to queue` })
        return item
      })

      updateStore((current) => ({
        ...current,
        queueImages: [...current.queueImages, ...queued],
      }))
      return queued
    },
    async removeFile(imageId: string) {
      await wait(80)
      updateStore((current) => ({
        ...current,
        queueImages: current.queueImages.filter((item) => item.id !== imageId),
        inspections: current.inspections.filter((inspection) => inspection.imageId !== imageId),
      }))
    },
    async clearManholeQueue(manholeId: string) {
      await wait(100)
      updateStore((current) => ({
        ...current,
        queueImages: current.queueImages.filter((item) => item.manholeId !== manholeId),
        inspections: current.inspections.filter((inspection) => inspection.manholeId !== manholeId),
      }))
    },
    async listQueue(manholeId: string) {
      await wait(60)
      return getStore()
        .queueImages
        .filter((item) => item.manholeId === manholeId)
        .sort((a, b) => a.orderIndex - b.orderIndex)
    },
  }

  const processor = {
    async processQueuedImages(manholeId: string, options?: ProcessOptions): Promise<ProcessBatchResult> {
      const queue = getStore()
        .queueImages
        .filter((item) => item.manholeId === manholeId)
        .sort((a, b) => a.orderIndex - b.orderIndex)

      let failed = 0
      let processed = 0

      for (const image of queue) {
        updateStore((current) => ({
          ...current,
          queueImages: mutateQueueImage(current.queueImages, image.id, {
            queueStatus: 'processing',
            progress: 12,
            errorMessage: undefined,
          }),
        }))
        emit({ type: 'started', imageId: image.id, progress: 12, message: `${image.jointLabel} processing started` })

        for (const step of [28, 53, 81]) {
          await wait(180)
          updateStore((current) => ({
            ...current,
            queueImages: mutateQueueImage(current.queueImages, image.id, { progress: step }),
          }))
          emit({ type: 'progress', imageId: image.id, progress: step, message: `Processing ${image.jointLabel}` })
        }

        if (options?.failAtImageId === image.id) {
          failed += 1
          updateStore((current) => ({
            ...current,
            queueImages: mutateQueueImage(current.queueImages, image.id, {
              queueStatus: 'failed',
              progress: 100,
              errorMessage: 'Edge detection confidence too low. Retake photo with cleaner lighting.',
            }),
          }))
          emit({ type: 'failed', imageId: image.id, progress: 100, message: `Processing failed for ${image.jointLabel}` })
          continue
        }

        const measurement = createMeasurement(image.id)
        const status = classifyGap(measurement.value)
        const inspectionId = makeId('inspection')
        const result: InspectionResult = {
          id: inspectionId,
          imageId: image.id,
          projectId: image.projectId,
          manholeId: image.manholeId,
          jointLabel: image.jointLabel,
          originalGapMm: measurement.value,
          finalGapMm: measurement.value,
          status,
          confidence: measurement.confidence,
          notes: status === 'PASS' ? 'Auto-measured within tolerance band.' : 'Auto-measured and needs inspector review.',
          processedAt: new Date().toISOString(),
          overrideApplied: false,
        }

        updateStore((current) => ({
          ...current,
          queueImages: mutateQueueImage(current.queueImages, image.id, {
            queueStatus: 'completed',
            progress: 100,
          }),
          inspections: upsertInspection(
            current.inspections.filter((inspection) => inspection.imageId !== image.id),
            result,
          ),
        }))
        emit({
          type: 'completed',
          imageId: image.id,
          inspectionId,
          progress: 100,
          message: `${image.jointLabel} measured at ${measurement.value.toFixed(1)} mm`,
        })
        processed += 1
      }

      return { manholeId, processed, failed }
    },
    async remeasureInspection(inspectionId: string) {
      await wait(220)
      let updated: InspectionResult | undefined
      updateStore((current) => {
        const inspection = current.inspections.find((item) => item.id === inspectionId)
        if (!inspection) return current
        const adjustedValue = Number(Math.max(0.5, inspection.originalGapMm - 0.4 + Math.random() * 1.1).toFixed(1))
        updated = {
          ...inspection,
          originalGapMm: adjustedValue,
          finalGapMm: inspection.overrideApplied ? inspection.finalGapMm : adjustedValue,
          status: classifyGap(inspection.overrideApplied ? inspection.finalGapMm : adjustedValue),
          confidence: Number(Math.min(0.99, inspection.confidence + 0.03).toFixed(2)),
          processedAt: new Date().toISOString(),
        }
        return {
          ...current,
          inspections: current.inspections.map((item) => (item.id === inspectionId ? updated! : item)),
        }
      })
      if (!updated) throw new Error('Inspection not found')
      return updated
    },
    subscribe(listener: (event: ProcessingEvent) => void) {
      return () => listener
    },
  }

  const inspectionService = {
    async listByManhole(manholeId: string) {
      await wait(120)
      return getStore()
        .inspections
        .filter((item) => item.manholeId === manholeId)
        .sort((a, b) => a.jointLabel.localeCompare(b.jointLabel))
    },
    async getInspection(inspectionId: string) {
      await wait(60)
      return getStore().inspections.find((item) => item.id === inspectionId) ?? null
    },
    async saveInspectorNote(inspectionId: string, note: string) {
      await wait(120)
      let updated: InspectionResult | undefined
      updateStore((current) => {
        updated = current.inspections.find((item) => item.id === inspectionId)
        if (!updated) return current
        updated = { ...updated, notes: note }
        return {
          ...current,
          inspections: current.inspections.map((item) => (item.id === inspectionId ? updated! : item)),
        }
      })
      if (!updated) throw new Error('Inspection not found')
      return updated
    },
    async applyOverride(input: ApplyOverrideInput) {
      await wait(180)
      let updated: InspectionResult | undefined
      updateStore((current) => {
        const existing = current.inspections.find((item) => item.id === input.inspectionId)
        if (!existing) return current
        updated = {
          ...existing,
          finalGapMm: input.overrideValueMm,
          status: classifyGap(input.overrideValueMm),
          overrideApplied: true,
          overrideValueMm: input.overrideValueMm,
          overrideReason: input.overrideReason.trim(),
          overrideAt: new Date().toISOString(),
        }
        return {
          ...current,
          inspections: current.inspections.map((item) => (item.id === input.inspectionId ? updated! : item)),
        }
      })
      if (!updated) throw new Error('Inspection not found')
      return updated
    },
    async clearOverride(inspectionId: string) {
      await wait(140)
      let updated: InspectionResult | undefined
      updateStore((current) => {
        const existing = current.inspections.find((item) => item.id === inspectionId)
        if (!existing) return current
        updated = {
          ...existing,
          finalGapMm: existing.originalGapMm,
          status: classifyGap(existing.originalGapMm),
          overrideApplied: false,
          overrideValueMm: undefined,
          overrideReason: undefined,
          overrideAt: undefined,
        }
        return {
          ...current,
          inspections: current.inspections.map((item) => (item.id === inspectionId ? updated! : item)),
        }
      })
      if (!updated) throw new Error('Inspection not found')
      return updated
    },
  }

  const summaryService = {
    async getProjectSummary(projectId: string) {
      await wait(120)
      return buildProjectSummary(getStore(), projectId)
    },
    async getManholeSummary(manholeId: string) {
      await wait(100)
      return buildManholeSummary(getStore(), manholeId)
    },
  }

  const exportService = {
    async exportJson(projectId: string) {
      await wait(80)
      const store = getStore()
      const payload = {
        project: store.projects.find((item) => item.id === projectId),
        manholes: store.manholes.filter((item) => item.projectId === projectId),
        queueImages: store.queueImages.filter((item) => item.projectId === projectId),
        inspections: store.inspections.filter((item) => item.projectId === projectId),
        disclaimer: 'Guidance only — not a formal adoption assessment.',
      }
      return new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    },
    async exportPdf(projectId: string) {
      await wait(80)
      const summary = buildProjectSummary(getStore(), projectId)
      const body = [
        'JointInspect Field Summary',
        `Project ID: ${projectId}`,
        `Total joints: ${summary.totalJoints}`,
        `PASS: ${summary.passCount}`,
        `REVIEW: ${summary.reviewCount}`,
        `FAIL: ${summary.failCount}`,
        'Guidance only — not a formal adoption assessment.',
      ].join('\n')
      return new Blob([body], { type: 'application/pdf' })
    },
    async exportEvidenceZip(projectId: string) {
      await wait(80)
      const body = `Evidence pack for ${projectId}\nContains local inspection metadata and image manifest.\nGuidance only — not a formal adoption assessment.`
      return new Blob([body], { type: 'application/zip' })
    },
  }

  return {
    projectService,
    manholeService,
    estimatorService,
    inspectionQueue,
    processor,
    inspectionService,
    summaryService,
    exportService,
  }
}
