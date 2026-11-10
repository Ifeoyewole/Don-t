"""Disabled-by-default research API; existing production routes remain unchanged."""
import hmac
import json
import os

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.app.core.cv.ai.research_sewer_runtime import cloud_service, cloud_phase1_service

router = APIRouter()


@router.post('/sewer-research/unified')
async def unified(file: UploadFile = File(...), options: str = Form('{}'),
                  authorization: str | None = Header(default=None)):
    if os.getenv('JOINTINSPECT_SEWER_FUSION_ENABLED', 'false') != 'true':
        raise HTTPException(404, 'Unified sewer research is disabled')
    token = os.getenv('JOINTINSPECT_PREVIEW_TOKEN', '')
    if not token:
        raise HTTPException(503, 'Research access is not configured')
    if not authorization or not hmac.compare_digest(authorization, 'Bearer '+token):
        raise HTTPException(401, 'Research authentication required')
    if len(options) > 64*1024:
        raise HTTPException(413, 'Research options too large')
    try:
        kwargs = json.loads(options)
        if not isinstance(kwargs, dict) or set(kwargs)-{'rois', 'task', 'geometry', 'receipt', 'sequence_id', 'frame_index', 'context'}:
            raise ValueError('Unsupported options')
        # Only bounded, integer pixel ROIs; no browser calibration/approval flags.
        rois = kwargs.get('rois', [])
        if not isinstance(rois, list) or len(rois) > 8 or any(not isinstance(r, list) or len(r) != 4 for r in rois):
            raise ValueError('Invalid ROIs')
    except (ValueError, TypeError):
        raise HTTPException(422, 'Invalid research options')
    payload = await file.read(8*1024*1024+1)
    if len(payload) > 8*1024*1024:
        raise HTTPException(413, 'Research image exceeds 8 MiB')
    try:
        phase1 = os.getenv('JOINTINSPECT_PHASE1_VERTEX_ENABLED') == 'true'
        if not phase1 and 'context' in kwargs:
            raise ValueError('Phase 1 metadata requires the isolated Phase 1 worker')
        service = await run_in_threadpool(cloud_phase1_service if phase1 else cloud_service)
        return await run_in_threadpool(service.infer, payload, **kwargs)
    except ValueError:
        raise HTTPException(422, 'Invalid research image or task')
    except Exception:
        raise HTTPException(503, 'Research worker unavailable; review required')
