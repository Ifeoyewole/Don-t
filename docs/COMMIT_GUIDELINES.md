# Commit Message Guidelines

## Conventional Commit Format

All commits should follow the Conventional Commits specification for clear, standardized commit messages.

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

## Commit Types

### `feat`
A new feature that is added to the codebase.

**Examples:**
```
feat: implement tolerance classification engine
feat: add PDF export functionality
feat: build upload inspection queue system
feat(ui): create inspection form component
```

### `fix`
A bug fix that resolves an issue.

**Examples:**
```
fix: correct tolerance calculation algorithm
fix: resolve image upload crash on mobile
fix: repair offline cache synchronization
fix(storage): fix IndexedDB connection timeout
```

### `style`
Changes that do not affect code meaning (formatting, missing semicolons, etc.). Also used for UI/styling updates.

**Examples:**
```
style: improve mobile inspection layout
style: redesign summary dashboard
style(spacing): adjust padding on project cards
style(animations): add smooth transition to modal
```

### `refactor`
Code changes that neither fix bugs nor add features, but improve code quality.

**Examples:**
```
refactor: separate image processing service
refactor: optimize IndexedDB schema
refactor(workers): consolidate WebWorker initialization
```

### `docs`
Changes to documentation only.

**Examples:**
```
docs: update API documentation
docs: add setup instructions
```

### `test`
Adding or updating test files.

**Examples:**
```
test: add unit tests for gap measurement
test: improve coverage for tolerance engine
```

### `chore`
Changes to build scripts, dependencies, or other non-source files.

**Examples:**
```
chore: update dependencies
chore: configure webpack
```

### `ci`
Changes to CI/CD configuration files.

**Examples:**
```
ci: add GitHub Actions workflow
ci: update deployment pipeline
```

## Commit Scope (Optional)

The scope specifies which part of the codebase is affected:

- `backend` — Backend/system engineering changes
- `frontend` — Frontend/UI engineering changes
- `storage` — Database/storage changes
- `workers` — Web Worker changes
- `ui` — User interface components
- `export` — Export functionality
- `pwa` — Progressive Web App features

**Example:**
```
feat(backend): implement gap measurement engine
fix(ui): resolve responsive layout bug
```

## Subject Line Rules

1. Use the imperative mood: "add" not "added" or "adds"
2. Do not capitalize the first letter
3. Do not end with a period (.)
4. Keep it under 50 characters
5. Be specific and descriptive

**Good Examples:**
```
feat: implement tolerance classification engine
fix: resolve image upload crash
style: improve mobile inspection layout
```

**Bad Examples:**
```
FEAT: Added tolerance classification engine
fix: improved the image upload
refactor: stuff
```

## Commit Body (Optional but Recommended)

The body provides additional context about the change. Separate from the subject by a blank line.

**Rules:**
1. Use the imperative mood
2. Wrap at 72 characters
3. Explain **what** and **why**, not **how**
4. Reference related issues

**Example:**
```
feat(backend): implement tolerance classification engine

The gap measurement engine now classifies gaps based on
tolerance thresholds. This allows inspectors to quickly
identify non-compliant joints.

Implements logic for:
- Standard tolerance comparison
- Custom tolerance ranges
- Classification status reporting

Fixes #42
Relates to #38
```

## Commit Footer (Optional)

The footer contains metadata about the commit. Reference issues or breaking changes.

**Issue References:**
```
Fixes #123
Closes #456
Relates to #789
```

**Breaking Changes:**
```
BREAKING CHANGE: PDF export format changed from A4 to A3
```

**Example:**
```
feat: implement PDF export functionality

Adds comprehensive PDF generation for inspection reports.
Includes images, measurements, and classification data.

Fixes #100
```

## Complete Example

```
feat(backend): implement gap measurement with tolerance classification

Add new tolerance classification engine that evaluates gap
measurements against configurable tolerance ranges. The engine
returns classification status (compliant/non-compliant) for
each joint.

Features:
- Configurable tolerance thresholds
- Multiple tolerance profile support
- Real-time classification feedback
- Error handling for edge cases

Fixes #42
Relates to #38
```

## Day-to-Day Workflow

### Good Commit Practice

```bash
# Make a small, focused change
git add src/services/gapMeasurement.js
git commit -m "feat(backend): add gap measurement calculation"

# Another focused change
git add src/components/InspectionForm.tsx
git commit -m "feat(ui): create inspection form component"

# Bug fix
git commit -m "fix(storage): resolve IndexedDB query timeout"
```

### What NOT to Do

```bash
# ❌ Too vague
git commit -m "update stuff"

# ❌ No type prefix
git commit -m "Improved the backend code"

# ❌ Combining multiple unrelated changes
git commit -m "feat: add measurement engine and fix UI bug and refactor storage"

# ❌ Capitalized, ends with period
git commit -m "Feat: Add Measurement Engine."
```

## Benefits

Following this convention provides:

- Clear project history
- Easier debugging with `git log`
- Automated changelog generation
- Better collaboration between developers
- Understanding of what changed and why

## Quick Reference

| Type | Usage |
|------|-------|
| `feat` | New feature |
| `fix` | Bug fix |
| `style` | Formatting/UI styling |
| `refactor` | Code improvement |
| `docs` | Documentation |
| `test` | Test files |
| `chore` | Build/dependencies |
| `ci` | CI/CD config |

---

**Remember:** Clear, consistent commits make the codebase easier to maintain and understand for both current and future developers.
