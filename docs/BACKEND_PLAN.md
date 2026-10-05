# BACKEND PLAN — Logic, Storage, Processing, Export

Owner focus: data, storage, measurement logic, processing orchestration, summaries, and export.

For this MVP, "backend" means client-side application logic. There is no required remote server. The backend-facing work lives inside the browser runtime through services, IndexedDB, and Web Workers.

## Scope Clarification

### In Scope

- IndexedDB persistence
- domain types and validation helpers
- estimator formulas
- joint sequence label generation
- tolerance classification
- image queue management
- Web Worker processing contract
- manual override persistence rules
- summaries and evidence export

### Out of Scope for MVP

- cloud sync
- user accounts
- remote APIs
- central database
- multi-device live synchronization

## Recommended Source Layout

Create and own these folders inside `src/`:

```txt
src/types/
src/db/
src/services/
src/workers/
src/lib/
src/utils/
```

## Canonical Domain Model

### Project

- `id`
- `name`
- `siteName`
- `createdAt`
- `updatedAt`

### Manhole

- `id`
- `projectId`
- `manholeId`
- `type` = `foul-water | surface-water`
- `meterRun`
- `pipeType`
- `pipeDiameterMm`
- `unitLengthM`
- `estimatedPipeCount`
- `estimatedJointCount`
- `createdAt`
- `updatedAt`

### Inspection Image

- `id`
- `projectId`
- `manholeId`
- `fileName`
- `mimeType`
- `blobKey`
- `orderIndex`
- `jointLabel`
- `captureSource` = `upload | camera`
- `queueStatus` = `queued | processing | completed | failed`
- `createdAt`

### Inspection Result

- `id`
- `imageId`
- `projectId`
- `manholeId`
- `jointLabel`
- `originalGapMm`
- `finalGapMm`
- `status` = `PASS | REVIEW | FAIL`
- `confidence`
- `notes`
- `processedAt`
- `overrideApplied`
- `overrideReason`
- `overrideValueMm`
- `overrideAt`

## Frontend-Facing Service Endpoints

These are the contracts the frontend should code against.

## `projectService`

- `listProjects(): Promise<ProjectSummary[]>`
- `getProject(projectId: string): Promise<ProjectDetail | null>`
- `createProject(input: CreateProjectInput): Promise<Project>`
- `updateProject(projectId: string, input: UpdateProjectInput): Promise<Project>`
- `deleteProject(projectId: string): Promise<void>`

### `CreateProjectInput`

- `name: string`
- `siteName?: string`

## `manholeService`

- `listByProject(projectId: string): Promise<Manhole[]>`
- `getManhole(manholeId: string): Promise<Manhole | null>`
- `createManhole(input: CreateManholeInput): Promise<Manhole>`
- `updateManhole(manholeId: string, input: UpdateManholeInput): Promise<Manhole>`
- `deleteManhole(manholeId: string): Promise<void>`

### `CreateManholeInput`

- `projectId: string`
- `manholeId: string`
- `type: 'foul-water' | 'surface-water'`
- `meterRun: number`
- `pipeType: '150mm-clay' | '225mm-clay' | '300mm-concrete' | '450mm-concrete' | '600mm-concrete'`

## `estimatorService`

- `calculate(input: EstimateMaterialsInput): Promise<EstimateMaterialsResult>`

### `EstimateMaterialsInput`

- `meterRun: number`
- `pipeType: PipeType`

### `EstimateMaterialsResult`

- `unitLengthM: number`
- `pipesNeeded: number`
- `jointsNeeded: number`

### Formula Rules

- `pipesNeeded = ceil(meterRun / unitLengthM)`
- `jointsNeeded = pipesNeeded + 2`

## `inspectionQueue`

- `addFiles(input: QueueFilesInput): Promise<QueuedInspectionImage[]>`
- `removeFile(imageId: string): Promise<void>`
- `clearManholeQueue(manholeId: string): Promise<void>`
- `listQueue(manholeId: string): Promise<QueuedInspectionImage[]>`

### `QueueFilesInput`

- `projectId: string`
- `manholeId: string`
- `files: File[]`

### Queue Behavior

- preserve upload order
- generate `orderIndex`
- generate sequential `jointLabel` values like `1-2`, `2-3`, `3-4`
- persist original files before processing starts

## `processor`

- `processQueuedImages(manholeId: string, options?: ProcessOptions): Promise<ProcessBatchResult>`
- `remeasureInspection(inspectionId: string): Promise<InspectionResult>`
- `subscribe(listener: (event: ProcessingEvent) => void): () => void`

### Processing Pipeline

1. image normalization
2. grayscale conversion
3. blur / noise reduction
4. pipe circle detection
5. edge extraction
6. pixel gap measurement
7. pixel-to-mm conversion
8. tolerance classification
9. persistence of result object

### `ProcessingEvent`

- `type: 'queued' | 'started' | 'progress' | 'completed' | 'failed'`
- `imageId: string`
- `inspectionId?: string`
- `progress?: number`
- `message?: string`

## `inspectionService`

- `listByManhole(manholeId: string): Promise<InspectionResult[]>`
- `getInspection(inspectionId: string): Promise<InspectionResult | null>`
- `saveInspectorNote(inspectionId: string, note: string): Promise<InspectionResult>`
- `applyOverride(input: ApplyOverrideInput): Promise<InspectionResult>`
- `clearOverride(inspectionId: string): Promise<InspectionResult>`

### `ApplyOverrideInput`

- `inspectionId: string`
- `overrideValueMm: number`
- `overrideReason: string`

### Override Rules

- preserve original measured value
- set `finalGapMm` to override value
- mark `overrideApplied = true`
- preserve override timestamp and reason

## `summaryService`

- `getProjectSummary(projectId: string): Promise<ProjectInspectionSummary>`
- `getManholeSummary(manholeId: string): Promise<ManholeInspectionSummary>`

### Summary Output Must Include

- total joints
- PASS count
- REVIEW count
- FAIL count
- overridden result count
- flagged joints list

## `exportService`

- `exportJson(projectId: string): Promise<Blob>`
- `exportPdf(projectId: string): Promise<Blob>`
- `exportEvidenceZip(projectId: string): Promise<Blob>`

### Export Payload Must Include

- project details
- manhole details
- timestamps
- uploaded images
- measurements
- final statuses
- notes
- override metadata
- footer disclaimer:
  - `Guidance only — not a formal adoption assessment.`

## Tolerance Rules

These rules should live in one shared utility and be reused everywhere:

| Gap Width | Status | Meaning |
| --- | --- | --- |
| `< 3mm` | `REVIEW` | gap too small |
| `3mm - 15mm` | `PASS` | within tolerance |
| `> 15mm - 25mm` | `REVIEW` | larger than typical |
| `> 25mm` | `FAIL` | excessive gap |

## Delivery Phases

1. Types and constants
   - define domain model and pipe spec table
   - implement tolerance utility

2. Persistence layer
   - define Dexie schema
   - implement CRUD repositories

3. Estimator and label generator
   - material formulas
   - sequential joint label generation

4. Queue and worker orchestration
   - image queue persistence
   - evented worker interface

5. Result mutation flows
   - notes
   - override handling
   - re-measure action

6. Summary and export
   - aggregate stats
   - JSON, PDF, ZIP exports

## Acceptance Criteria

- every frontend action has a documented service contract
- CRUD operations are deterministic and promise-based
- tolerance logic is unit-testable and reused consistently
- queue order remains stable for sequential joint mapping
- override flow never destroys original measurement data
- exported evidence contains all mandatory data and disclaimer text
