import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("preview_gate", Path(__file__).parents[1] / "app/core/cv/ai/preview_gate.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
gate_preview = module.gate_preview


def test_unsupported_and_unreliable_predictions_are_never_detections():
    r=gate_preview({'OPEN_JOINT':.99,'INFILTRATION':.99},{'OPEN_JOINT':.5,'INFILTRATION':.05},
                   model_version='r5',model_loaded=True,checksum_verified=True)
    assert all(x['detected'] is None for x in r['classes'].values())
    assert r['engineering_result'] is None
    assert r['geometry_status']=='joint_geometry_not_reliable'


def test_checksum_failure_prevents_ready_or_normal_detection():
    r=gate_preview({'NORMAL':.99},{'NORMAL':.45},model_version='r5',model_loaded=True,checksum_verified=False)
    assert not r['model_ready']
    assert r['classes']['NORMAL']['detected'] is None


def test_nonfinite_output_is_rejected():
    r=gate_preview({'NORMAL':float('nan')},{'NORMAL':.45},model_version='r5',model_loaded=True,checksum_verified=True)
    assert r['classes']['NORMAL']['status']=='INVALID_OUTPUT'
    assert r['classes']['NORMAL']['probability'] is None
