"""Explicitly reviewed, bounded cloud research worker; no job submission/retries."""
import argparse
import base64
import json
from pathlib import Path
import tempfile

from scripts.cloud.inspect_view_sam2_vertex import stage_verified, upload_create_only
from backend.app.core.cv.ai.unified_batch_manifest import validate_batch_manifest
from backend.app.core.cv.ai.research_sewer_runtime import cloud_service


def main():
    parser = argparse.ArgumentParser()
    for key in ('manifest-uri', 'manifest-sha', 'review-uri', 'review-sha', 'output-prefix'):
        parser.add_argument('--'+key, required=True)
    args = parser.parse_args()
    if not args.output_prefix.startswith('gs://joint-inspection-510310-data/models/inspect-view/research-results/'):
        raise ValueError('Unique private research output prefix required')
    from google.cloud import storage
    client = storage.Client(project='joint-inspection-510310')
    with tempfile.TemporaryDirectory(prefix='sewer-review-') as tmp:
        root = Path(tmp)
        stage_verified(client, args.manifest_uri, root/'manifest.json', args.manifest_sha, max_bytes=512*1024)
        stage_verified(client, args.review_uri, root/'review.json', args.review_sha, max_bytes=64*1024)
        manifest = validate_batch_manifest(json.loads((root/'manifest.json').read_text()))
        review = json.loads((root/'review.json').read_text())
        if review.get('manifest_sha256') != args.manifest_sha or not review.get('review_id'):
            raise ValueError('Documented manifest-bound research review required')
        if len(manifest['frames']) > 3:
            raise ValueError('This exploratory worker is bounded to three images')
        # No environment patch grants permission: operator must configure a
        # dedicated research worker and independently document usage permission.
        service = cloud_service()
        reports = []
        for index, frame in enumerate(manifest['frames']):
            image_path = root/f'{index}-original.bin'
            stage_verified(client, frame['image_uri'], image_path, frame['image_sha256'], max_bytes=8*1024*1024)
            result = service.infer(image_path.read_bytes(), rois=[frame['roi']],
                                   task=frame.get('task_type', 'JOINT_GEOMETRY'), geometry=frame.get('geometry'))
            target = args.output_prefix.rstrip('/')+'/'+str(index)
            upload_create_only(client, image_path, target+'/original.bin', 'application/octet-stream')
            overlay = root/f'{index}-overlay.png';overlay.write_bytes(base64.b64decode(result.pop('overlay_png_base64')))
            upload_create_only(client, overlay, target+'/overlay.png', 'image/png')
            for region in result['regions']:
                if 'mask_png_base64' in region:
                    mask = root/f'{index}-{region["region_id"]}-mask.png'
                    mask.write_bytes(base64.b64decode(region.pop('mask_png_base64')))
                    uri = target+f'/mask-{region["region_id"]}.png'
                    upload_create_only(client, mask, uri, 'image/png');region['mask_uri'] = uri
            result['manifest_sha256'] = args.manifest_sha
            result['review_id'] = review['review_id']
            result['initialization_failures'] = service.initialization_failures
            report = root/f'{index}-report.json';report.write_text(json.dumps(result, allow_nan=False, indent=2))
            upload_create_only(client, report, target+'/report.json', 'application/json')
            reports.append({'image_sha256':result['image_sha256'], 'report_uri':target+'/report.json',
                            'comparison':result['baseline_comparison']})
        summary = root/'summary.json';summary.write_text(json.dumps({'status':'RESEARCH_ONLY', 'frames':reports,
                                  'accuracy_improvement':None, 'commercial_eligible':False}, indent=2))
        upload_create_only(client, summary, args.output_prefix.rstrip('/')+'/summary.json', 'application/json')


if __name__ == '__main__':
    main()
