# ROADMAP — MVP Delivery Roadmap

This document is the high-level implementation roadmap for the Pipe Joint Inspection App MVP.

It has been aligned to the current repo state as of May 17, 2026:

- the repo is currently a single Vite + React + TypeScript app rooted at `src/`
- the `stitch_pipecheck_field_inspection_app/` folder contains the screen handoff for the frontend build
- the MVP is offline-first, so the primary "endpoints" are local service contracts, not cloud APIs

## Repo Audit Snapshot

### Current State

- `src/App.tsx` is still the default Vite starter and has not yet been replaced with product screens
- `src/main.tsx` is the standard React mount entry
- `package.json` currently includes only core React/Vite dependencies
- no `src/pages/`, `src/components/`, `src/services/`, `src/db/`, `src/workers/`, or `src/types/` folders exist yet
- Stitch handoff screens exist for:
  - dashboard
  - create project
  - manhole setup
  - photo upload
  - inspection results
  - inspection summary

### Main Documentation Drift Found

- earlier docs described a future monorepo layout with `frontend/`, `backend/`, and `shared/`
- the actual repo is not yet scaffolded that way
- some wording implied cloud sync and multi-device sync, which conflicts with the offline-first MVP brief
- "backend" work in this MVP is mostly client-side logic, storage, CV processing, and export

## Delivery Principles

- Keep the MVP fully offline-capable
- Treat IndexedDB plus Web Workers as the primary runtime platform
- Build the UI from the Stitch handoff, but align labels and logic to the pipe inspection domain
- Keep service contracts stable so frontend and logic work can proceed in parallel
- Prefer local async services that could later be mirrored by optional HTTP endpoints if needed

## Screen Flow From Stitch

1. Dashboard
   - overview metrics
   - recent projects
   - CTA to create a project

2. Create Project
   - create project record
   - capture project name, site name, created date

3. Manhole Setup
   - create or edit a manhole within a project
   - capture meter run, type, pipe spec
   - show estimator output

4. Photo Upload
   - upload or capture multiple images
   - assign sequential labels
   - queue files for processing

5. Inspection Results
   - review calculated measurements
   - add notes
   - trigger re-measure
   - apply manual override

6. Inspection Summary
   - aggregate PASS/REVIEW/FAIL totals
   - flag critical joints
   - export evidence pack

## MVP Service Contract Map

These are the frontend-facing local service endpoints for the MVP.

### Project Services

- `projectService.listProjects(): Promise<ProjectSummary[]>`
- `projectService.getProject(projectId: string): Promise<ProjectDetail | null>`
- `projectService.createProject(input: CreateProjectInput): Promise<Project>`
- `projectService.updateProject(projectId: string, input: UpdateProjectInput): Promise<Project>`
- `projectService.deleteProject(projectId: string): Promise<void>`

### Manhole Services

- `manholeService.listByProject(projectId: string): Promise<Manhole[]>`
- `manholeService.getManhole(manholeId: string): Promise<Manhole | null>`
- `manholeService.createManhole(input: CreateManholeInput): Promise<Manhole>`
- `manholeService.updateManhole(manholeId: string, input: UpdateManholeInput): Promise<Manhole>`
- `manholeService.deleteManhole(manholeId: string): Promise<void>`

### Estimator Services

- `estimatorService.calculate(input: EstimateMaterialsInput): Promise<EstimateMaterialsResult>`

### Inspection Queue Services

- `inspectionQueue.addFiles(input: QueueFilesInput): Promise<QueuedInspectionImage[]>`
- `inspectionQueue.removeFile(imageId: string): Promise<void>`
- `inspectionQueue.clearManholeQueue(manholeId: string): Promise<void>`
- `inspectionQueue.listQueue(manholeId: string): Promise<QueuedInspectionImage[]>`

### Processing Services

- `processor.processQueuedImages(manholeId: string, options?: ProcessOptions): Promise<ProcessBatchResult>`
- `processor.remeasureInspection(inspectionId: string): Promise<InspectionResult>`
- `processor.subscribe(listener: (event: ProcessingEvent) => void): Unsubscribe`

### Inspection Result Services

- `inspectionService.listByManhole(manholeId: string): Promise<InspectionResult[]>`
- `inspectionService.getInspection(inspectionId: string): Promise<InspectionResult | null>`
- `inspectionService.saveInspectorNote(inspectionId: string, note: string): Promise<InspectionResult>`
- `inspectionService.applyOverride(input: ApplyOverrideInput): Promise<InspectionResult>`
- `inspectionService.clearOverride(inspectionId: string): Promise<InspectionResult>`

### Summary Services

- `summaryService.getProjectSummary(projectId: string): Promise<ProjectInspectionSummary>`
- `summaryService.getManholeSummary(manholeId: string): Promise<ManholeInspectionSummary>`

### Export Services

- `exportService.exportJson(projectId: string): Promise<Blob>`
- `exportService.exportPdf(projectId: string): Promise<Blob>`
- `exportService.exportEvidenceZip(projectId: string): Promise<Blob>`

## Milestones

1. Foundation and Folder Scaffolding
   - replace starter app structure with product folders under `src/`
   - add routing, shared types, and service interfaces

2. Dashboard and Project Flow
   - implement dashboard and create-project screen from Stitch
   - wire project CRUD to IndexedDB

3. Manhole Setup and Estimator
   - implement manhole form
   - implement materials estimation logic and tests

4. Upload Queue and Sequential Mapping
   - implement image intake, local storage, queue state, and joint labels

5. CV Processing Worker
   - implement Web Worker processing contract
   - persist measurements and classifications

6. Results, Overrides, and Notes
   - implement inspection results screen
   - add manual override and re-measure flows

7. Summary and Export
   - implement inspection summary
   - generate JSON, PDF, and ZIP evidence bundle

8. PWA, Reliability, and QA
   - add PWA support
   - validate offline use, mobile layout, and export completeness

## Dependencies and Risks

- OpenCV.js may need tuning for accuracy and mobile performance
- browser storage limits may require image compression and export guidance
- large image batches may require concurrency caps and memory cleanup
- some Stitch copy references cloud sync; this must be rewritten to local offline-first wording in the product UI

## Definition of Done

- core flow works: project -> manhole -> upload -> process -> review -> export
- service contracts are documented and implemented consistently
- no screen depends on a remote server for MVP success
- exported evidence includes required project, manhole, image, measurement, and disclaimer data
- the UI matches the intended Stitch flow rather than the default Vite starter

## Immediate Next Actions

1. Scaffold real app folders under `src/`
2. Replace `src/App.tsx` starter content with route shell and screen placeholders
3. Implement the service contracts documented here before deep UI wiring
