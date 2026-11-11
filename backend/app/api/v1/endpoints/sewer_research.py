"""Disabled-by-default research API; existing production routes remain unchanged."""
import hmac
import json
import os

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.app.core.cv.ai.research_sewer_runtime import cloud_service, cloud_phase1_service
from backend.app.api.v1.endpoints.calibration import CalibrationReferenceCheck
from scripts.cloud.preview_spending import PreviewBudgetDenied

router = APIRouter()


async def authorize(authorization):
    if os.getenv('JOINTINSPECT_SEWER_FUSION_ENABLED', 'false') != 'true':
        raise HTTPException(404, 'Unified sewer research is disabled')
    if os.getenv('JOINTINSPECT_RESEARCH_IAM_ONLY') == 'true':
        try:
            from google.oauth2 import id_token
            from google.auth.transport.requests import Request
            audience = os.environ['JOINTINSPECT_RESEARCH_AUDIENCE']
            if not authorization or not authorization.startswith('Bearer '):
                raise ValueError('Missing identity')
            claims = await run_in_threadpool(id_token.verify_oauth2_token, authorization[7:], Request(), audience)
            if (claims.get('email_verified') is not True or claims.get('email') !=
                    os.environ['JOINTINSPECT_RESEARCH_INVOKER_EMAIL']):
                raise ValueError('Untrusted identity')
        except Exception:
            raise HTTPException(401, 'Private engineering identity required')
    else:
        token = os.getenv('JOINTINSPECT_PREVIEW_TOKEN', '')
        if not token:
            raise HTTPException(503, 'Research access is not configured')
        if not authorization or not hmac.compare_digest(authorization, 'Bearer '+token):
            raise HTTPException(401, 'Research authentication required')


@router.post('/sewer-research/unified')
async def unified(file: UploadFile = File(...), options: str = Form('{}'),
                  authorization: str | None = Header(default=None)):
    await authorize(authorization)
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
        cache_blob = None
        if os.getenv('JOINTINSPECT_RESEARCH_IAM_ONLY') == 'true':
            from scripts.cloud.engineering_preview_budget import reserve
            try:
                cache_blob, cached = await run_in_threadpool(reserve, payload, kwargs)
            except ValueError:
                raise HTTPException(429, 'Research spending allowance unavailable; no automatic retry')
            if cached is not None:
                return cached
        phase1 = os.getenv('JOINTINSPECT_PHASE1_VERTEX_ENABLED') == 'true'
        if not phase1 and 'context' in kwargs:
            raise ValueError('Phase 1 metadata requires the isolated Phase 1 worker')
        service = await run_in_threadpool(cloud_phase1_service if phase1 else cloud_service)
        result = await run_in_threadpool(service.infer, payload, **kwargs)
        if cache_blob is not None:
            from scripts.cloud.engineering_preview_budget import save
            await run_in_threadpool(save, cache_blob, result)
        return result
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(422, 'Invalid research image or task')
    except Exception:
        raise HTTPException(503, 'Research worker unavailable; review required')


@router.post('/sewer-research/context-suggestions')
async def context_suggestions(file: UploadFile = File(...),
        metadata_pipe_diameter_mm: float | None = Form(None, gt=0, le=5000),
        metadata_source: str = Form('MANHOLE_METADATA'), authorization: str | None = Header(default=None)):
    await authorize(authorization)
    payload=await file.read(3*1024*1024+1)
    if not payload or len(payload)>3*1024*1024:
        raise HTTPException(413,'Suggestion image must be nonempty and at most3MiB')
    if metadata_source not in ('PROJECT_METADATA','MANHOLE_METADATA'):
        raise HTTPException(422,'Invalid metadata source')
    try:
        from backend.app.core.cv.ai.research_sewer_runtime import cloud_reconciler
        from backend.app.core.cv.ai.inspection_advisory import suggest
        engine=await run_in_threadpool(cloud_reconciler)
        return await run_in_threadpool(suggest,payload,engine,metadata_pipe_diameter_mm,metadata_source)
    except PreviewBudgetDenied:
        raise HTTPException(429,'Research spending allowance unavailable; no automatic retry')
    except ValueError:
        raise HTTPException(502,'Gemini suggestion response could not be validated; editable inputs remain available')
    except Exception:
        raise HTTPException(503,'Gemini suggestions unavailable; editable inputs remain available')


@router.post('/sewer-research/check-reference')
async def check_reference(request: CalibrationReferenceCheck,
                          authorization: str | None = Header(default=None)):
    await authorize(authorization)
    from backend.app.api.v1.endpoints.calibration import check_calibration_reference
    return await check_calibration_reference(request)
