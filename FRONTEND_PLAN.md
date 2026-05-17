# FRONTEND PLAN — UI Build, Screen Flow, Service Wiring

Owner focus: screens, routing, interactions, async states, and Stitch-to-React implementation.

This document maps the Stitch handoff screens to real product pages and shows exactly which local service contracts each screen should call.

## Current Audit

### What Exists

- a working Vite + React + TypeScript shell
- `src/App.tsx` is still starter content and needs full replacement
- Stitch handoff folder contains the target screen references

### What Does Not Exist Yet

- routes
- page components
- reusable UI components
- domain types
- storage hooks
- inspection state management

## Proposed Frontend Structure

```txt
src/
  app/
  pages/
  components/
  layouts/
  hooks/
  services/
  db/
  types/
  workers/
  utils/
```

## Screen Map From Stitch

### 1. Dashboard

Stitch reference:

- `stitch_pipecheck_field_inspection_app/dashboard/code.html`

App route:

- `/`

Purpose:

- show project overview
- show recent activity
- start new project
- surface offline status

Frontend calls:

- `projectService.listProjects()`
- `summaryService.getProjectSummary(projectId)` for highlighted cards when needed

Primary actions:

- `New Project`
- `Open Project`
- `View All Projects`

## 2. Create Project

Stitch reference:

- `stitch_pipecheck_field_inspection_app/create_project/code.html`

App route:

- `/projects/new`

Purpose:

- create a project

Fields:

- project name
- site name
- created date shown as auto-generated

Frontend calls:

- `projectService.createProject(input)`

Success path:

- navigate to `/projects/:projectId/manholes/new`

## 3. Manhole Setup

Stitch reference:

- `stitch_pipecheck_field_inspection_app/manhole_setup/code.html`

App route:

- `/projects/:projectId/manholes/new`
- `/projects/:projectId/manholes/:manholeId`

Purpose:

- create or edit a manhole config
- compute materials estimate live

Fields:

- manhole ID
- type
- meter run
- pipe type

Frontend calls:

- `manholeService.createManhole(input)`
- `manholeService.updateManhole(manholeId, input)`
- `estimatorService.calculate(input)`

Success path:

- navigate to `/projects/:projectId/manholes/:manholeId/upload`

## 4. Photo Upload

Stitch reference:

- `stitch_pipecheck_field_inspection_app/photo_upload/code.html`

App route:

- `/projects/:projectId/manholes/:manholeId/upload`

Purpose:

- upload or capture multiple images
- show queue items and status
- start inspection processing

Frontend calls:

- `inspectionQueue.addFiles(input)`
- `inspectionQueue.removeFile(imageId)`
- `inspectionQueue.clearManholeQueue(manholeId)`
- `inspectionQueue.listQueue(manholeId)`
- `processor.processQueuedImages(manholeId)`
- `processor.subscribe(listener)`

UI states required:

- empty state
- queued
- processing
- completed
- failed

Success path:

- navigate to `/projects/:projectId/manholes/:manholeId/results`

## 5. Inspection Results

Stitch reference:

- `stitch_pipecheck_field_inspection_app/inspection_results/code.html`

App route:

- `/projects/:projectId/manholes/:manholeId/results`

Purpose:

- review each joint result
- add notes
- trigger re-measure
- apply overrides

Frontend calls:

- `inspectionService.listByManhole(manholeId)`
- `inspectionService.saveInspectorNote(inspectionId, note)`
- `inspectionService.applyOverride(input)`
- `inspectionService.clearOverride(inspectionId)`
- `processor.remeasureInspection(inspectionId)`
- `summaryService.getManholeSummary(manholeId)`

UI states required:

- status badge for PASS / REVIEW / FAIL
- original value
- final value
- override active indicator
- per-item error handling

Success path:

- navigate to `/projects/:projectId/summary`

## 6. Inspection Summary

Stitch reference:

- `stitch_pipecheck_field_inspection_app/inspection_summary/code.html`

App route:

- `/projects/:projectId/summary`

Purpose:

- show aggregated status counts
- list flagged items
- export evidence pack

Frontend calls:

- `summaryService.getProjectSummary(projectId)`
- `exportService.exportJson(projectId)`
- `exportService.exportPdf(projectId)`
- `exportService.exportEvidenceZip(projectId)`

## Frontend Endpoint Map

This is the frontend dev handoff contract.

| Screen | Action | Contract |
| --- | --- | --- |
| Dashboard | load projects | `projectService.listProjects()` |
| Dashboard | open project metrics | `summaryService.getProjectSummary(projectId)` |
| Create Project | save project | `projectService.createProject(input)` |
| Manhole Setup | live estimate | `estimatorService.calculate(input)` |
| Manhole Setup | save manhole | `manholeService.createManhole(input)` |
| Manhole Setup | update manhole | `manholeService.updateManhole(manholeId, input)` |
| Upload | add files | `inspectionQueue.addFiles(input)` |
| Upload | clear queue | `inspectionQueue.clearManholeQueue(manholeId)` |
| Upload | process files | `processor.processQueuedImages(manholeId)` |
| Upload | progress events | `processor.subscribe(listener)` |
| Results | load results | `inspectionService.listByManhole(manholeId)` |
| Results | save note | `inspectionService.saveInspectorNote(inspectionId, note)` |
| Results | re-measure | `processor.remeasureInspection(inspectionId)` |
| Results | apply override | `inspectionService.applyOverride(input)` |
| Results | clear override | `inspectionService.clearOverride(inspectionId)` |
| Summary | load summary | `summaryService.getProjectSummary(projectId)` |
| Summary | export JSON | `exportService.exportJson(projectId)` |
| Summary | export PDF | `exportService.exportPdf(projectId)` |
| Summary | export ZIP | `exportService.exportEvidenceZip(projectId)` |

## UX Rules To Preserve

- mobile-first layout
- high-contrast status treatment for field conditions
- touch targets at least 48px
- explicit labels above inputs
- offline banner shown consistently
- progress states for every async workflow
- no dead CTA buttons

## Copy Corrections Needed During Build

Some Stitch copy is generic or cloud-oriented. Replace it with MVP-safe wording:

- remove any implication of required cloud sync
- replace structural bridge language with pipe joint inspection language
- keep the brand style, but align terms to:
  - project
  - manhole
  - pipe type
  - joint label
  - gap measurement
  - evidence pack

## Delivery Phases

1. App shell and routes
   - replace starter app
   - set up route shell

2. Page components from Stitch
   - dashboard
   - create project
   - manhole setup
   - upload
   - results
   - summary

3. Shared UI components
   - status badge
   - offline banner
   - top app bar
   - bottom nav
   - empty state
   - progress row

4. Hook and service wiring
   - connect page actions to local services
   - add loading, error, and success states

5. QA and responsiveness
   - mobile viewport polish
   - interaction testing
   - export button verification

## Acceptance Criteria

- every Stitch screen has a matching React route
- every visible CTA has a real handler
- every async flow has a loading and failure state
- frontend calls only documented local service contracts
- wording matches the pipe inspection MVP and not a generic infrastructure dashboard
