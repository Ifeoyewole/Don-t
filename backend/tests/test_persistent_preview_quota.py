"""Accounting contracts: synthetic money, no provider calls or cloud resources."""
import copy
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from scripts.cloud.persistent_preview_quota import (
    CEILING, CYCLE, LEDGER_URI, LedgerConflict, QuotaDenied, reserve, validate_ledger,
)
from scripts.cloud.research_semantic_receipts import validate_scope


def policy():
    from backend.app.core.cv.ai.research_gemini_reconciliation import contract_sha
    return {'lifecycle': 'ENGINEERING_PREVIEW', 'mode': 'PREVIEW',
        'model': 'gemini-3.1-pro-preview', 'location': 'global',
        'review_approval_id': 'test-upload-permission', 'spending_approval_id': 'test-no-money',
        'input_authorization': 'IAM_AUTHENTICATED_WEBSITE_UPLOADS',
        'budget_ledger_uri': LEDGER_URI, 'budget_cycle': CYCLE, 'runtime_artifact_sha256': 'a'*64,
        'currency': 'USD', 'spending_cap': 100, 'max_analysis_passes': 2,
        'receipt_prefix': 'models/inspect-view/research-results/engineering-preview-persistent/v1',
        'prompt_sha256': contract_sha()}


def opening():
    return {'schema': 1, 'cycle': CYCLE, 'status': 'ACTIVE', 'currency': 'USD',
        'ceiling_microusd': CEILING, 'opening_approval_id': 'synthetic-only',
        'prior_accounting_evidence': 'Synthetic fixture; not a real account balance',
        'pricing_evidence': 'Synthetic conservative token envelope',
        'prior_consumption_bound_microusd': 10_000_000, 'infrastructure_reserve_microusd': 5_000_000,
        'period_seconds': 86400, 'period_limits': {'inspection': 5, 'gemini': 10},
        'operation_reservations_microusd': {'inspection': 1_000_000, 'gemini': 2_000_000},
        'claims': {}, 'period_usage': {}}


class MemoryLedger:
    def __init__(self, value=None):
        self.value = opening() if value is None else value
        self.generation = 1
        self.lock = threading.Lock()
    def read(self):
        with self.lock:
            return copy.deepcopy(self.value), self.generation
    def replace(self, value, generation):
        with self.lock:
            if generation != self.generation: raise LedgerConflict()
            self.value = copy.deepcopy(value); self.generation += 1


def key(n):
    return hashlib.sha256(str(n).encode()).hexdigest()


def claim(ledger, kind, n, now=100000):
    reserve(policy(), None, kind, key(n), now=now, ledger=ledger)


def test_calendar_quota_recovers_but_money_never_replenishes():
    ledger = MemoryLedger();ledger.value['period_limits']['inspection'] = 1
    claim(ledger, 'inspection', 'first')
    with pytest.raises(QuotaDenied, match='Period quota'): claim(ledger, 'inspection', 'second')
    claim(ledger, 'inspection', 'second', now=100000+86400)
    assert validate_ledger(ledger.value) == 17_000_000
    assert len(ledger.value['claims']) == 2


def test_total_budget_exhausts_independently_of_period_and_scope_revision():
    ledger = MemoryLedger();ledger.value['prior_consumption_bound_microusd'] = 94_000_000
    claim(ledger, 'inspection', 'one')
    changed = policy(); changed['review_approval_id'] += '-new-revision'
    with pytest.raises(QuotaDenied, match='Cumulative'):
        reserve(changed, None, 'inspection', key('two'), now=200000, ledger=ledger)
    assert validate_ledger(ledger.value) == CEILING


def test_duplicate_or_failed_work_is_never_automatically_refunded_or_retried():
    ledger = MemoryLedger();claim(ledger, 'gemini', 'failed')
    with pytest.raises(QuotaDenied, match='Previously reserved'): claim(ledger, 'gemini', 'failed', now=999999)
    assert validate_ledger(ledger.value) == 17_000_000


@pytest.mark.parametrize('change', [
    {'status': 'PAUSED'}, {'prior_consumption_bound_microusd': None}, {'currency': 'GBP'},
    {'ceiling_microusd': CEILING+1}, {'prior_accounting_evidence': ''}, {'pricing_evidence': ''},
    {'period_usage': {'1': {'inspection': 9, 'gemini': 0}}},
    {'operation_reservations_microusd': {'inspection': 1, 'gemini': 1}},
])
def test_corrupt_unfunded_or_underpriced_accounting_fails_closed(change):
    ledger = MemoryLedger();ledger.value.update(change)
    with pytest.raises(QuotaDenied): claim(ledger, 'inspection', 'blocked')
    assert not ledger.value['claims']


def test_atomic_concurrency_cannot_double_spend_remaining_funds():
    ledger = MemoryLedger();ledger.value['prior_consumption_bound_microusd'] = 94_000_000
    def run(n):
        try: claim(ledger, 'inspection', n);return True
        except QuotaDenied:return False
    with ThreadPoolExecutor(max_workers=16) as workers:
        assert sum(workers.map(run, range(16))) == 1
    assert len(ledger.value['claims']) == 1


def test_independent_process_handles_share_same_state_and_daily_quota():
    ledger = MemoryLedger()
    for n in range(5): claim(ledger, 'inspection', n)
    with pytest.raises(QuotaDenied, match='Period quota'): claim(ledger, 'inspection', 6)
    # New wrapper, same durable state (simulates worker restart).
    restarted = MemoryLedger(copy.deepcopy(ledger.value))
    with pytest.raises(QuotaDenied, match='Period quota'): claim(restarted, 'inspection', 6)


def test_policy_has_no_calendar_expiry_and_cannot_redirect_or_reset_budget():
    for now in (1, 1794393096, 4102444800): validate_scope(policy(), 'a'*64, now)
    for field, value in [('expires_unix', 4102444800), ('budget_ledger_uri', LEDGER_URI+'-new'),
                         ('mode', 'PRODUCTION'), ('spending_cap', 101)]:
        bad = policy();bad[field] = value
        with pytest.raises(ValueError): validate_scope(bad, 'a'*64, 100)


def test_reconciler_reserves_before_count_and_generate_and_reuses_authenticated_cache(monkeypatch):
    from backend.tests.test_phase1_unified import reconciler, interpretation, payload
    from backend.app.core.cv.ai.phase1_unified import Phase1Unified
    from backend.tests.test_phase1_unified import fusion
    import scripts.cloud.persistent_preview_quota as module
    ledger = MemoryLedger();monkeypatch.setattr(module, 'GcsLedger', lambda bucket: ledger)
    vertex = reconciler();vertex.scope = policy();vertex.store.bucket = SimpleNamespace(name='joint-inspection-510310-data')
    calls = []
    def count(body):
        assert len(ledger.value['claims']) == 1
        calls.append('count');return 2000
    vertex.token_counter = count
    vertex.transport = lambda body: (calls.append('generate') or interpretation(), {})
    service = Phase1Unified(fusion=fusion(), reconciler=vertex)
    first = service.infer(payload(), rois=[[50,20,150,100]])
    second = service.infer(payload(), rois=[[50,20,150,100]])
    assert first['gemini']['status'] == second['gemini']['status'] == 'AUTHENTICATED_ADVISORY'
    assert calls == ['count', 'generate']
    assert len(ledger.value['claims']) == 1


def test_input_cost_envelope_stops_generation_without_refunding_reservation(monkeypatch):
    from backend.tests.test_phase1_unified import reconciler, payload, fusion
    from backend.app.core.cv.ai.phase1_unified import Phase1Unified
    import scripts.cloud.persistent_preview_quota as module
    ledger = MemoryLedger();monkeypatch.setattr(module, 'GcsLedger', lambda bucket: ledger)
    vertex = reconciler();vertex.scope=policy();vertex.store.bucket=SimpleNamespace(name='joint-inspection-510310-data')
    vertex.token_counter = lambda body: 100001
    calls=[];vertex.transport=lambda body:calls.append(body)
    result=Phase1Unified(fusion=fusion(),reconciler=vertex).infer(payload(),rois=[[50,20,150,100]])
    assert not calls
    assert len(ledger.value['claims']) == 1
    assert result['gemini']['status'] != 'AUTHENTICATED_ADVISORY'


def test_preparation_never_invents_or_resets_historical_spending(tmp_path):
    from scripts.cloud.prepare_persistent_preview import prepare, money
    for amount in ('NaN', '-1', '101', '0.0000001', 'Infinity'):
        with pytest.raises(ValueError): money(amount)
    with pytest.raises(ValueError): prepare(prior_usd='96', evidence='owner upper bound', approval='owner', output=tmp_path, image_digest='sha256:'+'a'*64)
    scope, ledger = prepare(prior_usd='20', evidence='synthetic upper bound, no billing claim', approval='TEST', output=tmp_path, image_digest='sha256:'+'a'*64)
    assert validate_ledger(ledger) == 25_000_000
    assert 'expires_unix' not in scope
    assert ledger['ceiling_microusd'] == CEILING


def test_cache_identity_survives_deployments_approval_changes_and_new_upload_ids():
    from scripts.cloud.engineering_preview_budget import response_key
    first = policy(); second = policy(); second['review_approval_id']='another-approved-scope-revision'
    a=response_key(first,'a'*64,{'task':'JOINT_GEOMETRY','context':{'image_id':'local-one','project_id':'project'}})
    b=response_key(second,'a'*64,{'task':'JOINT_GEOMETRY','context':{'image_id':'local-two','project_id':'project'}})
    assert a==b
    second['runtime_artifact_sha256']='b'*64
    assert a!=response_key(second,'a'*64,{'task':'JOINT_GEOMETRY','context':{'project_id':'project'}})
    assert a!=response_key(first,'b'*64,{'task':'JOINT_GEOMETRY','context':{'project_id':'project'}})
    assert a!=response_key(first,'a'*64,{'task':'JOINT_GEOMETRY','context':{'project_id':'another-project'}})


def test_gcs_adapter_uses_generation_conditions_and_never_recreates_missing_ledger():
    import json
    from google.api_core.exceptions import NotFound, PreconditionFailed
    from scripts.cloud.persistent_preview_quota import GcsLedger
    class Blob:
        generation=7
        size=1024
        missing=False
        def reload(self, **kwargs):
            if self.missing:raise NotFound('missing')
        def download_as_bytes(self, **kwargs):
            assert kwargs['if_generation_match']==7
            return json.dumps(opening()).encode()
        def upload_from_string(self, payload, **kwargs):
            assert kwargs['if_generation_match']==7 and kwargs['retry'] is None
            raise PreconditionFailed('another writer won')
    blob=Blob();bucket=SimpleNamespace(name='joint-inspection-510310-data',blob=lambda path:blob)
    ledger=GcsLedger(bucket);value,generation=ledger.read()
    assert generation==7 and value['ceiling_microusd']==CEILING
    with pytest.raises(LedgerConflict):ledger.replace(value,generation)
    blob.missing=True
    with pytest.raises(QuotaDenied,match='never initialize'):ledger.read()


def test_private_worker_requires_iam_before_quota_and_never_initializes_models_when_denied(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    import google.oauth2.id_token
    import scripts.cloud.engineering_preview_budget as budget
    import backend.app.api.v1.endpoints.sewer_research as endpoint
    monkeypatch.setenv('JOINTINSPECT_SEWER_FUSION_ENABLED','true')
    monkeypatch.setenv('JOINTINSPECT_RESEARCH_IAM_ONLY','true')
    monkeypatch.setenv('JOINTINSPECT_RESEARCH_AUDIENCE','https://private-worker.a.run.app')
    monkeypatch.setenv('JOINTINSPECT_RESEARCH_INVOKER_EMAIL','allowed@example.test')
    calls=[]
    monkeypatch.setattr(endpoint,'cloud_phase1_service',lambda:calls.append('MODEL_MUST_NOT_LOAD'))
    def denied(*args):calls.append('budget');raise QuotaDenied('Cumulative research allowance exhausted')
    monkeypatch.setattr(budget,'reserve',denied)
    client=TestClient(app);url='/api/v1/cv/sewer-research/unified';files={'file':('frame.png',b'synthetic')}
    assert client.post(url,files=files).status_code==401
    monkeypatch.setattr(google.oauth2.id_token,'verify_oauth2_token',lambda *args:{'email':'wrong@example.test','email_verified':True})
    assert client.post(url,files=files,headers={'Authorization':'Bearer synthetic'}).status_code==401
    assert calls==[]
    monkeypatch.setattr(google.oauth2.id_token,'verify_oauth2_token',lambda *args:{'email':'allowed@example.test','email_verified':True})
    assert client.post(url,files=files,headers={'Authorization':'Bearer synthetic'}).status_code==429
    assert calls==['budget']
