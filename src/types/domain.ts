export type ManholeType = 'foul-water' | 'surface-water'

export type PipeType =
  | '150mm-clay'
  | '225mm-clay'
  | '300mm-concrete'
  | '450mm-concrete'
  | '600mm-concrete'

export type InspectionCaptureSource = 'upload' | 'camera'

export type QueueStatus = 'queued' | 'processing' | 'completed' | 'failed'

export type InspectionStatus = 'PASS' | 'REVIEW' | 'FAIL'

export interface Project {
  id: string
  name: string
  siteName?: string
  createdAt: string
  updatedAt: string
}

export interface ProjectSummary extends Project {
  manholeCount: number
  inspectionCount: number
  failCount: number
  reviewCount: number
}

export interface ProjectDetail extends Project {
  manholes: Manhole[]
}

export interface CreateProjectInput {
  name: string
  siteName?: string
}

export interface UpdateProjectInput {
  name?: string
  siteName?: string
}

export interface Manhole {
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

export interface CreateManholeInput {
  projectId: string
  manholeId: string
  type: ManholeType
  meterRun: number
  pipeType: PipeType
}

export interface UpdateManholeInput {
  manholeId?: string
  type?: ManholeType
  meterRun?: number
  pipeType?: PipeType
}

export interface InspectionImage {
  id: string
  projectId: string
  manholeId: string
  fileName: string
  mimeType: string
  blobKey: string
  orderIndex: number
  jointLabel: string
  captureSource: InspectionCaptureSource
  queueStatus: QueueStatus
  createdAt: string
}

export interface InspectionBlob {
  id: string
  imageId: string
  fileName: string
  mimeType: string
  blob: Blob
  createdAt: string
}

export interface QueuedInspectionImage extends InspectionImage {
  progress?: number
  errorMessage?: string
}

export interface QueueFilesInput {
  projectId: string
  manholeId: string
  files: File[]
}

export interface InspectionResult {
  id: string
  imageId: string
  projectId: string
  manholeId: string
  jointLabel: string
  originalGapMm: number
  finalGapMm: number
  status: InspectionStatus
  confidence?: number
  notes?: string
  processedAt: string
  overrideApplied: boolean
  overrideReason?: string
  overrideValueMm?: number
  overrideAt?: string
}

export interface ApplyOverrideInput {
  inspectionId: string
  overrideValueMm: number
  overrideReason: string
}

export interface EstimateMaterialsInput {
  meterRun: number
  pipeType: PipeType
}

export interface EstimateMaterialsResult {
  pipeType: PipeType
  pipeDiameterMm: number
  unitLengthM: number
  pipesNeeded: number
  jointsNeeded: number
}

export interface ProcessingEvent {
  type: 'queued' | 'started' | 'progress' | 'completed' | 'failed'
  imageId: string
  inspectionId?: string
  progress?: number
  message?: string
}

export interface ProcessOptions {
  concurrency?: number
}

export interface ProcessBatchResult {
  manholeId: string
  total: number
  completed: number
  failed: number
  inspectionIds: string[]
}

export interface FlaggedInspectionSummary {
  inspectionId: string
  jointLabel: string
  status: InspectionStatus
  finalGapMm: number
  overrideApplied: boolean
}

export interface ProjectInspectionSummary {
  projectId: string
  totalJoints: number
  passCount: number
  reviewCount: number
  failCount: number
  overriddenCount: number
  flaggedJoints: FlaggedInspectionSummary[]
}

export interface ManholeInspectionSummary {
  manholeId: string
  totalJoints: number
  passCount: number
  reviewCount: number
  failCount: number
  overriddenCount: number
  flaggedJoints: FlaggedInspectionSummary[]
}
