# JointInspect full imported-dataset audit

Status: **COMPLETED** for technical inventory; independent annotations, lineage and commercial rights remain unverified.

## Complete record accounting

| Evidence | Actual result |
|---|---:|
| Records audited | 1,034 (978 Sewer Defects Public + 56 Pipeline CCTV Defect Public) |
| Decoded images / matching SHA-256 / matching dimensions | 1,034 / 1,034 / 1,034 |
| Structurally valid annotation files | 1,034 |
| Exact SHA-256 duplicates within imports | 0 |
| Exact SHA-256 matches against available hashes in four baseline inventories | 0 |
| Exact baseline dHash collision candidates | 1 (not proof of duplication) |
| Near-duplicate candidate pairs / involved images | 1,135 / 416 |
| Cross-dataset candidate pairs / cross-split candidate pairs | 11 / 555 |
| Conservative similarity/family-hint groups | 98 |
| Records in candidate groups crossing original splits | 964 |
| Source image-label occurrences / verified label records | 1,422 / 0 |
| Unverified label records / verified lineage records | 1,034 / 0 |
| Technically readable unique classification candidates | 1,034 |
| Approved task-aware inference / verified evaluation / commercial training eligible | 0 / 0 / 0 |

Near-duplicate rule: pHash64 distance <=8 OR compatible dHash64 distance <=6. These are unreviewed candidates, not 1,135 confirmed duplicate pairs. Original splits remain unchanged. Baseline comparison reads the existing 20,000-record manifest plus SRuibo (1,952), robotic-pipe (1,917) and PVC (3,064) registries, comparing available recorded hashes; it is not a fresh byte audit of baseline images or an exhaustive near-duplicate search against every historical dataset.

## Annotation format finding

The source registry describes all records as YOLO bounding boxes. Actual files include **41 polygon-only images and two mixed box/polygon images: 64 polygons across 43 images**. There are 989 box-only and two empty annotation files. A first box-only parser flagged those 43 files; inspecting the original coordinates revealed the format mismatch. The regression-tested polygon parser resolved all structural failures and source-label mismatches, reusing the 1,034 generation-pinned image checks. Empty annotations do not prove NORMAL. Original annotations were preserved, not converted into approved ROIs or masks.

## Rights and label interpretation

Source `data.yaml`, README files and both registries declare CC BY 4.0. They attribute publication to Roboflow users, not an independently verified original CCTV owner. Both sources remain `RESEARCH_QUARANTINE`; upstream rights and commercial training permission are unverified.

`Joint offset`/`Offset joint` -> provisional JOINT_DISPLACEMENT; `Utility intrusion` -> provisional PROTRUDING_LATERAL; `Leak` -> provisional INFILTRATION investigation only. `Joint` does not establish OPEN_JOINT. Crack, buckling, roots, debris, holes and broken-pipe labels remain source observations with provisional mappings. No verified NORMAL_PIPE, OPEN_JOINT, active-infiltration or lateral positives are created.

## Deliverables

The artifact prefix contains `dataset_inventory.jsonl`, `duplicate_candidates.csv`, `source_family_audit.csv`, `label_mapping_review.csv`, `research_eligibility.csv`, `annotation_format_review.csv`, source metadata, 52 private contact sheets, stage packages, an evaluation protocol and a resumable run ledger. Source object generations and actual image/annotation hashes are recorded.

Next action: appoint a reviewer for task, ROI and real source-lineage decisions. Do not train or publish accuracy from the current source labels.

## Reproducibility and limits

Private audit artifacts: `gs://joint-inspection-510310-data/models/inspect-view/research-results/unified-audit/20261109T164513Z-85af07dc`. Original data and registry objects are unchanged. Model identities: Inspect View `repr-convnext-masked-r5-20261104` (SHA `659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7`); SAM2.1 Tiny (SHA `7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69`); OpenCV; Gemini `gemini-3.1-pro-preview`, configured location `global`.

Existing image: `europe-west2-docker.pkg.dev/joint-inspection-510310/joint-inspection-training/inspect-view-sam2-research@sha256:a3db9ffaa1d0704290ccee7c3dd9af81c9af860755be3a076187b9fe866db37c`; build `77fef1c6-b099-49e2-a9d3-840f3d936a52`. Seven baseline worker/receipt/model-loader source files match its build archive after Windows CRLF/BOM normalization and Python AST comparison. The new summary-count regression fix is not in that image and needs normal review before an approved rebuild. No rebuild was performed.

Tests: **274 backend tests passed**, including audit, task routing, signed receipts and the reporting regression. Compilation and diff checks passed. This proves software contracts, not current-container model accuracy or a new SAM2 runtime load. GPU jobs this cycle: **none**. Gemini calls this cycle: **none**. Exact cloud currency charges are unavailable; ordinary GCS operations/storage were used, not new paid compute jobs.

Production remains on `pipe-joint-api-00015-fej`; no APIs, gates, weights, IAM or runtime settings changed. Inspect View weights and these datasets remain research-scoped. No commercial release or production PASS is authorized.

Artifact upload verified: **81 create-only objects**, 13,899,846 bytes including the upload manifest. `upload_manifest.json` SHA-256: `9138fa9f03880dff6340d18f45ac265580ba81ef93754f65452f903d4f153a33`.
