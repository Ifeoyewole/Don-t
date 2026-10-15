"""Rights-first WRc InceptionResNetV2 fine-tuning feasibility gate.

No training, weights export, weight downloads or inferred permissions. This audits
metadata and fails closed if explicit fine-tuning rights are not documented.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

REQUIRED=['original_weights_sha256','source_commit','original_class_codes',
          'preprocessing','research_finetune_allowed','rights_evidence_uri',
          'authorized_training_dataset','architecture_available']


def evaluate(metadata):
    missing=[k for k in REQUIRED if k not in metadata or metadata[k] is None]
    blockers=[]
    if missing:blockers.append('Missing provenance/authorization fields: '+', '.join(missing))
    if metadata.get('research_finetune_allowed') is not True:
        blockers.append('Fine-tuning rights not explicitly established (research_finetune_allowed != true)')
    if metadata.get('commercial_release_allowed') is not True:
        blockers.append('Commercial release rights are pending or expressly excluded')
    if metadata.get('architecture_available') is not True:
        blockers.append('Trainable Keras/TensorFlow architecture not verified')
    if metadata.get('training_head_strategy') not in ('original_13_class','new_multilabel_head'):
        blockers.append('13-softmax vs multi-label training-head strategy unspecified')
    if metadata.get('label_mapping_verified') is not True:
        blockers.append('Expert-verified mapping and training labels unavailable')
    ready_research=not any('Commercial release' not in x for x in blockers)
    return {'wrc_retrained':False,'wrc_finetuned':False,
            'research_finetune_ready':ready_research,
            'production_approved':False,'blockers':blockers}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--metadata',required=True)
    p.add_argument('--output',required=True)
    args=p.parse_args()
    meta=json.loads(Path(args.metadata).read_text())
    result=evaluate(meta)
    Path(args.output).write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
    if not result['research_finetune_ready']:raise SystemExit(2)
if __name__=='__main__':main()
