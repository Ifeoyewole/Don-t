import pytest
from backend.tests.test_inspection_advisory import engine
from backend.tests.test_phase1_unified import payload
from backend.app.core.cv.ai.review_interpretation import interpret


def test_optional_review_is_signed_cached_and_does_not_train_or_override(monkeypatch):
    response={'proposed_label':'GEOMETRY_UNCERTAIN','explanation':'Operator correction needs independent verification.','boundary_guidance':'Compare the two material edges.','needs_clarification':True}
    vertex,ledger,calls=engine(monkeypatch,response)
    review={'notes':'Boundary is misplaced','defect':'UNCERTAIN','siteMeasuredGapMm':3.5,'measurementMethod':'feeler gauge','revision':1}
    first=interpret(payload(),review,vertex);second=interpret(payload(),review,vertex)
    assert first==second and len(calls)==1 and len(ledger.value['claims'])==1
    assert first['authoritative'] is False and first['training_eligible'] is False
    assert first['interpretation']['proposed_label']=='GEOMETRY_UNCERTAIN'
    key=next(k for k in vertex.store.data if k.startswith('optional-reviews/'))
    vertex.store.data[key]['interpretation']['explanation']='tampered'
    with pytest.raises(ValueError):interpret(payload(),review,vertex)


def test_review_rejects_invented_physical_measurements(monkeypatch):
    vertex,_,_=engine(monkeypatch,{'proposed_label':'OPEN_JOINT','explanation':'Gap is 12 mm.','boundary_guidance':'Inspect edges.','needs_clarification':False})
    with pytest.raises(ValueError):interpret(payload(),{'notes':'test'},vertex)


def test_review_does_not_accept_client_training_authorization(monkeypatch):
    vertex,_,calls=engine(monkeypatch)
    with pytest.raises(ValueError):interpret(payload(),{'training_eligible':True},vertex)
    assert calls==[]


def test_invalid_upload_is_rejected_before_any_budget_reservation(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    import scripts.cloud.engineering_preview_budget as budget
    monkeypatch.setenv('JOINTINSPECT_SEWER_FUSION_ENABLED','true')
    monkeypatch.setenv('JOINTINSPECT_RESEARCH_IAM_ONLY','true')
    monkeypatch.setenv('JOINTINSPECT_RESEARCH_AUDIENCE','https://private.test')
    monkeypatch.setenv('JOINTINSPECT_RESEARCH_INVOKER_EMAIL','test@example.test')
    import google.oauth2.id_token
    monkeypatch.setattr(google.oauth2.id_token,'verify_oauth2_token',lambda *a:{'email_verified':True,'email':'test@example.test'})
    calls=[];monkeypatch.setattr(budget,'reserve',lambda *a:calls.append(True))
    response=TestClient(app).post('/api/v1/cv/sewer-research/unified',headers={'Authorization':'Bearer test'},files={'file':('bad.jpg',b'not an image')})
    assert response.status_code==422 and calls==[]


def test_identical_feedback_revisions_do_not_duplicate_paid_calls(monkeypatch):
    response={'proposed_label':'UNMAPPED','explanation':'Needs independent review.','boundary_guidance':'Inspect the edges.','needs_clarification':True}
    vertex,_,calls=engine(monkeypatch,response)
    first=interpret(payload(),{'notes':'same correction','revision':1},vertex)
    second=interpret(payload(),{'notes':'same correction','revision':2},vertex)
    assert len(calls)==1 and first['review_revision']==1 and second['review_revision']==2
