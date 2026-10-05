# Human Annotation & Quality Review Workflow

## 1. Principles & Zero-Guessing Integrity

Every machine-learning model in JointInspect depends upon verified ground-truth training signals. To eliminate label noise and ensure legal/provenance compliance:
- **No unreviewed external public dataset** may be marked `VERIFIED`.
- **Zero-Guessing Measurement Invariant**: The human reviewer does not estimate physical millimetre gap values by visual guesswork. Millimetre gap ground truth is only recorded when backed by calibrated physical test rig instruments (feeler gauge, vernier caliper) or exact synthetic procedural parameters.
- **Immutable Audit Trail**: All human review actions are permanently recorded in `data/reviews/annotation_events.jsonl` (and mirrored to `gs://joint-inspection-510310-data/datasets/production/jointinspect-v1/reviews/`). Review histories are never overwritten or deleted.

---

## 2. Review States & Taxonomy

### Review States:
1. `PENDING`: Staged in quarantine or initial import; awaiting engineer review.
2. `VERIFIED`: Confirmed by qualified inspector; eligible for production training manifest.
3. `REJECTED`: Fails image quality, severe motion blur, or provenance verification.
4. `AMBIGUOUS`: Severe occlusion or ambiguous joint feature; requires senior engineer adjudication.
5. `NEEDS_SECOND_REVIEW`: Flagged for cross-validation between two independent inspectors.

### Condition Taxonomy:
- `NORMAL_JOINT`: Intact, concentric pipe joint with no structural damage and gap $\le 1.0\text{ mm}$.
- `DISPLACED_JOINT`: Angular deflection or eccentric radial offset.
- `DAMAGED_JOINT`: Fractured socket, spalling, chips, cracks, or mechanical deformation.
- `INTRUDING_SEAL`: Extruded or displaced rubber elastomeric gasket.
- `DEPOSITS_OBSTACLES`: Invert sediment, silt accumulation, intruding tree roots, or foreign obstacles.
- `DIFFICULT_CONDITION`: Heavy turbid standing water, optical glare, or obscured geometry.

### Visibility Ratings:
- `FULL_VISIBILITY`: Complete $360^\circ$ joint circumference clearly visible.
- `PARTIAL_VISIBILITY`: $\ge 50\%$ circumference visible (e.g. minor invert sediment).
- `OBSCURED`: $< 50\%$ circumference visible.
- `UNUSABLE`: Unsuitable for automated measurement or supervised training.

---

## 3. Review Interface

The internal review interface (`tools/annotation-ui/`) can be launched locally via:
```bash
python -m tools.annotation_ui.server --port 8088
```
It provides real-time canvas visualization of joint boundaries, bounding box adjustments, and atomic event logging via `/api/review`.
