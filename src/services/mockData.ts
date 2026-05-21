import type {
  AppStore,
  InspectionResult,
  Manhole,
  PipeType,
  Project,
} from '../types/domain'

const now = '2026-05-20T08:15:00.000Z'

const projects: Project[] = [
  {
    id: 'project-north-basin',
    name: 'North Basin Relief Main',
    siteName: 'Terminal 4 drainage corridor',
    createdAt: '2026-05-18T06:45:00.000Z',
    updatedAt: '2026-05-20T07:12:00.000Z',
  },
  {
    id: 'project-riverside',
    name: 'Riverside Joint Renewal',
    siteName: 'Sector C interceptor run',
    createdAt: '2026-05-14T10:20:00.000Z',
    updatedAt: now,
  },
]

const manholes: Manhole[] = [
  {
    id: 'manhole-nb-1',
    projectId: 'project-north-basin',
    manholeId: 'MH-204',
    type: 'surface-water',
    meterRun: 22.5,
    pipeType: '225mm-clay',
    pipeDiameterMm: 225,
    unitLengthM: 2,
    estimatedPipeCount: 12,
    estimatedJointCount: 14,
    createdAt: '2026-05-18T07:20:00.000Z',
    updatedAt: '2026-05-20T07:12:00.000Z',
  },
  {
    id: 'manhole-rv-1',
    projectId: 'project-riverside',
    manholeId: 'MH-117',
    type: 'foul-water',
    meterRun: 18,
    pipeType: '300mm-concrete',
    pipeDiameterMm: 300,
    unitLengthM: 2.6,
    estimatedPipeCount: 7,
    estimatedJointCount: 9,
    createdAt: '2026-05-14T11:00:00.000Z',
    updatedAt: now,
  },
]

const inspections: InspectionResult[] = [
  {
    id: 'inspection-1',
    imageId: 'seed-image-1',
    projectId: 'project-north-basin',
    manholeId: 'manhole-nb-1',
    jointLabel: '1-2',
    originalGapMm: 4.8,
    finalGapMm: 4.8,
    status: 'PASS',
    confidence: 0.96,
    notes: 'Clean joint edge and stable ring alignment.',
    processedAt: '2026-05-20T07:05:00.000Z',
    overrideApplied: false,
  },
  {
    id: 'inspection-2',
    imageId: 'seed-image-2',
    projectId: 'project-north-basin',
    manholeId: 'manhole-nb-1',
    jointLabel: '2-3',
    originalGapMm: 2.4,
    finalGapMm: 2.4,
    status: 'REVIEW',
    confidence: 0.82,
    notes: 'Potential shadowing along lower left quadrant.',
    processedAt: '2026-05-20T07:07:00.000Z',
    overrideApplied: false,
  },
  {
    id: 'inspection-3',
    imageId: 'seed-image-3',
    projectId: 'project-riverside',
    manholeId: 'manhole-rv-1',
    jointLabel: '1-2',
    originalGapMm: 28.4,
    finalGapMm: 26.1,
    status: 'FAIL',
    confidence: 0.91,
    notes: 'Override applied after second visual confirmation.',
    processedAt: '2026-05-20T08:00:00.000Z',
    overrideApplied: true,
    overrideReason: 'Inspector confirmed chipped edge did not affect final seating.',
    overrideValueMm: 26.1,
    overrideAt: '2026-05-20T08:04:00.000Z',
  },
]

export const pipeSpecs: Record<PipeType, { label: string; unitLengthM: number; diameterMm: number }> = {
  '150mm-clay': { label: '150 mm (clay) - 1.75m', unitLengthM: 1.75, diameterMm: 150 },
  '225mm-clay': { label: '225 mm (clay) - 2m', unitLengthM: 2, diameterMm: 225 },
  '300mm-concrete': { label: '300 mm (concrete) - 2.6m', unitLengthM: 2.6, diameterMm: 300 },
  '450mm-concrete': { label: '450 mm (concrete) - 2.6m', unitLengthM: 2.6, diameterMm: 450 },
  '600mm-concrete': { label: '600 mm (concrete) - 2.6m', unitLengthM: 2.6, diameterMm: 600 },
  '900mm-concrete': { label: '900 mm (concrete)', unitLengthM: 2.6, diameterMm: 900 },
}

export const createInitialStore = (): AppStore => ({
  projects,
  manholes,
  queueImages: [
    {
      id: 'seed-image-1',
      projectId: 'project-north-basin',
      manholeId: 'manhole-nb-1',
      fileName: 'mh204_joint_1-2.jpg',
      mimeType: 'image/jpeg',
      blobKey: 'seed-1',
      orderIndex: 1,
      jointLabel: '1-2',
      captureSource: 'upload',
      queueStatus: 'completed',
      createdAt: '2026-05-20T06:58:00.000Z',
      progress: 100,
    },
    {
      id: 'seed-image-2',
      projectId: 'project-north-basin',
      manholeId: 'manhole-nb-1',
      fileName: 'mh204_joint_2-3.jpg',
      mimeType: 'image/jpeg',
      blobKey: 'seed-2',
      orderIndex: 2,
      jointLabel: '2-3',
      captureSource: 'upload',
      queueStatus: 'completed',
      createdAt: '2026-05-20T06:59:00.000Z',
      progress: 100,
    },
    {
      id: 'seed-image-3',
      projectId: 'project-riverside',
      manholeId: 'manhole-rv-1',
      fileName: 'mh117_joint_1-2.jpg',
      mimeType: 'image/jpeg',
      blobKey: 'seed-3',
      orderIndex: 1,
      jointLabel: '1-2',
      captureSource: 'upload',
      queueStatus: 'completed',
      createdAt: '2026-05-20T07:55:00.000Z',
      progress: 100,
    },
  ],
  inspections,
})

export const makeId = (prefix: string) =>
  `${prefix}-${Math.random().toString(36).slice(2, 10)}`
