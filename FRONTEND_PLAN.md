# FRONTEND PLAN — Vikky (UI / Screens)

Owner: Vikky — focuses on screens, UX, and client-side wiring using mock data.

## Purpose

This file details the frontend deliverables, folder structure, phased tasks, acceptance criteria, and integration points with the backend logic (Mavis).

## Folders

```
src/pages/
src/components/
src/layouts/
src/styles/
src/assets/
src/hooks/
src/types/
```

## Main Screens & Components

- Landing / Dashboard
- Project creation
- Manhole creation
- Materials estimator UI
- Image upload / camera capture
- Joint inspection results (list + detail)
- Summary / Dashboard
- Report preview / export UI
- Settings / Offline sync indicators

## UX Requirements

- Mobile-first responsive design
- Clear loading states for each async action
- Error messages and retry options when processing fails
- Visual design for PASS / REVIEW / FAIL statuses (color + icon + text)
- Accessibility basics (keyboard nav, contrast, labels)

## Development Phases

Phase 1 — UI skeleton (mock data)
- Scaffold pages and routes
- Build components with placeholder data and controls
- Implement responsive layout and Tailwind classes

Phase 2 — Connect to shared types & mocks
- Add `src/types/` and import shared type placeholders
- Replace hard-coded mocks with fixture files

Phase 3 — Integrate real services (stubbed API)
- Replace mock service calls with asynchronous calls to `src/hooks/` that call `services` provided by Mavis
- Add loading and error states

Phase 4 — Polish & testing
- UI unit tests (Vitest + React Testing Library)
- Basic e2e flows for upload→process→export (Playwright)

## Integration Points (with Mavis)

- Project and manhole CRUD — call `services/projectService` (read/write IndexedDB)
- Upload images — call `services/imageQueue` which posts to WebWorker
- Request processing — call `services/processor` and await job results
- Export — call `services/exportService` to generate ZIP/PDF/JSON

## Acceptance Criteria

- All screens render with mock data and navigation flows work
- Upload UI queues images and displays progress bars
- Results screen displays classification badges and allows manual override
- Exports trigger and download a ZIP/PDF containing expected fields

## Notes for Vikky

- Build interfaces to accept both mock and real service providers through dependency injection (simple stubs). This allows parallel work with Mavis.
- Do not implement heavy CV logic in the UI; delegate to WebWorkers via `services/` hooks.
