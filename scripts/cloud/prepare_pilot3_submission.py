"""Offline-only three-frame job builder. Never submits Vertex or spends credits."""
import hashlib,json,math,re,time
from backend.app.core.cv.ai.unified_batch_manifest import validate_batch_manifest,checked_gcs_uri

IMAGE_RE=re.compile(r'^europe-west2-docker\.pkg\.dev/joint-inspection-510310/joint-inspection-training/inspect-view-sam2-research@sha256:[a-f0-9]{64}$')


def build_job(manifest,*,manifest_uri,image_uri,output_prefix,review,budget,active_gpu_jobs=0):
    manifest=validate_batch_manifest(manifest)
    if len(manifest['frames'])!=3:raise ValueError('Pilot3 requires exactly three reviewed frames')
    payload=(json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n').encode();sha=hashlib.sha256(payload).hexdigest()
    if not isinstance(review,dict) or review.get('manifest_sha256')!=sha or not review.get('review_id'):
        raise ValueError('Documented manifest-bound human review required')
    if (not isinstance(budget,dict) or budget.get('manifest_sha256')!=sha or not budget.get('approval_id')
        or budget.get('scope')!='PILOT3_GPU_ONLY' or budget.get('currency') not in ('GBP','USD')
        or type(budget.get('spending_cap')) not in (int,float) or not math.isfinite(budget['spending_cap'])
        or budget['spending_cap']<=0 or type(budget.get('expires_unix')) is not int or budget['expires_unix']<int(time.time())):
        raise ValueError('Unexpired explicit pilot3 GPU spending scope required')
    if active_gpu_jobs!=0:raise ValueError('GPU concurrency must remain one')
    if not IMAGE_RE.fullmatch(image_uri):raise ValueError('Immutable research container digest required')
    checked_gcs_uri(manifest_uri);checked_gcs_uri(output_prefix+'/marker.json')
    if not output_prefix.startswith('gs://joint-inspection-510310-data/models/inspect-view/research-results/'):
        raise ValueError('Unique private research output prefix required')
    spec={'serviceAccount':'joint-inspection-trainer@joint-inspection-510310.iam.gserviceaccount.com',
      'scheduling':{'strategy':'SPOT','timeout':'7200s','disableRetries':True,'restartJobOnWorkerRestart':False},
      'workerPoolSpecs':[{'machineSpec':{'machineType':'n1-standard-4','acceleratorType':'NVIDIA_TESLA_T4','acceleratorCount':1},
        'replicaCount':1,'diskSpec':{'bootDiskType':'pd-ssd','bootDiskSizeGb':100},
        'containerSpec':{'imageUri':image_uri,'command':['python','-m','scripts.cloud.inspect_view_sam2_batch_vertex'],
          'args':['--project=joint-inspection-510310','--manifest-uri='+manifest_uri,'--manifest-sha='+sha,
            '--inspect-uri=gs://joint-inspection-510310-data/models/inspect-view/research-candidates/repr-convnext-masked-r5-20261104/best.pt',
            '--inspect-sha=659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7',
            '--sam-uri=gs://joint-inspection-510310-data/models/sam2/publisher-quarantine/ecc6e8ce-4fb5-464a-a70d-20283a0e98c8/sam2.1_hiera_tiny.pt',
            '--sam-sha=7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69',
            '--output-prefix='+output_prefix,'--limit=3']}}]}
    return {'job_spec':spec,'manifest_bytes':payload,'manifest_sha256':sha,'submit_executed':False,
            'gemini_permission':'SEPARATE_REVIEWED_RECEIPT_SCOPE_REQUIRED'}
