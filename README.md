# Pipe Joint Inspection App — Git Workflow Setup

## 🎯 Overview

This repository contains the complete version control and development workflow setup for the **Pipe Joint Inspection App**, a collaborative project between two specialized developers:

- **Mavis** — Backend/System Engineering
- **Vikky** — Frontend/UI Engineering

## 📁 Repository Structure

```
pipe-joint-inspect/
├── VERSION_CONTROL.md                # Complete workflow documentation
├── DEVELOPMENT_SETUP.md              # Quick start guide for developers
├── COMMIT_GUIDELINES.md              # Commit message conventions
├── BRANCH_PROTECTION_RULES.md        # GitHub protection configuration
├── PULL_REQUEST_TEMPLATE.md          # PR submission template
├── README.md                         # This file
├── .github/
│   ├── CODEOWNERS                    # Code ownership configuration
│   └── workflows/
│       └── ci.yml                    # CI/CD pipeline configuration
├── src/
│   ├── services/                     # Backend services (Mavis)
│   ├── db/                           # Database layer (Mavis)
│   ├── workers/                      # Web Workers (Mavis)
│   ├── lib/                          # Libraries (Mavis)
│   ├── utils/                        # Utilities (Mavis)
│   ├── pages/                        # Pages (Vikky)
│   ├── components/                   # Components (Vikky)
│   ├── layouts/                      # Layouts (Vikky)
│   ├── styles/                       # Styles (Vikky)
│   ├── assets/                       # Assets (Vikky)
│   ├── hooks/                        # Shared hooks
│   ├── types/                        # Shared types
│   ├── App.tsx                       # Shared app component
│   └── main.tsx                      # Shared entry point
└── ... (other project files)
```

## 🌳 Git Branch Structure

```
main (Production)
│
└── develop (Integration & Staging)
    │
    ├── mavis-backend (Backend Development)
    │
    └── vikky-frontend (Frontend Development)
```

| Branch | Purpose | Developer | Status |
|--------|---------|-----------|--------|
| `main` | Production-ready code | Both (PR required) | 🔒 Protected |
| `develop` | Integration & testing | Both | 🟡 Protected |
| `mavis-backend` | Backend features | Mavis | ⚪ Unprotected |
| `vikky-frontend` | Frontend features | Vikky | ⚪ Unprotected |

## 📚 Documentation Files

### [VERSION_CONTROL.md](VERSION_CONTROL.md)
Complete overview of the version control strategy including:
- Branch responsibilities and rules
- Development workflow
- Merge strategy
- Conflict prevention techniques

👉 **Start here** to understand the overall architecture.

### [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md)
Quick start guide with:
- First-time repository setup
- Daily workflow for each developer
- Common Git commands
- Troubleshooting tips

👉 **Read this first** if you're a developer joining the project.

### [COMMIT_GUIDELINES.md](COMMIT_GUIDELINES.md)
Detailed commit message conventions:
- Conventional Commits format
- Commit types (feat, fix, style, refactor, etc.)
- Subject and body best practices
- Examples and anti-patterns

👉 **Reference this** when writing commit messages.

### [BRANCH_PROTECTION_RULES.md](BRANCH_PROTECTION_RULES.md)
GitHub configuration guide:
- Main and develop branch protection rules
- Status check requirements
- CODEOWNERS setup
- CI/CD integration

👉 **Follow this** to set up GitHub branch protections.

### [PULL_REQUEST_TEMPLATE.md](PULL_REQUEST_TEMPLATE.md)
PR submission template with:
- Description requirements
- Testing checklist
- Screenshot guidance
- Developer and reviewer checklists

👉 **Use this** as a template when creating pull requests.

## ⚡ Quick Start

### 1. Initial Repository Setup (Admin Only)

```bash
# Verify branches
git branch -a

# Push to remote
git remote add origin https://github.com/yourorg/pipe-joint-inspect.git
git push -u origin main develop mavis-backend vikky-frontend

# Configure GitHub
# - Set default branch to 'develop'
# - Enable branch protection for 'main' and 'develop'
# - Configure CODEOWNERS at .github/CODEOWNERS
```

### 2. Developer Setup (Mavis & Vikky)

```bash
# Clone repository
git clone https://github.com/yourorg/pipe-joint-inspect.git
cd pipe-joint-inspect

# Configure Git
git config user.name "Your Name"
git config user.email "your.email@example.com"

# Install dependencies
npm install

# Switch to your branch
git checkout mavis-backend        # Mavis
# OR
git checkout vikky-frontend       # Vikky
```

### 3. Daily Workflow

```bash
# Start of day: sync with latest integrate branch
git checkout develop
git pull origin develop

# Update your personal branch
git checkout mavis-backend        # Mavis
# OR
git checkout vikky-frontend       # Vikky
git merge develop

# Start developing features
git checkout -b feature/new-feature

# Commit with proper format
git commit -m "feat: add new feature"

# Push and create PR to develop
git push origin feature/new-feature
```

## 🔄 Workflow Overview

### Feature Development

1. **Create feature branch** from personal branch
2. **Develop & commit** with proper commit messages
3. **Push to personal branch** (e.g., `mavis-backend`)
4. **Create PR** to `develop`
5. **Code review & testing**
6. **Merge to develop** when approved

### Integration Testing

- Features are merged into `develop` branch
- Full application testing occurs
- Integration issues are resolved
- Frontend and backend verified together

### Release to Production

1. **All tests pass** on `develop`
2. **Create PR** from `develop` to `main`
3. **Final review** from both developers
4. **Merge to main** (production)
5. **Tag release** with version number

## 📋 Key Rules

### ✅ DO

- Communicate before editing shared files
- Pull `develop` daily to stay synchronized
- Create focused, small commits
- Write descriptive commit messages
- Test your code before pushing
- Review code before merging
- Keep branches up to date

### ❌ DON'T

- Push directly to `main` or `develop`
- Mix unrelated changes in one commit
- Edit shared files without coordination
- Rewrite history on shared branches
- Force push to `develop` or `main`
- Commit broken code
- Create long-lived branches (keep < 1 week)

## 🛠️ Development Responsibilities

### Mavis (Backend/System Engineering)

**Owned Folders:**
- `src/services/` — Business logic & integrations
- `src/db/` — Database operations
- `src/workers/` — Web Worker implementations
- `src/lib/` — Core libraries
- `src/utils/` — Utility functions

**Key Features:**
- OpenCV.js integration
- WebAssembly processing
- Gap measurement engine
- Tolerance classification
- PDF & JSON export
- PWA & offline support

### Vikky (Frontend/UI Engineering)

**Owned Folders:**
- `src/pages/` — Page components
- `src/components/` — Reusable components
- `src/layouts/` — Layout structures
- `src/styles/` — Styling & CSS
- `src/assets/` — Images & media

**Key Features:**
- Responsive layouts
- Inspection screens
- Project management UI
- Report pages
- Upload interfaces
- Mobile optimization

### Shared Areas

**Files requiring coordination:**
- `src/hooks/`
- `src/types/`
- `src/App.tsx`
- `src/main.tsx`

## 🚀 Typical Workflow Example

### Mavis Implementing Gap Classification

```bash
# 1. Sync with develop
git checkout develop && git pull origin develop

# 2. Update backend branch
git checkout mavis-backend && git merge develop

# 3. Create feature branch
git checkout -b feature/gap-classification

# 4. Develop and commit
git add src/services/gapClassification.ts
git commit -m "feat(backend): implement tolerance classification engine"

# 5. Push to personal branch
git push origin mavis-backend

# 6. Create PR in GitHub
# - From: mavis-backend
# - To: develop
# - Include testing confirmation

# 7. After review and approval, merge
```

### Vikky Creating Upload Interface

```bash
# 1. Sync with develop
git checkout develop && git pull origin develop

# 2. Update frontend branch
git checkout vikky-frontend && git merge develop

# 3. Create feature branch
git checkout -b feature/upload-interface

# 4. Develop and commit
git add src/components/UploadForm.tsx
git commit -m "feat(frontend): build upload inspection interface"

# 5. Push to personal branch
git push origin vikky-frontend

# 6. Create PR in GitHub
# - From: vikky-frontend
# - To: develop
# - Include screenshots

# 7. After review and approval, merge
```

## 🐛 Troubleshooting

### Merge Conflicts

**Problem:** Getting merge conflicts when pulling develop

```bash
# 1. Check conflicted files
git status

# 2. Open files and resolve conflicts (remove markers)

# 3. Stage and commit
git add .
git commit -m "fix: resolve merge conflict with develop"
```

### Branch Behind

**Problem:** Personal branch is behind develop

```bash
# 1. Merge develop into your branch
git checkout mavis-backend
git merge develop

# 2. Push updated branch
git push origin mavis-backend
```

### Undo Last Commit

**Problem:** Committed wrong thing

```bash
# Keep changes, undo commit
git reset --soft HEAD~1

# Discard changes and commit
git reset --hard HEAD~1
```

### Push to Wrong Branch

**Problem:** Accidentally pushed to develop

```bash
# Revert the bad commit
git revert <commit-hash>

# Push the revert
git push origin develop
```

## 📊 CI/CD Pipeline

The project includes automated checks:

- **Build:** TypeScript compilation
- **Lint:** ESLint & Prettier validation
- **Test:** Unit & integration tests
- **Security:** Dependency audit

All checks must pass before merging to `develop` or `main`.

## 🔐 GitHub Protection Rules

### Main Branch
- ✅ Require PR reviews (1 approval)
- ✅ Require status checks to pass
- ✅ Require branch to be up to date
- ✅ Require CODEOWNERS review
- ❌ No direct pushes

### Develop Branch
- ✅ Require PR creation
- ✅ Require status checks to pass
- ✅ Require branch to be up to date
- ⚪ Optional: Code owner review

## 📞 Support & Questions

For help with:
- **Workflow questions** → See [VERSION_CONTROL.md](VERSION_CONTROL.md)
- **Getting started** → See [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md)
- **Commit messages** → See [COMMIT_GUIDELINES.md](COMMIT_GUIDELINES.md)
- **GitHub setup** → See [BRANCH_PROTECTION_RULES.md](BRANCH_PROTECTION_RULES.md)
- **PR submission** → See [PULL_REQUEST_TEMPLATE.md](PULL_REQUEST_TEMPLATE.md)

## 📝 Version & Updates

- **Created:** May 17, 2026
- **Version:** 1.0.0
- **Maintained By:** DevOps Team & Project Leads

### Change Log

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | May 17, 2026 | Initial setup with complete documentation |

---

## 📌 Quick Links

- [Complete Version Control Strategy](VERSION_CONTROL.md)
- [Developer Setup Guide](DEVELOPMENT_SETUP.md)
- [Commit Message Guidelines](COMMIT_GUIDELINES.md)
- [Branch Protection Rules](BRANCH_PROTECTION_RULES.md)
- [PR Template](PULL_REQUEST_TEMPLATE.md)
- [GitHub Configuration](.github/CODEOWNERS)

---

**Last Updated:** May 17, 2026  
**Status:** ✅ Complete & Ready for Implementation

