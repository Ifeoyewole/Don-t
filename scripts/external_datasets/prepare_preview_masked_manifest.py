"""Rebuild preview labels from evidence without inventing negative annotations."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from training.preview_annotation_policy import sewer_manifest_annotations


def build(base, originals, labels):
    source = {r['sha256']: r for r in originals}
    output, excluded = [], Counter()
    for old in base:
        row = dict(old)
        if row['split'] == 'test':
            excluded['held_out_test_excluded'] += 1
            continue
        name = row['dataset_name']
        if name == 'Sewer-ML':
            raw = source.get(row['sha256'])
            if raw is None:
                excluded['missing_full_original_annotations'] += 1
                continue
            row.update(sewer_manifest_annotations(raw, labels))
            row['original_annotations'] = {k:raw[k] for k in raw if k in
                ('ND','FS','RB','DE','FO','IN','OB','AF','BE','IS','RO','GR','PB')}
        elif name == 'Robotic Pipe Defect Detection v7':
            row['jointinspect_labels'] = [x for x in row['jointinspect_labels'] if x != 'GEOMETRY_UNCERTAIN']
            # Cross-class negatives require source annotation completeness audit.
            row['observed_jointinspect_labels'] = list(row['jointinspect_labels'])
        elif name == 'Pipeline Defect Detection v8':
            row['jointinspect_labels'] = ['CORROSION'] if 'corrosion' in row['source_labels'] else []
            row['observed_jointinspect_labels'] = list(row['jointinspect_labels'])
        else:
            excluded['unresolved_source_label_semantics'] += 1
            continue
        if not row['observed_jointinspect_labels']:
            excluded['no_observed_targets'] += 1
            continue
        row['annotation_policy'] = 'explicit_observed_labels_v1'
        row['evaluation_eligibility'] = 'EXPLORATORY_PENDING_ANCESTOR_EXPOSURE_AUDIT'
        output.append(row)
    digest = [r['sha256'] for r in output]
    if len(digest) != len(set(digest)):
        raise ValueError('Duplicate SHA in prepared manifest')
    summary = {'records':len(output),'split_counts':dict(Counter(r['split'] for r in output)),
        'positive_counts':dict(Counter(x for r in output for x in r['jointinspect_labels'])),
        'excluded':dict(excluded),'training_ready':False,
        'blockers':['Validate masked trainer in PyTorch','Audit inherited evaluation exposure',
                    'Verify negative annotation completeness for external sources'],
        'production_approved':False,'locked_test_evaluated':False}
    return output, summary


def main():
    p=argparse.ArgumentParser()
    for n in ('base','originals','labels','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    base=[json.loads(x) for x in a.base.read_text().splitlines() if x.strip()]
    rows,report=build(base,json.loads(a.originals.read_text())['records'],json.loads(a.labels.read_text())['canonical_labels'])
    a.output.mkdir(parents=True,exist_ok=True)
    payload=''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows)
    (a.output/'representation.jsonl').write_text(payload)
    report['manifest_sha256']=hashlib.sha256(payload.encode()).hexdigest()
    (a.output/'preparation_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
