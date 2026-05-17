# Development Setup & Quick Start Guide

## Initial Repository Setup

### For Repository Owner/Admin

1. **Push branches to GitHub:**
   ```bash
   git remote add origin https://github.com/yourorg/pipe-joint-inspect.git
   git push -u origin main
   git push -u origin develop
   git push -u origin mavis-backend
   git push -u origin vikky-frontend
   ```

2. **Default branch choice:**
   - Keep `main` as the default branch unless you intentionally want the repository centered on staging work
   - Use `develop` as the integration branch for pull requests and testing

3. **Configure branch protection rules:**
   - Follow instructions in [BRANCH_PROTECTION_RULES.md](../BRANCH_PROTECTION_RULES.md)
   - Protect `main` and `develop` branches

4. **Create GitHub CODEOWNERS:**
   - File should be at `.github/CODEOWNERS`
   - Already configured in this repository

### For Each Developer

#### First-Time Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourorg/pipe-joint-inspect.git
   cd pipe-joint-inspect
   ```

2. **Verify branches are available:**
   ```bash
   git branch -a
   ```

   Expected output:
   ```
     develop
   * main
     mavis-backend
     remotes/origin/develop
     remotes/origin/main
     remotes/origin/mavis-backend
     remotes/origin/vikky-frontend
   ```

3. **Configure Git locally:**
   ```bash
   git config user.name "Your Name"
   git config user.email "your.email@example.com"
   ```

4. **Install project dependencies:**
   ```bash
   npm install
   ```

5. **Set up Git hooks (for commit message validation):**
   ```bash
   npm install husky @commitlint/config-conventional @commitlint/cli --save-dev
   npx husky install
   npx husky add .husky/commit-msg 'npx --no-dev commitlint --edit $1'
   ```

---

## Daily Workflow for Developers

### Mavis (Backend Developer)

#### Start of Day

```bash
# Switch to develop and pull latest changes
git checkout develop
git pull origin develop

# Update personal backend branch
git checkout mavis-backend
git merge develop
```

#### During Development

```bash
# Make changes to your owned folders:
# - src/services/
# - src/db/
# - src/workers/
# - src/lib/
# - src/utils/

# Commit with proper message format
git add .
git commit -m "feat(backend): implement tolerance classification engine"

# Push to your branch
git push origin mavis-backend
```

#### Creating a Pull Request

1. Go to GitHub
2. Create PR: `mavis-backend` → `develop`
3. Fill out [PR template](../PULL_REQUEST_TEMPLATE.md)
4. Add testing confirmation
5. Request review from Ifeoyewole for shared files
6. If review changes are requested, push fixes to `mavis-backend`
7. Ifeoyewole merges approved work into `develop`

#### When Working on Shared Files

```bash
# IMPORTANT: Communicate before editing shared files
# Shared files: src/hooks/, src/types/, src/App.tsx, src/main.tsx

# Before making changes:
# 1. Slack/message Vikky that you're updating shared file
# 2. Pull latest develop
git checkout develop
git pull origin develop

# 3. Make minimal changes to shared file
# 4. Commit and push immediately
git add src/types/
git commit -m "feat(types): add inspection data types"
git push origin mavis-backend

# 5. Create PR to develop and request review from Ifeoyewole
```

### Vikky (Frontend Developer)

#### Start of Day

```bash
# Switch to develop and pull latest changes
git checkout develop
git pull origin develop

# Update personal frontend branch
git checkout vikky-frontend
git merge develop
```

#### During Development

```bash
# Make changes to your owned folders:
# - src/pages/
# - src/components/
# - src/layouts/
# - src/styles/
# - src/assets/

# Commit with proper message format
git add .
git commit -m "feat(frontend): build upload inspection interface"

# Push to your branch
git push origin vikky-frontend
```

#### Creating a Pull Request

1. Go to GitHub
2. Create PR: `vikky-frontend` → `develop`
3. Fill out [PR template](../PULL_REQUEST_TEMPLATE.md)
4. Add screenshots of UI changes
5. Add testing confirmation
6. For shared files, notify Mavis as well
7. Ifeoyewole merges approved work into `develop`

#### When Working on Shared Files

Same process as Mavis (see above) - communicate before editing.

---

## Commit Message Examples

### Backend Examples (Mavis)

```bash
# Feature commits
git commit -m "feat(backend): implement gap measurement algorithm"
git commit -m "feat(backend): add WebWorker for image processing"
git commit -m "feat(storage): create IndexedDB schema for inspections"

# Bug fixes
git commit -m "fix(workers): resolve WebWorker memory leak"
git commit -m "fix(storage): correct database query timeout"

# Refactoring
git commit -m "refactor(services): separate image processing logic"
git commit -m "refactor(db): optimize IndexedDB performance"
```

### Frontend Examples (Vikky)

```bash
# Feature commits
git commit -m "feat(frontend): create inspection form component"
git commit -m "feat(ui): build project management dashboard"
git commit -m "style: improve mobile responsive layout"

# Bug fixes
git commit -m "fix(ui): resolve form validation error"
git commit -m "fix(layout): correct mobile navigation spacing"

# Styling
git commit -m "style(animations): add smooth transitions to modals"
git commit -m "style(colors): update color scheme for accessibility"
```

For more details, see [COMMIT_GUIDELINES.md](../COMMIT_GUIDELINES.md)

---

## Pull Request Checklist

Before creating a PR, ensure:

- [ ] Code follows project style guide
- [ ] All tests pass locally: `npm run test`
- [ ] Linter checks pass: `npm run lint`
- [ ] Code builds successfully: `npm run build`
- [ ] Changes are committed with proper messages
- [ ] Latest develop branch is merged in
- [ ] For frontend: screenshots added to PR description
- [ ] For backend: testing confirmation included
- [ ] PR description filled out completely
- [ ] For shared files: other developer notified and reviewed

---

## Common Commands Reference

### Branch Management

```bash
# List all branches
git branch -a

# Create new branch
git branch feature/new-feature
git checkout -b feature/new-feature    # Create and switch

# Delete branch locally
git branch -d feature/new-feature

# Delete branch remotely
git push origin --delete feature/new-feature

# Switch branch
git checkout mavis-backend
git checkout develop
```

### Staying Updated

```bash
# Pull latest from develop
git checkout develop
git pull origin develop

# Merge develop into current branch
git merge develop

# Rebase current branch on develop (cleaner history)
git rebase develop

# Check if branches have diverged
git log develop..mavis-backend    # Commits in mavis-backend not in develop
```

### Undoing Changes

```bash
# Undo uncommitted changes
git checkout -- filename.js

# Undo uncommitted changes in all files
git reset --hard

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes)
git reset --hard HEAD~1

# Undo pushed commit (creates new commit)
git revert HEAD
```

### Checking Status

```bash
# View status
git status

# View recent commits
git log --oneline -10

# View commits by author
git log --author="Mavis" --oneline

# View changes not yet committed
git diff
```

---

## Troubleshooting

### Merge Conflict

If you encounter a merge conflict:

1. **Identify conflicts:**
   ```bash
   git status    # Shows conflicted files
   ```

2. **Resolve conflicts:**
   - Open conflicted files
   - Find `<<<<<<`, `======`, `>>>>>` markers
   - Edit to keep desired code
   - Remove conflict markers

3. **Complete merge:**
   ```bash
   git add .
   git commit -m "fix: resolve merge conflict with develop"
   ```

### Branch Behind Develop

If your branch is behind develop:

```bash
# Option 1: Merge develop into your branch
git checkout mavis-backend
git merge develop

# Option 2: Rebase on develop (cleaner history)
git rebase develop
```

### Accidentally Committed to Wrong Branch

```bash
# Option 1: Move commits to correct branch
git log --oneline -5    # See recent commits

# Reset current branch, keeping changes
git reset --soft HEAD~1

# Switch to correct branch
git checkout correct-branch

# Re-commit there
git commit -m "feat: my feature"
```

### Need to Revert a Merged PR

```bash
# Find the commit hash of the merge
git log --oneline

# Revert it
git revert -m 1 <merge-commit-hash>
```

---

## Integration Testing on Develop

When your PR is merged to develop, the full application will be tested:

1. **Automated tests run:** See GitHub Actions workflow
2. **Full integration is verified:** Frontend + Backend
3. **If tests fail:** Check Actions tab, fix issues, push new commit
4. **If tests pass:** Feature is ready for production

---

## Release to Production

When feature set is complete and tested on develop:

1. **Ensure all tests pass on develop**
2. **Create PR:** `develop` → `main`
3. **Add release notes in PR description**
4. **Request review from both developers**
5. **After approval, Ifeoyewole merges to main**
6. **Tag the release:** `git tag -a v1.0.0 -m "Release v1.0.0"`
7. **Push tag:** `git push origin v1.0.0`

---

## Resources

- [Version Control Overview](../VERSION_CONTROL.md)
- [Commit Guidelines](../COMMIT_GUIDELINES.md)
- [PR Template](../PULL_REQUEST_TEMPLATE.md)
- [Branch Protection Rules](../BRANCH_PROTECTION_RULES.md)

---

**Questions or Issues?**

If you encounter issues or have questions about the workflow:

1. Check this guide
2. Review the referenced documentation
3. Ask the team lead
4. Update this guide if you find outdated information

---

Last Updated: May 17, 2026
