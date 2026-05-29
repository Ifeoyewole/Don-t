export type ManholeType = 'foul-water' | 'surface-water'

export type PipeType =
  | '150mm-clay'
  | '225mm-clay'
  | '300mm-concrete'
  | '450mm-concrete'
  | '600mm-concrete'
  | '900mm-concrete'

export type InspectionCaptureSource = 'upload' | 'camera'
export type QueueStatus = 'queued' | 'processing' | 'completed' | 'failed'
export type InspectionStatus = 'PASS' | 'REVIEW' | 'FAIL'
export type GuidedPhotoStatus = 'ready' | 'retake'
export type MeasurementSource = 'cv' | 'ai-assisted' | 'ai-estimated' | 'ai-review' | 'manual' | 'fallback'

export interface MeasurementOverlayHints {
  pipeCenter?: { x: number; y: number }
  innerRadiusPx?: number
  outerRadiusPx?: number
  gapLine?: { x1: number; y1: number; x2: number; y2: number }
}

export interface CvMeasurementDebug {
  pipeDetected: boolean
  imageWidth?: number
  imageHeight?: number
  innerRadiusPx?: number
  outerRadiusPx?: number
  gapPixels?: number
  mmPerPixel?: number
  visibleSectors?: number
  edgeStrength?: number
  failureStage?: string
  enhancementUsed?: boolean
  overlayHints?: MeasurementOverlayHints
}

export interface AiMeasurementReview {
  provider: 'mock-gemini' | 'gemini'
  model: string
  usable: boolean
  jointVisible: boolean
  pipeOpeningVisible: boolean
  cvPlausible: boolean
  estimatedGapMm: number | null
  confidence: number
  reason: string
  retakeMessage?: string
  overlayHints?: MeasurementOverlayHints
  reviewedAt: string
}

export interface MeasurementAudit {
  originalSource: MeasurementSource
  finalSource: MeasurementSource
  cvConfidence?: number
  aiConfidence?: number
  cvGapMm?: number
  aiEstimatedGapMm?: number | null
  enhancementUsed?: boolean
  decision: string
}

export interface Project {
  id: string
  name: string
  siteName?: string
  createdAt: string
  updatedAt: string
}

export interface ProjectSummary extends Project {
  manholeCount?: number
  inspectionCount?: number
  failCount: number
  reviewCount: number
  totalManholes?: number
  totalJoints?: number
  completedInspections?: number
  status?: InspectionStatus | 'IN PROGRESS'
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
  previewUrl?: string
  progress?: number
  errorMessage?: string
  validationStatus?: GuidedPhotoStatus
  validationMessage?: string
  validationScore?: number
}

export interface InspectionBlob {
  id: string
  imageId: string
  fileName: string
  mimeType: string
  blob: Blob
  createdAt: string
}

export type QueuedInspectionImage = InspectionImage

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
  fileName?: string
  manholeLabel?: string
  originalGapMm: number
  finalGapMm: number
  status: InspectionStatus
  confidence?: number
  measurementSource?: MeasurementSource
  measurementNote?: string
  cvDebug?: CvMeasurementDebug
  aiReview?: AiMeasurementReview
  overlayHints?: MeasurementOverlayHints
  measurementAudit?: MeasurementAudit
  previewUrl?: string
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
  unitLengthM: number
  pipesNeeded: number
  jointsNeeded: number
  pipeType?: PipeType
  pipeDiameterMm?: number
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
  failAtImageId?: string
}

export interface ProcessBatchResult {
  success: boolean
  manholeId: string
  failed: number
  inspectionId?: string
  resultIds?: string[]
  queueStatus?: QueueStatus
  message?: string
  total?: number
  completed?: number
  processed?: number
}

export interface FlaggedInspectionSummary {
  inspectionId: string
  jointLabel: string
  fileName?: string
  manholeLabel?: string
  status: InspectionStatus
  finalGapMm: number
  measurementSource?: MeasurementSource
  overrideApplied?: boolean
  note?: string
  previewUrl?: string
  processedAt?: string
  photoCount?: number
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
  projectId?: string
  manholeId: string
  totalJoints: number
  passCount: number
  reviewCount: number
  failCount: number
  overriddenCount: number
  flaggedJoints: FlaggedInspectionSummary[]
}

export interface AppStore {
  projects: Project[]
  manholes: Manhole[]
  queueImages: InspectionImage[]
  inspections: InspectionResult[]
}
