"""Current annotation bytes, not cached approvals, determine technical evidence."""
from types import SimpleNamespace
import hashlib
import pytest
from scripts.cloud.audit_unified_dataset import audit_annotation,reusable_image_fields,duplicate_pairs,leakage_groups,source_relation

SOURCE={'original_annotation_path':'train/labels/a.txt','source_labels':['Crack']}
BLOB=SimpleNamespace(name='source/train/labels/a.txt',generation=42)
PAYLOAD=b'0 .5 .5 .2 .2'

def verified_cache():
    fresh=audit_annotation(SOURCE,['Crack','Roots'],BLOB,None,lambda b,n:PAYLOAD)
    return dict(fresh,original_labels=['Crack'])

@pytest.mark.parametrize('field,value',[
    ('annotation_sha256','0'*64),('annotation_generation','41'),
    ('original_annotation_path','train/labels/other.txt'),('annotation_uri','gs://other/a.txt'),
    ('decoded_annotation_labels',['Roots']),('original_labels',['Roots']),
    ('annotation_labels_match_registry',False),('annotation_structure_valid',False),
    ('observed_annotation_format','YOLO_POLYGON')])
def test_changed_or_invalid_cache_is_invalidated(field,value):
    old=verified_cache();old[field]=value;calls=[]
    actual=audit_annotation(SOURCE,['Crack','Roots'],BLOB,old,lambda b,n:calls.append(b) or PAYLOAD)
    assert len(calls)==1 and actual['annotation_cache_status']=='INVALIDATED'
    assert actual['decoded_annotation_labels']==['Crack']
    assert actual['annotation_sha256']==hashlib.sha256(PAYLOAD).hexdigest()


def test_missing_annotation_does_not_retain_cached_success():
    actual=audit_annotation(SOURCE,['Crack'],None,verified_cache())
    assert not actual['annotation_structure_valid'] and not actual['annotation_labels_match_registry']
    assert actual['annotation_sha256'] is None and actual['decoded_annotation_labels']==[]


def test_modified_bytes_same_generation_are_detected_and_registry_mismatch_survives():
    actual=audit_annotation(SOURCE,['Crack','Roots'],BLOB,verified_cache(),lambda b,n:b'1 .5 .5 .2 .2')
    assert actual['annotation_cache_status']=='INVALIDATED'
    assert actual['decoded_annotation_labels']==['Roots'] and not actual['annotation_labels_match_registry']


def test_valid_cache_still_reads_current_bytes():
    actual=audit_annotation(SOURCE,['Crack'],BLOB,verified_cache(),lambda b,n:PAYLOAD)
    assert actual['annotation_cache_status']=='VERIFIED'


def test_invalid_image_cache_never_copies_eligibility_or_annotation_fields():
    assert reusable_image_fields({},dict(sha256='a'*64,original_image_path='a',width=40,height=40),'gs://b/a','1') is None


def test_perceptual_similarity_is_not_verified_video_lineage():
    base=dict(integrity_status='VERIFIED',dataset_name='A',original_split='train',actual_sha256='a'*64,dhash='0'*16,phash='0'*16,source_family_hint='PI1',record_id='a')
    other=dict(base,record_id='b',original_split='test',actual_sha256='b'*64)
    pair=duplicate_pairs([base,other])[0]
    assert pair['status']=='NEAR_DUPLICATE_CANDIDATE_UNVERIFIED'
    assert pair['source_relation']=='UNVERIFIED_FILENAME_FAMILY_HINT'
    leakage_groups([base,other],[pair])
    assert base['candidate_group_crosses_original_splits'] and not base.get('source_family_verified')
    other['dataset_name']='B'
    assert source_relation(base,other)=='UNESTABLISHED'


def test_confirmed_video_frames_need_explicit_matching_evidence_even_without_similarity():
    base=dict(integrity_status='VERIFIED',dataset_name='A',original_split='train',actual_sha256='a'*64,dhash='0'*16,phash='0'*16,record_id='a',source_family_verified=True,verified_source_video_id='V1',source_lineage_evidence_id='REVIEW-1')
    other=dict(base,record_id='b',original_split='test',actual_sha256='b'*64,dhash='f'*16,phash='f'*16)
    pair=duplicate_pairs([base,other])[0]
    assert pair['status']=='SOURCE_RELATION_ONLY' and pair['source_relation']=='CONFIRMED_SHARED_SOURCE_VIDEO'
    other.pop('source_lineage_evidence_id')
    assert source_relation(base,other)=='UNESTABLISHED' and duplicate_pairs([base,other])==[]


def test_nondict_annotation_cache_is_revalidated_not_trusted():
    result=audit_annotation(SOURCE,['Crack'],BLOB,'invalid',lambda b,n:PAYLOAD)
    assert result['annotation_structure_valid'] and result['annotation_cache_status']=='INVALIDATED'
    assert result['annotation_cache_invalidation_reasons']==['INVALID_CACHE_ENTRY']


@pytest.mark.parametrize('change',['missing_annotation','modified_annotation','generation','invalid_image_cache'])
def test_resume_integration_never_copies_stale_annotation_state(tmp_path,monkeypatch,change):
    from io import BytesIO
    import json
    from PIL import Image
    import scripts.cloud.audit_unified_dataset as audit
    buffer=BytesIO();Image.new('RGB',(40,40),'red').save(buffer,format='PNG');image=buffer.getvalue()
    prefix='source/'
    row=dict(original_image_path='train/images/a.png',original_annotation_path='train/labels/a.txt',
             sha256=hashlib.sha256(image).hexdigest(),width=40,height=40,source_labels=['Crack'],split='train')
    registry=dict(dataset_version='1',source='https://example.test',records=[row],original_classes=['Crack','Roots'],source_root_within_extracted_archive='.')
    payloads={prefix+'dataset_registry.json':json.dumps(registry).encode(),prefix+'extracted/train/images/a.png':image,
              prefix+'extracted/train/labels/a.txt':PAYLOAD}
    blobs={name:SimpleNamespace(name=name,generation=1,payload=data,size=len(data)) for name,data in payloads.items()}
    class Client:
        def bucket(self,name):return self
        def blob(self,name):return blobs[name]
        def list_blobs(self,name,prefix):return [b for n,b in blobs.items() if n.startswith(prefix)]
    monkeypatch.setattr(audit,'SOURCE_PREFIXES',{'Test':prefix});monkeypatch.setattr(audit,'BASELINES',[])
    monkeypatch.setattr(audit,'download',lambda b,limit=audit.MAX_BYTES:b.payload)
    audit.run(Client(),tmp_path/'first',1)
    if change=='missing_annotation':del blobs[prefix+'extracted/train/labels/a.txt']
    elif change=='modified_annotation':
        blob=blobs[prefix+'extracted/train/labels/a.txt'];blob.payload=b'1 .5 .5 .2 .2';blob.generation=2
    elif change=='generation':blobs[prefix+'extracted/train/images/a.png'].generation=2
    else:
        path=tmp_path/'first/dataset_inventory.jsonl';cached=json.loads(path.read_text());cached['actual_sha256']='bad';path.write_text(json.dumps(cached)+'\n')
    audit.run(Client(),tmp_path/'second',1,tmp_path/'first')
    result=json.loads((tmp_path/'second/dataset_inventory.jsonl').read_text())
    if change=='missing_annotation':assert not result['annotation_structure_valid'] and result['annotation_sha256'] is None
    elif change=='modified_annotation':assert result['decoded_annotation_labels']==['Roots'] and not result['annotation_labels_match_registry']
    else:assert not result.get('image_evidence_reused_generation_pinned',False) and result['actual_sha256']==row['sha256']
    assert not result['research_inference_eligible'] and not result['training_eligible']
