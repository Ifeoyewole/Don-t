
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
    "camera_id": "CCTV-STANDARD-01"
  }
]
```

A measurement can expose authoritative millimetres only when the server finds a
matching trusted record and the final measurement decision is
`ACCEPTED_MEASUREMENT`. Review or rejected results remain diagnostic only.
