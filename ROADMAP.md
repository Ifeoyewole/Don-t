# ROADMAP — General Implementation Roadmap

This file outlines high-level milestones, dependencies, timelines, and CI alignment for the MVP.

## Milestones

1. Scaffolding & Types (0.5–1 day)
  - Create `frontend/`, `shared/`, `backend/` folders
  - Add root `package.json` workspace and shared types

2. Frontend UI Skeleton (1–2 days)
  - Pages and routes
  - Placeholder components and mock fixtures

3. Storage & Estimator (1–2 days)
  - IndexedDB schema (Dexie)
  - Materials estimator and unit tests

4. CV Worker Prototype (3–5 days)
  - Implement worker pipeline with OpenCV.js
  - Create deterministic test images

5. Export & PWA (2–3 days)
  - Implement PDF/JSON/ZIP export
  - Add PWA manifest and service worker caching

6. Tests & CI (1–2 days)
  - Unit tests for shared logic
  - CI job for lint/build/test

7. Polish & UX (1–2 days)
  - Accessibility, error flows, manual override UX

8. Handoff & Documentation (0.5 day)
  - Final README, developer guides, and demonstration video

## Dependencies & Risks

- OpenCV.js in browser may require tuning and may not be perfectly deterministic across platforms; include a small backend test harness for reliable CI tests.
- Large images on mobile may need client-side resizing and memory management.
- Offline storage limits vary by browser; provide export options frequently.

## CI Alignment

- Ensure root `package.json` or workflow updates so `.github/workflows/ci.yml` can run `npm ci`, `npm run build`, and `npm run test` successfully.
- Add slow integration job for CV tests that can be skipped in quick runs.

## Release Checklist

- All unit tests passing
- Core flows (upload → process → export) verified on mobile viewport
- Manual override and persistence validated
- Exports contain required metadata and images

## Next Actions

- Choose one scaffold target: `scaffold workspace`, `prototype cvWorker`, or `add test images and CLI harness`.
