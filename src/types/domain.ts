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
export type InspectionDomainStatus =
  | 'PIPE_JOINT_INSPECTION'
  | 'PIPE_INTERIOR_NO_JOINT'
  | 'UNRELATED_IMAGE'
  | 'AMBIGUOUS_IMAGE'
  | 'LOW_QUALITY_IMAGE'
  | 'UNSUPPORTED_IMAGE'
export type MeasurementSource = 'fastapi' | 'cv' | 'offline-preview' | 'ai-assisted' | 'ai-review' | 'manual' | 'fallback'

export type MeasurementResultStatus =
  | 'ACCEPTED_MEASUREMENT'
  | 'REVIEW_REQUIRED'
  | 'REJECTED_UNRELIABLE'

export type JointConditionClass =
  | 'NORMAL'
  | 'OPEN_JOINT'
  | 'ANGULAR_DEFLECTION'
  | 'SURFACE_DAMAGE'
  | 'DEPOSITS_OBSTACLES'
  | 'INTRUDING_SEAL'
  | 'UNKNOWN'

export interface ConfidenceBreakdown {
  totalConfidence: number
  qualityFactor: number
  geometricConsistency: number
  modelConfidence: number
  stabilityFactor: number
  failureRiskRate: number
}

export interface MeasurementOverlayHints {
  pipeCenter?: { x: number; y: number }
  innerRadiusPx?: number
  outerRadiusPx?: number
  gapLine?: { x1: number; y1: number; x2: number; y2: number }
  jointTrace?: Array<{ x: number; y: number }>
  jointEdgeA?: Array<{ x: number; y: number }>
  jointEdgeB?: Array<{ x: number; y: number }>
}

export interface CvMeasurementDebug {
  pipeDetected: boolean
  imageWidth?: number
  imageHeight?: number
  pipeDiameterMm?: number
  innerRadiusPx?: number
  outerRadiusPx?: number
  gapPixels?: number
  gapPixelSamples?: number[]
  mmPerPixel?: number
  visibleSectors?: number
  edgeStrength?: number
  failureStage?: string
  enhancementUsed?: boolean
  overlayHints?: MeasurementOverlayHints
  resultStatus?: MeasurementResultStatus
  condition?: JointConditionClass
  confidenceBreakdown?: ConfidenceBreakdown
  rejectionReason?: string
  externalClassifier?: ExternalClassifierResult
  modelComparison?: ModelComparisonResult
  classifierEvidence?: ClassifierEvidence
  calibrationProfile?: CalibrationProfile
  geometryTier?: 'ACCEPTABLE_GEOMETRY' | 'PARTIAL_REVIEW_GEOMETRY' | 'REJECTED_UNRELIABLE' | string
  candidateGapMm?: number | null
  authoritativeGapMm?: number | null
  engineeringResult?: string
  authoritativeReason?: string
  aiExplanation?: string
}

export interface CalibrationProfile {
  calibration_reference_id: string
  project_id: string
  source: string
  pipe_diameter_mm?: number | null
  camera_id?: string | null
  verified: boolean
  verified_at?: string | null
  notes?: string | null

  // camelCase aliases
  calibrationReferenceId?: string
  projectId?: string
  pipeDiameterMm?: number | null
  cameraId?: string | null
  verifiedAt?: string | null
}

export interface ClassifierEvidence {
  classifier: string
  model_id: string
  raw_prediction: string
  raw_code?: string
  confidence: number
  mapped_condition?: string | null
  mapping_status: string
  top_k: ExternalClassTopK[]
  classification_status: string
}

export interface AiMeasurementReview {
  provider: 'mock-gemini' | 'gemini' | 'mock-dev' | 'unavailable' | 'vertex'
  model: string
  usable: boolean
  jointVisible: boolean
  pipeOpeningVisible: boolean
  cvPlausible: boolean
  estimatedGapMm?: number | null
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
  resultStatus?: MeasurementResultStatus
  rejectionReason?: string
}

export interface ExternalClassTopK {
  index: number
  raw_class_name: string
  raw_class_code?: string
  score: number
  jointinspect_mapping?: string | null
}

export interface ExternalClassifierResult {
  model_id: string
  source: string
  raw_class_code?: string
  raw_class_name: string
  confidence: number
  top_k: ExternalClassTopK[]
  jointinspect_mapping?: string | null
  mapping_status: 'DIRECT' | 'GROUPED' | 'UNMAPPED' | 'AMBIGUOUS' | string
  advisory_only: boolean
  status: 'SUCCESS' | 'LOW_CONFIDENCE_CLASSIFICATION' | 'EXTERNAL_CLASSIFIER_UNAVAILABLE' | string
}

export interface ModelComparisonResult {
  wrc_baseline_prediction?: string | null
  wrc_baseline_score?: number | null
  native_model_b_prediction?: string | null
  native_model_b_score?: number | null
  vertex_observation?: string | null
  wrc_vs_native_agreement: 'AGREE' | 'DISAGREE' | 'NOT_COMPARABLE' | 'UNMAPPED' | string
  wrc_vs_vertex_agreement: 'AGREE' | 'DISAGREE' | 'NOT_COMPARABLE' | 'UNMAPPED' | string
  native_vs_vertex_agreement: 'AGREE' | 'DISAGREE' | 'NOT_COMPARABLE' | 'UNMAPPED' | string
  human_review_required: boolean
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
  resultStatus?: MeasurementResultStatus
  condition?: JointConditionClass
  confidenceBreakdown?: ConfidenceBreakdown
  rejectionReason?: string
  externalClassifier?: ExternalClassifierResult
  modelComparison?: ModelComparisonResult
  classifierEvidence?: ClassifierEvidence
  calibrationProfile?: CalibrationProfile
  geometryTier?: 'ACCEPTABLE_GEOMETRY' | 'PARTIAL_REVIEW_GEOMETRY' | 'REJECTED_UNRELIABLE' | string
  candidateGapMm?: number | null
  authoritativeGapMm?: number | null
  engineeringResult?: string
  authoritativeReason?: string
  aiExplanation?: string
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
  operatorContext?: string
  calibrationSource?: string
  calibrationVerified?: boolean
  calibrationReferenceId?: string
  projectId?: string
  pipeDiameterMm?: number
  calibrationProfile?: CalibrationProfile
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
