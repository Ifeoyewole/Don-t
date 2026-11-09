# JointInspect Unified Vision — task-aware research batch

**Research only: not deployed.** The new batch worker separates
joint geometry, object segmentation and infiltration investigation, rather
than forcing every CCTV frame to be treated as a joint-gap measurement.

## Allowed task types

| task_type | Evidence | Limitations |
|---|---|---|
| JOINT_GEOMETRY | Existing r5 + SAM2 + OpenCV joint geometry, optional signed Gemini | No physical mm without calibration; no engineering PASS |
| OBJECT_SEGMENTATION | r5 exploratory evidence + SAM2 object mask, optional signed Gemini | No OpenCV joint seam measurement; no automatic PROTRUDING_LATERAL diagnosis |
| INFILTRATION_REVIEW | r5 exploratory evidence + optional SAM2 feature mask, optional signed Gemini | A still does not prove active groundwater entry; requires multi-frame or inspector evidence |

All tasks return research_only=true, REVIEW_REQUIRED, defect=UNDETERMINED,
physical_gap_mm=null and engineering_result=null unless a separately
validated engineering pipeline is later authorized. Object/infiltration
tasks always have geometry.status=NOT_APPLICABLE_FOR_TASK and
pixel_candidate=null.

The normal Gemini 3.1 Pro gate may return PIPE_INTERIOR_NO_JOINT with
processing_allowed=false because joint-gap measurement is not justified.
A correctly signed, same-image receipt with pipe_visible=true, good quality
and no prompt conflict can still describe a pipe scene as
RESEARCH_PIPE_INTERIOR_ACCEPTED on nonjoint tasks, WITHOUT reversing the
live processing_allowed=false. Bad, wrong-scene or unverifiable receipts
block mask acceptance. Missing receipts explicitly say NOT_PROVIDED.
The GPU worker never invokes Gemini.

## Four reviewed-pilot candidate frames

These are provisional ROIs from uploaded 416x416 export images, NOT approved
or independently verified dataset annotations:

| Frame | Task | Proposed initial ROI | Still needed |
|---|---|---|---|
| #10 | JOINT_GEOMETRY | [96,125,401,404] | Confirm visible offset boundaries; embedded caption covers some pixels |
| #26 | OBJECT_SEGMENTATION | [164,51,410,415] | Verify the diagonal material is truly an intrusive lateral |
| #34 | OBJECT_SEGMENTATION | [42,109,375,248] | Verify the horizontal cylinder is a lateral protrusion |
| #41 | INFILTRATION_REVIEW | No approved ROI | Obtain adjacent CCTV frames or field evidence; stain alone is insufficient |

Do not automatically mark these frames READY_FOR_RESEARCH. Rights,
original video/source lineage, image SHA-256 and human-reviewed ROI are
separate requirements.

## CSV task selection

The worklist generator now includes a blank task_type_TO_REVIEW column.
For an existing worklist without it, add the column manually. Populate
values only after human inspection; NEVER infer task from the original
Roboflow source label. Unspecified task retains the legacy joint-geometry
mode, which still requires a reviewer-defined geometry.

Example, PowerShell, preparing task categories without approving any ROI:

~~~powershell
$rows = @(Import-Csv ".\unified-pilot-14-review.csv")
foreach ($row in $rows) {
    $row | Add-Member -NotePropertyName task_type_TO_REVIEW -NotePropertyValue "" -Force
    switch ([int]$row.contact_sheet_number) {
        10 { $row.task_type_TO_REVIEW = "JOINT_GEOMETRY" }
        26 { $row.task_type_TO_REVIEW = "OBJECT_SEGMENTATION" }
        34 { $row.task_type_TO_REVIEW = "OBJECT_SEGMENTATION" }
        41 { $row.task_type_TO_REVIEW = "INFILTRATION_REVIEW" }
    }
}
$rows | Export-Csv ".\unified-pilot-14-task-review.csv" -NoTypeInformation -Encoding UTF8
~~~

For JOINT_GEOMETRY the CSV must have geometry_TO_REVIEW set to
VERTICAL_SEAM, HORIZONTAL_SEAM or CIRCULAR_OPENING. For the other two
task types, geometry_TO_REVIEW MUST remain blank: the converter rejects
an artificial joint geometry. Every task still requires a manually
selected 4-point ROI in the original image coordinates, a confirmed
source family, original image GCS URI/hash, and rights/label status.

Convert only human-reviewed rows with
scripts/cloud/create_unified_batch_manifest.py. Follow the existing batch
instructions in docs/ml/UNIFIED_VISION_BATCH_V1.md.

## Validation and deployment

The new tests check manifest task restrictions, signed Gemini evidence,
same-decoded-frame SAM2 masks, nonjoint OpenCV abstention, lack of mm and
infiltration temporal uncertainty. Existing joint-geometry behavior
remains unchanged.

After merging, build a NEW research Docker image with
scripts/cloud/cloudbuild-inspect-view-sam2.yaml and pin its SHA-256 digest.
The previous GPU smoke container does NOT include task-aware code.
Use only a reviewer-approved manifest, a unique GCS output prefix and
the existing Spot T4 bounded batch template. Do not launch any paid
research GPU inference without reviewed sample and rights provenance.
