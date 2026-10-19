"""Cloud-only incremental Sewer-ML curation (20K -> 30K -> up to 100K TOTAL).

Source CSVs and archive list must be supplied from authorized metadata. This script
never transfers images through a developer workstation and only runs --execute on
GCP. Range-supported ZIP sources are read without downloading entire archives.
Unsupported Range => fail closed; provision a bounded cloud-disk extraction job.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
import os
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin
import requests
from PIL import Image
from bounded_archive import open_authorized_archive

TARGETS = ('FS','IS','RB','DE','RO','AF','BE','FO','ND')
GROUP_KEYS = ('video_id', 'VideoID', 'VideoId', 'inspection_id', 'InspectionID', 'SequenceID', 'source_group')
STAGES = (20000, 30000, 100000)
MAX_IMAGE_BYTES = 32 * 1024 * 1024


def csv_records(content: bytes):
    return list(csv.DictReader(io.StringIO(content.decode('utf-8-sig'))))


def labels(row):
    return [c for c in TARGETS if row.get(c) in ('1','1.0')]


def group_id(row):
    for key in GROUP_KEYS:
        if row.get(key):
            return str(row[key]).strip()
    return None


def stable_unit(seed: int, name: str) -> float:
    number=int.from_bytes(hashlib.sha256(f'{seed}:{name}'.encode()).digest()[:8],'big')
    return (number+1)/(2**64+1)


def staged_select(rows, target, *, seed=20261015, group_cap=300, reserve=0, allow_unverified_split=False):
    """Deterministic nested ranking using inverse-frequency rarity weights.

    Every smaller stage is a subset of larger stages if metadata is unchanged.
    Unchanged source groups can have at most group_cap selected examples.
    The selection is not a substitute for downstream image-hash deduplication.
    """
    if target not in STAGES:
        raise ValueError('Stage must be 20000, 30000 or 100000 TOTAL')
    seen=set(); valid=[]
    for row in rows:
        fn=str(row.get('Filename','')).strip()
        if not fn or fn.casefold() in seen:
            continue
        gid=group_id(row)
        if not gid:
            if allow_unverified_split:
                gid = 'official_train_unsegmented'
                row['source_group'] = gid
            else:
                raise ValueError(f'Missing sequence/group ID for {fn}; group-safe curation cannot be established')
        seen.add(fn.casefold())
        valid.append(row)
    if len(valid)<target:
        raise ValueError(f'Only {len(valid)} unique metadata rows; target is {target}')
    selection_limit=min(len(valid),target+max(0,reserve))
    counts=Counter(c for row in valid for c in labels(row))
    rarity={c:(len(valid)/max(1,counts[c]))**0.65 for c in TARGETS}
    scores=[]
    for row in valid:
        active=labels(row)
        weight=max([rarity[c] for c in active], default=1.0)
        score=-math.log(stable_unit(seed,row['Filename']))/weight
        scores.append((score,row['Filename'],row))
    scores.sort(key=lambda t:(t[0],t[1]))
    selected=[]; groups=Counter()
    for _,_,row in scores:
        gid=group_id(row)
        if not allow_unverified_split and groups[gid]>=group_cap: continue
        selected.append(row)
        groups[gid]+=1
        if len(selected)==selection_limit: return selected
    raise ValueError(f'Group cap limits selection to {len(selected)} of {target}; revise group cap based on source statistics')


def partition_validation(rows, seed=20261015, allow_unverified_split=False):
    """Disjoint validation groups: early stopping, thresholds, development report.
    Official TEST annotations are never accepted into this function.
    """
    splits={'early_stop':[],'threshold_tune':[],'dev_report':[]}
    for row in rows:
        gid=group_id(row)
        if gid is None or gid in ('official_val_unsegmented', 'official_train_unsegmented'):
            if allow_unverified_split:
                gid = 'official_val_unsegmented'
                row['source_group'] = gid
                h = stable_unit(seed, row['Filename'])
            else:
                raise ValueError('Validation group identifier missing')
        else:
            h=stable_unit(seed,gid)
        name='early_stop' if h<0.50 else 'threshold_tune' if h<0.75 else 'dev_report'
        splits[name].append(row)
    if any(not v for v in splits.values()):
        raise ValueError('One of the validation partitions is empty')
    verify_disjoint(splits)
    return splits


def verify_disjoint(splits):
    seen_filenames={}; seen_groups={}
    for split,rows in splits.items():
        for row in rows:
            name=row['Filename'].casefold()
            gid=group_id(row)
            if name in seen_filenames and seen_filenames[name]!=split:
                raise ValueError(f'Split leakage: {name} appears in {seen_filenames[name]} and {split}')
            seen_filenames[name]=split
            if gid and gid not in ('official_train_unsegmented', 'official_val_unsegmented'):
                if gid in seen_groups and seen_groups[gid]!=split:
                    raise ValueError(f'Split leakage: {gid} appears in {seen_groups[gid]} and {split}')
                seen_groups[gid]=split
    return {'filenames':len(seen_filenames),'groups':len(seen_groups)}


def image_dhash(data: bytes) -> int:
    with Image.open(io.BytesIO(data)) as im:
        im.verify()
    with Image.open(io.BytesIO(data)) as im:
        im=im.convert('L').resize((9,8))
        px=im.tobytes()
    value=0
    for y in range(8):
        for x in range(8):
            value=(value<<1)|int(px[y*9+x]>px[y*9+x+1])
    return value


class NearDuplicateIndex:
    """64-bit dHash 4x16-bit band LSH; <=3 bit differences share a band."""
    def __init__(self):
        self.hashes={}
        self.bands=defaultdict(set)
        self.digests=set()

    def add(self, filename, digest, dhash, distance=3):
        if digest in self.digests: return False, 'exact_duplicate'
        candidates=set()
        for idx in range(4):
            band=(dhash>>(16*idx))&0xffff
            candidates |= self.bands[(idx,band)]
        if any((self.hashes[key]^dhash).bit_count()<=distance for key in candidates):
            return False,'near_duplicate'
        self.digests.add(digest)
        self.hashes[filename]=dhash
        for idx in range(4):
            self.bands[(idx,(dhash>>(16*idx))&0xffff)].add(filename)
        return True,'unique'


def source_archive_index(urls, user, password):
    """ZIP central-directory-only index. Never fetches full archives."""
    result={}
    for url in urls:
        archive=url.rsplit('/',1)[-1]
        with open_authorized_archive(url,user,password) as z:
            for member in z.infolist():
                if member.is_dir(): continue
                filename=Path(member.filename).name
                if not filename.lower().endswith(('.jpg','.jpeg','.png')): continue
                if filename in result:
                    raise ValueError(f'Ambiguous source archive filename {filename}: {archive}')
                result[filename]={'archive':archive,'member':member.filename,'url':url,
                                  'size':member.file_size,'crc':member.CRC}
    return result


def gcp_attestation(expected_project):
    for url in ('http://metadata.google.internal/computeMetadata/v1/project/project-id',
                'http://169.254.169.254/computeMetadata/v1/project/project-id'):
        try:
            r = requests.get(url, headers={'Metadata-Flavor': 'Google'}, timeout=2)
            if r.status_code == 200 and r.text.strip() == expected_project:
                return
        except requests.RequestException:
            pass
    if os.environ.get('PROJECT_ID') == expected_project or os.environ.get('GCP_PROJECT') == expected_project:
        if os.name != 'nt' and (os.path.exists('/sys/hypervisor') or os.path.exists('/dev/kvm') or os.environ.get('BUILD_ID') or os.environ.get('CLOUD_RUN_JOB')):
            return
    raise RuntimeError('Cloud-only safeguard: execute this job inside approved GCP, not a workstation')


def export_splits(bucket, output_prefix: str, train_records: list[dict], *,
                  val_manifest: str = 'datasets/sewer-ml/splits/validation/curated_val.csv',
                  val_image_prefix: str = 'datasets/sewer-ml/curated/images',
                  allow_unverified_split: bool = False) -> dict:
    """Generate and write standardized split CSV files for train and validation partitions."""
    fieldnames = ['Filename', 'sha256', 'GCS_URI', 'source_group'] + list(TARGETS)
    splits_dir = f"{output_prefix.rstrip('/')}/splits"
    
    # 1. train.csv
    train_out = io.StringIO()
    writer = csv.DictWriter(train_out, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    for r in train_records:
        row_dict = {k: r.get(k, '') for k in fieldnames}
        if not row_dict.get('source_group'):
            row_dict['source_group'] = 'official_train_unsegmented' if allow_unverified_split else group_id(r)
        writer.writerow(row_dict)
    bucket.blob(f"{splits_dir}/train.csv").upload_from_string(train_out.getvalue(), content_type='text/csv')
    
    # 2. Validation records
    val_blob = bucket.blob(val_manifest)
    val_records = []
    if val_blob.exists():
        raw_val = csv_records(val_blob.download_as_bytes())
        for r in raw_val:
            fn = r['Filename']
            img_blob = bucket.blob(f"{val_image_prefix.rstrip('/')}/{fn}")
            if not img_blob.exists():
                continue
            sha = (img_blob.metadata or {}).get('sha256')
            if not sha or len(sha) != 64:
                sha = hashlib.sha256(img_blob.download_as_bytes()).hexdigest()
                img_blob.metadata = {**(img_blob.metadata or {}), 'sha256': sha}
                try:
                    img_blob.patch()
                except Exception:
                    pass
            rec = {
                **r,
                'sha256': sha,
                'GCS_URI': f"gs://{bucket.name}/{img_blob.name}",
                'source_group': 'official_val_unsegmented' if allow_unverified_split else (group_id(r) or 'official_val'),
                'split': 'val'
            }
            val_records.append(rec)
    
    if not val_records:
        raise RuntimeError("No valid validation images found in approved validation manifest")
    
    val_splits = partition_validation(val_records, allow_unverified_split=allow_unverified_split)
    verify_disjoint({'train': train_records, **val_splits})
    
    for split_name in ('early_stop', 'threshold_tune', 'dev_report'):
        s_out = io.StringIO()
        s_writer = csv.DictWriter(s_out, fieldnames=fieldnames, extrasaction='ignore')
        s_writer.writeheader()
        for r in val_splits[split_name]:
            r_out = {k: r.get(k, '') for k in fieldnames}
            s_writer.writerow(r_out)
        bucket.blob(f"{splits_dir}/{split_name}.csv").upload_from_string(s_out.getvalue(), content_type='text/csv')
        
    return {
        'train': len(train_records),
        'early_stop': len(val_splits['early_stop']),
        'threshold_tune': len(val_splits['threshold_tune']),
        'dev_report': len(val_splits['dev_report']),
    }


def run(args):
    if args.stage not in STAGES: raise ValueError('Unsupported target')
    if args.execute: gcp_attestation(args.project)
    from google.cloud import storage
    client=storage.Client(project=args.project)
    bucket=client.bucket(args.bucket)
    data=bucket.blob(args.train_manifest).download_as_bytes()
    train_rows=csv_records(data)
    selected=staged_select(train_rows,args.stage,group_cap=args.group_cap,
                           reserve=max(2000,args.stage//5) if args.execute else 0,
                           allow_unverified_split=args.allow_unverified_split)
    if not args.execute:
        stats=Counter(c for row in selected for c in labels(row))
        print(json.dumps({'stage_target_total':args.stage,'metadata_selected':len(selected),
                          'class_positive_counts':stats,'executed':False},indent=2))
        return
    user=os.environ.get('SEWER_USER','operator')
    password=os.environ.get('SEWER_PASSWORD')
    if not password: raise RuntimeError('Missing SEWER_PASSWORD from GCP Secret Manager')
    url_list=json.loads(bucket.blob(args.archive_list).download_as_text())
    # URL list references only authorized training archives, not test/validation.
    from urllib.parse import urlsplit
    if any(urlsplit(u).hostname != 'sciencedata.dk' for u in url_list):
        raise ValueError('Unauthorized training archive source host')
    if any('train' not in urlsplit(u).path.rsplit('/',1)[-1].lower() for u in url_list):
        raise ValueError('Training archive list contains non-training ZIP')
    index_blob=bucket.blob(args.archive_index)
    if index_blob.exists():
        archive_index=json.loads(index_blob.download_as_text())
    else:
        archive_index=source_archive_index(url_list,user,password)
        index_blob.upload_from_string(json.dumps(archive_index,sort_keys=True),content_type='application/json')
    root=f'{args.output_prefix.rstrip("/")}/images'
    manifest_blob=bucket.blob(f'{args.output_prefix.rstrip("/")}/manifest.json')
    prior=json.loads(manifest_blob.download_as_text()) if manifest_blob.exists() else {'records':[]}
    prior_records={x['Filename']:x for x in prior['records']}
    hashes=NearDuplicateIndex()
    for row in prior_records.values():
        hashes.add(row['Filename'],row['sha256'],int(row['dhash'],16))
    byarchive=defaultdict(list)
    for row in selected:
        fn=row['Filename']
        if fn in prior_records: continue
        loc=archive_index.get(fn)
        if loc is None: raise RuntimeError(f'Expected training image {fn} not found in approved archive index')
        byarchive[loc['url']].append((row,loc))
    added=0; duplicates=[]
    for url,entries in byarchive.items():
        if len(prior_records)>=args.stage: break
        with open_authorized_archive(url,user,password) as z:
            for row,loc in entries:
                if len(prior_records)>=args.stage: break
                fn=row['Filename']
                member=z.getinfo(loc['member'])
                if member.file_size>MAX_IMAGE_BYTES: raise RuntimeError(f'Image exceeds cap: {fn}')
                content=z.read(member)  # ZIP decompression + CRC verification
                digest=hashlib.sha256(content).hexdigest()
                dhash=image_dhash(content)
                accepted,reason=hashes.add(fn,digest,dhash)
                if not accepted:
                    duplicates.append({'Filename':fn,'reason':reason})
                    continue
                object_name=f'{root}/{fn}'
                target=bucket.blob(object_name)
                target.metadata={'sha256':digest,'source_archive':loc['archive']}
                # A prior worker may have completed upload but expired before
                # writing the next manifest checkpoint. Verify and resume.
                if target.exists():
                    target.reload()
                    if (target.metadata or {}).get('sha256') != digest:
                        raise RuntimeError(f'Existing resumed object digest mismatch: {object_name}')
                else:
                    target.upload_from_string(content,content_type='image/png' if fn.lower().endswith('.png') else 'image/jpeg',if_generation_match=0)
                prior_records[fn]={**row,'sha256':digest,'dhash':f'{dhash:016x}',
                                   'source_archive':loc['archive'],'source_member':loc['member'],
                                   'source_crc':loc['crc'],'GCS_URI':f'gs://{args.bucket}/{object_name}',
                                   'generation':target.generation,'split':'train'}
                added+=1
                # Batch checkpoint minimizes GCS writes. Object-level generation
                # preconditions make restart after an interrupted batch safe.
                if added % 200 == 0:
                    manifest_blob.upload_from_string(json.dumps({'records':list(prior_records.values())},sort_keys=True))
    manifest_blob.upload_from_string(json.dumps({'records':list(prior_records.values())},sort_keys=True))
    if len(prior_records)<args.stage:
        # Cannot claim target achieved merely because candidate manifest had N entries.
        raise RuntimeError(f'Target not met: {len(prior_records)} unique images after dedup; '
                           f'{len(duplicates)} duplicates. Re-run with expanded candidate oversampling.')
    splits_summary = export_splits(bucket, args.output_prefix, list(prior_records.values()),
                                   val_manifest=args.val_manifest,
                                   val_image_prefix=args.val_image_prefix,
                                   allow_unverified_split=args.allow_unverified_split)
    print(json.dumps({'executed':True,'stage_target_total':args.stage,
                      'verified_unique_records':len(prior_records),'added':added,
                      'duplicates':len(duplicates),'splits':splits_summary},indent=2))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--project',default='joint-inspection-510310')
    p.add_argument('--bucket',default='joint-inspection-510310-data')
    p.add_argument('--stage',type=int,choices=STAGES,required=True)
    p.add_argument('--train-manifest',default='datasets/sewer-ml/original-annotations/SewerML_Train.csv')
    p.add_argument('--val-manifest',default='datasets/sewer-ml/splits/validation/curated_val.csv')
    p.add_argument('--val-image-prefix',default='datasets/sewer-ml/curated/images')
    p.add_argument('--archive-list',default='datasets/sewer-ml/source/train_archive_urls.json')
    p.add_argument('--archive-index',default='datasets/sewer-ml/source/train_archive_index.json')
    p.add_argument('--output-prefix',default='datasets/sewer-ml/curated-v3')
    p.add_argument('--group-cap',type=int,default=300)
    p.add_argument('--allow-unverified-split',action='store_true',
                   help='Explicitly allow unsegmented partition without sequence IDs; certifies research-only')
    p.add_argument('--execute',action='store_true')
    run(p.parse_args())
if __name__=='__main__':main()
