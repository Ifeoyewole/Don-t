"""Real same-image WRc / Sewer-ML ONNX inference and taxonomy-safe comparison.

Always uses model-specific preprocessing. Never compares historical headline metrics,
forces ambiguous WRc classes into Sewer-ML labels, tunes on locked tests, or
converts probabilities into physical geometry. Run on GCP ephemeral worker.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import time
from pathlib import Path
import numpy as np
from PIL import Image
from curate_staged import TARGETS, gcp_attestation
from metrics_v3 import complete_report,metrics,calibration


def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def preprocess(image: Image.Image,model_spec):
    """Match archived WRc NHWC raw-RGB model; native v1/v2/v3 CHW ImageNet."""
    mode=model_spec['preprocess']
    if mode=='wrc_raw_rgb_nhwc':
        target=299
        img=image.convert('RGB')
        w,h=img.size
        scale=min(target/w,target/h)
        size=(max(1,int(w*scale)),max(1,int(h*scale)))
        resized=img.resize(size,Image.Resampling.LANCZOS)
        canvas=Image.new('RGB',(target,target),(0,0,0))
        canvas.paste(resized,((target-size[0])//2,(target-size[1])//2))
        return np.asarray(canvas,dtype=np.float32)[None,:,:,:]
    if mode=='imagenet_rgb_nchw':
        target=int(model_spec['image_size'])
        img=image.convert('RGB').resize((target,target),Image.Resampling.BILINEAR)
        arr=np.asarray(img,dtype=np.float32)/255.0
        arr=(arr-np.array([.485,.456,.406],dtype=np.float32))/np.array([.229,.224,.225],dtype=np.float32)
        return np.transpose(arr,(2,0,1))[None,:,:,:]
    raise ValueError(f'Unverified preprocessing mode {mode}')


def validate_specs(specs):
    if not specs:raise ValueError('No models specified')
    allowed={'wrc_raw_rgb_nhwc','imagenet_rgb_nchw'}
    if len(set(x['name'] for x in specs))!=len(specs):raise ValueError('Repeated model identifiers')
    for spec in specs:
        if spec['preprocess'] not in allowed:raise ValueError('Unknown preprocessing')
        if spec['kind'] not in ('wrc_single_softmax','sewerml_multilabel_sigmoid'):
            raise ValueError('Unknown prediction semantics')
        if spec['kind']=='wrc_single_softmax' and spec['preprocess']!='wrc_raw_rgb_nhwc':
            raise ValueError('WRc preprocessing mismatch')
        if spec['kind']=='sewerml_multilabel_sigmoid' and spec['preprocess'] not in ('imagenet_rgb_nchw', 'wrc_raw_rgb_nhwc'):
            raise ValueError('Sewer-ML preprocessing mismatch')
        if len(spec['class_codes'])!=(13 if spec['kind']=='wrc_single_softmax' else 9):
            raise ValueError('Output head dimension is not verified for this model')
        if spec['kind']=='sewerml_multilabel_sigmoid' and spec['class_codes']!=list(TARGETS):
            raise ValueError('Native output ordering differs from original Sewer-ML labels')
        if spec['kind']=='wrc_single_softmax' and spec['class_codes'][6]!='JD':
            raise ValueError('WRc index 6 must be the displaced-joint (JD) class')
        if spec['kind']=='sewerml_multilabel_sigmoid' and set(spec['thresholds'])!=set(TARGETS):
            raise ValueError('Native per-class thresholds absent')
        if any(float(v)<0 or float(v)>1 for v in spec.get('thresholds',{}).values()):
            raise ValueError('Invalid threshold')
        file=Path(spec['model'])
        if not file.is_file() or digest(file)!=spec['sha256'].lower():
            raise ValueError(f'Model missing/hash mismatch: {spec["name"]}')


def read_locked_manifest(path,integrity_path):
    manifest=Path(path).read_bytes()
    integrity=json.loads(Path(integrity_path).read_text())
    if not integrity.get('immutable') or hashlib.sha256(manifest).hexdigest()!=integrity['manifest_sha256']:
        raise RuntimeError('Locked-test manifest not sealed or digest disagrees')
    payload=json.loads(manifest)
    rows=list(payload['rows'].values())
    if len(rows)!=integrity['sample_count'] or any(x.get('split')!='locked_test' for x in rows):
        raise RuntimeError('Locked-test manifest failed count/split integrity')
    if len({x['Filename'].casefold() for x in rows})!=len(rows):
        raise RuntimeError('Duplicate test filenames')
    return sorted(rows,key=lambda r:r['Filename'])


def run_evaluation(specs,rows,images_dir,output_dir):
    import onnxruntime as ort
    validate_specs(specs)
    roots=Path(images_dir);out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    truth=np.array([[float(r.get(c) in ('1','1.0')) for c in TARGETS] for r in rows],dtype=np.float32)
    reports={}; outputs={}
    for spec in specs:
        session=ort.InferenceSession(spec['model'],providers=['CPUExecutionProvider'])
        output_name=session.get_outputs()[0].name
        output_rows=[];per_image_ms=[]
        for row in rows:
            filename=row['Filename']
            path=roots/filename
            if path.name!=filename or digest(path)!=row['sha256']:
                raise RuntimeError(f'Image digest mismatch: {filename}')
            with Image.open(path) as img:
                blob=preprocess(img,spec)
            started=time.perf_counter()
            arr=np.asarray(session.run([output_name],{session.get_inputs()[0].name:blob})[0])[0]
            elapsed_ms=(time.perf_counter()-started)*1000
            if arr.shape!=(len(spec['class_codes']),) or not np.isfinite(arr).all():
                raise RuntimeError(f'Invalid output from {spec["name"]} on {filename}')
            if spec['kind']=='sewerml_multilabel_sigmoid':
                if spec.get('output_activation')=='logits':
                    arr=1/(1+np.exp(-np.clip(arr,-60,60)))
                elif spec.get('output_activation')!='probability':
                    raise ValueError('Unspecified native activation')
            elif (arr<0).any() or abs(float(arr.sum())-1)>0.01:
                raise ValueError('WRc output is not a normalized softmax distribution')
            per_image_ms.append(elapsed_ms)
            output_rows.append(arr)
        probs=np.asarray(output_rows)
        outputs[spec['name']]=probs
        if spec['kind']=='sewerml_multilabel_sigmoid':
            thresholds=[spec['thresholds'][c] for c in TARGETS]
            report=complete_report(truth,probs,TARGETS,thresholds)
        else:
            # The archived WRc head lacks a NORMAL class and cannot emit simultaneous
            # defects. Only directly justified Sewer-ML FS <-> WRc JD is compared.
            # A generic deposit class is NOT forced onto AF or BE.
            top1=probs.argmax(axis=1)
            fs_pred=top1==6
            fs_true=truth[:,0].astype(bool)
            report={'native_13_class_top1_counts':{spec['class_codes'][i]:int((top1==i).sum()) for i in range(13)},
                    'common_taxonomy':{'FS_displaced_joint_DIRECT_only':metrics(fs_true,fs_pred)},
                    'fs_probability_calibration':calibration(fs_true[:,None],probs[:,6:7]),
                    'uncomparable_classes':['IS','RB','DE','RO','AF','BE','FO','ND'],
                    'multilabel_positive_count':int((truth.sum(axis=1)>1).sum()),
                    'single_label_head_limitation':True,'sample_count':len(rows)}
        report['model_id']=spec['name']
        report['model_sha256']=spec['sha256']
        report['latency_ms_median']=float(np.median(per_image_ms))
        report['latency_ms_p95']=float(np.percentile(per_image_ms,95))
        report['model_size_bytes']=Path(spec['model']).stat().st_size
        report['production_approved']=False
        reports[spec['name']]=report
        with (out/f'{spec["name"]}_predictions.jsonl').open('w') as dest:
            for row,p in zip(rows,probs):
                dest.write(json.dumps({'Filename':row['Filename'],'source_sha256':row['sha256'],
                                       'class_codes':spec['class_codes'],'probabilities':p.tolist()},sort_keys=True)+'\n')
    (out/'same_image_report.json').write_text(json.dumps({'models':reports,'identical_ordered_images':True,
                                        'sample_count':len(rows),'locked_test_used_for_tuning':False},indent=2))
    return reports


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',default='joint-inspection-510310')
    for x in ('model-config','manifest','integrity','images-dir','output'):parser.add_argument('--'+x,required=True)
    args=parser.parse_args()
    gcp_attestation(args.project)
    specs=json.loads(Path(args.model_config).read_text())['models']
    rows=read_locked_manifest(args.manifest,args.integrity)
    result=run_evaluation(specs,rows,args.images_dir,args.output)
    print(json.dumps({'evaluated_models':list(result),'images':len(rows),'production_approved':False},indent=2))
if __name__=='__main__':main()
