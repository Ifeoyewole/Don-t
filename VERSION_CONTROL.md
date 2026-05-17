# Pipe Joint Inspection App — Version Control Overview

## Version Control Strategy

The project will use a structured Git-based version control workflow to support collaborative development between two developers:

- **Mavis** (Backend/System Engineering)
- **Vikky** (Frontend/UI Engineering)

The workflow is designed to:

- Prevent unstable code from reaching production
- Reduce merge conflicts
- Separate frontend and backend responsibilities
- Maintain clean project history
- Support safe feature integration and testing

## Repository Structure

The repository will contain four primary branches:

```
main
│
└── develop
    │
    ├── mavis-backend
    └── vikky-frontend
```

## Branch Responsibilities

### 1. Main Branch

**Branch Name:** `main`

**Purpose**

The main branch represents the stable production-ready version of the application.

Only:
- Tested
- Reviewed
- Fully functional code

may be merged into this branch.

**Rules**
- No direct development occurs on main
- No experimental features are committed directly
- All merges into main must originate from develop

### 2. Develop Branch

**Branch Name:** `develop`

**Purpose**

The develop branch acts as the integration and staging branch.

This branch is used to:
- Combine frontend and backend work
- Perform testing
- Resolve integration issues
- Validate new features before release

**Responsibilities**
- Merge completed work from both developers
- Run full application testing
- Resolve merge conflicts
- Validate feature compatibility

### 3. Backend Development Branch

**Branch Name:** `mavis-backend`

**Assigned Developer:** Mavis

**Responsibilities**

**Core System Engineering**
- OpenCV.js integration
- WebAssembly processing
- Gap measurement engine
- Tolerance classification engine
- Web Worker architecture

**Local Storage**
- IndexedDB architecture
- Project persistence
- Inspection persistence
- Local image storage

**Export Systems**
- PDF generation
- JSON export
- ZIP evidence packs

**PWA Infrastructure**
- Service workers
- Offline caching
- Background processing

**Materials Estimator Logic**
- Pipe calculations
- Joint calculations
- Estimation formulas

**Owned Folders**
- `src/services/`
- `src/db/`
- `src/workers/`
- `src/lib/`
- `src/utils/`

### 4. Frontend Development Branch

**Branch Name:** `vikky-frontend`

**Assigned Developer:** Vikky

**Responsibilities**

**User Interface**
- Responsive layouts
- Inspection screens
- Project management screens
- Report pages
- Upload interfaces

**Styling**
- Tailwind CSS
- Animations
- Mobile responsiveness
- UI transitions

**User Experience**
- Navigation flow
- Forms
- Interaction feedback
- Loading states
- Visual summaries

**Owned Folders**
- `src/pages/`
- `src/components/`
- `src/layouts/`
- `src/styles/`
- `src/assets/`

### Shared Areas

The following files are considered shared integration files:

- `src/hooks/`
- `src/types/`
- `src/App.tsx`
- `src/main.tsx`

**Shared File Rules**
- Communicate before editing shared files
- Avoid simultaneous modifications
- Pull latest develop branch before changes

## Development Workflow

### Daily Workflow

#### Step 1 — Pull Latest Changes

Before starting development:

```bash
git checkout develop
git pull origin develop
```

#### Step 2 — Update Personal Branch

**Backend Developer**
```bash
git checkout mavis-backend
git merge develop
```

**Frontend Developer**
```bash
git checkout vikky-frontend
git merge develop
```

This ensures both branches remain synchronized with the latest integrated codebase.

### Feature Development Workflow

#### Backend Workflow Example

```bash
git checkout mavis-backend
```

Develop feature: Gap classification engine

Commit changes:

```bash
git add .
git commit -m "feat: implement tolerance classification engine"
git push origin mavis-backend
```

Create Pull Request: `mavis-backend → develop`

#### Frontend Workflow Example

```bash
git checkout vikky-frontend
```

Develop feature: Inspection upload interface

Commit changes:

```bash
git add .
git commit -m "feat: build upload inspection page"
git push origin vikky-frontend
```

Create Pull Request: `vikky-frontend → develop`

## Merge Strategy

### Integration Phase

All completed features are first merged into: `develop`

Testing is then performed on the integrated application.

### Release Phase

When:
- Frontend is stable
- Backend is stable
- Testing passes
- Integration issues are resolved

The develop branch is merged into: `main`

## Commit Message Convention

The project follows structured commit naming conventions.

### Feature Commits
```
feat: add pipe estimator engine
feat: implement pdf export
feat: add upload queue system
```

### Bug Fix Commits
```
fix: correct tolerance classification
fix: resolve image upload crash
fix: repair offline cache issue
```

### UI Commits
```
style: improve mobile inspection layout
style: redesign summary dashboard
```

### Refactor Commits
```
refactor: separate image processing service
refactor: optimize indexeddb schema
```

## Conflict Prevention Strategy

To minimize merge conflicts:

- Frontend and backend responsibilities remain separated
- Developers avoid editing shared files simultaneously
- Develop is pulled daily
- Feature integration occurs frequently
- Commits remain small and focused

## Recommended GitHub Settings

### Branch Protection

**Protect:** `main`

**Rules:**
- No direct pushes
- Pull request required
- Review required before merge

### Pull Request Requirements

Every PR should include:

- Feature description
- Screenshots (frontend)
- Testing confirmation
- Issue references if applicable

## Version Control Summary

The project version control architecture is designed to:

- Support parallel frontend/backend development
- Maintain codebase stability
- Simplify collaboration
- Reduce integration risks
- Ensure safe MVP deployment

The workflow separates:

- **Production** (`main`)
- **Integration** (`develop`)
- **Backend Development** (`mavis-backend`)
- **Frontend Development** (`vikky-frontend`)

Creating a clean and scalable collaborative engineering structure for the Pipe Joint Inspection App.
