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


def test_validate_specs_supports_both_architectures_for_sewerml(tmp_path):
    from evaluate_same_images import validate_specs
    from curate_staged import TARGETS

    m1 = tmp_path / "eff.onnx"
    m1.write_bytes(b"eff_dummy")
    h1 = hashlib.sha256(b"eff_dummy").hexdigest()

    m2 = tmp_path / "wrc_adapted.onnx"
    m2.write_bytes(b"wrc_dummy")
    h2 = hashlib.sha256(b"wrc_dummy").hexdigest()

    specs = [
        {
            "name": "eff-v3",
            "model": str(m1),
            "sha256": h1,
            "kind": "sewerml_multilabel_sigmoid",
            "preprocess": "imagenet_rgb_nchw",
            "image_size": 224,
            "class_codes": list(TARGETS),
            "output_activation": "probability",
            "thresholds": {c: 0.5 for c in TARGETS},
        },
        {
            "name": "wrc-adapted-v3",
            "model": str(m2),
            "sha256": h2,
            "kind": "sewerml_multilabel_sigmoid",
            "preprocess": "wrc_raw_rgb_nhwc",
            "class_codes": list(TARGETS),
            "output_activation": "probability",
            "thresholds": {c: 0.5 for c in TARGETS},
        },
    ]
    validate_specs(specs)

