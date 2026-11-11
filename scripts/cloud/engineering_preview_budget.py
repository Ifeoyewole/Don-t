"""Pre-inference, persistent inspection allowance for the isolated preview.

Only called after IAM verification. A failed claim is never retried; successful
same-input requests reuse their saved response without running models again.
"""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from scripts.cloud.inspect_view_sam2_vertex import stage_verified
from scripts.cloud.research_semantic_receipts import GcsCreateOnlyStore, validate_scope
from scripts.cloud.preview_spending import persistent, reserve as reserve_persistent
from backend.app.core.cv.ai.research_gemini_reconciliation import canonical, contract_sha


def reserve(payload, options):
    from google.cloud import storage
    from google.api_core.exceptions import NotFound
    client = storage.Client(project='joint-inspection-510310')
    uri = os.environ['JOINTINSPECT_PHASE1_SCOPE_URI']
    if not uri.startswith('gs://joint-inspection-510310-data/models/inspect-view/research-results/'):
        raise ValueError('Private research scope required')
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)/'scope.json'
        stage_verified(client, uri, path, os.environ['JOINTINSPECT_PHASE1_SCOPE_SHA256'], max_bytes=64*1024)
        scope = json.loads(path.read_text())
    digest = hashlib.sha256(payload).hexdigest()
    validate_scope(dict(scope, approved_image_sha256s=[digest]), digest, int(time.time()))
    if os.getenv('JOINTINSPECT_PREVIEW_LIFECYCLE') == 'ENGINEERING_PREVIEW' and not persistent(scope):
        raise ValueError('Persistent deployment cannot use an expiring one-off scope')
    if persistent(scope) and os.getenv('JOINTINSPECT_PREVIEW_IMAGE_SHA256') != scope['runtime_artifact_sha256']:
        raise ValueError('Preview image/policy identity mismatch')
    maximum = scope.get('max_inspections')
    if not persistent(scope) and (scope.get('input_authorization') != 'AUTHENTICATED_ENGINEERING_UPLOADS'
            or type(maximum) is not int or not 1 <= maximum <= 3
            or scope.get('max_requests', 101) > 6 or scope.get('prompt_sha256') != contract_sha()):
        raise ValueError('Explicit bounded engineering scope required')
    if scope.get('prompt_sha256') != contract_sha():
        raise ValueError('Exact reconciliation contract required')
    bucket = client.bucket('joint-inspection-510310-data')
    store = GcsCreateOnlyStore(bucket, scope['receipt_prefix'])
    key = response_key(scope, digest, options)
    blob = bucket.blob(store.prefix+'/responses/'+key+'.json')
    try:
        blob.reload()
        if blob.size > 5*1024*1024: raise ValueError('Response cache exceeds limit')
        result = json.loads(blob.download_as_bytes(if_generation_match=blob.generation))
        if result.get('image_sha256') != digest or result.get('research_only') is not True:
            raise ValueError('Cached response identity mismatch')
        return blob, result
    except NotFound:
        pass
    claim = {'image_sha256': digest, 'issued_at': int(time.time()), 'status': 'NO_AUTOMATIC_RETRY'}
    if persistent(scope):
        reserve_persistent(scope, store, 'inspection', key)
    if not store.create('inspection-claims/'+key+'.json', claim):
        raise ValueError('Prior inspection pending or failed; no automatic retry')
    if not persistent(scope) and not any(store.create(f'inspection-slots/{i}.json', claim) for i in range(maximum)):
        raise ValueError('Engineering inspection allowance exhausted')
    return blob, None


def response_key(scope, digest, options):
    meaningful_options = json.loads(json.dumps(options))
    if isinstance(meaningful_options.get('context'), dict):
        meaningful_options['context'].pop('image_id', None)
    # Scope approval/version changes must not rebill the same executable evidence.
    identity = {'budget_cycle': scope['budget_cycle'], 'contract': scope['prompt_sha256'],
        'runtime_artifact_sha256': scope['runtime_artifact_sha256'],
        'calibration_registry_sha256': hashlib.sha256(os.getenv('JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON', '[]').encode()).hexdigest()} if persistent(scope) else scope
    return hashlib.sha256(canonical({'scope': identity, 'image_sha256': digest, 'options': meaningful_options})).hexdigest()


def save(blob, result):
    payload = json.dumps(result, allow_nan=False)
    if len(payload.encode()) > 5*1024*1024: raise ValueError('Response exceeds bounded preview cache')
    blob.upload_from_string(payload, content_type='application/json', if_generation_match=0)
