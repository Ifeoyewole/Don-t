"""Rights-gated multilabel training preparation; default execution is synthetic CPU only.

No Vertex submission, pretrained downloads, production publishing or automatic
promotion. Real data needs a separately pinned eligibility registry and execution
approval. Existing research weights are never initialization candidates here.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import random
from collections import Counter

LABELS=['NORMAL','OPEN_JOINT','FAULTY_JOINT','JOINT_DISPLACEMENT','JOINT_MISALIGNMENT',
        'DEFORMATION','RUPTURE','BROKEN_PIPE','BLOCKAGE','OBSTACLE','INFILTRATION',
        'SURFACE_DAMAGE','CORROSION','PROTRUDING_LATERAL','GEOMETRY_UNCERTAIN']


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def eligibility(row):
    reasons=[]
    for flag in ['commercial_training_eligible','annotation_verified','source_family_verified']:
        if row.get(flag) is not True:reasons.append(flag.upper()+'_REQUIRED')
    for field in ['original_source','commercial_training_permission_id','annotation_review_id',
                  'source_family_review_id','source_family_id','license_spdx']:
        if not isinstance(row.get(field),str) or not row[field].strip():reasons.append(field.upper()+'_REQUIRED')
    if row.get('rights_status')=='RESEARCH_QUARANTINE':reasons.append('RESEARCH_QUARANTINE')
    if row.get('duplicate_status') not in ('UNIQUE_VERIFIED','CANONICAL_EXACT_REPRESENTATIVE_VERIFIED'):
        reasons.append('DUPLICATE_REVIEW_REQUIRED')
    if row.get('split') not in ('train','val','test'):reasons.append('SPLIT_REQUIRED')
    if len(str(row.get('rights_document_sha256','')))!=64:reasons.append('RIGHTS_DOCUMENT_HASH_REQUIRED')
    return reasons


def validate_manifest(manifest,config,registry=None):
    if config.get('pretrained_checkpoint') is not None:raise ValueError('Unapproved pretrained weights prohibited')
    labels=config['labels'];rows=manifest['records']
    if not rows or len(labels)!=len(set(labels)):raise ValueError('Nonempty records and unique labels required')
    synthetic=config['mode']=='synthetic_smoke'
    if synthetic:
        if config['architecture']!='synthetic_test_only' or config['epochs']>2 or config['device']!='cpu':
            raise ValueError('Synthetic smoke is bounded CPU testing only')
    else:
        if config['mode']!='commercial_candidate' or config['architecture']!='convnext_tiny':raise ValueError('Unsupported training mode')
        if registry is None or digest(registry)!=config.get('eligibility_registry_sha256'):raise ValueError('Pinned eligibility registry required')
        authoritative={r['record_id']:r for r in registry['records']}
    groups={};hashes={};record_ids=set()
    for row in rows:
        if row['record_id'] in record_ids:raise ValueError('Duplicate record ID')
        record_ids.add(row['record_id'])
        if len(row['sha256'])!=64:raise ValueError('Image hash required')
        if synthetic:
            if row.get('synthetic') is not True:raise ValueError('Real data cannot enter synthetic smoke')
        else:
            approved=authoritative.get(row['record_id'])
            if not approved or eligibility(approved):raise ValueError('Unapproved commercial training record')
            for field in ['sha256','image_uri','source_family_id','split','labels','observed_labels']:
                if approved.get(field)!=row.get(field):raise ValueError('Manifest differs from approved eligibility registry')
            if 'INFILTRATION' in row['labels'] and not approved.get('temporal_or_field_evidence_id'):
                raise ValueError('Infiltration requires temporal or field evidence')
        if row['split'] not in ('train','val','test'):raise ValueError('Invalid split')
        if not set(row['labels'])<=set(row['observed_labels'])<=set(labels):raise ValueError('Explicit observed labels required')
        for key in [row['source_family_id'],row.get('near_duplicate_group')]:
            if key:
                if key in groups and groups[key]!=row['split']:raise ValueError('Family/similarity cross-split leakage')
                groups[key]=row['split']
        if row['sha256'] in hashes:raise ValueError('Exact duplicate image in manifest')
        hashes[row['sha256']]=row['split']
    if set(r['split'] for r in rows)!=set(('train','val','test')):raise ValueError('Train, val and locked test families required')
    return rows


def read_payload(uri):
    if uri.startswith('gs://'):
        from google.cloud import storage
        bucket,name=uri[5:].split('/',1);blob=storage.Client().bucket(bucket).blob(name);blob.reload()
        if blob.size>8*1024*1024:raise ValueError('Oversized training image')
        return blob.download_as_bytes(if_generation_match=blob.generation)
    return Path(uri).read_bytes()


class VerifiedDataset:
    def __init__(self,rows,labels,image_size,augment=False):
        self.rows,self.labels,self.augment=rows,labels,augment
        from torchvision import transforms
        # No geometry-distorting crops/flips; preserve the complete inspection view.
        ops=[transforms.Resize((image_size,image_size))]
        if augment:ops.append(transforms.ColorJitter(brightness=.15,contrast=.15))
        self.transform=transforms.Compose(ops+[transforms.ToTensor(),transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
    def __len__(self):return len(self.rows)
    def __getitem__(self,index):
        import torch
        from PIL import Image
        row=self.rows[index];payload=read_payload(row['image_uri'])
        if hashlib.sha256(payload).hexdigest()!=row['sha256']:raise ValueError('Image checksum mismatch')
        with Image.open(io.BytesIO(payload)) as image:
            if image.width*image.height>16_000_000:raise ValueError('Oversized image dimensions')
            tensor=self.transform(image.convert('RGB'))
        targets=torch.full((len(self.labels),),-1.)
        for i,label in enumerate(self.labels):
            if label in row['observed_labels']:targets[i]=float(label in row['labels'])
        return tensor,targets


def class_balance(rows,labels):
    positive=Counter(l for r in rows for l in r['labels']);observed=Counter(l for r in rows for l in r['observed_labels'])
    return [min(10.,max(1.,(observed[l]-positive[l])/positive[l])) if positive[l] else 1. for l in labels]


def metrics(model,loader,labels):
    import torch
    tp=torch.zeros(len(labels));fp=tp.clone();fn=tp.clone();observed=tp.clone()
    model.eval()
    with torch.inference_mode():
        for images,target in loader:
            predicted=torch.sigmoid(model(images))>=.5;mask=target>=0;actual=target>0
            tp+=((predicted & actual)&mask).sum(0);fp+=((predicted & ~actual)&mask).sum(0)
            fn+=((~predicted & actual)&mask).sum(0);observed+=mask.sum(0)
    report={}
    for i,l in enumerate(labels):
        p=float(tp[i]/(tp[i]+fp[i])) if tp[i]+fp[i]>0 else None
        r=float(tp[i]/(tp[i]+fn[i])) if tp[i]+fn[i]>0 else None
        f=float(2*tp[i]/(2*tp[i]+fp[i]+fn[i])) if 2*tp[i]+fp[i]+fn[i]>0 else None
        report[l]={'precision':p,'recall':r,'f1':f,'tp':int(tp[i]),'fp':int(fp[i]),'fn':int(fn[i]),'observed':int(observed[i])}
    return report


def save_new_checkpoint(path,state):
    import torch
    temp=path.with_suffix('.partial')
    try:
        with temp.open('xb') as out:torch.save(state,out)
        os.link(temp,path) # Atomic create-only destination: never overwrite a checkpoint.
    finally:
        if temp.exists():temp.unlink()
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_model(config):
    import torch
    if config['architecture']=='convnext_tiny':
        from torchvision.models import convnext_tiny
        model=convnext_tiny(weights=None)
        model.classifier[2]=torch.nn.Linear(model.classifier[2].in_features,len(config['labels']))
        return model
    if config['architecture']!='synthetic_test_only':raise ValueError('Unsupported architecture')
    return torch.nn.Sequential(torch.nn.Conv2d(3,4,3,padding=1),torch.nn.ReLU(),torch.nn.AdaptiveAvgPool2d(1),torch.nn.Flatten(),torch.nn.Linear(4,len(config['labels'])))


def run_training(manifest,config,out,resume=None,registry=None):
    import torch
    from torch.utils.data import DataLoader
    rows=validate_manifest(manifest,config,registry)
    if config['mode']!='synthetic_smoke':
        raise ValueError('Commercial execution remains disabled until separately reviewed launch/budget integration')
    out=Path(out);out.mkdir(parents=True,exist_ok=bool(resume))
    random.seed(config['seed']);torch.manual_seed(config['seed']);torch.use_deterministic_algorithms(True)
    labels=config['labels'];signature=digest({k:v for k,v in config.items() if k!='epochs'})
    model=build_model(config)
    optimizer=torch.optim.SGD(model.parameters(),lr=config['learning_rate'],momentum=.9)
    generator=torch.Generator().manual_seed(config['seed']);start=0
    if resume:
        state=torch.load(resume,map_location='cpu',weights_only=True)
        if state['config_signature']!=signature or state['manifest_sha256']!=digest(manifest):raise ValueError('Resume provenance mismatch')
        model.load_state_dict(state['model'],strict=True);optimizer.load_state_dict(state['optimizer']);start=state['epoch']+1
        torch.set_rng_state(state['torch_rng']);generator.set_state(state['loader_rng']);random.setstate(state['python_rng'])
    train=[r for r in rows if r['split']=='train'];val=[r for r in rows if r['split']=='val'];test=[r for r in rows if r['split']=='test']
    loader=DataLoader(VerifiedDataset(train,labels,config['image_size'],True),batch_size=config['batch_size'],shuffle=True,generator=generator,num_workers=0)
    val_loader=DataLoader(VerifiedDataset(val,labels,config['image_size']),batch_size=config['batch_size'])
    pos_weight=torch.tensor(class_balance(train,labels));history=[]
    for epoch in range(start,config['epochs']):
        model.train();total=0.
        for images,target in loader:
            optimizer.zero_grad();mask=target>=0
            loss=torch.nn.functional.binary_cross_entropy_with_logits(model(images),target.clamp_min(0),pos_weight=pos_weight,reduction='none')
            loss=(loss*mask).sum()/mask.sum().clamp_min(1);loss.backward();optimizer.step();total+=float(loss.detach())
        record={'epoch':epoch,'synthetic_only':True,'loss_sum':total,'validation':metrics(model,val_loader,labels),'unsupported_training_classes':[l for l in labels if not any(l in r['labels'] for r in train)]}
        state={'model':model.state_dict(),'optimizer':optimizer.state_dict(),'epoch':epoch,'torch_rng':torch.get_rng_state(),'loader_rng':generator.get_state(),'python_rng':random.getstate(),'config_signature':signature,'manifest_sha256':digest(manifest),'synthetic_only':True,'production_eligible':False,'config':config}
        record['checkpoint_sha256']=save_new_checkpoint(out/f'epoch-{epoch:03d}.pt',state)
        with (out/'experiments.jsonl').open('a') as stream:stream.write(json.dumps(record)+'\n')
        history.append(record)
    result={'status':'SYNTHETIC_SMOKE_COMPLETED','trained_commercial_model':False,'production_eligible':False,
            'manifest_sha256':digest(manifest),'config_signature':signature,'epochs_executed':len(history),
            'locked_test_synthetic_only':metrics(model,DataLoader(VerifiedDataset(test,labels,config['image_size']),batch_size=config['batch_size']),labels)}
    with (out/f'result-through-{config["epochs"]:03d}.json').open('x') as stream:json.dump(result,stream,indent=2)
    return result


def synthetic_manifest(out,labels):
    from PIL import Image
    out=Path(out);out.mkdir(parents=True,exist_ok=False);records=[]
    for split in ('train','val','test'):
        for i in range(4):
            path=out/f'{split}-{i}.png';image=Image.new('RGB',(32,32),(40+i*40,70+('train','val','test').index(split)*10,90));image.save(path)
            records.append({'record_id':path.stem,'image_uri':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                            'split':split,'source_family_id':split+'-synthetic-family','synthetic':True,
                            'labels':[labels[i%len(labels)]],'observed_labels':labels})
    return {'records':records,'purpose':'SYNTHETIC_SOFTWARE_TEST_ONLY'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--synthetic-smoke-dir',type=Path,required=True)
    args=parser.parse_args();root=args.synthetic_smoke_dir;root.mkdir(parents=True,exist_ok=False)
    config={'mode':'synthetic_smoke','architecture':'synthetic_test_only','pretrained_checkpoint':None,'device':'cpu','labels':LABELS,
            'epochs':2,'seed':20261109,'image_size':32,'batch_size':2,'learning_rate':.01}
    manifest=synthetic_manifest(root/'images',LABELS)
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2));(root/'config.json').write_text(json.dumps(config,indent=2))
    print(json.dumps(run_training(manifest,config,root/'experiment'),indent=2))

if __name__=='__main__':main()
