"""Local HTTP integration fixture using recorded real artifacts, never models.

Must be launched explicitly by verify-unified-site.mjs. Not a serving backend,
not deployed, no model-loading fallback and no fabricated live interpretation.
"""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path

import backend.app.api.v1.endpoints.sewer_research as endpoint
from backend.app.main import app

root = Path(os.environ['JOINTINSPECT_REPLAY_DIR'])
recorded = json.loads((root/'unified-report.json').read_text())


class RecordedOnly:
    def infer(self, payload, **kwargs):
        if hashlib.sha256(payload).hexdigest() != recorded['image_sha256']:
            raise ValueError('Replay only accepts its exact recorded original')
        result = copy.deepcopy(recorded)
        result['overlay_png_base64'] = base64.b64encode((root/'overlay.png').read_bytes()).decode()
        for region in result['regions']:
            path = root/f'mask-{region["region_id"]}.png'
            if path.exists(): region['mask_png_base64'] = base64.b64encode(path.read_bytes()).decode()
        result['gemini']['status'] = 'RECORDED_REPLAY_NO_NEW_VERTEX_CALL'
        result['summary'] = 'RECORDED ARTIFACT REPLAY — '+result['summary']
        result['replay_only'] = True
        return result


endpoint.cloud_phase1_service = lambda: RecordedOnly()
