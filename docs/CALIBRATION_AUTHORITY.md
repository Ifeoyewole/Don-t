
# Calibration authority

JointInspect keeps user access open, but engineering calibration authority is
server-owned. The browser may submit a reference ID and metadata; it cannot
verify itself.

Configure trusted records through `JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON`.
Example:

```json
[
  {
    "reference_id": "CAL-RIG-300-2026-001",
    "project_id": "project-123",
    "source": "TEST_RIG",
    "pipe_diameter_mm": 300.0,
    "camera_id": "CCTV-STANDARD-01",
    "validated_joint_types": ["CIRCULAR_OPENING"]
  }
]
```

A measurement can expose authoritative millimetres only when the server finds a
matching trusted record and the final measurement decision is
`ACCEPTED_MEASUREMENT`. Review or rejected results remain diagnostic only.

## Reference verification and mixed-image evidence

An inspector can save a camera/reference suggestion per manhole and query
`POST /api/v1/cv/calibration/check-reference`. This read-only preflight
responds whether the supplied project, diameter, source and camera match a
server-owned record. It never registers a calibration or accepts
`calibration_verified=true` from the client.

All physical measurements require a server-owned reference with an explicit
`camera_id`. A record can limit supported geometry through
`validated_joint_types`; a missing list defaults conservatively to
`["CIRCULAR_OPENING"]`. Seam geometry must be explicitly authorized in the
server registry following an appropriate calibration protocol. A nominal pipe
diameter or a Gemini-generated observation cannot validate perspective,
camera intrinsics or physical scale.

Each uploaded image stores its own joint geometry, inspector note and
AI suggestion. An image with unclear or unsupported measurement geometry may
be retained in `EVIDENCE_ONLY` mode and reported as `REVIEW`, without an
authoritative millimetre gap or engineering PASS. This enables mixed pipe
materials, side laterals and other conditions to be reviewed without
relabeling them as open joints. It does not claim defect classifier validation
for all such conditions.

Production operators must register verified calibration references through
the deployment's protected configuration, using genuine calibration evidence
and camera IDs. No test or example data should be treated as production
calibration authority.

## Image-specific measured reference for close-up seams

Close-ups must not convert pipe diameter using an assumed fraction of image
width. The seam detector now requires a measured scale from a server-owned
record. Keep the existing project, source, internal pipe diameter, camera and
validated joint type fields, and supply all of:

- `reference_length_mm`: measured physical length of the reference at the joint plane.
- `reference_span_px`: corresponding span in the rectified original image, along the measurement direction.
- `image_sha256`: SHA-256 of the exact uploaded file bytes.
- `image_width` and `image_height`: rectified image resolution in pixels.

The trusted scale is `reference_span_px / reference_length_mm` pixels/mm.
An engineer must verify the reference plane, camera correction, perspective
and span before placing the record in the protected calibration configuration.
Do not use a ruler on a different plane or an arbitrary image-width fraction.
Changing the image bytes, crop or resolution invalidates this seam reference.
A camera-intrinsics profile alone does not establish metric scale.

Diameter, camera and geometry still have to match the existing registry checks.
Circular openings continue to use verified internal diameter and detected pipe
geometry; each photo can have its own diameter. Old diameter-only seam records
now produce pixel diagnostics with no authoritative mm. Existing saved reports
are not rewritten; explicitly remeasure after registering a genuine reference.
The read-only reference preflight matches record identity; actual image binding
and reliable geometry are checked during measurement.
