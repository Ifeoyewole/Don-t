"""Synthetic provider responses test advisory wiring, not detection accuracy."""
from types import SimpleNamespace
import pytest
from backend.tests.test_preview_spending import policy,MemoryLedger
from backend.tests.test_phase1_unified import reconciler,payload
from backend.app.core.cv.ai.inspection_advisory import suggest


def visual():
    return {'domain_status':'PIPE_JOINT_INSPECTION','pipe_visible':True,'quality_usable':True,
        'geometry':'VERTICAL_SEAM','inspection_context':'A seam is visible with debris on its lower edge.',
        'possible_gap_visible':True,'calibration_guidance':'Use a known-length target beside the seam at its plane; debris obscures the lower edge.',
        'reference_kind':'NONE','reference_bbox':[],'limitations':['No visible known-size reference.']}


def engine(monkeypatch,response=None):
    import scripts.cloud.preview_spending as spending
    ledger=MemoryLedger();monkeypatch.setattr(spending,'GcsLedger',lambda bucket:ledger)
    vertex=reconciler();vertex.scope=policy();vertex.store.bucket=SimpleNamespace(name='joint-inspection-510310-data')
    calls=[];vertex.token_counter=lambda body:2000
    vertex.transport=lambda body:(calls.append(body) or (response or visual()),{})
    return vertex,ledger,calls


def test_actual_suggestion_path_is_image_specific_signed_cached_and_never_claims_calibration(monkeypatch):
    vertex,ledger,calls=engine(monkeypatch)
    first=suggest(payload(),vertex,900,'MANHOLE_METADATA')
    second=suggest(payload(),vertex,300,'MANHOLE_METADATA')
    assert len(calls)==1 and len(ledger.value['claims'])==1
    assert first['suggested_inspection_context']==visual()['inspection_context']
    assert first['calibration']['suggested_notes']==visual()['calibration_guidance']
    assert first['calibration']['pipe_diameter_mm']==900 and second['calibration']['pipe_diameter_mm']==300
    assert first['calibration']['verified'] is False and first['calibration']['calibration_reference_id'] is None
    assert calls[0]['contents'][0]['parts'][1]['inlineData']['data']


@pytest.mark.parametrize('mutation',[{'reference_bbox':[0,0,9999,9999],'reference_kind':'MARKED_RULER'},
                                    {'calibration_guidance':'The gap is 15 mm.'}])
def test_invalid_reference_or_fabricated_physical_measurement_is_rejected(monkeypatch,mutation):
    result=visual();result.update(mutation);vertex,_,_=engine(monkeypatch,result)
    with pytest.raises(ValueError):suggest(payload(),vertex)


def test_non_joint_pipe_gets_context_but_no_fabricated_joint_orientation(monkeypatch):
    result=visual();result.update(domain_status='PIPE_INTERIOR_NO_JOINT',geometry='NONE',possible_gap_visible=False)
    vertex,_,_=engine(monkeypatch,result);response=suggest(payload(),vertex)
    assert response['processing_allowed'] and response['suggested_inspection_context']
    assert response['suggested_joint_type'] is None


def test_private_reference_lookup_returns_missing_reference_not_service_failure(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    monkeypatch.setenv('JOINTINSPECT_SEWER_FUSION_ENABLED','true')
    monkeypatch.setenv('JOINTINSPECT_RESEARCH_IAM_ONLY','false')
    monkeypatch.setenv('JOINTINSPECT_PREVIEW_TOKEN','synthetic')
    monkeypatch.setenv('JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON','[]')
    response=TestClient(app).post('/api/v1/cv/sewer-research/check-reference',headers={'Authorization':'Bearer synthetic'},
        json={'reference_id':'actual-requested-reference','project_id':'test','source':'MANHOLE_METADATA','pipe_diameter_mm':900})
    assert response.status_code==200
    assert response.json()['reference_verified'] is False
    assert response.json()['status']=='CALIBRATION_REQUIRED'
