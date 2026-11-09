"""Regression checks for the offline dataset audit; no cloud or model calls."""
from io import BytesIO

from PIL import Image
import pytest

from scripts.cloud.audit_unified_dataset import check_yolo, duplicate_pairs, image_evidence, leakage_groups, resolve_name


def test_ambiguous_or_escaping_source_path_is_not_guessed():
    registry = {'source_root_within_extracted_archive': '.'}
    names = ['prefix/a/extracted/train/images/image.jpg', 'prefix/b/extracted/train/images/image.jpg']
    assert resolve_name(registry, 'train/images/image.jpg', 'prefix/', names) is None
    with pytest.raises(ValueError):
        resolve_name(registry, '../image.jpg', 'prefix/', names)


@pytest.mark.parametrize('label', ['0 nan .5 .1 .1', '0 .99 .5 .4 .1', '3 .5 .5 .1 .1', '0 .5 .5 0 .1', '0 .5 .5 .1'])
def test_invalid_yolo_geometry_never_becomes_structurally_valid(label):
    assert check_yolo(label, ['Joint offset'])['annotation_structure_valid'] is False


def test_structural_annotation_check_does_not_adjudicate_identity():
    result = check_yolo('0 .5 .5 .1 .2', ['Utility intrusion'])
    assert result['annotation_structure_valid'] is True
    assert result['decoded_annotation_labels'] == ['Utility intrusion']
    assert 'reviewed_label' not in result


def test_integrity_and_hashes_decode_actual_bytes():
    buffer = BytesIO(); Image.new('RGB', (40, 50), 'red').save(buffer, format='PNG')
    evidence, thumb = image_evidence(buffer.getvalue())
    assert (evidence['width'], evidence['height']) == (40, 50)
    assert len(evidence['dhash']) == 16 and len(evidence['phash']) == 16
    assert thumb.width == 40
    with pytest.raises(Exception): image_evidence(b'not an image')


def test_near_duplicate_candidates_are_not_exact_duplicates_or_lineage_proof():
    base = {'integrity_status':'VERIFIED', 'dataset_name':'A','original_split':'train',
            'actual_sha256':'a'*64,'dhash':'0'*16,'phash':'0'*16,'source_family_hint':None}
    rows = [dict(base,record_id='a'),dict(base,record_id='b',actual_sha256='b'*64,original_split='test'),
            dict(base,record_id='c',actual_sha256='a'*64,dataset_name='B')]
    pairs = duplicate_pairs(rows)
    assert sum(p['status']=='SHA256_EXACT' for p in pairs) == 1
    assert sum(p['status']=='NEAR_DUPLICATE_CANDIDATE_UNVERIFIED' for p in pairs) == 2
    leakage_groups(rows,pairs)
    assert len({r['conservative_leakage_group'] for r in rows}) == 1
    assert all(r['candidate_group_crosses_original_splits'] for r in rows)
    assert all('source_family_verified' not in r for r in rows)


def test_polygon_annotation_is_preserved_as_polygon_not_corrupt_box():
    result=check_yolo('0 .1 .1 .8 .1 .8 .8 .1 .8 .1 .1', ['Offset joint'])
    assert result['annotation_structure_valid']
    assert result['observed_annotation_format']=='YOLO_POLYGON'
    assert result['annotation_polygon_count']==1
    assert result['annotation_box_count']==0
    assert result['decoded_annotation_labels']==['Offset joint']
    assert not check_yolo('0 .1 .1 .1 .1 .1 .1',['Offset joint'])['annotation_structure_valid']
    assert not check_yolo('0 .1 .1 1.2 .1 .8 .8',['Offset joint'])['annotation_structure_valid']


def test_resume_preserves_polygon_format_and_supports_legacy_box_cache():
    from scripts.cloud.audit_unified_dataset import cached_annotation_format
    polygon=check_yolo('0 .1 .1 .8 .1 .8 .8 .1 .8',['Offset joint'])
    resumed=cached_annotation_format(polygon)
    assert resumed['observed_annotation_format']=='YOLO_POLYGON'
    assert resumed['annotation_polygon_count']==1
    assert cached_annotation_format({'annotation_box_count':2})['observed_annotation_format']=='YOLO_BOUNDING_BOX'
