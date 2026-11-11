"""Isolated research semantic receipts; no production authentication changes.

No CLI performs paid inference. The callable requires an explicit reviewed,
budgeted scope and an atomic create-only store. Failed or uncertain requests
retain claims and are never retried automatically.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
import time
from typing import Mapping

from backend.app.core.cv.ai.signed_gemini_receipt import verify_signed_semantic_receipt,sign_existing_semantic_result
MODEL='gemini-3.1-pro-preview'
LOCATION='global'


def semantic_contract_sha256():
    import inspect
    from backend.app.core.cv.ai.vertex_semantic_gate import VertexSemanticGate
    return hashlib.sha256(inspect.getsource(VertexSemanticGate.evaluate).replace('\r\n','\n').encode()).hexdigest()


def receipt_key(image_sha256,prompt_sha256):
    if any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in (image_sha256,prompt_sha256)):
        raise ValueError('Image and prompt SHA-256 required')
    return hashlib.sha256(f'{MODEL}:{LOCATION}:{image_sha256}:{prompt_sha256}'.encode()).hexdigest()


def check_existing(receipt,image_sha256,secret,now=None):
    gate=verify_signed_semantic_receipt(receipt,original_image_sha256=image_sha256,signing_secret=secret,now=now)
    if gate['semantic_gate']['model']!=MODEL:raise ValueError('Unexpected Gemini model; no silent substitution')
    return gate


def validate_scope(scope,image_sha256,now):
    if not isinstance(scope,Mapping):raise ValueError('Research review and spending authorization required')
    if (scope.get('model')!=MODEL or scope.get('location')!=LOCATION
        or not isinstance(scope.get('review_approval_id'),str) or not scope['review_approval_id'].strip()
        or not isinstance(scope.get('spending_approval_id'),str) or not scope['spending_approval_id'].strip()):
        raise ValueError('Explicit review, model and spending scope required')
    from scripts.cloud.persistent_preview_quota import persistent, validate_policy
    if persistent(scope):
        validate_policy(scope)
        if not isinstance(image_sha256, str) or not re.fullmatch('[a-f0-9]{64}', image_sha256):
            raise ValueError('Original image hash required')
        return
    hashes=scope.get('approved_image_sha256s');maximum=scope.get('max_requests');cap=scope.get('spending_cap')
    expiry=scope.get('expires_unix')
    if (not isinstance(hashes,list) or type(maximum) is not int or not 1<=maximum<=100
        or len(hashes)>maximum or len(set(hashes))!=len(hashes)
        or image_sha256 not in hashes or any(not isinstance(h,str) or not re.fullmatch('[a-f0-9]{64}',h) for h in hashes)
        or type(expiry) is not int or expiry<now
        or type(cap) not in (int,float) or not math.isfinite(cap) or cap<=0
        or scope.get('currency') not in ('GBP','USD')):
        raise ValueError('Invalid or expired bounded spending scope')


class GcsCreateOnlyStore:
    """Explicit research storage adapter; constructing it makes no cloud call."""
    def __init__(self,bucket,prefix):
        if bucket.name!='joint-inspection-510310-data' or not prefix.startswith('models/inspect-view/research-results/'):
            raise ValueError('Private project research prefix required')
        self.bucket,self.prefix=bucket,prefix.rstrip('/')
    def get(self,name):
        from google.api_core.exceptions import NotFound
        blob=self.bucket.blob(self.prefix+'/'+name)
        try:
            blob.reload()
            if blob.size>64*1024:raise ValueError('Oversized receipt/claim')
            return json.loads(blob.download_as_bytes(if_generation_match=blob.generation))
        except NotFound:return None
    def create(self,name,value):
        from google.api_core.exceptions import PreconditionFailed
        try:
            self.bucket.blob(self.prefix+'/'+name).upload_from_string(json.dumps(value),content_type='application/json',if_generation_match=0)
            return True
        except PreconditionFailed:return False


def read_signing_secret(resource):
    if not re.fullmatch(r'projects/(?:567370443508|joint-inspection-510310)/secrets/jointinspect-research-semantic-hmac/versions/[1-9][0-9]*',resource):
        raise ValueError('Pinned isolated research Secret Manager version required')
    from google.cloud import secretmanager
    return secretmanager.SecretManagerServiceClient().access_secret_version(name=resource).payload.data


def make_isolated_gate():
    """New research client with copied settings; production singleton is untouched."""
    from backend.app.core.cv.ai.vertex_semantic_gate import VertexSemanticGate
    gate=VertexSemanticGate()
    gate.settings=gate.settings.model_copy(update={'VERTEX_MAX_RETRIES':0})
    if gate.model!=MODEL or gate.location!=LOCATION:
        raise ValueError('Configure the isolated research process for the exact model/global endpoint')
    return gate


def get_or_create_receipt(payload,*,prompt_sha256,store,scope,secret,gate_factory,now=None):
    """Reuse authentic evidence first; never retry a paid request after claim.

    gate_factory must construct the existing VertexSemanticGate implementation.
    It is injected so offline tests never contact Vertex. In live use provide
    backend.app.core.cv.ai.vertex_semantic_gate.VertexSemanticGate directly.
    """
    if not isinstance(secret,(str,bytes)) or len(secret.encode() if isinstance(secret,str) else secret)<32:
        raise ValueError('Signing secret must be configured before any paid request')
    now=int(time.time()) if now is None else now
    if not isinstance(payload,bytes) or not 0<len(payload)<=8*1024*1024:raise ValueError('Bounded original bytes required')
    if prompt_sha256!=semantic_contract_sha256():raise ValueError('Semantic contract hash mismatch')
    image_sha=hashlib.sha256(payload).hexdigest();key=receipt_key(image_sha,prompt_sha256)
    cached=store.get('receipts/'+key+'.json')
    if cached is not None:
        check_existing(cached,image_sha,secret,now)
        return cached,'REUSED_AUTHENTICATED'
    validate_scope(scope,image_sha,now)
    from scripts.cloud.persistent_preview_quota import persistent
    if persistent(scope):
        raise ValueError('Persistent preview requires the metered unified reconciler')
    if scope.get('prompt_sha256')!=prompt_sha256:raise ValueError('Approval must bind the exact semantic contract')
    from PIL import Image
    from io import BytesIO
    with Image.open(BytesIO(payload)) as original:
        if original.width*original.height>16_000_000:raise ValueError('Image dimensions exceed research limit')
    import cv2,numpy as np
    image=cv2.imdecode(np.frombuffer(payload,np.uint8),cv2.IMREAD_COLOR)
    if image is None or image.shape[0]*image.shape[1]>16_000_000:raise ValueError('Image cannot be decoded within limits')
    gate=gate_factory()
    if getattr(getattr(gate,'settings',None),'VERTEX_MAX_RETRIES',None)!=0:
        raise ValueError('Research semantic requests require zero automatic retries')
    if gate.model!=MODEL or gate.location!=LOCATION:raise ValueError('Semantic gate model/location mismatch')
    if not store.create('claims/'+key+'.json',{'image_sha256':image_sha,'model':MODEL,'prompt_sha256':prompt_sha256,
                 'issued_at':now,'spending_approval_id':scope['spending_approval_id'],'status':'CLAIMED_NO_AUTOMATIC_RETRY'}):
        raise ValueError('Request already claimed; inspect outcome instead of charging twice')
    result=gate.evaluate(image) # Existing semantic contract; no production flag or auth override.
    receipt=sign_existing_semantic_result(payload,result.model_dump(mode='json'),signing_secret=secret,issued_at=now)
    check_existing(receipt,image_sha,secret,now)
    if not store.create('receipts/'+key+'.json',receipt):raise ValueError('Receipt conflict; do not repeat provider request')
    return receipt,'CREATED_AUTHENTICATED_RESEARCH'
