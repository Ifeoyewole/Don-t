# IMPLEMENTATION GUIDE — Source of Truth for MVP Build

This guide aligns the product brief, the Stitch folder, and the current repo state.

## Key Decision

The MVP should be implemented as a single offline-first frontend application rooted in `src/`.

That means:

- no required backend server
- no required remote API
- no required monorepo split yet
- frontend and "backend logic" can live in the same codebase behind clear service boundaries

## Current Repo Reality

As of May 17, 2026:

- the repo is a single Vite + React + TypeScript project
- `src/App.tsx` is still starter content
- the Stitch folder is the main UI handoff for the frontend developer
- the current docs previously over-described future structure that does not yet exist

## Recommended Build Architecture

```txt
src/
  app/
  pages/
  components/
  layouts/
  hooks/
  services/
  db/
  workers/
  types/
  utils/
```

## Product Modules

1. Project Management
2. Manhole Management
3. Materials Pre-Estimator
4. Pipe Joint Inspection Upload
5. Sequential Joint Mapping
6. CV Measurement Engine
7. Tolerance Classification
8. Manual Override
9. Bulk Processing
10. Offline Storage
11. Summary Dashboard
12. Report and Evidence Export
13. PWA / Offline Runtime

## Stitch-to-Product Mapping

| Stitch screen | Product page | Route |
| --- | --- | --- |
| `dashboard` | Field overview | `/` |
| `create_project` | Create project | `/projects/new` |
| `manhole_setup` | Manhole setup | `/projects/:projectId/manholes/new` |
| `photo_upload` | Upload evidence | `/projects/:projectId/manholes/:manholeId/upload` |
| `inspection_results` | Review results | `/projects/:projectId/manholes/:manholeId/results` |
| `inspection_summary` | Export summary | `/projects/:projectId/summary` |

## Service Contract Map

These are the stable interfaces the app should build around.

### Project

- `projectService.listProjects()`
- `projectService.getProject(projectId)`
- `projectService.createProject(input)`
- `projectService.updateProject(projectId, input)`
- `projectService.deleteProject(projectId)`

### Manhole

- `manholeService.listByProject(projectId)`
- `manholeService.getManhole(manholeId)`
- `manholeService.createManhole(input)`
- `manholeService.updateManhole(manholeId, input)`
- `manholeService.deleteManhole(manholeId)`

### Estimator

- `estimatorService.calculate(input)`

### Queue and Processing

- `inspectionQueue.addFiles(input)`
- `inspectionQueue.removeFile(imageId)`
- `inspectionQueue.clearManholeQueue(manholeId)`
- `inspectionQueue.listQueue(manholeId)`
- `processor.processQueuedImages(manholeId, options?)`
- `processor.remeasureInspection(inspectionId)`
- `processor.subscribe(listener)`

### Results and Overrides

- `inspectionService.listByManhole(manholeId)`
- `inspectionService.getInspection(inspectionId)`
- `inspectionService.saveInspectorNote(inspectionId, note)`
- `inspectionService.applyOverride(input)`
- `inspectionService.clearOverride(inspectionId)`

### Summary and Export

- `summaryService.getProjectSummary(projectId)`
- `summaryService.getManholeSummary(manholeId)`
- `exportService.exportJson(projectId)`
- `exportService.exportPdf(projectId)`
- `exportService.exportEvidenceZip(projectId)`

## Data Flow

1. User creates a project
2. User creates a manhole under the project
3. Estimator calculates pipes and joints from meter run and pipe spec
4. User uploads multiple images
5. Queue assigns sequential labels like `1-2`, `2-3`, `3-4`
6. Worker processes each image and returns gap measurement
7. Tolerance engine classifies result
8. User adds notes or overrides result if needed
9. Summary aggregates counts and flagged items
10. Export generates JSON, PDF, and ZIP evidence pack

## Offline Storage Design

Use IndexedDB through Dexie with these logical tables:

- `projects`
- `manholes`
- `inspectionImages`
- `inspectionResults`
- `overrides`
- `exportJobs` if export staging is needed

## Domain Rules

### Pipe Unit Lengths

| Pipe Type | Unit Length |
| --- | --- |
| `150mm-clay` | `1.75m` |
| `225mm-clay` | `2.0m` |
| `300mm-concrete` | `2.6m` |
| `450mm-concrete` | `2.6m` |
| `600mm-concrete` | `2.6m` |

### Estimator Formulas

- `pipesNeeded = ceil(distance / unitLength)`
- `jointsNeeded = pipesNeeded + 2`

### Tolerance Rules

| Gap Width | Status |
| --- | --- |
| `< 3mm` | `REVIEW` |
| `3mm - 15mm` | `PASS` |
| `> 15mm - 25mm` | `REVIEW` |
| `> 25mm` | `FAIL` |

### Override Rules

- original measured result must always be preserved
- final result may differ from original if override is applied
- override requires reason text

## Frontend Handoff Notes

The frontend developer should treat the Stitch folder as visual reference only, not final product copy.

### Keep

- layout rhythm
- visual hierarchy
- status-driven cards
- mobile-first spacing
- strong CTA visibility

### Change

- replace generic structural bridge copy with pipe inspection wording
- remove cloud-sync claims
- replace fake metrics with real project/manhole/result data
- wire every button to a route or service call

## Build Order

1. Create route shell and folders
2. Replace starter `App.tsx`
3. Build page skeletons for all Stitch screens
4. Define types and service interfaces
5. Implement IndexedDB and estimator
6. Implement upload queue and worker contract
7. Implement results, override, and summary flows
8. Implement export and PWA behavior

## Audit Summary

### Documentation Issues Fixed In This Pass

- corrected the architecture from future monorepo language to current single-app reality
- clarified that the MVP has local service contracts instead of remote endpoints
- mapped each Stitch screen to a route and service calls
- aligned frontend and backend plans to the same contract surface

### Remaining Repo Work

- actual app scaffolding is still pending
- routes and services still need to be created
- Stitch UI still needs to be ported into React components

## Recommended Next Build Step

Start by replacing `src/App.tsx` with a routed application shell and page placeholders for the six Stitch-backed screens. That creates the clean seam both frontend and logic work can build against.
