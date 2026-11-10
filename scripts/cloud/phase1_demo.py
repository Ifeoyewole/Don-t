"""One bounded CPU Phase 1 demonstration on existing GCS CCTV frames.

Does not submit jobs, acquire models or alter production. The caller supplies a
SHA-pinned plan. All weights/inference stay in the ephemeral GCP worker. The
existing authenticated API is exercised in-process by FastAPI TestClient.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import resource
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--plan-sha256', required=True)
    args = parser.parse_args()
    plan_bytes = Path(args.plan).read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != args.plan_sha256:
        raise ValueError('Demonstration plan SHA mismatch')
    plan = json.loads(plan_bytes)
    frames = plan['frames']
    if not 1 <= len(frames) <= 3 or plan.get('automatic_retries') != 0 or plan.get('gpu_count') != 0:
        raise ValueError('One bounded CPU run, up to three frames, no retries')
    if (plan.get('total_cycle_cap_usd') != 100 or not plan.get('usage_authorization')
            or not 0 < plan.get('reservation_usd', 0) <= 5):
        raise ValueError('Documented existing research authorization required')
    prefix = plan['output_prefix'].rstrip('/')
    if not prefix.startswith('gs://joint-inspection-510310-data/models/inspect-view/research-results/phase1/'):
        raise ValueError('Unique private research output prefix required')
    # These settings apply ONLY to this explicitly authorized research process.
    os.environ.update(plan['worker_environment'])
    os.environ['JOINTINSPECT_PREVIEW_TOKEN'] = __import__('secrets').token_urlsafe(32)
    os.environ['OMP_NUM_THREADS'] = '2'
    os.environ['MKL_NUM_THREADS'] = '2'
    from google.cloud import storage
    from fastapi.testclient import TestClient
    import torch
    import cv2
    from backend.app.main import app
    from scripts.cloud.inspect_view_sam2_vertex import stage_verified, upload_create_only
    client = storage.Client(project='joint-inspection-510310')
    torch.set_num_threads(2)
    cv2.setNumThreads(2)
    started = time.perf_counter()
    summary = {'status': 'STARTED', 'frames': [], 'plan_sha256': args.plan_sha256,
               'gpu_count': 0, 'training': False, 'actual_billed_cost_usd': None,
               'accuracy_precision_recall_f1': None, 'production_changed': False}
    with tempfile.TemporaryDirectory(prefix='phase1-demo-') as tmp:
        root = Path(tmp)

        def save(name, data, kind='application/json'):
            path = root/name.replace('/', '-')
            path.write_bytes(data if isinstance(data, bytes) else json.dumps(data, indent=2, allow_nan=False).encode())
            upload_create_only(client, path, prefix+'/'+name, kind)

        save('execution_plan.json', plan)
        try:
            with TestClient(app) as api:
                for frame in frames:
                    frame_start = time.perf_counter()
                    original = root/'input.bin'
                    stage_verified(client, frame['uri'], original, frame['sha256'], max_bytes=8*1024*1024)
                    payload = original.read_bytes()
                    options = {'rois': frame.get('rois', []), 'task': frame['task'],
                               'geometry': frame.get('geometry'),
                               'context': {'frame_id': str(frame['frame']), 'source_uri': frame['uri'],
                                           'source_review_status': 'UNVERIFIED_SOURCE_LABEL',
                                           'usage': 'USER_AUTHORIZED_EXPLORATORY_PROTOTYPE_NOT_ENGINEERING_ACCEPTANCE'}}
                    response = api.post('/api/v1/cv/sewer-research/unified',
                        headers={'Authorization': 'Bearer '+os.environ['JOINTINSPECT_PREVIEW_TOKEN']},
                        files={'file': ('frame.jpg', payload, 'image/jpeg')},
                        data={'options': json.dumps(options)})
                    if response.status_code != 200:
                        raise RuntimeError('Unified API returned '+str(response.status_code))
                    report = response.json()
                    name = 'frame-'+str(frame['frame'])
                    save(name+'/original.jpg', payload, 'image/jpeg')
                    save(name+'/overlay.png', base64.b64decode(report.pop('overlay_png_base64')), 'image/png')
                    for region in report['regions']:
                        mask = region.pop('mask_png_base64', None)
                        if mask:
                            mask_name = name+f'/mask-{region["region_id"]}.png'
                            save(mask_name, base64.b64decode(mask), 'image/png')
                            region['mask_uri'] = prefix+'/'+mask_name
                    report['cloud_context'] = {'input_uri': frame['uri'], 'plan_sha256': args.plan_sha256,
                        'source_commit': plan['source_commit'], 'container_digest': plan['container_digest'],
                        'inference_location': 'GCP_CLOUD_BUILD_CPU', 'model_weights_on_developer_pc': False}
                    save(name+'/unified-report.json', report)
                    row = {'frame': frame['frame'], 'report_uri': prefix+'/'+name+'/unified-report.json',
                           'functional_path_complete': report['phase1']['functional_path_complete'],
                           'gemini_status': report['gemini']['status'],
                           'actual_masks': report['baseline_comparison']['actual_mask_count'],
                           'joint_measurement': report['joint_measurement'],
                           'latency_seconds': report['latency_seconds'],
                           'elapsed_including_initialization': round(time.perf_counter()-frame_start, 3)}
                    summary['frames'].append(row)
                    print(json.dumps(row), flush=True)
            summary['status'] = ('INTEGRATED_REAL_PATH_COMPLETED_NOT_ENGINEERING_ACCEPTANCE'
                                 if all(f['functional_path_complete'] for f in summary['frames'])
                                 else 'PARTIAL_COMPONENT_FAILURE_NO_AUTOMATIC_RETRY')
        except Exception as exc:
            summary['status'] = 'FAILED_NO_AUTOMATIC_RETRY'
            summary['failure_type'] = type(exc).__name__
            # Avoid accidental credentials/provider body exposure in diagnostics.
            print('Phase 1 execution failed; sanitized diagnostics preserved.', flush=True)
        finally:
            summary['elapsed_seconds'] = round(time.perf_counter()-started, 3)
            summary['peak_process_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            save('summary.json', summary)
            print(json.dumps(summary), flush=True)
    if summary['status'] != 'INTEGRATED_REAL_PATH_COMPLETED_NOT_ENGINEERING_ACCEPTANCE':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
