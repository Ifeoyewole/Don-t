# BACKEND PLAN — Mavis (Logic / Storage / Processing)

Owner: Mavis — data, logic, storage, measurement, export, and worker orchestration.

## Purpose

This document describes backend responsibilities (client-side logic) that power the PWA, including storage, measurement engine, classification rules, and export features.

## Folders

```
src/services/
src/db/
src/lib/
src/utils/
src/workers/
src/types/
```

## Core Responsibilities

- IndexedDB storage layer (Dexie.js) for projects, manholes, inspections, images, overrides
- Project and manhole save/load APIs
- Materials estimator calculation logic (shared converters)
- Joint label generation (sequential mapping: `1-2`, `2-3`, ...)
- Tolerance classification logic (PASS/REVIEW/FAIL)
- OpenCV.js image processing orchestration (WebWorker entrypoints)
- Manual override storage and merging rules
- PDF report generation, JSON export, ZIP evidence pack generation
- Offline-first behaviors (service worker hooks, retry queues)

## Development Phases

Phase 1 — Shared types and utilities
- Create `src/types/` with canonical types (Project, Manhole, Inspection, Measurement)
- Implement `tolerance.ts` with unit-tested boundaries

Phase 2 — Storage and basic services
- Implement `db/` (Dexie) schema and CRUD services
- Add `services/projectService` and `services/manholeService`

Phase 3 — Estimator and label generator
- Implement `converters` for pipe math and `labelGenerator` for sequences
- Unit tests for math formulas and edge cases

Phase 4 — CV worker and processing pipeline
- Implement `workers/cvWorker.ts` which accepts an image buffer and returns measurement results
- Pipeline: grayscale → blur → Hough circle → canny → edge analysis → pixel gap → convert to mm
- Provide deterministic unit/integration tests using small test images

Phase 5 — Export and report generation
- Implement `exportService` to create JSON, PDF (pdf-lib), and ZIP (JSZip)
- Include metadata and images, preserve original and override values

Phase 6 — Offline reliability & QA
- Implement job queues, retry logic, and storage compaction strategies
- Add type-safe APIs for Vikky to consume via `services/` hooks

## Integration Points (with Vikky)

- Expose `services/*` methods that return promises and emit progress events
- Ensure shared `src/types/` align with Vikky's `src/types/`
- Provide mock service adapters for UI development

## Acceptance Criteria

- Storage operations complete within 200ms for CRUD on small datasets
- Tolerance logic is fully unit-tested and deterministic
- CV worker returns consistent measurement objects for test images
- Export outputs include required fields and images

## Notes for Mavis

- Keep APIs promise-based and emit progress via `EventTarget` or simple callbacks
- Maintain identical classification logic in `tolerance.ts` used by both UI and worker tests
