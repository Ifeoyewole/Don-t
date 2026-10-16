from pathlib import Path
import sys
from wrc_feasibility import evaluate

def test_pending_provenance_blocks_training():
    result=evaluate({'research_finetune_allowed':False})
    assert result['research_finetune_ready'] is False
    assert result['wrc_finetuned'] is False
    assert result['production_approved'] is False

def test_research_governance_remains_nonproduction():
    metadata=dict(original_weights_sha256='test',source_commit='sha',original_class_codes=['JD'],
                  preprocessing='raw_rgb_nhwc',research_finetune_allowed=True,
                  rights_evidence_uri='signed-approval',authorized_training_dataset='licensed',
                  architecture_available=True,training_head_strategy='new_multilabel_head',
                  label_mapping_verified=True,commercial_release_allowed=False)
    result=evaluate(metadata)
    assert result['research_finetune_ready'] is True
    assert result['production_approved'] is False
