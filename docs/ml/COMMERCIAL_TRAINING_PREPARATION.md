# Commercial training preparation — not a commercially trained model

The next classifier retains the 15 canonical output heads and prioritises
OPEN_JOINT, INFILTRATION and PROTRUDING_LATERAL. The current 1,034-image audit
has zero independently verified label records, zero confirmed lineage records
and zero commercially cleared training records. Source annotation polygons do
not change those facts. Research r5 weights are not a commercial initializer.

`training/configs/commercial_candidate_v1.json` selects torchvision ConvNeXt Tiny
with `weights=None`; no pretrained weights or datasets are downloaded. The
pipeline rejects any non-null pretrained checkpoint. The future commercially
eligible registry must be independently approved and pinned by canonical JSON
SHA-256. Every record must match its approved hash, URI, family, split, labels
and explicitly observed labels. Rights/annotation/family review IDs and rights
proof hashes are required; INFILTRATION additionally requires temporal/field
evidence. Source labels and nominal permission flags alone do not establish rights.

The prepared loader verifies image SHA-256 before decoding. Unknown labels use
masked loss rather than becoming false negatives. Mild photometric augmentation
preserves the whole image; no synthetic defect identity or calibration is added.
Class weights use observed positives/negatives and a cap of ten; absent classes
are reported unsupported rather than invented by sampling. Family and similarity
groups cannot cross train/validation/test, and exact duplicate hashes fail closed.

The offline training harness exercises optimization, augmentation, validation,
fixed 0.5 thresholds, TP/FP/FN and per-class precision/recall/F1, immutable epoch
checkpoints, optimizer/RNG state, configuration/manifest fingerprints, experiment
JSONL and deterministic epoch-boundary resumption. The runnable CLI is bounded
to TWO synthetic CPU epochs and uses a tiny test model. Those checkpoints contain
`synthetic_only=true` and `production_eligible=false`; they are not Inspect View
candidates and their numerical results are not real defect-detection accuracy.
Regression tests verify uninterrupted versus resumed parameter equality,
checksum failure, leakage rejection and checkpoint non-overwrite.

Commercial execution remains disabled in the new harness until separately
reviewed eligible data, a training approval and a bounded launch adapter exist.
The real architecture factory and configuration are prepared, not a trained
ConvNeXt checkpoint. No paid training job or new commercial weights are claimed.
Segmentation IoU/Dice must use the existing segmentation evaluator only after
reviewed pixel masks exist. Compare r5 on the SAME independently held-out data
for research evaluation; do not initialize commercial weights from it.

Synthetic execution (local CPU only):

```sh
python -m training.commercial_candidate --synthetic-smoke-dir=/NEW/UNIQUE/SCRATCH/DIRECTORY
```

The next launch review must specify model/data/config hashes, verified family
partitions, no evaluation-image training or threshold tuning, GPU/runtime/currency
bounds, private create-only GCS checkpoint paths, checkpoint cadence and rollback.
No Vertex job submission or production deployment is included in this change.
