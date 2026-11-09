"""Synthetic contract tests, never dataset accuracy or real checkpoint results."""
import hashlib
import io
from types import SimpleNamespace

import cv2
import numpy as np
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from backend.app.core.cv.ai.research_sewer_detector import SewerOnnxDetector
from backend.app.core.cv.ai.research_sewer_fusion import SewerFusion, decode
from backend.app.core.cv.ai.research_sam2_adapter import Sam2MaskEvidence, propose_sam2_mask
from backend.app.main import app

NAMES = {0:'Cracks / Breaks / Collapses', 1:'Intruding Sealing Material', 2:'Roots', 3:'Displaced Joint',
         4:'Pipe Surface Damage', 5:'Infiltration', 6:'Attached Deposits', 7:'Settled Deposits'}


class Session:
    def __init__(self, output=None, names=None):
        self.output = np.zeros((1, 2, 12), dtype=np.float32) if output is None else output
        self.output[0, :, :4] = [.5, .5, .4, .6]
        self.output[0, :, 9] = .9  # Infiltration, deliberately not class ID zero.
        self.names = NAMES if names is None else names
    def get_inputs(self):
        return [SimpleNamespace(name='images', type='tensor(float)', shape=[1,3,640,640])]
    def get_modelmeta(self):
        return SimpleNamespace(custom_metadata_map={'names':repr(self.names)})
    def run(self, _names, data):
        self.last_input = data['images']
        return [self.output]


def payload(color=90):
    out = io.BytesIO();Image.new('RGB', (200, 120), (color, 20, 30)).save(out, format='PNG');return out.getvalue()


def classifier(data):
    return {'image_sha256':hashlib.sha256(data).hexdigest(), 'model_version':'repr-convnext-masked-r5-20261104',
            'model_ready':True, 'research_preview':True,
            'classes':{'NORMAL':{'status':'EXPLORATORY','probability':.8,'detected':True},
                       'INFILTRATION':{'status':'UNRELIABLE','probability':.1,'detected':None}}}


def segment(image, box):
    mask = np.zeros(image.shape[:2], np.uint8);x0,y0,x1,y1=box;mask[y0:y1,x0:x1]=255
    return Sam2MaskEvidence('MASK_CANDIDATE_RESEARCH','sam2.1_hiera_tiny',box,box,.9,mask,'SYNTHETIC_TEST_MASK',
                            hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest())


def test_detector_coordinates_rgb_and_deduplication():
    session=Session();detector=SewerOnnxDetector(session);rows=detector.predict(decode(payload()))
    assert len(rows)==1 and rows[0].bbox==(59,23,141,97)
    assert rows[0].jointinspect_candidate=='INFILTRATION'
    assert session.last_input.shape==(1,3,640,640)
    assert session.last_input[0,0,0,0]==pytest.approx(90/255)
    assert detector.provenance()['production_eligible'] is False


@pytest.mark.parametrize('names',[{}, {1:'Infiltration'}, ['a']*8, {i:None for i in range(8)}])
def test_missing_or_invalid_graph_names_fail_closed(names):
    with pytest.raises(ValueError):SewerOnnxDetector(Session(names=names))


@pytest.mark.parametrize('threshold',[0,2,float('nan'),True])
def test_threshold_validation(threshold):
    with pytest.raises(ValueError):SewerOnnxDetector(Session(),threshold=threshold)


def test_export_layout_not_guessed():
    session=Session();session.output=np.zeros((1,12,300),np.float32)
    with pytest.raises(ValueError):SewerOnnxDetector(session).predict(decode(payload()))


def test_no_workstation_model_loading(tmp_path):
    with pytest.raises(ValueError,match='Cloud research'):SewerOnnxDetector.from_verified_cloud_checkpoint(tmp_path/'missing')
    wrong=tmp_path/'model';wrong.write_bytes(b'not weights')
    with pytest.raises(ValueError,match='SHA-256'):SewerOnnxDetector.from_verified_cloud_checkpoint(wrong,cloud_worker=True)


def test_unified_real_mask_handoff_and_geometry():
    service=SewerFusion(classifier=classifier,detector=SewerOnnxDetector(Session()),segmenter=segment)
    result=service.infer(payload())
    assert result['components']['inspect_view']['evidence']==classifier(payload())
    assert result['regions'][0]['mask_status']=='ACTUAL_MASK_CANDIDATE'
    import base64
    mask=cv2.imdecode(np.frombuffer(base64.b64decode(result['regions'][0]['mask_png_base64']),np.uint8),0)
    assert mask.shape==(120,200) and np.count_nonzero(mask)>50
    assert result['regions'][0]['pixel_geometry']['foreground_area_px']==np.count_nonzero(mask)
    assert result['decision']=='REVIEW_REQUIRED' and result['engineering_result'] is None
    assert result['physical_gap_mm'] is None
    assert result['preliminary_findings'][0]['active_infiltration_confirmed'] is False
    assert result['baseline_comparison']['accuracy_improvement'] is None
    assert result['weak_class_validation']['OPEN_JOINT']=='UNSUPPORTED'


def test_existing_sam_adapter_produces_pixels_then_unified_handoff(tmp_path):
    checkpoint=tmp_path/'stub';checkpoint.write_bytes(b'SYNTHETIC_TEST_ONLY')
    class Predictor:
        def set_image(self,image):self.shape=image.shape[:2]
        def predict(self,*,box,multimask_output):
            mask=np.zeros(self.shape,np.float32);mask[30:90,60:140]=1
            return mask[None],np.array([.9]),None
    def sam(image, box):
        return propose_sam2_mask(image,box,enabled=True,checkpoint_path=checkpoint,
                                 expected_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                                 predictor_factory=lambda path:Predictor())
    result=SewerFusion(classifier=classifier,segmenter=sam).infer(payload(),rois=[[50,20,150,100]])
    assert result['regions'][0]['mask_status']=='ACTUAL_MASK_CANDIDATE'
    assert result['regions'][0]['pixel_geometry']['foreground_area_px']==4800


@pytest.mark.parametrize('failed',['classifier','detector','segmenter'])
def test_partial_component_failures(failed):
    def broken(*args):raise RuntimeError('private exception must not leak')
    kwargs=dict(classifier=classifier,detector=SewerOnnxDetector(Session()),segmenter=segment)
    kwargs[failed]=broken
    result=SewerFusion(**kwargs).infer(payload(),rois=[[50,20,150,100]])
    assert result['decision']=='REVIEW_REQUIRED' and 'private exception' not in str(result)
    if failed=='segmenter':assert all(r['mask_status']=='UNAVAILABLE_OR_REJECTED' for r in result['regions'])


def test_reject_cross_frame_mask():
    def bad(image,box):
        good=segment(image,box)
        return Sam2MaskEvidence(good.status,good.model_id,box,box,.9,good.mask,'test','0'*64)
    result=SewerFusion(classifier=classifier,segmenter=bad).infer(payload(),rois=[[50,20,150,100]])
    assert result['regions'][0]['mask_status']=='UNAVAILABLE_OR_REJECTED'


def test_no_joint_geometry_without_signed_semantic_gate(monkeypatch):
    def forbidden(*a,**kw):raise AssertionError('Joint geometry must not run')
    monkeypatch.setattr('backend.app.core.cv.ai.research_sewer_fusion.combine_inspect_view_and_sam2',forbidden)
    result=SewerFusion(classifier=classifier,segmenter=segment).infer(payload(),rois=[[50,20,150,100]],
                        task='JOINT_GEOMETRY',geometry='VERTICAL_SEAM',receipt={'fake':'receipt'})
    assert result['gemini']['status']=='INVALID_REJECTED'
    assert result['regions'][0]['geometry']['physical_gap_mm'] is None
    with pytest.raises(ValueError):SewerFusion(classifier=classifier).infer(payload(),geometry='VERTICAL_SEAM')


def test_temporal_consistency_is_not_infiltration_confirmation():
    service=SewerFusion(classifier=classifier,detector=SewerOnnxDetector(Session()))
    first=service.infer(payload(),sequence_id='seq',frame_index=0)
    second=service.infer(payload(91),sequence_id='seq',frame_index=1)
    assert second['components']['sewer_detector']['detections'][0]['temporal_observations']==2
    assert second['preliminary_findings'][0]['active_infiltration_confirmed'] is False
    replay=service.infer(payload(91),sequence_id='seq',frame_index=1)
    assert replay['components']['sewer_detector']['detections'][0]['temporal_status']=='OUT_OF_ORDER_NOT_FUSED'
    other=service.infer(payload(92),sequence_id='different',frame_index=2)
    assert other['components']['sewer_detector']['detections'][0]['temporal_observations']==1
    assert first['components']['sewer_detector']['detections'][0]['temporal_observations']==1


def test_research_api_default_disabled_and_authenticated(monkeypatch):
    client=TestClient(app);url='/api/v1/cv/sewer-research/unified'
    monkeypatch.delenv('JOINTINSPECT_SEWER_FUSION_ENABLED',raising=False)
    assert client.post(url,files={'file':('x.png',payload(),'image/png')}).status_code==404
    monkeypatch.setenv('JOINTINSPECT_SEWER_FUSION_ENABLED','true')
    monkeypatch.setenv('JOINTINSPECT_PREVIEW_TOKEN','test-only-token')
    assert client.post(url,files={'file':('x.png',payload(),'image/png')}).status_code==401
    monkeypatch.setattr('backend.app.api.v1.endpoints.sewer_research.cloud_service',lambda:SewerFusion(classifier=classifier,segmenter=segment))
    response=client.post(url,headers={'Authorization':'Bearer test-only-token'},
                         files={'file':('x.png',payload(),'image/png')},data={'options':'{"rois":[[50,20,150,100]]}'})
    assert response.status_code==200 and response.json()['decision']=='REVIEW_REQUIRED'
    assert client.get('/health').status_code==200


def test_cloud_session_initialization_is_checksum_bound(tmp_path, monkeypatch):
    import sys
    path=tmp_path/'synthetic.onnx';path.write_bytes(b'SYNTHETIC TEST GRAPH ONLY')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr('backend.app.core.cv.ai.research_sewer_detector.CHECKPOINT_SHA256',digest)
    calls=[]
    def session(filename, providers):
        calls.append((filename,providers));return Session()
    monkeypatch.setitem(sys.modules,'onnxruntime',SimpleNamespace(InferenceSession=session))
    detector=SewerOnnxDetector.from_verified_cloud_checkpoint(path,cloud_worker=True)
    assert calls==[(str(path),['CPUExecutionProvider'])]
    assert detector.predict(decode(payload()))


def test_cloud_runtime_requires_explicit_research_scope(monkeypatch):
    from backend.app.core.cv.ai.research_sewer_runtime import cloud_service
    cloud_service.cache_clear()
    monkeypatch.delenv('JOINTINSPECT_CLOUD_RESEARCH_WORKER',raising=False)
    with pytest.raises(RuntimeError,match='Dedicated cloud'):cloud_service()
    monkeypatch.setenv('JOINTINSPECT_CLOUD_RESEARCH_WORKER','true')
    monkeypatch.delenv('JOINTINSPECT_ISWDS_NONCOMMERCIAL_RESEARCH_ALLOWED',raising=False)
    with pytest.raises(RuntimeError,match='permission'):cloud_service()


@pytest.mark.parametrize('value',[float('nan'),float('inf'),-.2,1.2])
def test_nonfinite_or_nonprobabilistic_detector_output(value):
    session=Session();session.output[0,0,4]=value
    with pytest.raises(ValueError):SewerOnnxDetector(session).predict(decode(payload()))


def test_unknown_labels_are_preserved_not_reinterpreted():
    names={i:'unknown_source_'+str(i) for i in range(8)}
    row=SewerOnnxDetector(Session(names=names)).predict(decode(payload()))[0]
    assert row.source_label=='unknown_source_5' and row.jointinspect_candidate is None


def test_mask_holes_do_not_become_gap_measurement():
    def hole(image,box):
        good=segment(image,box);good.mask[45:60,80:100]=0;return good
    result=SewerFusion(classifier=classifier,segmenter=hole).infer(payload(),rois=[[50,20,150,100]])
    assert result['regions'][0]['pixel_geometry']['foreground_area_px']==7700
    assert result['regions'][0]['geometry']['physical_gap_mm'] is None


class PostprocessedSession:
    """Matches real checkpoint names observed through bounded remote metadata."""
    def get_inputs(self):
        return [SimpleNamespace(name='images',type='tensor(float)',shape=['N',3,640,640]),
                SimpleNamespace(name='orig_target_sizes',type='tensor(int64)',shape=['N',2])]
    def get_outputs(self):
        return [SimpleNamespace(name=name) for name in ['labels','boxes','scores']]
    def get_modelmeta(self):
        return SimpleNamespace(custom_metadata_map={})
    def run(self,_names,feed):
        self.target=feed['orig_target_sizes']
        return [np.array([[5]]),np.array([[[50.,20.,150.,100.]]]),np.array([[.9]])]


def test_actual_iswds_postprocessed_export_contract_without_invented_labels():
    session=PostprocessedSession();detector=SewerOnnxDetector(session)
    row=detector.predict(decode(payload()))[0]
    assert session.target.tolist()==[[120,200]]
    assert row.bbox==(50,20,150,100)
    assert row.source_class_id==5 and row.jointinspect_candidate is None
    assert row.source_label=='UNVERIFIED_SOURCE_CLASS_ID_5'
    assert detector.provenance()['class_order_source']=='UNAVAILABLE_NO_CLASS_MAPPING'
    result=SewerFusion(classifier=classifier,detector=detector,segmenter=segment).infer(payload())
    assert result['baseline_comparison']['actual_mask_count']==1
    assert result['preliminary_findings']==[]


def test_real_onnxruntime_executes_tiny_synthetic_export_contract():
    import base64
    ort=pytest.importorskip("onnxruntime")
    # Constant-only synthetic graph; no pretrained model or accuracy evidence.
    data=base64.b64decode('CAk60AIKMBIGbGFiZWxzIghDb25zdGFudCocCgV2YWx1ZSoQCAEIARAHSggFAAAAAAAAAKABBAo5EgVib3hlcyIIQ29uc3RhbnQqJgoFdmFsdWUqGggBCAEIBBABShAAAEhCAACgQQAAFkMAAMhCoAEECiwSBnNjb3JlcyIIQ29uc3RhbnQqGAoFdmFsdWUqDAgBCAEQAUoEZmZmP6ABBBIXU1lOVEhFVElDX0NPTlRSQUNUX09OTFlaIwoGaW1hZ2VzEhkKFwgBEhMKAxIBTgoCCAMKAwiABQoDCIAFWiQKEW9yaWdfdGFyZ2V0X3NpemVzEg8KDQgHEgkKAxIBTgoCCAJiGAoGbGFiZWxzEg4KDAgHEggKAggBCgIIAWIbCgVib3hlcxISChAIARIMCgIIAQoCCAEKAggEYhgKBnNjb3JlcxIOCgwIARIICgIIAQoCCAFCBAoAEA0=')
    session=ort.InferenceSession(data,providers=["CPUExecutionProvider"])
    detector=SewerOnnxDetector(session)
    result=SewerFusion(classifier=classifier,detector=detector,segmenter=segment).infer(payload())
    assert result["baseline_comparison"]["actual_mask_count"]==1
    assert result["components"]["sewer_detector"]["detections"][0]["source_class_id"]==5
    assert result["physical_gap_mm"] is None
