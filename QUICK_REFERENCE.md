# Quick Reference Card

## 📌 Developer Quick Reference

**Print this or bookmark for daily use!**

---

## 🌳 Branch Cheat Sheet

| Branch | Use | Who |
|--------|-----|-----|
| `main` | Production only | Both (via PR) |
| `develop` | Integration & staging | Both (via PR) |
| `mavis-backend` | Backend features | Mavis |
| `vikky-frontend` | Frontend features | Vikky |

---

## ⚡ Daily Command Sequence

```bash
# 1. Start of day - sync develop
git checkout develop
git pull origin develop

# 2. Update your branch
git checkout mavis-backend          # or vikky-frontend
git merge develop

# 3. Create feature branch
git checkout -b feature/my-feature

# 4. Do work, then commit
git add .
git commit -m "feat: describe your feature"

# 5. Push and create PR
git push origin mavis-backend
# Go to GitHub and create PR
```

---

## 💾 Commit Message Format

```
feat: add new feature
fix: fix a bug
style: update UI styling
refactor: improve code structure
docs: update documentation
test: add test cases
```

**Examples:**
```
feat(backend): implement gap measurement
fix(frontend): resolve mobile layout issue
style(ui): improve button spacing
refactor(db): optimize query performance
```

---

## 🔄 Common Tasks

### Push Changes
```bash
git add .
git commit -m "feat: my feature"
git push origin mavis-backend
```

### Sync with Latest Develop
```bash
git checkout develop
git pull origin develop
git checkout mavis-backend
git merge develop
```

### Update Just Before PR
```bash
git fetch origin
git merge origin/develop
git push origin mavis-backend
```

### Undo Last Commit (Keep Changes)
```bash
git reset --soft HEAD~1
```

### View Recent Commits
```bash
git log --oneline -10
```

### Check Branch Status
```bash
git status
git branch -a
```

---

## 🚨 Emergency Commands

### Undo All Uncommitted Changes
```bash
git reset --hard
```

### Undo Commit + Discard Changes
```bash
git reset --hard HEAD~1
```

### Revert Merged Commit (Safe)
```bash
git revert -m 1 <commit-hash>
```

### Fix Merge Conflict
```bash
# 1. Open conflicted files
# 2. Remove <<<<<<, ======, >>>>>> markers
# 3. Keep desired code
git add .
git commit -m "fix: resolve merge conflict"
```

---

## ✅ Pre-PR Checklist

- [ ] Code builds: `npm run build`
- [ ] Linter passes: `npm run lint`
- [ ] Tests pass: `npm run test`
- [ ] Branch synced: `git merge develop`
- [ ] Commit messages follow convention
- [ ] For UI: screenshots ready
- [ ] For backend: testing confirmed

---

## 📝 Commit Examples

### Backend (Mavis)
```bash
git commit -m "feat(backend): add WebWorker for image processing"
git commit -m "fix(storage): resolve IndexedDB timeout"
git commit -m "refactor(services): separate measurement logic"
```

### Frontend (Vikky)
```bash
git commit -m "feat(frontend): create inspection form"
git commit -m "style(ui): improve mobile responsiveness"
git commit -m "fix(layout): correct dashboard spacing"
```

---

## 🔗 File Ownership

| Path | Owner |
|------|-------|
| `src/services/` | Mavis |
| `src/db/` | Mavis |
| `src/workers/` | Mavis |
| `src/lib/` | Mavis |
| `src/utils/` | Mavis |
| `src/pages/` | Vikky |
| `src/components/` | Vikky |
| `src/layouts/` | Vikky |
| `src/styles/` | Vikky |
| `src/assets/` | Vikky |
| `src/hooks/` | **Both** |
| `src/types/` | **Both** |
| `src/App.tsx` | **Both** |
| `src/main.tsx` | **Both** |

---

## ⚠️ DO's & DON'Ts

### ✅ DO:
- Communicate before shared file edits
- Keep commits focused and small
- Pull develop daily
- Write descriptive commit messages
- Review code before merging
- Test locally before pushing
- Follow the workflow

### ❌ DON'T:
- Push directly to `main` or `develop`
- Mix unrelated changes in one commit
- Edit shared files without coordination
- Force push to shared branches
- Commit broken code
- Rewrite shared history
- Bypass reviews

---

## 📚 Documentation Links

| Doc | Use For |
|-----|---------|
| [README.md](README.md) | Overview & links |
| [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md) | Setup & daily workflow |
| [COMMIT_GUIDELINES.md](COMMIT_GUIDELINES.md) | Commit standards |
| [VERSION_CONTROL.md](VERSION_CONTROL.md) | Strategy details |
| [BRANCH_PROTECTION_RULES.md](BRANCH_PROTECTION_RULES.md) | GitHub config |
| [PULL_REQUEST_TEMPLATE.md](PULL_REQUEST_TEMPLATE.md) | PR template |

---

## 🎯 Typical Feature Flow

```
1. Sync with develop
2. Create feature branch
3. Make commits (with proper messages)
4. Push to personal branch
5. Create PR to develop
6. Code review
7. All checks pass
8. Merge to develop
9. Deployed to staging
10. Later: Merge develop to main for production
```

---

## 💡 Pro Tips

1. **Commit often** - Small, focused commits are easier to review
2. **Push daily** - Don't lose work by holding commits locally
3. **Check before PR** - Run tests & lint before creating PR
4. **Read feedback** - Reviews help you grow as a developer
5. **Keep synchronized** - Pull develop at least daily
6. **Clear messages** - Future you will thank you for clear commits
7. **One issue per commit** - Makes reverting easier if needed
8. **Test on develop** - Merged code gets tested on develop first

---

## 🚀 Release Workflow

```bash
# When ready to release
git checkout develop
git pull origin develop

# Verify all tests pass
npm run test

# Create release PR
git checkout -b release/v1.0.0
git push origin release/v1.0.0

# In GitHub:
# 1. Create PR: develop → main
# 2. Add release notes
# 3. Request final review
# 4. Merge when approved

# Tag the release
git checkout main
git pull origin main
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

---

## 🔍 Helpful Commands

```bash
# See what's different between branches
git log develop..mavis-backend

# See commits from last 24 hours
git log --since="24 hours ago" --oneline

# See what changed in last commit
git show

# Search commit history
git log --grep="payment" --oneline

# See commits by author
git log --author="Mavis" --oneline

# See file history
git log -- src/services/measurement.ts
```

---

## 🆘 When Things Go Wrong

| Problem | Solution |
|---------|----------|
| Merge conflict | Open file, remove markers, add, commit |
| Behind develop | `git merge develop` or `git rebase develop` |
| Wrong commit | `git reset --soft HEAD~1` then recommit |
| Pushed to wrong branch | Create revert PR with `git revert` |
| Lost commits | `git reflog` (shows all recent actions) |

---

## 📞 Quick Help

**Question:** Can I edit `src/types/`?  
**Answer:** Yes, but notify the other developer first.

**Question:** How long should branches live?  
**Answer:** Usually less than 1 week. Merge to develop ASAP.

**Question:** Do I have to write perfect code?  
**Answer:** No, but follow patterns, write tests, ask for help.

**Question:** Can I rewrite history?  
**Answer:** Only on YOUR branch before PR. Never on develop/main.

**Question:** What if I make a mistake?  
**Answer:** Git remembers everything. Use `git reflog` to recover.

---

**Bookmark this page!** 🔖  
Print and keep at your desk for quick reference.

---

Last Updated: May 17, 2026  
For more info: See [DEVELOPMENT_SETUP.md](DEVELOPMENT_SETUP.md)
