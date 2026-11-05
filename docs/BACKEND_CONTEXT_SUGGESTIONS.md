# JointInspect backend advisory context suggestions

## Purpose

The calibration form and inspection-context fields are separate concerns.
Gemini on Vertex AI can **suggest** visible joint geometry, possible gap
evidence, and a neutral observation. It **cannot infer** the nominal pipe
diameter, physical millimetres, camera intrinsics, calibrated scale, project
reference ID, verified material type or engineering PASS from a single image.

## API

`POST /api/v1/cv/context-suggestions` (multipart image, <=15 MiB)

* `file`: JPEG, PNG or WebP.
* `metadata_pipe_diameter_mm`: optional nominal diameter from an existing
  project/manhole record. Never taken from Gemini's visual guess.
* `metadata_source`: PROJECT_METADATA (default) or MANHOLE_METADATA.

Example response shape:

```json
{
  "domain_status": "PIPE_JOINT_INSPECTION",
  "processing_allowed": true,
  "model": "gemini-3.1-pro-preview",
  "image_quality_usable": true,
  "suggested_joint_type": "VERTICAL_SEAM",
  "suggested_inspection_context": "Two visible boundaries flank a dark strip; review possible separation.",
  "possible_gap_visible": true,
  "calibration": {
    "pipe_diameter_mm": 900,
    "source": "MANHOLE_METADATA",
    "calibration_reference_id": null,
    "verified": false,
    "authority": "UNVERIFIED_METADATA"
  },
  "review_required": true,
  "reason": "AI suggestions are advisory. An inspector must confirm geometry; only server-verified calibration can authorize millimetres."
}
```

Values above are an **illustrative contract only**, not a real analysis.

## Frontend integration handoff (Victor's separate task)

Once a photo is selected, send it to this endpoint with the already-saved
`manhole.pipeDiameterMm` (if reliable). Pre-fill **joint geometry** and
**inspection notes** as editable AI suggestions and clearly label them
"AI suggested - confirm". The inspector may accept or change them.
Pre-fill **nominal pipe diameter** only from project/manhole metadata.
Never tick "verified by operator" or manufacture a reference ID. A saved
browser profile is NOT equivalent to server verification.

Continue using `POST /api/v1/cv/measure` for measurements. The existing
server-owned `JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON` check remains the
only engineering calibration authority; physical millimetres remain withheld
without verified calibration and suitable geometry. The suggestion endpoint
does not change PASS/FAIL/REVIEW or classifier output.

The current Vertex semantic domain gate intentionally rejects non-pipe
interiors, ambiguous images and unrelated imagery. A close-up photograph
of concrete edges may not establish that it is internal pipe CCTV, and
therefore may produce no automatic suggestion.

## Deployment

Gemini 3.1 Pro Preview model ID: `gemini-3.1-pro-preview`.
Set `VERTEX_INSPECTION_MODEL=gemini-3.1-pro-preview` and
`VERTEX_INSPECTION_LOCATION=global` on **Cloud Run**, not Vite.
The supported global REST hostname is `aiplatform.googleapis.com`
with path `/locations/global/...`. The code defaults are updated but
existing deployed environment variables override them. This is a
preview model: verify project entitlement, billing, quota, latency, region
and response format before production. No unverified fallback to
Gemini 2.5 Flash is silently introduced.
