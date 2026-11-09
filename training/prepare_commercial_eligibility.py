"""Build a training eligibility matrix without promoting quarantined source data."""
import argparse,csv,json
from collections import Counter
from pathlib import Path
from training.commercial_candidate import eligibility


def prepare(inventory,out):
    rows=[json.loads(line) for line in Path(inventory).read_text().splitlines()];matrix=[]
    for source in rows:
        candidate={'record_id':source['record_id'],'original_source':source.get('source',''),
                   'source_image_uri':source.get('image_uri'),'sha256':source.get('actual_sha256'),
                   'original_labels':source.get('original_labels',[]),'split':source.get('original_split'),
                   'rights_status':source.get('rights_status'),'commercial_training_eligible':source.get('commercial_training_eligible') is True,
                   'annotation_verified':source.get('annotation_verification_status')=='REVIEWED_GROUND_TRUTH',
                   'source_family_verified':source.get('source_family_verified') is True,
                   'source_family_hint':source.get('source_family_hint'),'duplicate_status':'CANDIDATE_REVIEW_REQUIRED' if source.get('near_duplicate_candidate') else 'UNVERIFIED_DUPLICATE_REVIEW',
                   'commercial_training_permission_id':source.get('commercial_training_permission_id'),
                   'annotation_review_id':source.get('review_id'),'source_family_review_id':source.get('source_lineage_evidence_id'),
                   'source_family_id':source.get('verified_source_video_id'),'license_spdx':None,
                   'rights_document_sha256':source.get('rights_document_sha256')}
        candidate['blocking_reasons']=eligibility(candidate);candidate['eligible']=not candidate['blocking_reasons'];matrix.append(candidate)
    out=Path(out)
    with out.open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(matrix[0]));writer.writeheader()
        for row in matrix:writer.writerow({k:json.dumps(v) if isinstance(v,list) else v for k,v in row.items()})
    return {'records':len(matrix),'eligible':sum(r['eligible'] for r in matrix),
            'blocker_counts':dict(Counter(v for r in matrix for v in r['blocking_reasons'])),
            'training_executed':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inventory',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.inventory,args.out),indent=2))
