"""Training policy tests plus bounded synthetic CPU loop and deterministic resume."""
import copy
import json
from pathlib import Path
import pytest
from training.commercial_candidate import LABELS,eligibility,validate_manifest,synthetic_manifest,run_training,VerifiedDataset,save_new_checkpoint


def config(epochs=2):
    return dict(mode='synthetic_smoke',architecture='synthetic_test_only',pretrained_checkpoint=None,
                device='cpu',labels=LABELS,epochs=epochs,seed=42,image_size=32,batch_size=2,learning_rate=.01)


def test_quarantined_training_records_are_never_eligible():
    reasons=eligibility({'rights_status':'RESEARCH_QUARANTINE','commercial_training_eligible':False})
    assert 'RESEARCH_QUARANTINE' in reasons and 'ANNOTATION_VERIFIED_REQUIRED' in reasons
    with pytest.raises(ValueError,match='Pinned eligibility'):
        validate_manifest({'records':[{}]},dict(config(),mode='commercial_candidate',architecture='convnext_tiny'))


def test_noncommercial_pretrained_weights_are_not_accepted():
    with pytest.raises(ValueError,match='pretrained'):
        validate_manifest({'records':[{}]},dict(config(),pretrained_checkpoint='r5.pt'))


def test_family_and_exact_image_leakage_rejected(tmp_path):
    manifest=synthetic_manifest(tmp_path/'images',LABELS)
    changed=copy.deepcopy(manifest);changed['records'][4]['source_family_id']=changed['records'][0]['source_family_id']
    with pytest.raises(ValueError,match='leakage'):validate_manifest(changed,config())
    changed=copy.deepcopy(manifest);changed['records'][4]['sha256']=changed['records'][0]['sha256']
    with pytest.raises(ValueError,match='Exact duplicate'):validate_manifest(changed,config())
    changed=copy.deepcopy(manifest);changed['records'][0]['synthetic']=False
    with pytest.raises(ValueError,match='Real data'):validate_manifest(changed,config())


def test_cpu_smoke_resume_matches_uninterrupted_and_preserves_checkpoints(tmp_path):
    torch=pytest.importorskip('torch');torch.set_num_threads(2)
    manifest=synthetic_manifest(tmp_path/'images',LABELS)
    continuous=run_training(manifest,config(),tmp_path/'continuous')
    run_training(manifest,config(1),tmp_path/'resumed')
    original=(tmp_path/'resumed/epoch-000.pt').read_bytes()
    resumed=run_training(manifest,config(),tmp_path/'resumed',tmp_path/'resumed/epoch-000.pt')
    a=torch.load(tmp_path/'continuous/epoch-001.pt',weights_only=True)
    b=torch.load(tmp_path/'resumed/epoch-001.pt',weights_only=True)
    assert all(torch.equal(a['model'][k],b['model'][k]) for k in a['model'])
    assert original==(tmp_path/'resumed/epoch-000.pt').read_bytes()
    assert continuous['trained_commercial_model'] is False and resumed['production_eligible'] is False
    with pytest.raises(FileExistsError):save_new_checkpoint(tmp_path/'resumed/epoch-000.pt',b)
    with pytest.raises(ValueError,match='provenance'):
        run_training(manifest,dict(config(),seed=43),tmp_path/'resumed',tmp_path/'resumed/epoch-000.pt')


def test_training_loader_rejects_modified_image(tmp_path):
    pytest.importorskip('torch')
    manifest=synthetic_manifest(tmp_path/'images',LABELS)
    Path(manifest['records'][0]['image_uri']).write_bytes(b'modified')
    with pytest.raises(ValueError,match='checksum'):VerifiedDataset(manifest['records'],LABELS,32)[0]
