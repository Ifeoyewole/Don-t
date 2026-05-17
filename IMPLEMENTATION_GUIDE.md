**Implementation Guide — Frontend / Backend Split**

This document describes an implementation plan for the Pipe Joint Inspection App MVP split into a Frontend (PWA + CV) and a Backend (optional local/CLI components), and explains how to keep both sides aligned with the repo workflow and CI.

**Project Principles**:
- **Frontend-first MVP:** full offline PWA that performs all core functionality inside the browser (IndexedDB, WebWorkers, OpenCV.js).
- **Backend (optional):** small Node.js CLI or local service used for heavy processing, test harnesses, or future server sync. Not required for the core offline MVP.
- **Single source of truth:** shared TypeScript types and validation logic in a `shared/` package to avoid duplication.

**Top-level repo layout (recommended)**

- `frontend/` — React + TypeScript + Vite PWA app (production build produces `dist/`).
- `backend/` — Optional Node service or CLI written in TypeScript (transpiled to `dist/`).
- `shared/` — TypeScript library for types, tolerance rules, measurement converters, and tests.
- `.github/workflows/ci.yml` — CI builds/tests both packages.
- `package.json` (root) — workspace scripts to build/test both packages, or simple pass-through scripts.

Example filesystem:

```
frontend/
  src/
    app/
    features/
      projects/
      manholes/
      estimator/
      inspection/
      dashboard/
      export/
    workers/
      cvWorker.ts
    libs/
      indexeddb.ts
      pwa.ts
  public/
  vite.config.ts
  package.json

backend/
  src/
    cli.ts
    worker.ts
    api/
      process.ts
  package.json

shared/
  src/
    types.ts
    tolerance.ts
    converters.ts
  package.json

IMPLEMENTATION_GUIDE.md
.github/workflows/ci.yml
README.md
```

**Frontend: Implementation Tasks**

- **Tech stack:** React + TypeScript + Vite, Tailwind CSS, OpenCV.js (WASM), Dexie.js for IndexedDB, vite-plugin-pwa.
- **PWA & offline:** Implement service worker with caching strategy: app shell cached, runtime caching for images, background sync for optional upload attempts.
- **IndexedDB model:** Use `Dexie` with tables: `projects`, `manholes`, `inspections`, `images`, `overrides`.
- **Project / Manhole UI:** CRUD screens, selecting active project/manhole before inspection. Persist creation time and metadata.
- **Materials estimator:** UI that maps UI fields to `shared/converters.ts` formulas. Unit tests for formulas.
- **Inspection flow:**
  - Multi-image upload UI (drag/drop, camera input). Accept batch and queue for processing.
  - Queue images to a WebWorker `cvWorker.ts` (one worker per logical queue) to avoid blocking UI.
  - Worker pipeline: grayscale → blur → Hough circle detection → Canny → edge analysis → pixel gap measurement → convert pixels→mm via scale.
  - Save result object to IndexedDB with `originalMeasurement`, `calculatedGapMm`, `status` (PASS/REVIEW/FAIL), `override` flag, and image references.
- **Manual override UI:** show original, allow numeric override, and store `overrideBy`, `overrideAt`, `overrideReason`.
- **Sequential mapping:** create labels `n-(n+1)` when storing ordered images; store order index for each image.
- **Bulk processing & WebWorkers:** implement job queue with concurrency limit (configurable, e.g., 2 workers on mobile, 4 on desktop). Use `postMessage` and transferable buffers for performance.
- **Export:** `export` feature to generate JSON, ZIP (JSZip), and PDF (pdf-lib). Generate evidence pack with images, measurements, and timestamps.
- **Tests:** unit tests for tolerance logic, converter functions and integration tests (Vitest + jsdom). Add lightweight e2e tests with Playwright (headless) to exercise upload → process → export flow.
- **Scripts:** in `frontend/package.json` include:
  - `dev`: `vite`
  - `build`: `vite build`
  - `preview`: `vite preview`
  - `lint`: `eslint --ext .ts,.tsx src`
  - `test`: `vitest`

**Backend: Implementation Tasks (optional / future-proofing)**

- **Purpose:** provide a local CLI test harness and optional local service for heavy batch processing, reproducible CV runs, and CI-based image regression tests.
- **Design options:**
  - CLI (`node ./dist/cli.js`) that accepts a folder of images and outputs JSON reports using the same shared `tolerance` and `converters` logic.
  - Lightweight Express API (optional) with endpoints: `/process-batch`, `/status`, `/health` for local usage or future sync.
- **Shared code:** reuse `shared` package for types, classification and conversion logic so frontend and backend behave identically.
- **Scripts:** in `backend/package.json` include:
  - `build`: `tsc -p tsconfig.build.json`
  - `start`: `node dist/cli.js`
  - `test`: `vitest` or `node`-based mocha tests

**CI / Workflow alignment**

- Current CI (`.github/workflows/ci.yml`) expects Node and npm. To keep CI green, create a top-level `package.json` or use a monorepo workspace so CI `npm ci`, `npm run build`, `npm run test` succeed.
- Recommended root `package.json` (minimal) to run both packages:

```json
{
  "name": "pipe-joint-inspect",
  "private": true,
  "workspaces": ["frontend","backend","shared"],
  "scripts": {
    "build": "pnpm -w -r build || npm run -w frontend build && npm run -w backend build",
    "test": "pnpm -w -r test || npm run -w shared test && npm run -w frontend test && npm run -w backend test",
    "lint": "eslint . --ext .ts,.tsx"
  }
}
```

- If you prefer not to use workspaces, add a root `package.json` that forwards to `frontend` scripts and ensures `npm ci` and `npm run build` succeed.
- Keep `.github/workflows/ci.yml` to run `npm ci` then `npm run build` and `npm run test`. Our current workflow already builds node projects; ensure `package.json` exists at repo root or update workflow to run per-package steps.

**Quality gates & tests**

- Unit tests for `shared/tolerance.ts` to assert PASS/REVIEW/FAIL boundaries.
- Deterministic CV tests: include a small set of test images and expected pixel/mm outputs run in CI (backend CLI can be used to run these deterministically in Node). Mark these as integration tests and run on a separate job if heavy.
- Lint and type-check in CI (`eslint` and `tsc --noEmit`).

**Roadmap & milestones (suggested)**

1. Repository scaffolding (1 day)
  - Create `frontend`, `shared`, `backend` folders and initial `package.json` files.
  - Add root `package.json` and toolchain choice (npm/pnpm/yarn).
2. Frontend core (3–5 days)
  - Project + manhole CRUD, IndexedDB models, and UI skeleton.
  - Multi-image upload and queuing UI.
3. CV worker (3–7 days)
  - Implement `cvWorker.ts` pipeline with OpenCV.js and basic gap measurement.
  - Add demo test images and tune scale conversion.
4. Export & PWA polish (2–3 days)
  - Evidence export, PWA manifest, offline caching strategies.
5. Tests & CI (2–3 days)
  - Unit tests, integration test harness (backend CLI), update CI to run tests.
6. Manual override & UX polish (1–2 days)

**Developer instructions (Quick start)**

1. Clone repo and install dependencies (from repo root):

```bash
git clone https://github.com/Ifeoyewole/Don-t.git
cd Don-t
# choose package manager; examples below use npm
npm ci
```

2. Run frontend locally:

```bash
cd frontend
npm ci
npm run dev
```

3. Run backend CLI (optional):

```bash
cd backend
npm ci
npm run build
npm start -- --input ./test-images --output ./reports
```

4. Run tests from root (if workspace configured):

```bash
npm run test
```

**What I can do next (pick one)**
- Scaffold the `frontend`/`shared`/`backend` packages and create minimal `package.json` files and a root workspace (I can implement and push these changes).
- Implement a prototype `cvWorker.ts` with OpenCV.js wiring and a small demo page in `frontend`.
- Add deterministic test images and a backend CLI test harness so CI can run image regression.

---
This file is a concise, actionable plan that aligns the frontend work (PWA + CV + offline) and the backend (optional CLI/service and automated tests) so CI and team workflows run predictably. Tell me which next step you want me to perform and I'll scaffold or implement it.
