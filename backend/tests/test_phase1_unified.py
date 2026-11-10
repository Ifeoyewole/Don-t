"""Offline contracts; synthetic masks here are NOT the real cloud demonstration."""
import base64
import copy
import hashlib
from types import SimpleNamespace
import time

import cv2
import numpy as np
import pytest

from backend.app.core.cv.ai.phase1_unified import Phase1Unified
from backend.app.core.cv.ai.research_gemini_reconciliation import (
    VertexEvidenceReconciler, contract_sha, safe_analysis,
    vertex_response_schema,
)
from backend.app.core.cv.ai.research_joint_boundaries import boundary_evidence
from backend.app.core.cv.ai.research_sewer_fusion import SewerFusion
from backend.app.core.cv.ai.signed_gemini_receipt import verify_signed_semantic_receipt
from backend.tests.test_sewer_unified_research import classifier, payload, segment, Session
from backend.app.core.cv.ai.research_sewer_detector import SewerOnnxDetector

SECRET = b'only-a-synthetic-test-secret-value-32bytes'


class Store:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return copy.deepcopy(self.data.get(key))

    def create(self, key, value):
        if key in self.data:
            return False
        self.data[key] = copy.deepcopy(value)
        return True


def interpretation(proposal=False):
    return {'scene': {'domain_status': 'PIPE_JOINT_INSPECTION', 'pipe_visible': True,
                      'joint_visible': True, 'quality': 'OK', 'prompt_image_conflict': False},
            'summary': 'Possible seam; independent evidence remains uncertain.',
            'hypotheses': [{'label': 'OPEN_JOINT', 'status': 'POSSIBLE', 'region_ids': [0],
                            'explanation': 'A visible dark seam is not proof of an open joint.'}],
            'region_assessments': [{'region_id': 0, 'mask_target': 'JOINT_BOUNDARY_BAND',
                                    'suitable_for_joint_boundary_analysis': True,
                                    'explanation': 'The mask may follow the seam.'}],
            'agreements': [], 'contradictions': [], 'limitations': ['No verified physical calibration.'],
            'additional_regions': [{'bbox': [60, 20, 140, 100], 'geometry': 'VERTICAL_SEAM',
                                    'reason': 'Inspect the seam boundary.'}] if proposal else []}


def reconciler(data=None, store=None, maximum=6, transport=None):
    gate = SimpleNamespace(model='gemini-3.1-pro-preview', location='global',
                           project_id='joint-inspection-510310', settings=SimpleNamespace(VERTEX_MAX_RETRIES=0))
    scope = {'model': gate.model, 'location': gate.location, 'review_approval_id': 'USER_EXPLORATORY_ONLY',
             'spending_approval_id': 'TEST_NO_PAID_CALLS', 'approved_image_sha256s': [hashlib.sha256(payload()).hexdigest()],
             'max_requests': maximum, 'expires_unix': int(time.time())+600, 'spending_cap': 1,
             'currency': 'USD', 'prompt_sha256': contract_sha()}
    return VertexEvidenceReconciler(gate=gate, store=store or Store(), scope=scope, secret=SECRET,
        transport=transport or (lambda body: (data or interpretation(), {'totalTokenCount': 123})))


def fusion():
    return SewerFusion(classifier=classifier, detector=SewerOnnxDetector(Session()),
                       segmenter=segment, receipt_secret=SECRET)


def test_unified_real_contract_keeps_advisory_and_physical_fields_separate():
    result = Phase1Unified(fusion=fusion(), reconciler=reconciler()).infer(payload(), rois=[[50, 20, 150, 100]])
    assert result['phase1']['functional_path_complete']
    assert result['gemini']['status'] == 'AUTHENTICATED_ADVISORY'
    assert result['physical_gap_mm'] is None and result['decision'] == 'REVIEW_REQUIRED'
    assert result['joint_measurement']['physical_gap_mm'] is None
    assert result['baseline_comparison']['accuracy_improvement'] is None
    assert result['preliminary_findings'][-1]['status'] == 'GEMINI_VISUAL_HYPOTHESIS_NOT_CONFIRMED'


def test_original_overlay_masks_and_all_component_evidence_reach_vertex():
    calls = []
    def transport(body):
        calls.append(body)
        return interpretation(), {}
    result = Phase1Unified(fusion=fusion(), reconciler=reconciler(transport=transport)).infer(payload())
    parts = calls[0]['contents'][0]['parts']
    assert base64.b64decode(parts[2]['inlineData']['data']) == payload()
    assert len([p for p in parts if 'inlineData' in p]) >= 3
    text = parts[0]['text']
    assert all(k in text for k in ['inspect_view', 'sewer_detector', 'foreground_area_px', 'mask_sha256'])
    assert result['gemini_analyses'][0]['usage'] == {}


def test_one_targeted_pass_only_even_if_gemini_requests_more():
    calls = []
    def transport(body):
        calls.append(body)
        return interpretation(proposal=True), {}
    result = Phase1Unified(fusion=fusion(), reconciler=reconciler(transport=transport)).infer(payload())
    assert len(calls) == 2 and result['phase1']['model_passes'] == 2
    assert result['gemini']['analysis']['additional_regions'] == []
    assert any(r['source'] == 'GEMINI_TARGETED_UNVERIFIED_PROMPT' for r in result['regions'])


def test_failed_second_pass_does_not_reuse_first_gate():
    calls = []
    def transport(body):
        calls.append(body)
        if len(calls) == 2:
            raise TimeoutError('do not retry')
        return interpretation(proposal=True), {}
    result = Phase1Unified(fusion=fusion(), reconciler=reconciler(transport=transport)).infer(payload())
    assert len(calls) == 2 and result['gemini']['status'] == 'UNAVAILABLE_OR_INVALID'
    assert not result['phase1']['functional_path_complete']
    assert result['joint_measurement']['candidates'] == []


def test_paid_request_claim_survives_timeout_and_is_not_retried():
    store = Store(); calls = []
    def broken(body):
        calls.append(body)
        raise TimeoutError()
    model = reconciler(store=store, transport=broken)
    engine = Phase1Unified(fusion=fusion(), reconciler=model)
    for _ in range(2):
        result = engine.infer(payload())
        assert result['gemini']['status'] == 'UNAVAILABLE_OR_INVALID'
    assert len(calls) == 1


def test_cache_reuse_and_tampering_rejection():
    store = Store(); calls = []
    def transport(body):
        calls.append(body)
        return interpretation(), {}
    engine = Phase1Unified(fusion=fusion(), reconciler=reconciler(store=store, transport=transport))
    engine.infer(payload()); second = engine.infer(payload())
    assert len(calls) == 1 and second['gemini']['cache_status'] == 'REUSED_AUTHENTICATED'
    key = next(k for k in store.data if k.startswith('analysis/'))
    store.data[key]['analysis']['summary'] = 'Forged analysis'
    assert engine.infer(payload())['gemini']['status'] == 'UNAVAILABLE_OR_INVALID'
    assert len(calls) == 1


def test_global_slots_bound_changed_bundle_requests():
    store = Store(); calls = []
    def transport(body):
        calls.append(body)
        return interpretation(), {}
    engine = Phase1Unified(fusion=fusion(), reconciler=reconciler(store=store, maximum=1, transport=transport))
    assert engine.infer(payload(), context={'x': 'a'})['gemini']['status'] == 'AUTHENTICATED_ADVISORY'
    assert engine.infer(payload(), context={'x': 'b'})['gemini']['status'] == 'UNAVAILABLE_OR_INVALID'
    assert len(calls) == 1


def test_vertex_wire_schema_uses_supported_subset_and_resolves_refs():
    import json
    schema = vertex_response_schema()
    serialized = json.dumps(schema)
    assert schema['type'] == 'OBJECT'
    assert '$ref' not in serialized and '$defs' not in serialized
    assert 'maxLength' not in serialized and 'additionalProperties' not in serialized
    assert schema['properties']['scene']['properties']['joint_visible']['type'] == 'BOOLEAN'


def test_operator_scope_can_disable_the_targeted_pass():
    calls = []
    def transport(body):
        calls.append(body)
        return interpretation(proposal=True), {}
    result = Phase1Unified(fusion=fusion(), reconciler=reconciler(transport=transport), max_analysis_passes=1).infer(payload())
    assert len(calls) == 1 and result['phase1']['model_passes'] == 1


@pytest.mark.parametrize('change', ['unknown_region', 'outside_roi', 'measurement', 'extra_field', 'confidence'])
def test_invalid_provider_analysis_rejected(change):
    raw = interpretation()
    if change == 'unknown_region': raw['hypotheses'][0]['region_ids'] = [999]
    if change == 'outside_roi': raw['additional_regions'] = [{'bbox': [0, 0, 999, 999], 'geometry': 'NONE', 'reason': 'Look'}]
    if change == 'measurement': raw['summary'] = 'The gap is 4 mm.'
    if change == 'extra_field': raw['physical_gap_mm'] = 4
    if change == 'confidence': raw['hypotheses'][0]['confidence'] = .99
    with pytest.raises(ValueError): safe_analysis(raw, width=200, height=120, region_ids={0}, pass_index=0)


def test_receipt_reuses_existing_authenticated_semantic_gate_contract():
    result = Phase1Unified(fusion=fusion(), reconciler=reconciler()).infer(payload())
    receipt = result['gemini']['semantic_receipt']
    assert verify_signed_semantic_receipt(receipt, original_image_sha256=hashlib.sha256(payload()).hexdigest(),
                                          signing_secret=SECRET)['semantic_gate']['processing_allowed']
    with pytest.raises(ValueError):
        verify_signed_semantic_receipt(receipt, original_image_sha256='0'*64, signing_secret=SECRET)


def test_component_failure_preserves_partial_evidence_but_not_completion():
    def broken(data): raise RuntimeError('model unavailable')
    base = SewerFusion(classifier=broken, segmenter=segment, receipt_secret=SECRET)
    result = Phase1Unified(fusion=base, reconciler=reconciler()).infer(payload(), rois=[[50, 20, 150, 100]])
    assert result['baseline_comparison']['actual_mask_count'] == 1
    assert not result['phase1']['functional_path_complete']
    assert result['decision'] == 'REVIEW_REQUIRED'


def test_mask_supported_pixel_pairs_and_no_diameter_to_mm():
    image = np.full((200, 200, 3), 190, np.uint8);image[:, 90:110] = 20
    mask = np.zeros((200, 200), np.uint8);mask[:, 85:115] = 255
    result = boundary_evidence(image, mask, [40, 10, 160, 190], 'VERTICAL_SEAM')
    assert result['status'] == 'PRELIMINARY_PIXEL_BOUNDARY_SEPARATION'
    assert result['candidate_separation_px'] == pytest.approx(20, abs=3)
    assert len(result['edge_pairs']) >= 16 and result['physical_gap_mm'] is None
    assert not result['joint_opening_confirmed']


def test_unrelated_mask_does_not_validate_edge_pairs():
    image = np.full((200, 200, 3), 190, np.uint8);image[:, 90:110] = 20
    mask = np.zeros((200, 200), np.uint8);mask[:, :20] = 255
    result = boundary_evidence(image, mask, [40, 10, 160, 190], 'VERTICAL_SEAM')
    assert result['candidate_separation_px'] is None
    assert result['reason'] == 'MASK_AND_INTENSITY_BOUNDARIES_DISAGREE'


def test_research_gemini_unavailable_keeps_models_and_masks():
    result = Phase1Unified(fusion=fusion(), reconciler=None).infer(payload(), context={'pipe_diameter_mm': 300})
    assert result['baseline_comparison']['actual_mask_count'] > 0
    assert result['gemini']['status'] == 'UNAVAILABLE'
    assert result['physical_gap_mm'] is None and not result['phase1']['functional_path_complete']


def test_partial_annular_mask_width_remains_projected_band_not_axial_gap():
    image = np.full((200, 200, 3), 120, np.uint8)
    mask = np.zeros((200, 200), np.uint8)
    cv2.ellipse(mask, (100, 100), (60, 50), 0, 10, 175, 255, 12)
    result = boundary_evidence(image, mask, [10, 10, 190, 190], 'CIRCULAR_OPENING')
    assert len(result['edge_pairs']) >= 16
    assert result['candidate_separation_px'] is not None
    assert result['physical_gap_mm'] is None and not result['joint_opening_confirmed']
    assert result['reason'] == 'PROJECTED_SAM_BAND_WIDTH_NOT_VERIFIED_AXIAL_JOINT_GAP'


def test_filled_disk_is_not_a_narrow_joint_band():
    image = np.full((200, 200, 3), 120, np.uint8)
    mask = np.zeros((200, 200), np.uint8)
    cv2.circle(mask, (100, 100), 70, 255, -1)
    result = boundary_evidence(image, mask, [10, 10, 190, 190], 'CIRCULAR_OPENING')
    assert result['candidate_separation_px'] is None


def test_phase1_api_uses_same_auth_and_rejects_client_spending_flags(monkeypatch):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    monkeypatch.setenv('JOINTINSPECT_SEWER_FUSION_ENABLED', 'true')
    monkeypatch.setenv('JOINTINSPECT_PHASE1_VERTEX_ENABLED', 'true')
    monkeypatch.setenv('JOINTINSPECT_PREVIEW_TOKEN', 'synthetic-test-access')
    engine = Phase1Unified(fusion=fusion(), reconciler=reconciler())
    monkeypatch.setattr('backend.app.api.v1.endpoints.sewer_research.cloud_phase1_service', lambda: engine)
    client = TestClient(app)
    url = '/api/v1/cv/sewer-research/unified'
    assert client.post(url, files={'file': ('x.png', payload())}).status_code == 401
    args = {'headers': {'Authorization': 'Bearer synthetic-test-access'}, 'files': {'file': ('x.png', payload())}}
    assert client.post(url, **args, data={'options': '{"spending_cap": 1000}'}).status_code == 422
    response = client.post(url, **args, data={'options': '{"context":{"pipe_diameter_mm":300}}'})
    assert response.status_code == 200
    assert response.json()['engine'] == 'jointinspect-phase1-unified-v1'
    assert response.json()['physical_gap_mm'] is None
