"""Immutable, resumable, range-only Sewer-ML locked-test extraction inside GCP.

Never uses subprocess credential arguments, cross-origin credential redirects,
or full-archive fallback. Registry must supply complete authorized test ZIP URLs.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import os
from collections import Counter,defaultdict
from pathlib import Path
from zipfile import ZipFile
from bounded_archive import open_authorized_archive
from curate_staged import image_dhash, stable_unit, gcp_attestation, group_id, verify_disjoint, csv_records, TARGETS

PROJECT='joint-inspection-510310'
BUCKET='joint-inspection-510310-data'
BASE='datasets/sewer-ml/locked-test-v2'


def selection(rows, cap=2000, seed=20261015):
    """Deterministic multi-label rare-class rank. Final annotations only."""
    if not rows: raise ValueError('Empty official Test.csv')
    seen=set(); candidates=[]
    counts=Counter(c for r in rows for c in TARGETS if r.get(c) in ('1','1.0'))
    for r in rows:
        fn=r.get('Filename','').strip()
        if not fn or fn.casefold() in seen: continue
        seen.add(fn.casefold())
        active=[c for c in TARGETS if r.get(c) in ('1','1.0')]
        rarity=max((len(rows)/max(1,counts[c]) for c in active),default=1)
        score=stable_unit(seed,fn)/rarity
        candidates.append((score,fn,r))
    candidates.sort(key=lambda x:(x[0],x[1]))
    return {r['Filename']:r for _,_,r in candidates[:cap]}


def run():
    gcp_attestation(PROJECT)
    password=os.environ.get('SEWER_PASSWORD')
    if not password: raise RuntimeError('Secret Manager SEWER_PASSWORD environment binding required')
    user=os.environ.get('SEWER_USER','operator')
    from google.cloud import storage
    client=storage.Client(project=PROJECT)
    bucket=client.bucket(BUCKET)
    annotations=bucket.blob('datasets/sewer-ml/original-annotations/SewerML_Test.csv').download_as_text()
    rows=list(csv.DictReader(io.StringIO(annotations)))
    selected=selection(rows)
    # Require cross-partition, group-level provenance before locking the test.
    # Do not assume unique filenames imply independent inspection sequences.
    train=csv_records(bucket.blob('datasets/sewer-ml/original-annotations/SewerML_Train.csv').download_as_bytes())
    val=csv_records(bucket.blob('datasets/sewer-ml/original-annotations/SewerML_Val.csv').download_as_bytes())
    if any(group_id(row) is None for row in [*selected.values(), *train, *val]):
        raise RuntimeError('Official split metadata lacks verified inspection/video groups; do not seal leakage-uncertain test')
    verify_disjoint({'train':train,'official_validation':val,'locked_test':list(selected.values())})
    manifest_blob=bucket.blob(f'{BASE}/manifest.json')
    lock_blob=bucket.blob(f'{BASE}/integrity.json')
    if lock_blob.exists():
        raise RuntimeError('Locked test already sealed: refuses any mutation or reselection')
    archive_list=json.loads(bucket.blob('datasets/sewer-ml/source/test_archive_urls.json').download_as_text())
    from urllib.parse import urlsplit
    if not archive_list or any(urlsplit(x).hostname != 'sciencedata.dk' for x in archive_list):
        raise RuntimeError('Unapproved test archive host')
    if any('test' not in urlsplit(x).path.rsplit('/',1)[-1].lower() for x in archive_list):
        raise RuntimeError('Missing / invalid verified TEST archive URL inventory')
    prior=json.loads(manifest_blob.download_as_text()) if manifest_blob.exists() else {'rows':{}}
    saved=prior['rows']
    members={}
    for archive_url in archive_list:
        with open_authorized_archive(archive_url,user,password) as z:
            for info in z.infolist():
                name=Path(info.filename).name
                if name in selected:
                    if name in members:
                        raise ValueError(f'Ambiguous selected filename {name} in two archives')
                    members[name]={'url':archive_url,'member':info.filename,'archive':archive_url.rsplit('/',1)[-1]}
    missing=set(selected)-set(members)
    if missing: raise RuntimeError(f'{len(missing)} selected test images not located in archive index. Refuse incomplete lock.')
    by_url=defaultdict(list)
    for name in sorted(selected):
        if name in saved: continue
        by_url[members[name]['url']].append(name)
    for url,filenames in by_url.items():
        with open_authorized_archive(url,user,password) as z:
            for name in filenames:
                info=z.getinfo(members[name]['member'])
                if info.file_size > 32*1024*1024:
                    raise RuntimeError(f'Image too large: {name}')
                blob=z.read(info)  # CRC checked by ZipFile
                image_dhash(blob)  # rejects invalid image without creating fabricated inputs
                digest=hashlib.sha256(blob).hexdigest()
                output=f'{BASE}/images/{name}'
                dest=bucket.blob(output)
                if dest.exists():
                    dest.reload()
                    if (dest.metadata or {}).get('sha256') != digest:
                        raise RuntimeError(f'Stale/altered resumed object: {output}')
                else:
                    dest.metadata={'sha256':digest,'source_archive':members[name]['archive']}
                    dest.upload_from_string(blob,content_type='image/png' if name.lower().endswith('.png') else 'image/jpeg',if_generation_match=0)
                saved[name]={**selected[name], 'sha256':digest, 'source_archive':members[name]['archive'],
                            'source_member':members[name]['member'], 'GCS_URI':f'gs://{BUCKET}/{output}',
                            'split':'locked_test'}
                manifest_blob.upload_from_string(json.dumps({'rows':saved},sort_keys=True),content_type='application/json')
    if set(saved)!=set(selected): raise RuntimeError('Test set incomplete; no seal created')
    manifest=json.dumps({'rows':saved},sort_keys=True).encode()
    content_hash=hashlib.sha256(manifest).hexdigest()
    integrity={'sample_count':len(saved),'manifest_sha256':content_hash,
               'source_archives':sorted({r['source_archive'] for r in saved.values()}),
               'immutable':True,'production_approved':False}
    lock_blob.upload_from_string(json.dumps(integrity,sort_keys=True),content_type='application/json',if_generation_match=0)
    print(json.dumps(integrity,indent=2))
if __name__=='__main__':run()
