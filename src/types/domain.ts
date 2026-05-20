export type ManholeType = 'foul-water' | 'surface-water'

export type PipeType =
  | '150mm-clay'
  | '225mm-clay'
  | '300mm-concrete'
  | '450mm-concrete'
  | '600mm-concrete'

export type QueueStatus = 'queued' | 'processing' | 'completed' | 'failed'
export type InspectionStatus = 'PASS' | 'REVIEW' | 'FAIL'

export type Project = {
  id: string
  name: string
  siteName?: string
  createdAt: string
  updatedAt: string
}

export type Manhole = {
  id: string
  projectId: string
  manholeId: string
  type: ManholeType
  meterRun: number
  pipeType: PipeType
  pipeDiameterMm: number
  unitLengthM: number
  estimatedPipeCount: number
  estimatedJointCount: number
  createdAt: string
  updatedAt: string
}

export type InspectionImage = {
  id: string
  projectId: string
  manholeId: string
  fileName: string
  mimeType: string
  blobKey: string
  orderIndex: number
  jointLabel: string
  captureSource: 'upload' | 'camera'
  queueStatus: QueueStatus
  createdAt: string
  previewUrl?: string
  progress?: number
  errorMessage?: string
}

export type InspectionResult = {
  id: string
  imageId: string
  projectId: string
  manholeId: string
  jointLabel: string
  originalGapMm: number
  finalGapMm: number
  status: InspectionStatus
  confidence: number
  notes: string
  processedAt: string
  overrideApplied: boolean
  overrideReason?: string
  overrideValueMm?: number
  overrideAt?: string
}

export type FlaggedJoint = {
  inspectionId: string
  jointLabel: string
  status: InspectionStatus
  finalGapMm: number
  note: string
}

export type ProjectSummary = {
  id: string
  name: string
  siteName?: string
  createdAt: string
  updatedAt: string
  totalManholes: number
  totalJoints: number
  completedInspections: number
  failCount: number
  reviewCount: number
  status: InspectionStatus | 'IN PROGRESS'
}

export type ProjectInspectionSummary = {
  projectId: string
  totalJoints: number
  passCount: number
  reviewCount: number
  failCount: number
  overriddenCount: number
  flaggedJoints: FlaggedJoint[]
}

export type ManholeInspectionSummary = ProjectInspectionSummary & {
  manholeId: string
}

export type EstimateMaterialsInput = {
  meterRun: number
  pipeType: PipeType
}

export type EstimateMaterialsResult = {
  unitLengthM: number
  pipesNeeded: number
  jointsNeeded: number
}

export type CreateProjectInput = {
  name: string
  siteName?: string
}

export type UpdateProjectInput = Partial<CreateProjectInput>

export type CreateManholeInput = {
  projectId: string
  manholeId: string
  type: ManholeType
  meterRun: number
  pipeType: PipeType
}

export type UpdateManholeInput = Partial<CreateManholeInput>

export type QueueFilesInput = {
  projectId: string
  manholeId: string
  files: File[]
}

export type ApplyOverrideInput = {
  inspectionId: string
  overrideValueMm: number
  overrideReason: string
}

export type ProcessOptions = {
  failAtImageId?: string
}

export type ProcessBatchResult = {
  manholeId: string
  processed: number
  failed: number
}

export type ProcessingEvent = {
  type: 'queued' | 'started' | 'progress' | 'completed' | 'failed'
  imageId: string
  inspectionId?: string
  progress?: number
  message?: string
}

export type AppStore = {
  projects: Project[]
  manholes: Manhole[]
  queueImages: InspectionImage[]
  inspections: InspectionResult[]
}
