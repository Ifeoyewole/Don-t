"""Cloud-only, checksum-pinned acquisition. Does not grant commercial rights.

Do not execute until noncommercial usage permission and remaining research
budget are established. No paid job is submitted by this script.
"""
import argparse
import hashlib
import os
import tempfile
from pathlib import Path

from backend.app.core.cv.ai.research_sewer_detector import CHECKPOINT_SHA256, MODEL_ID, REVISION, SOURCE
from scripts.cloud.inspect_view_sam2_vertex import upload_create_only


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--permission-record-id', required=True)
    args = parser.parse_args()
    if os.name == 'nt' or os.getenv('JOINTINSPECT_CLOUD_RESEARCH_WORKER') != 'true':
        raise ValueError('Dedicated cloud worker required')
    if os.getenv('JOINTINSPECT_ISWDS_NONCOMMERCIAL_RESEARCH_ALLOWED') != 'true' or not args.permission_record_id.strip():
        raise ValueError('Documented permitted noncommercial research scope required')
    import requests
    from google.cloud import storage
    with tempfile.TemporaryDirectory(prefix='iswds-stage-') as temp:
        path = Path(temp)/MODEL_ID; hasher = hashlib.sha256(); size = 0
        with requests.get(SOURCE+'/resolve/'+REVISION+'/'+MODEL_ID, stream=True, timeout=(15, 60)) as response:
            response.raise_for_status()
            with path.open('wb') as output:
                for block in response.iter_content(1024*1024):
                    size += len(block)
                    if size > 103295200:
                        raise ValueError('Publisher file size exceeded')
                    hasher.update(block);output.write(block)
        if size != 103295200 or hasher.hexdigest() != CHECKPOINT_SHA256:
            raise ValueError('Official checkpoint checksum mismatch')
        client = storage.Client(project='joint-inspection-510310')
        prefix = 'gs://joint-inspection-510310-data/models/external/iswds/research-quarantine/'+REVISION
        upload_create_only(client, path, prefix+'/'+MODEL_ID, 'application/octet-stream')
        import json
        record = Path(temp)/'provenance.json'
        record.write_text(json.dumps({'source':SOURCE,'revision':REVISION,'sha256':CHECKPOINT_SHA256,
                          'permission_record_id':args.permission_record_id,'license':'fair-noncommercial-research-license',
                          'commercial_eligible':False,'production_eligible':False}, indent=2))
        upload_create_only(client, record, prefix+'/provenance.json', 'application/json')
        print('Research quarantine checkpoint staged; commercial use remains prohibited.')


if __name__ == '__main__':
    main()
