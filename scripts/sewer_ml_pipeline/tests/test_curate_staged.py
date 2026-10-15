from pathlib import Path
import io,sys
import pytest
from PIL import Image
from curate_staged import staged_select, partition_validation, verify_disjoint, NearDuplicateIndex, image_dhash

def rows(n):
    return [{'Filename':f'{i}.png','video_id':f'vid{i//25}','FS':str(int(i%3==0)),
             'DE':str(int(i%40==0)), 'ND':str(int(i%3!=0))} for i in range(n)]

def test_stages_are_nested_not_additive():
    data=rows(100030)
    s20=staged_select(data,20000)
    s30=staged_select(data,30000)
    s100=staged_select(data,100000)
    assert set(r['Filename'] for r in s20)<set(r['Filename'] for r in s30)
    assert set(r['Filename'] for r in s30)<set(r['Filename'] for r in s100)

def test_validation_disjoint_by_source_group():
    groups=partition_validation(rows(3000))
    assert verify_disjoint(groups)['filenames']==3000
    assert set(groups)=={'early_stop','threshold_tune','dev_report'}

def test_group_overlap_rejected():
    with pytest.raises(ValueError):
        verify_disjoint({'train':[{'Filename':'a.png','video_id':'v'}],
                         'val':[{'Filename':'b.png','video_id':'v'}]})

def test_missing_groups_fail_closed():
    bad=rows(20000);bad[0].pop('video_id')
    with pytest.raises(ValueError): staged_select(bad,20000)

def test_exact_and_near_duplicates():
    index=NearDuplicateIndex()
    assert index.add('a','sha1',0x123456789abcdef0)[0]
    assert not index.add('b','sha1',0x123456789abcdef0)[0]
    assert not index.add('c','sha2',0x123456789abcdef1)[0]
    assert index.add('d','sha3',0xffffffffffffffff)[0]

def test_valid_image_hash():
    im=Image.new('RGB',(16,16),'white'); b=io.BytesIO(); im.save(b,format='PNG')
    assert isinstance(image_dhash(b.getvalue()),int)
