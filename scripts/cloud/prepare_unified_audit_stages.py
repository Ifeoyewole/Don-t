"""Prepare unapproved stage review packages from an actual full-dataset audit.

Never approves an ROI, labels or source family. Never submits a cloud job.
Existing source contact-sheet numbers are preserved, not inferred from filenames.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from scripts.cloud.audit_unified_dataset import write_csv
from scripts.cloud.create_unified_batch_manifest import convert_worklist

PILOT3 = {10: ('JOINT_GEOMETRY', [96,125,401,404], 'PI005455'),
          26: ('OBJECT_SEGMENTATION', [164,51,410,415], 'PI005286'),
          34: ('OBJECT_SEGMENTATION', [42,109,375,248], 'PI008113')}


def prepare(audit: Path, existing: Path) -> dict:
    records = [json.loads(line) for line in (audit/'dataset_inventory.jsonl').read_text().splitlines()]
    original = list(csv.DictReader(existing.open(encoding='utf-8-sig')))
    keyed = {(r['dataset_name'],r['original_image_path'],r['expected_sha256']):r for r in records}
    pairs = list(csv.DictReader((audit/'duplicate_candidates.csv').open()))
    conflicts = {frozenset((p['left_id'],p['right_id'])) for p in pairs}
    work = []
    for number, row in enumerate(original,1):
        item = dict(row)
        match = keyed.get((row['dataset_name'], row['source_image_path'], row['image_sha256']))
        item.update(contact_sheet_number=number, review_status='NEEDS_HUMAN_REVIEW',
                    task_type_TO_REVIEW='', source_family_TO_VERIFY='', geometry_TO_REVIEW='',
                    roi_x0='',roi_y0='',roi_x1='',roi_y1='',review_id='',reviewed_ground_truth_label='',
                    rights_review='RESEARCH_QUARANTINE',annotation_review='UNVERIFIED_SOURCE_LABEL',
                    stage_approval=False)
        if match:
            item.update(audit_record_id=match['record_id'],integrity_status=match['integrity_status'],
                        image_uri_TO_VERIFY=match.get('image_uri',''),
                        image_generation=match.get('image_generation'), source_family_hint=match['source_family_hint'],
                        lineage_status=match['lineage_status'],near_duplicate_candidate=match['near_duplicate_candidate'],
                        technical_classification_candidate=match['technical_classification_candidate'],
                        original_uri_matches_audit=row.get('image_uri_TO_VERIFY')==match.get('image_uri'),
                        conservative_leakage_group=match['conservative_leakage_group'])
        else: item.update(audit_record_id='',integrity_status='UNRESOLVED',technical_classification_candidate=False)
        work.append(item)
    pilot = []
    for number,(task,roi,hint) in PILOT3.items():
        if number>len(work): continue
        item=dict(work[number-1]); expected_hint=item.get('source_family_hint')==hint
        roi_in_bounds=(roi[2]<=int(item['width']) and roi[3]<=int(item['height']))
        item.update(provisional_task=task,provisional_roi=roi,expected_family_hint=hint,
                    family_hint_matches_request=expected_hint,provisional_roi_in_bounds=roi_in_bounds,
                    selection_note='User-proposed task/ROI only; human targeting and lineage approval absent')
        pilot.append(item)
    # Disjoint from pilot3, so successful earlier frames need not be recharged.
    pilot_ids={r['audit_record_id'] for r in pilot}
    pool=[r for r in work if r.get('technical_classification_candidate') and r['audit_record_id'] not in pilot_ids]
    fourteen=[]; used_hints=set()
    categories=['INFILTRATION_CANDIDATE_UNVERIFIED','JOINT_DISPLACEMENT_CANDIDATE',
                'PROTRUDING_LATERAL_CANDIDATE_UNVERIFIED','HARD_NEGATIVE_OR_OTHER_CANDIDATE']
    grouped={category:[r for r in pool if r.get('candidate_bucket')==category] for category in categories}
    ordered=[]
    for index in range(max((len(v) for v in grouped.values()),default=0)):
        for category in categories:
            if index<len(grouped[category]): ordered.append(grouped[category][index])
    for require_distinct_hint in (True,False):
        for row in ordered:
            if len(fourteen)>=14: break
            if row in fourteen: continue
            hint=row.get('source_family_hint')
            if require_distinct_hint and (not hint or hint in used_hints): continue
            if any(frozenset((row['audit_record_id'],s['audit_record_id'])) in conflicts for s in fourteen): continue
            fourteen.append(dict(row));used_hints.add(hint)
    review=audit/'stage-review';review.mkdir()
    write_csv(review/'pilot3_review.csv',pilot)
    write_csv(review/'pilot14_review.csv',fourteen)
    write_csv(review/'research80_review.csv',work)
    replacements=[{'contact_sheet_number':r['contact_sheet_number'],'audit_record_id':r['audit_record_id'],
                   'replacement_made':False,'reason':'No automatic replacement; reviewer must adjudicate similarity and suitability',
                   'near_duplicate_candidate':r.get('near_duplicate_candidate')} for r in work]
    write_csv(review/'research80_selection_review.csv',replacements)
    result={}
    for name,rows,target in [('pilot3',pilot,3),('pilot14',fourteen,14),('research80',work,80)]:
        try:
            convert_worklist(rows,manifest_id=f'{name}_unapproved',limit=target)
            raise AssertionError('Unreviewed worklist unexpectedly executable')
        except ValueError as exc:
            validation={'executable':False,'actual_converter_rejection':str(exc)}
        package={'type':'REVIEW_PACKAGE_NOT_EXECUTABLE','status':'BLOCKED_REVIEW','stage':name,
                 'target_count':target,'candidate_count':len(rows),'approved_count':0,'executable_manifest':None,
                 'container_digest':'sha256:a3db9ffaa1d0704290ccee7c3dd9af81c9af860755be3a076187b9fe866db37c',
                 'additional_blockers':['BLOCKED_BUDGET','GEMINI_AUTHENTICATED_RECEIPTS_UNAVAILABLE'],
                 'review_worklist':f'{name}_review.csv','validation':validation,
                 'coverage':dict(Counter(r.get('candidate_bucket') for r in rows)),
                 'coverage_limitations':['No independently verified normal/open-joint positives',
                    'Lighting/camera diversity and object identity require human inspection',
                    'Leak candidate is not confirmed active infiltration'],
                 'frame_bindings':[{'record_id':r.get('audit_record_id'),'sha256':r['image_sha256'],
                    'image_uri':r.get('image_uri_TO_VERIFY'),'contact_sheet_number':r['contact_sheet_number'],
                    'review_status':'NEEDS_HUMAN_REVIEW'} for r in rows]}
        (review/f'taskaware_{name}_manifest.json').write_text(json.dumps(package,indent=2)+'\n')
        result[name]=package
    full={'status':'BLOCKED_REVIEW','inventory_count':len(records),'approved_task_inference_count':0,
          'executable_batches':[], 'maximum_frames_per_manifest':100,'gpu_concurrency':1,
          'automatic_retries':0,'full_dataset_cost_estimate':None,
          'cost_estimate_reason':'Requires measured approved pilot runtime and then-current Spot GPU/VM/disk/API pricing',
          'unreviewed_images':'INVENTORY_ONLY_AND_HUMAN_REVIEW_QUEUE',
          'no_automatic_ROI_or_defect_identity':True}
    (review/'full_inference_plan.json').write_text(json.dumps(full,indent=2)+'\n')
    (review/'stage_summary.json').write_text(json.dumps({k:{x:v[x] for x in ['status','candidate_count','approved_count','coverage']} for k,v in result.items()},indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-dir',type=Path,required=True);parser.add_argument('--existing-worklist',type=Path,required=True)
    args=parser.parse_args(); result=prepare(args.audit_dir,args.existing_worklist)
    print(json.dumps({k:{'status':v['status'],'candidates':v['candidate_count']} for k,v in result.items()},indent=2))

if __name__=='__main__':main()
