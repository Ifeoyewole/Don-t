from pathlib import Path
import io,sys,json,hashlib
from PIL import Image
import numpy as np
import pytest
from evaluate_same_images import preprocess,read_locked_manifest

def test_wrc_raw_nhwc_aspect_preserving():
    image=Image.new('RGB',(40,20),'white')
    result=preprocess(image,{'preprocess':'wrc_raw_rgb_nhwc'})
    assert result.shape==(1,299,299,3) and result.dtype==np.float32
    assert result.max()==255 and result[0,0,0,0]==0

def test_native_imagenet_nchw():
    image=Image.new('RGB',(40,20),'white')
    result=preprocess(image,{'preprocess':'imagenet_rgb_nchw','image_size':224})
    assert result.shape==(1,3,224,224) and result.dtype==np.float32
    assert result[0,0,0,0]>2

def test_unsealed_locked_data_rejected(tmp_path):
    data=json.dumps({'rows':{'a':{'Filename':'a.png','split':'locked_test'}}},sort_keys=True).encode()
    (tmp_path/'manifest.json').write_bytes(data)
    (tmp_path/'integrity.json').write_text(json.dumps({'immutable':False,'manifest_sha256':hashlib.sha256(data).hexdigest(),'sample_count':1}))
    with pytest.raises(RuntimeError):read_locked_manifest(tmp_path/'manifest.json',tmp_path/'integrity.json')
