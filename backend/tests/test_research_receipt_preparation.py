"""Offline-only receipt signature, request deduplication and authorization tests."""
import hashlib
from io import BytesIO
from types import SimpleNamespace
from PIL import Image
import pytest
from scripts.cloud.research_semantic_receipts import get_or_create_receipt,check_existing,MODEL,semantic_contract_sha256
from backend.app.core.cv.ai.signed_gemini_receipt import sign_existing_semantic_result

SECRET=b'test-only-not-a-production-key-000000000000'
NOW=1800000000
GATE=dict(model=MODEL,domain_status='PIPE_INTERIOR_NO_JOINT',pipe_visible=True,joint_visible=False,
          quality='OK',processing_allowed=False,prompt_image_conflict=False,suggested_joint_type=None)

class Store:
    def __init__(self):self.data={}
    def get(self,name):return self.data.get(name)
    def create(self,name,value):
        if name in self.data:return False
        self.data[name]=value;return True


def setup():
    stream=BytesIO();Image.new('RGB',(32,32),'gray').save(stream,format='PNG');payload=stream.getvalue()
    scope=dict(model=MODEL,location='global',review_approval_id='SYNTHETIC-TEST-REVIEW',spending_approval_id='SYNTHETIC-TEST-BUDGET',approved_image_sha256s=[hashlib.sha256(payload).hexdigest()],max_requests=1,prompt_sha256=semantic_contract_sha256(),spending_cap=1,currency='GBP',expires_unix=NOW+60)
    return payload,scope


def test_reuse_is_authenticated_and_does_not_repeat_paid_call():
    payload,scope=setup();store=Store();calls=[]
    gate=SimpleNamespace(model=MODEL,location='global',settings=SimpleNamespace(VERTEX_MAX_RETRIES=0),evaluate=lambda image:calls.append(1) or SimpleNamespace(model_dump=lambda **kw:GATE))
    args=dict(prompt_sha256=semantic_contract_sha256(),store=store,scope=scope,secret=SECRET,gate_factory=lambda:gate,now=NOW)
    first,status=get_or_create_receipt(payload,**args)
    second,status=get_or_create_receipt(payload,**dict(args,scope=None))
    assert calls==[1] and first==second and status=='REUSED_AUTHENTICATED'
    assert second['semantic_gate']['processing_allowed'] is False


def test_no_approval_no_paid_call_and_failed_call_claim_is_not_retried():
    payload,scope=setup();store=Store();calls=[]
    def fail(image):calls.append(1);raise RuntimeError('simulated provider uncertainty')
    gate=SimpleNamespace(model=MODEL,location='global',settings=SimpleNamespace(VERTEX_MAX_RETRIES=0),evaluate=fail)
    args=dict(prompt_sha256=semantic_contract_sha256(),store=store,secret=SECRET,gate_factory=lambda:gate,now=NOW)
    with pytest.raises(ValueError,match='authorization'):get_or_create_receipt(payload,scope=None,**args)
    assert not calls and not store.data
    with pytest.raises(RuntimeError):get_or_create_receipt(payload,scope=scope,**args)
    with pytest.raises(ValueError,match='already claimed'):get_or_create_receipt(payload,scope=scope,**args)
    assert calls==[1]


@pytest.mark.parametrize('mutation',['signature','issuer','hash','expiry','model'])
def test_invalid_receipts_are_not_reused(mutation):
    payload,_=setup();sha=hashlib.sha256(payload).hexdigest()
    gate=dict(GATE,model='wrong-model') if mutation=='model' else GATE
    receipt=sign_existing_semantic_result(payload,gate,signing_secret=SECRET,issued_at=NOW)
    if mutation=='signature':receipt['signature']='0'*64
    if mutation=='issuer':receipt['issuer']='untrusted'
    if mutation=='hash':sha='b'*64
    with pytest.raises(ValueError):check_existing(receipt,sha,SECRET,NOW+31*86400 if mutation=='expiry' else NOW)


def test_invalid_signing_configuration_and_prompt_do_not_call_provider():
    payload,scope=setup();calls=[]
    args=dict(payload=payload,prompt_sha256=semantic_contract_sha256(),store=Store(),scope=scope,
              secret=b'short',gate_factory=lambda:calls.append(1),now=NOW)
    with pytest.raises(ValueError,match='Signing secret'):get_or_create_receipt(**args)
    with pytest.raises(ValueError,match='contract hash'):get_or_create_receipt(**dict(args,secret=SECRET,prompt_sha256='a'*64))
    assert not calls
