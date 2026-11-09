"""Actual mask binding and diagnostics; no GPU allocation or model inference."""
import hashlib
from types import SimpleNamespace
import cv2,numpy as np
from scripts.cloud.research_runtime_diagnostics import write_verified_candidate_mask,runtime_diagnostics


def test_mask_artifact_requires_same_pixels_and_existing_acceptance(tmp_path):
    image=np.zeros((32,32,3),np.uint8);mask=np.zeros((32,32),np.uint8);mask[5:20,5:20]=255
    sam=SimpleNamespace(status='MASK_CANDIDATE_RESEARCH',mask=mask,image_sha256=hashlib.sha256(image.tobytes()).hexdigest(),mask_bbox=(5,5,20,20))
    path=tmp_path/'mask.png'
    assert write_verified_candidate_mask(sam,image,path,False) is None and not path.exists()
    sam.image_sha256='0'*64
    assert write_verified_candidate_mask(sam,image,path,True) is None
    sam.image_sha256=hashlib.sha256(image.tobytes()).hexdigest()
    metadata=write_verified_candidate_mask(sam,image,path,True)
    assert np.array_equal(cv2.imread(str(path),0),mask)
    assert metadata['defect_identity_verified'] is False and metadata['nonzero_pixels']==225
    assert hashlib.sha256(path.read_bytes()).hexdigest()==metadata['sha256']


def test_cpu_diagnostics_never_invents_gpu_memory():
    torch=SimpleNamespace(__version__='test-only',cuda=SimpleNamespace(is_available=lambda:False))
    result=runtime_diagnostics(torch)
    assert result['gpu_memory'] is None and result['cuda_available'] is False


def test_job_builder_cannot_bypass_review_or_budget():
    import pytest
    from scripts.cloud.prepare_pilot3_submission import build_job
    frames=[{'frame_id':f'f{i}','image_uri':f'gs://joint-inspection-510310-data/{i}.png','image_sha256':f'{i:064x}',
             'task_type':'OBJECT_SEGMENTATION','roi':[1,1,30,30],'source_family':f'TEST-FAMILY-{i}',
             'source_id':str(i),'rights_status':'RESEARCH_QUARANTINE','annotation_status':'UNVERIFIED_SOURCE_LABEL'} for i in (1,2,3)]
    manifest={'schema_version':'1.0','manifest_id':'synthetic_test_only','frames':frames}
    with pytest.raises(ValueError,match='human review'):
        build_job(manifest,manifest_uri='gs://joint-inspection-510310-data/test.json',
                  image_uri='mutable:latest',output_prefix='gs://joint-inspection-510310-data/models/inspect-view/research-results/test',review=None,budget=None)
