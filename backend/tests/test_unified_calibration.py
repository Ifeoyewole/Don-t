"""Known synthetic scales exercise server authority; no field calibration claim."""
import json
import pytest

from backend.app.core.cv.calibration_authority import clear_calibration_cache
from backend.app.core.cv.ai.unified_calibration import calibrated_gap


def record():
    return dict(reference_id='synthetic-rig', project_id='test-project', camera_id='test-camera',
        source='TEST_RIG', pipe_diameter_mm=300, validated_joint_types=['VERTICAL_SEAM', 'CIRCULAR_OPENING'],
        reference_length_mm=10, reference_span_px=30, image_sha256='a'*64,
        image_width=220, image_height=220, joint_plane_verified=True,
        measurement_direction='AXIAL_JOINT_GAP', image_is_rectified=True,
        plane_homography=[[1.5, 0, 0], [0, 1.5, 0], [0, 0, 1]], scale_uncertainty_fraction=.01)


def evidence():
    return {'status': 'VISIBLE_GAP_PIXEL_CANDIDATE', 'gap_estimate_px': 12,
            'edge_pairs': [{'a': [40, y], 'b': [52, y]} for y in range(20, 100, 4)]}


def run(monkeypatch, change=None, **kwargs):
    server = record(); server.update(change or {})
    monkeypatch.setenv('JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON', json.dumps([server]));clear_calibration_cache()
    context = dict(calibration_reference_id='synthetic-rig', project_id='test-project', camera_id='test-camera',
                   calibration_source='TEST_RIG', pipe_diameter_mm=300)
    result = calibrated_gap(evidence(), image_sha256=kwargs.get('sha', 'a'*64), dimensions=[220, 220],
                            context=context, geometry=kwargs.get('geometry', 'VERTICAL_SEAM'))
    clear_calibration_cache()
    return result


def test_rectifies_actual_edge_points_before_mm_conversion(monkeypatch):
    result = run(monkeypatch)
    assert result['physical_gap_mm'] == pytest.approx(6)
    assert result['calibration_uncertainty_mm'] == pytest.approx(.06)
    assert result['calibration_authority_verified'] and not result['engineering_acceptance']


@pytest.mark.parametrize('change', [{'joint_plane_verified': False}, {'measurement_direction': 'RADIAL_RING_SPACING'},
    {'camera_id': 'different-camera'}, {'project_id': 'different-project'}, {'image_width': 221},
    {'plane_homography': [[0,0,0],[0,0,0],[0,0,0]]}])
def test_rejects_invalid_authority_or_projection(monkeypatch, change):
    assert run(monkeypatch, change)['physical_gap_mm'] is None


def test_hash_binding_and_circular_depth_ambiguity(monkeypatch):
    assert run(monkeypatch, sha='b'*64)['physical_gap_mm'] is None
    assert run(monkeypatch, geometry='CIRCULAR_OPENING')['physical_gap_mm'] is None


def test_nominal_diameter_and_client_verified_flag_do_not_authorize_mm(monkeypatch):
    monkeypatch.setenv('JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON', '[]');clear_calibration_cache()
    result = calibrated_gap(evidence(), image_sha256='a'*64, dimensions=[220,220], geometry='VERTICAL_SEAM',
        context={'pipe_diameter_mm':300, 'calibration_source':'PROJECT_METADATA', 'verified':True})
    assert result['physical_gap_mm'] is None


def test_full_unified_path_reports_calibrated_mm_with_research_decision(monkeypatch):
    import io
    import hashlib
    import numpy as np
    from PIL import Image
    from backend.tests.test_phase1_unified import fusion, reconciler
    from backend.app.core.cv.ai.phase1_unified import Phase1Unified
    array = np.full((120, 200, 3), 190, np.uint8);array[:, 94:106] = 20
    stream = io.BytesIO();Image.fromarray(array).save(stream, format='PNG');payload = stream.getvalue()
    server = record();server.update(image_sha256=hashlib.sha256(payload).hexdigest(), image_width=200, image_height=120,
                                   plane_homography=None, reference_span_px=20)
    monkeypatch.setenv('JOINTINSPECT_VERIFIED_CALIBRATIONS_JSON', json.dumps([server]));clear_calibration_cache()
    vertex = reconciler();vertex.scope['approved_image_sha256s'] = [server['image_sha256']]
    result = Phase1Unified(fusion=fusion(), reconciler=vertex).infer(payload, rois=[[40, 10, 160, 110]],
        task='JOINT_GEOMETRY', geometry='VERTICAL_SEAM', context={'calibration_reference_id':'synthetic-rig',
        'calibration_source':'TEST_RIG', 'project_id':'test-project', 'camera_id':'test-camera', 'pipe_diameter_mm':300})
    assert result['primary_measurement_unit'] == 'mm'
    assert result['physical_gap_mm'] == pytest.approx(6, abs=1)
    assert result['joint_measurement']['calibration_authority_verified']
    assert result['decision'] == 'REVIEW_REQUIRED' and result['engineering_result'] is None
    clear_calibration_cache()
