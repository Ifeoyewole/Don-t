# Branch Protection Rules Configuration

## GitHub Branch Protection Settings

This document outlines the recommended GitHub branch protection rules for the Pipe Joint Inspection App repository.

## Main Branch Protection

### Branch: `main`

**Status:** 🔒 Protected - Strict enforcement required

### Protection Rules

#### 1. Require Pull Request Reviews

- **Require approvals:** Yes
- **Number of required approvals:** 1
- **Dismiss stale PR approvals when new commits are pushed:** Yes
- **Require review from Code Owners:** Yes

**Rationale:** Ensures all production code is reviewed before merging.

#### 2. Require Status Checks to Pass

- **Require branches to be up to date before merging:** Yes
- **Required status checks:**
  - `build` (CI/CD pipeline)
  - `test` (automated test suite)
  - `lint` (code quality checks)

**Rationale:** Ensures code quality and test coverage before production deployment.

#### 3. Require Branches to Be Up to Date

- **Enabled:** Yes

**Rationale:** Prevents merging when develop branch has newer changes that haven't been validated.

#### 4. Require Code Owners Review

- **Enabled:** Yes
- **CODEOWNERS file:** Required

**Rationale:** Ensures domain experts review changes to critical areas.

#### 5. Restrict Who Can Push to Matching Branches

- **Allowed to push:**
  - Repository admins only
- **Include administrators:** No (admins must also follow the rules)

**Rationale:** Prevents accidental direct commits to production.

#### 6. Include Administrators in Restrictions

- **Enforce all rules for administrators:** Yes

**Rationale:** Ensures even admins follow the merge process.

#### 7. Require Conversation Resolution

- **Enabled:** Yes

**Rationale:** All PR comments must be resolved before merging.

#### 8. Require Signed Commits

- **Enabled:** Yes (recommended for production)

**Rationale:** Verifies code authenticity and accountability.

#### 9. Dismiss Stale Pull Request Approvals

- **Enabled:** Yes

**Rationale:** Ensures reviews are current when new commits are pushed.

#### 10. Require a Merge Queue

- **Enabled:** Yes (optional, advanced teams)
- **Merge queue method:** Squash

**Rationale:** Prevents race conditions when multiple PRs are merged simultaneously.

## Develop Branch Protection (Recommended)

### Branch: `develop`

**Status:** 🟡 Protected - Moderate enforcement

### Protection Rules

#### 1. Require Pull Request Reviews

- **Require approvals:** No (optional)
- **Number of required approvals:** 0

**Rationale:** Faster integration for testing, but PRs still required to maintain history.

#### 2. Require PR for All Changes

- **Enabled:** Yes

**Rationale:** All changes documented, but faster than main branch.

#### 3. Require Branches to Be Up to Date

- **Enabled:** Yes

**Rationale:** Prevents merge conflicts.

#### 4. Dismiss Stale PR Approvals

- **Enabled:** Yes

**Rationale:** Keeps approvals current.

#### 5. Require Status Checks

- **Enabled:** Yes (optional)
- **Required status checks:**
  - `test` (if test suite is fast)

**Rationale:** Catches obvious errors before merge.

## Personal Development Branch Rules (Optional)

### Branches: `mavis-backend`, `vikky-frontend`

**Status:** ⚪ Unprotected - Developer discretion

### Optional Protection Rules

#### 1. Auto-Cleanup

- **Enabled:** Yes
- **Cleanup:** Delete head branches after merge

**Rationale:** Keeps branch list clean.

#### 2. Require PR Creation

- **Enabled:** No (but strongly recommended practice)

**Rationale:** Developers can push directly but should use PRs.

## CODEOWNERS Configuration

Create `.github/CODEOWNERS` file:

```
# Backend
src/services/                   @mavis
src/db/                         @mavis
src/workers/                    @mavis
src/lib/                        @mavis
src/utils/                      @mavis

# Frontend
src/pages/                      @vikky
src/components/                 @vikky
src/layouts/                    @vikky
src/styles/                     @vikky
src/assets/                     @vikky

# Shared areas (require both)
src/hooks/                      @mavis @vikky
src/types/                      @mavis @vikky
src/App.tsx                     @mavis @vikky
src/main.tsx                    @mavis @vikky

# Project config (both must review)
package.json                    @mavis @vikky
tsconfig.json                   @mavis @vikky
vite.config.ts                  @mavis @vikky
.github/workflows/              @mavis @vikky
```

## GitHub Status Checks

### CI/CD Pipeline Configuration

All PRs to `develop` and `main` must pass:

1. **Build Check**
   - Verifies TypeScript compilation
   - Checks bundle size

2. **Test Check**
   - Runs unit tests
   - Runs integration tests
   - Requires > 80% coverage

3. **Lint Check**
   - ESLint validation
   - TypeScript strict mode
   - Prettier formatting

### Workflow File Location

`.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [develop, main]
  pull_request:
    branches: [develop, main]

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm ci
      - run: npm run build
      - run: npm run test
      - run: npm run lint
```

## GitHub Repository Settings

### General

- **Default branch:** `develop`
- **Branch and pull request auto-deletion:** Enabled
- **Allow auto-merge:** Enabled
- **Require status checks to pass:** Yes

### Collaborator Access

| Role | Branches | Permissions |
|------|----------|-------------|
| Admin | All | Full control |
| Mavis | mavis-backend, develop, main | Push, PR, merge |
| Vikky | vikky-frontend, develop, main | Push, PR, merge |

## Setup Instructions

### To Enable Main Branch Protection

1. Go to **Settings → Branches**
2. Click **Add rule** under "Branch protection rules"
3. Enter branch name pattern: `main`
4. Check:
   - ✅ Require a pull request before merging
   - ✅ Require approvals (1)
   - ✅ Require status checks to pass before merging
   - ✅ Require branches to be up to date before merging
   - ✅ Require code owner reviews
   - ✅ Require conversation resolution
   - ✅ Enforce for administrators
5. Click **Create**

### To Enable Develop Branch Protection

1. Follow same process as main
2. Enter branch name pattern: `develop`
3. Uncheck approval requirement (optional)
4. Check PR and status check requirements

### To Create CODEOWNERS File

1. Create `.github/CODEOWNERS`
2. Add developer assignments (see template above)
3. Commit and push to develop

## Verification Checklist

- [ ] Main branch protection enabled
- [ ] Develop branch protection enabled
- [ ] CODEOWNERS file created
- [ ] CI/CD workflows configured
- [ ] Status checks passing on all PRs
- [ ] Code owners receiving review notifications
- [ ] All developers have appropriate access levels
- [ ] PR template configured
- [ ] Branch deletion after merge enabled

## Troubleshooting

### PR Cannot Be Merged

**Reason:** Status checks failing or approvals missing

**Solution:**
1. Check GitHub Actions tab for failing checks
2. Request review from code owners if needed
3. Ensure branch is up to date with develop/main

### Frequent Merge Conflicts

**Reason:** Branches not frequently synchronized

**Solution:**
1. Pull develop daily
2. Merge develop into personal branch regularly
3. Keep commits small and focused

### Lost Access to Main Branch

**Reason:** Protection rules restricting all users

**Solution:**
1. Have repository owner disable restrictions temporarily
2. Adjust to allow administrators if needed
3. Re-enable after fixing permissions

---

**Last Updated:** May 17, 2026  
**Maintained By:** DevOps Team
