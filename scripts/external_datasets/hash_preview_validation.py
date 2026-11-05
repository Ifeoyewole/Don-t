"""Recover validation perceptual hashes from checksum-verified GCS images."""
import hashlib,io,json
from concurrent.futures import ThreadPoolExecutor
from google.cloud import storage
from PIL import Image
client=storage.Client(project='joint-inspection-510310')
bucket=client.bucket('joint-inspection-510310-data')
uri='datasets/manifests/inspect-view-representation-sewerml-v4-r2-20261103/representation.jsonl'
rows=[json.loads(x) for x in bucket.blob(uri).download_as_text().splitlines()]
rows=[r for r in rows if r['dataset_name']=='Sewer-ML' and r['split']=='val']
def process(r):
 b,n=r['image_uri'][5:].split('/',1)
 payload=client.bucket(b).blob(n).download_as_bytes()
 if hashlib.sha256(payload).hexdigest()!=r['sha256']:raise ValueError('Image SHA mismatch')
 with Image.open(io.BytesIO(payload)) as im:
  w,h=im.size;p=list(im.convert('L').resize((9,8),Image.Resampling.LANCZOS).getdata())
 v=0
 for y in range(8):
  for x in range(8):v=(v<<1)|int(p[y*9+x+1]>p[y*9+x])
 return {'sha256':r['sha256'],'dhash':f'{v:016x}','width':w,'height':h,'hash_policy':'lanczos_9x8_right_gt_left_v1'}
with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(process,rows))
blob=bucket.blob('datasets/manifests/preview-validation-hashes-20261104/validation_hashes.json')
blob.upload_from_string(json.dumps({'records':results,'count':len(results)}),content_type='application/json',if_generation_match=0)
print(json.dumps({'status':'PASS','verified_images':len(results)}))
