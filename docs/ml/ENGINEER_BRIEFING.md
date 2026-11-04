# JointInspect engineer briefing

Inspect View is integrated into the normal inspection workflow. For the clearest evidence, use focused internal pipe/sewer CCTV images with the joint or defect visible, adequate lighting, limited glare, and minimal obstruction.

The best-supported current model findings are joint displacement (F1 0.946, recall 98.0%, 443 development positives) and normal pipe condition (F1 0.933, recall 94.5%, 183 positives). These development results are preliminary and do not guarantee field performance. Normal pipe classification does not prove joint visibility, joint integrity or engineering acceptance.

Broken pipe, surface damage and deformation need closer review. Open-joint and protruding-lateral detection are unvalidated. Infiltration and obstacle detection are unreliable. A below-threshold prediction does not rule out a defect. Blurred, dark, obstructed or reflective images may be rejected or require recapture/review.

Inspect View supplies defect evidence, OpenCV resolves image geometry, and Gemini on Vertex AI provides scene assessment and observations. Physical millimetres require server-verified calibration and reliable geometry. Unsupported imagery, model failures or missing calibration must never silently become engineering PASS.

## Dataset partnerships and requests

We need datasets from utilities, inspection contractors and private research collections. Prioritize open joints, active infiltration, protruding laterals and visually similar negatives. Ask for original images/videos, original labels and annotation instructions, source video/asset IDs, timestamps, camera/material/diameter metadata when available, and written permission covering training, evaluation and intended deployment. Do not send account passwords or API keys in inspection notes.

- Sewer-ML access request: https://forms.gle/hBaPtoweZumZAi4u9
- AI-Hub dataset 139 (LP): https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=139 — request download approval on the introduction tab.
- VideoPipe access conditions: https://videopipe.github.io/
- Co-UDlabs source and contacts: https://github.com/Co-UDlabs/sewer_defects/tree/coudlabs

These are access-request leads, not promises of access or commercial permission. We can provide additional partner-specific links when available; no private organisation is represented as having approved access.
