"""Actual geometry contracts; test-generated images are not field accuracy data."""
import io
import hashlib
import numpy as np
import pytest
from PIL import Image

from backend.app.core.cv.ai.independent_seam import measure_image_seam
from backend.app.core.cv.ai.phase1_unified import Phase1Unified
from backend.app.core.cv.ai.research_sewer_fusion import SewerFusion
from backend.tests.test_phase1_unified import reconciler,interpretation,SECRET


def curved():
    im=np.full((200,240,3),190,np.uint8)
    for x in range(240):
        y=int(65+.0015*(x-120)**2)
        im[y:y+18,x]=20
    return im


def test_curve_uses_observed_boundaries_and_local_normals_without_sam():
    result=measure_image_seam(curved(),'HORIZONTAL_SEAM')
    assert result['status']=='VISIBLE_GAP_PIXEL_CANDIDATE'
    assert 15<result['gap_estimate_px']<21
    assert result['accepted_cross_sections']>=16
    assert any(p['a'][0]!=p['b'][0] for p in result['edge_pairs'])
    assert result['physical_gap_mm'] is None and not result['joint_opening_confirmed']


@pytest.mark.parametrize('kind',['uniform','one_edge','wrong_orientation'])
def test_no_candidate_from_uniform_surface_or_one_edge(kind):
    im=np.full((200,240,3),190,np.uint8)
    if kind=='one_edge':im[:100]=20
    if kind=='wrong_orientation':im[:,100:115]=20
    assert measure_image_seam(im,'HORIZONTAL_SEAM')['gap_estimate_px'] is None


def _payload():
    out=io.BytesIO();Image.fromarray(curved()).save(out,format='PNG');return out.getvalue()


def test_missing_all_models_keeps_cv_diagnostics_without_authorizing_mm():
    def broken(_):raise RuntimeError('not loaded')
    engine=Phase1Unified(fusion=SewerFusion(classifier=broken),reconciler=None)
    result=engine.infer(_payload(),task='JOINT_GEOMETRY',geometry='HORIZONTAL_SEAM')
    assert result['joint_measurement']['candidates']
    assert result['physical_gap_mm'] is None and result['decision']=='REVIEW_REQUIRED'
    assert result['scene_validation']['status']=='UNVERIFIED_OR_UNSUITABLE'
    assert not result['phase1']['functional_path_complete']
    assert result['regions'][0]['mask_status']=='NOT_REQUIRED_FOR_OPENCV'


def test_normal_or_unclassified_joint_does_not_erase_geometry():
    payload=_payload();data=interpretation();data['hypotheses']=[];data['region_assessments']=[]
    vertex=reconciler(data=data);vertex.scope['approved_image_sha256s']=[hashlib.sha256(payload).hexdigest()]
    engine=Phase1Unified(fusion=SewerFusion(classifier=lambda _:None,receipt_secret=SECRET),reconciler=vertex)
    result=engine.infer(payload,task='JOINT_GEOMETRY',geometry='HORIZONTAL_SEAM')
    assert result['joint_measurement']['candidates'] and result['physical_gap_mm'] is None
    assert result['scene_validation']['measurement_authorized']
    assert result['engineering_result'] is None


def test_unrelated_scene_never_authorizes_physical_measurement():
    payload=_payload();data=interpretation();data['scene'].update(pipe_visible=False,joint_visible=False,domain_status='UNRELATED_IMAGE')
    data['hypotheses']=[];data['region_assessments']=[]
    vertex=reconciler(data=data);vertex.scope['approved_image_sha256s']=[hashlib.sha256(payload).hexdigest()]
    result=Phase1Unified(fusion=SewerFusion(classifier=lambda _:None,receipt_secret=SECRET),reconciler=vertex).infer(payload,task='JOINT_GEOMETRY',geometry='HORIZONTAL_SEAM')
    assert result['joint_measurement']['candidates']  # Explicit diagnostics, not pipe identification.
    assert result['physical_gap_mm'] is None and not result['scene_validation']['measurement_authorized']


def test_caption_filter_does_not_exclude_random_rough_surface_as_text():
    from backend.app.core.cv.ai.joint_gap_recovery import text_exclusion_candidates
    rng=np.random.default_rng(42)
    noise=np.repeat(rng.integers(110,245,(300,300),dtype=np.uint8)[:,:,None],3,axis=2)
    excluded,_=text_exclusion_candidates(noise)
    assert np.count_nonzero(excluded)<noise.shape[0]*noise.shape[1]*.1


def test_verified_scale_and_pipe_scene_can_measure_without_defect_label_or_sam(monkeypatch):
    import json
    from backend.tests.test_unified_calibration import record
    from backend.app.core.cv.calibration_authority import clear_calibration_cache
    image=np.full((120,200,3),190,np.uint8);image[:,94:106]=20
    stream=io.BytesIO();Image.fromarray(image).save(stream,format='PNG');payload=stream.getvalue()
    server=record();server.update(image_sha256=hashlib.sha256(payload).hexdigest(),image_width=200,image_height=120,
                                 plane_homography=None,reference_span_px=20)
    monkeypatch.setenv('JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON',json.dumps([server]));clear_calibration_cache()
    try:
        data=interpretation();data['hypotheses']=[];data['region_assessments']=[]
        vertex=reconciler(data=data);vertex.scope['approved_image_sha256s']=[server['image_sha256']]
        result=Phase1Unified(fusion=SewerFusion(classifier=lambda _:None,receipt_secret=SECRET),reconciler=vertex).infer(
            payload,task='JOINT_GEOMETRY',geometry='VERTICAL_SEAM',context={
                'calibration_reference_id':'synthetic-rig','project_id':'test-project','camera_id':'test-camera',
                'calibration_source':'TEST_RIG','pipe_diameter_mm':300})
        assert result['physical_gap_mm']==pytest.approx(6,abs=1)
        assert result['engineering_result'] is None and result['decision']=='REVIEW_REQUIRED'
        assert not result['phase1']['functional_path_complete']  # No SAM or sewer classifiers in this fixture.
        assert result['phase1']['geometry_path_complete']
    finally:clear_calibration_cache()
