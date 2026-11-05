
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
