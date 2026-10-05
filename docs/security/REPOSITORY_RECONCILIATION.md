# JointInspect — Repository History & Commit Reconciliation

**Target Branch:** `main`  
**Remote Baseline:** `2bd1e52` (`HEAD -> main, origin/main`)  
**Reconciliation Date:** October 2026  
**Auditor:** Release Remediation Agent  

---

## 1. Executive Summary

During previous operational passes, a sequence of commits (`46de447`, `87a06b6`, `b94b9fa`, `d17433d`, `9a4a139`, `8b71802`) was generated in local workspaces to implement zero-guessing radial profiling, operator context, domain gating, and legacy AI millimeter stripping. However, when the WRc InceptionResNetV2 sewer baseline was integrated, the local branch was reset to `d657469` before creating `2bd1e52`, leaving those commits in the local git reflog (`HEAD@{3}` to `HEAD@{8}`).

This audit reconciles the true state of the repository, classifies every commit, and selectively recovers valid technical enhancements into the current canonical baseline `2bd1e52` without destroying the WRc model integration.

---

## 2. Commit Classification Matrix

| Commit Hash | Reflog Location | Description | Reconciliation Status | Disposition |
|---|---|---|---|---|
| `46de447` | `HEAD@{8}` | Backend & UI domain gating | **SUPERSEDED** | Re-implemented cleanly in `2bd1e52` via `VertexSemanticGate` |
| `87a06b6` | `HEAD@{7}` | UI domain validation states | **RECOVERED** | Domain validation UI & status badges recovered to frontend |
| `b94b9fa` | `HEAD@{6}` | Zero-guessing OpenCV radial evidence | **RECOVERED** | `valid_ray_fraction >= 0.60`, 8-sector tracking ported to `circular_detector.py` |
| `d17433d` | `HEAD@{5}` | Remove AI mm estimation | **RECOVERED** | Legacy 70/30 AI mm fusion and `ai-estimated` removed from `measurementFusion.ts` |
| `9a4a139` | `HEAD@{4}` | Benchmark scripts update | **SUPERSEDED** | Upgraded to support multimodal Vertex semantic gate + WRc comparison |
| `8b71802` | `HEAD@{3}` | Unified pre-WRc checkpoint | **MERGED & RECONCILED** | Key zero-guessing & UI safety recovered; WRc baseline preserved |
| `2bd1e52` | `HEAD`, `origin/main` | WRc InceptionResNetV2 integration | **ACTIVE BASELINE** | Valid remote baseline running in production |

---

## 3. History State Verification

```text
* 2bd1e52 (HEAD -> main, origin/main) feat(cv): integrate WRc InceptionResNetV2 external baseline classifier
* d657469 chore: update lockfile and cloudbuild
...
```

Reflog trace:
- `HEAD@{0}`: commit `2bd1e52`
- `HEAD@{1}`: reset moving to `d657469`
- `HEAD@{2}`: commit `8b71802`
- `HEAD@{3}`: commit `9a4a139`
- `HEAD@{4}`: commit `d17433d`
- `HEAD@{5}`: commit `b94b9fa`
- `HEAD@{6}`: commit `87a06b6`
- `HEAD@{7}`: commit `46de447`

---

## 4. Recovered Assets & Invariants

1. **Circular Profiler Zero-Guessing (Phase 23 & 24):**
   - No synthetic fallback radii when edge gradients fail.
   - Outliers are marked and excluded, not rewritten as medians.
   - Rejection when `valid_ray_fraction < 0.60` or `coverage_sector_count < 6`.
2. **AI Millimeter Deprecation (Phase 18 & 20):**
   - Stripped `70% CV + 30% AI` physical fusion from `measurementFusion.ts`.
   - Archived/removed `netlify/functions/ai-measure-photo.ts` and Vite dev Gemini middleware.
3. **Domain Gating & Operator Context (Phase 14 & 16):**
   - Frontend stores and transmits operator context as data (never prompt instructions).
   - Prompt injection tests verify zero physical authority.
4. **WRc InceptionResNetV2 Baseline (Phase 29 & 30):**
   - Preserved fully from `2bd1e52`.
   - SHA-256 build and runtime verification intact.
