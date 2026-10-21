"""Cloud-only baseline inventory and WRc checkpoint compatibility audit."""
import argparse, hashlib, json, tempfile, traceback
from pathlib import Path
from google.cloud import storage

PROJECT='joint-inspection-510310'; BUCKET='joint-inspection-510310-data'

def digest_blob(blob):
    h=hashlib.sha256()
    with blob.open('rb') as source:
        for chunk in iter(lambda:source.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def upload(bucket,name,data):
    bucket.blob(name).upload_from_string(json.dumps(data,indent=2),content_type='application/json')

def baseline_inventory(bucket):
    prefixes=['models/candidates/sewer-condition-v1/','models/candidates/sewer-condition-v2/',
              'models/external/wrc/inceptionresnetv2/v1/']
    rows=[]
    for prefix in prefixes:
        for blob in bucket.list_blobs(prefix=prefix):
            if blob.name.endswith(('.onnx','.data','.json')):
                rows.append({'gcs_uri':f'gs://{BUCKET}/{blob.name}','generation':int(blob.generation),
                             'bytes':int(blob.size or 0),'sha256':digest_blob(blob)})
    report={'status':'complete','artifact_count':len(rows),'artifacts':rows}
    upload(bucket,'audits/checkpoint4/baseline_inventory.json',report);print(json.dumps(report))

def wrc_compatibility(bucket):
    from wrc_feasibility import evaluate
    from wrc_adaptation import build_adapted_wrc_keras_model
    rights=json.loads(bucket.blob('provenance/wrc_rights.json').download_as_text())
    result={'rights':evaluate(rights),'compatible':False}
    with tempfile.TemporaryDirectory() as work:
        target=Path(work)/'weights.h5'; blob=bucket.blob('models/external/wrc/inceptionresnetv2/v1/weights.h5')
        blob.download_to_filename(str(target),if_generation_match=blob.generation)
        result['weights_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
        result['expected_sha256']=rights.get('original_weights_sha256')
        try:
            model=build_adapted_wrc_keras_model(target,False)
            result.update({'compatible':True,'model_name':model.name,'parameter_count':model.count_params(),
                           'backbone_layers':len(model.layers[1].layers) if hasattr(model.layers[1],'layers') else None})
        except Exception as exc:
            result.update({'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()[-4000:]})
    upload(bucket,'audits/checkpoint4/wrc_compatibility.json',result);print(json.dumps(result))

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=('baselines','wrc'),required=True);a=p.parse_args()
    bucket=storage.Client(project=PROJECT).bucket(BUCKET)
    baseline_inventory(bucket) if a.mode=='baselines' else wrc_compatibility(bucket)
if __name__=='__main__':main()
