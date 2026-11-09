"""Review packages cannot silently become executable GPU manifests."""
import csv
import json
from pathlib import Path

from scripts.cloud.prepare_unified_audit_stages import prepare


def test_all_stages_remain_unapproved_and_keep_provisional_pilot_separate(tmp_path: Path):
    rows=[]; inventory=[]
    for i in range(1,81):
        sha=f'{i:064x}'; hint={10:'PI005455',26:'PI005286',34:'PI008113'}.get(i,f'FAMILY{i}')
        source={'dataset_name':'Sewer Defects Public','source_image_path':f'train/{i}.jpg',
                'image_sha256':sha,'width':'416','height':'416','source_labels':'Joint offset',
                'source_media_id':f'{hint}_f100','candidate_bucket':'JOINT_DISPLACEMENT_CANDIDATE',
                'image_uri_TO_VERIFY':f'gs://joint-inspection-510310-data/{i}.jpg'}
        rows.append(source)
        inventory.append({'record_id':f'sewer-{i:04d}','dataset_name':source['dataset_name'],
             'original_image_path':source['source_image_path'],'expected_sha256':sha,
             'image_uri':source['image_uri_TO_VERIFY'],'image_generation':'1',
             'source_family_hint':hint,'integrity_status':'VERIFIED','lineage_status':'LINEAGE_UNCERTAIN',
             'near_duplicate_candidate':False,'technical_classification_candidate':True,
             'conservative_leakage_group':str(i)})
    (tmp_path/'dataset_inventory.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in inventory))
    (tmp_path/'duplicate_candidates.csv').write_text('left_id,right_id,status\n')
    existing=tmp_path/'existing.csv'
    with existing.open('w',newline='') as out:
        w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result=prepare(tmp_path,existing)
    assert [result[k]['candidate_count'] for k in ['pilot3','pilot14','research80']]==[3,14,80]
    for stage in result.values():
        assert stage['approved_count']==0 and stage['status']=='BLOCKED_REVIEW'
        assert stage['executable_manifest'] is None
        assert stage['validation']['executable'] is False
    pilot=list(csv.DictReader((tmp_path/'stage-review/pilot3_review.csv').open()))
    assert all(not r['roi_x0'] and not r['source_family_TO_VERIFY'] and not r['task_type_TO_REVIEW'] for r in pilot)
    assert all(r['provisional_roi'] and r['provisional_task'] for r in pilot)
    first={r['record_id'] for r in result['pilot3']['frame_bindings']}
    second={r['record_id'] for r in result['pilot14']['frame_bindings']}
    assert not first.intersection(second)
