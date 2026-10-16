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

def test_missing_groups_allowed_with_unverified_split():
    data = [{'Filename': f'{i}.png', 'FS': str(int(i % 3 == 0)), 'ND': str(int(i % 3 != 0))} for i in range(25000)]
    selected = staged_select(data, 20000, allow_unverified_split=True)
    assert len(selected) == 20000
    assert all(r['source_group'] == 'official_train_unsegmented' for r in selected)

def test_partition_validation_unverified_split():
    val_data = [{'Filename': f'val_{i}.png', 'FS': '0', 'ND': '1'} for i in range(1200)]
    splits = partition_validation(val_data, allow_unverified_split=True)
    assert set(splits) == {'early_stop', 'threshold_tune', 'dev_report'}
    assert sum(len(v) for v in splits.values()) == 1200
    res = verify_disjoint(splits)
    assert res['filenames'] == 1200

def test_export_splits():
    from curate_staged import export_splits
    class MockBlob:
        def __init__(self, name, content=b""):
            self.name = name
            self.content = content
            self.metadata = {}
        def exists(self):
            return True
        def download_as_bytes(self):
            return self.content
        def upload_from_string(self, s, content_type=""):
            self.content = s.encode("utf-8") if isinstance(s, str) else s
        def patch(self):
            pass
    class MockBucket:
        name = "test-bucket"
        def __init__(self):
            self.blobs = {}
        def blob(self, name):
            if name not in self.blobs:
                self.blobs[name] = MockBlob(name)
            return self.blobs[name]

    bucket = MockBucket()
    val_rows = [f"val_{i}.png,{int(i%3==0)},{int(i%3!=0)}" for i in range(300)]
    val_csv = "Filename,FS,ND\n" + "\n".join(val_rows) + "\n"
    bucket.blobs["val.csv"] = MockBlob("val.csv", val_csv.encode("utf-8"))
    for i in range(300):
        bucket.blobs[f"curated/images/val_{i}.png"] = MockBlob(f"curated/images/val_{i}.png", b"fakeimagedata")

    train_records = [{"Filename": f"tr_{i}.png", "sha256": "a"*64, "GCS_URI": f"gs://test-bucket/tr_{i}.png", "FS": "1", "ND": "0"} for i in range(10)]
    res = export_splits(bucket, "prefix", train_records, val_manifest="val.csv", val_image_prefix="curated/images", allow_unverified_split=True)
    assert res["train"] == 10
    assert res["early_stop"] + res["threshold_tune"] + res["dev_report"] == 300
    assert "prefix/splits/train.csv" in bucket.blobs
    assert "prefix/splits/early_stop.csv" in bucket.blobs
    assert "prefix/splits/threshold_tune.csv" in bucket.blobs
    assert "prefix/splits/dev_report.csv" in bucket.blobs
