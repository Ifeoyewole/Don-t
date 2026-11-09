"""CPU-only, generation-pinned audit of quarantined Unified Vision datasets.

Writes inventories to a NEW local directory. No GPU, Gemini, training, deletion,
annotation approval, production mutation or automatic commercial clearance.
Uploads are a separate explicit operator action.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import re
from typing import Any

from scripts.cloud.create_unified_review_contact_sheets import (
    BUCKET, SOURCE_PREFIXES, expected_archive_suffix, tentative_family,
)

BASELINES = [
    'datasets/sewer-ml/curated-v4/20k/manifest.json',
    'datasets/quarantine/sruibo-sewer-pipe-defects/7fafcbe676aad60f38d8fe39cde93cf599f8362e/dataset_registry.json',
    'datasets/quarantine/roboflow/hatim-husaini/pipe-defect-detection/v7/dataset_registry.json',
    'datasets/quarantine/roboflow/esha-gupta-jfldf/pvc-pipe-defect/v2/dataset_registry.json',
]
MAPPINGS = {
    'Crack': 'SURFACE_DAMAGE', 'Utility intrusion': 'PROTRUDING_LATERAL',
    'Joint offset': 'JOINT_DISPLACEMENT', 'Offset joint': 'JOINT_DISPLACEMENT',
    'Debris': 'BLOCKAGE', 'Obstacle': 'OBSTACLE', 'Buckling': 'DEFORMATION',
    'Hole': 'BROKEN_PIPE', 'Broken pipe': 'BROKEN_PIPE', 'Roots': 'OBSTACLE',
    'Leak': 'INFILTRATION',
}
MAX_BYTES = 8 * 1024 * 1024


def resolve_name(registry: dict, path: str, prefix: str, names: list[str]) -> str | None:
    suffix = expected_archive_suffix(registry, path)
    matches = [n for n in names if n.startswith(prefix) and (n == prefix + suffix or n.endswith('/' + suffix))]
    return matches[0] if len(matches) == 1 else None


def image_evidence(data: bytes) -> tuple[dict, Any]:
    import cv2
    import numpy as np
    from PIL import Image
    with Image.open(BytesIO(data)) as image:
        w, h = image.size
        if not (24 <= w and 24 <= h and w * h <= 16_000_000):
            raise ValueError('Image dimensions outside audit limits')
        image.verify()
    with Image.open(BytesIO(data)) as opened:
        image = opened.convert('RGB')
        image.load()
    small = image.convert('L').resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(small.getdata())
    dhash = 0
    for row in range(8):
        for col in range(8):
            dhash = (dhash << 1) | int(pixels[row * 9 + col + 1] > pixels[row * 9 + col])
    gray = np.array(image.convert('L').resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float32)
    low = cv2.dct(gray)[:8, :8].flatten()
    median = float(np.median(low[1:]))
    bits = low > median
    bits[0] = False  # Exclude brightness/DC from similarity comparisons.
    phash = 0
    for bit in bits:
        phash = (phash << 1) | int(bit)
    thumb = image.copy()
    thumb.thumbnail((250, 172))
    return {'width': w, 'height': h, 'dhash': f'{dhash:016x}', 'phash': f'{phash:016x}'}, thumb


def check_yolo(text: str, classes: list[str]) -> dict:
    """Validate actual boxes or polygons; this never approves defect identity."""
    labels, boxes, polygons, errors = [], 0, 0, []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            fields = line.split(); class_id = int(fields[0])
            if class_id < 0 or class_id >= len(classes): raise ValueError()
            coords = list(map(float, fields[1:]))
            if not all(math.isfinite(v) for v in coords): raise ValueError()
            if len(coords) == 4:
                x, y, w, h = coords
                if (not (0 < w <= 1 and 0 < h <= 1)
                    or x - w/2 < -1e-5 or y - h/2 < -1e-5
                    or x + w/2 > 1+1e-5 or y + h/2 > 1+1e-5): raise ValueError()
                boxes += 1
            elif len(coords) >= 6 and len(coords) % 2 == 0:
                if any(v < 0 or v > 1 for v in coords): raise ValueError()
                points = list(zip(coords[::2], coords[1::2]))
                if len(set(points)) < 3: raise ValueError()
                area2 = sum(x*y2-x2*y for (x,y),(x2,y2) in zip(points,points[1:]+points[:1]))
                if abs(area2) <= 1e-10: raise ValueError()
                polygons += 1
            else: raise ValueError()
            labels.append(classes[class_id])
        except (ValueError, TypeError, IndexError): errors.append(number)
    kinds = (["YOLO_BOUNDING_BOX"] if boxes else []) + (["YOLO_POLYGON"] if polygons else [])
    return {'annotation_structure_valid': not errors, 'annotation_error_lines': errors,
            'annotation_box_count': boxes, 'annotation_polygon_count': polygons,
            'observed_annotation_format': '+'.join(kinds) if kinds else 'EMPTY' if not errors else 'INVALID',
            'decoded_annotation_labels': sorted(set(labels))}


def cached_annotation_format(old: dict) -> dict:
    """Preserve polygon evidence on later resumes; infer boxes only for v1 cache."""
    return {'annotation_polygon_count': old.get('annotation_polygon_count', 0),
            'observed_annotation_format': old.get('observed_annotation_format') or
                ('YOLO_BOUNDING_BOX' if old['annotation_box_count'] else 'EMPTY')}


def duplicate_pairs(rows: list[dict]) -> list[dict]:
    pairs = []
    for i, left in enumerate(rows):
        if left.get('integrity_status') != 'VERIFIED':
            continue
        for right in rows[i + 1:]:
            if right.get('integrity_status') != 'VERIFIED':
                continue
            exact = left['actual_sha256'] == right['actual_sha256']
            dh = (int(left['dhash'], 16) ^ int(right['dhash'], 16)).bit_count()
            ph = (int(left['phash'], 16) ^ int(right['phash'], 16)).bit_count()
            if exact or dh <= 6 or ph <= 8:
                pairs.append({'left_id': left['record_id'], 'right_id': right['record_id'],
                    'status': 'SHA256_EXACT' if exact else 'NEAR_DUPLICATE_CANDIDATE_UNVERIFIED',
                    'dhash_distance': dh, 'phash_distance': ph,
                    'cross_dataset': left['dataset_name'] != right['dataset_name'],
                    'cross_split': left['original_split'] != right['original_split']})
    return pairs


def leakage_groups(rows: list[dict], pairs: list[dict]) -> None:
    parents = {r['record_id']: r['record_id'] for r in rows}
    def root(x):
        while parents[x] != x:
            parents[x] = parents[parents[x]]; x = parents[x]
        return x
    def join(a, b):
        a, b = root(a), root(b)
        parents[max(a, b)] = min(a, b)
    hints = {}
    for row in rows:
        hint = row.get('source_family_hint')
        if hint:
            # Hints are conservative grouping constraints, never verified lineage.
            key = (row['dataset_name'], hint)
            if key in hints: join(row['record_id'], hints[key])
            hints[key] = row['record_id']
    for pair in pairs: join(pair['left_id'], pair['right_id'])
    for row in rows: row['conservative_leakage_group'] = root(row['record_id'])
    splits = defaultdict(set)
    for row in rows: splits[row['conservative_leakage_group']].add(row['original_split'])
    for row in rows: row['candidate_group_crosses_original_splits'] = len(splits[row['conservative_leakage_group']]) > 1


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    fields = fields or (list(rows[0]) if rows else ['status'])
    with path.open('w', newline='', encoding='utf-8') as out:
        writer = csv.DictWriter(out, fieldnames=fields, extrasaction='ignore'); writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def download(blob, limit=MAX_BYTES) -> bytes:
    if blob.size is None: blob.reload(timeout=30)
    if blob.size is None or blob.size > limit: raise ValueError('Bounded object-size limit')
    from google.api_core.retry import Retry
    return blob.download_as_bytes(if_generation_match=blob.generation, timeout=30,
                                  retry=Retry(initial=1, maximum=2, deadline=60))


def run(client, out: Path, workers: int = 4, reuse: Path | None = None) -> dict:
    if out.exists(): raise ValueError('Output directory must be new; preserve previous audit runs')
    out.mkdir(parents=True)
    bucket = client.bucket(BUCKET)
    registries, objects, provenance = {}, {}, []
    for dataset, prefix in SOURCE_PREFIXES.items():
        blob = bucket.blob(prefix + 'dataset_registry.json'); data = download(blob, 20 * 1024 * 1024)
        reg = json.loads(data); registries[dataset] = reg
        listed = list(client.list_blobs(BUCKET, prefix=prefix)); objects[dataset] = {b.name: b for b in listed}
        provenance.append({'dataset': dataset, 'registry_uri': f'gs://{BUCKET}/{blob.name}',
            'generation': str(blob.generation), 'sha256': hashlib.sha256(data).hexdigest(),
            'record_count': len(reg['records']), 'source_export': reg.get('source_export'),
            'source_license': reg.get('source_license'), 'rights_provenance_verified': reg.get('rights_provenance_verified'),
            'commercial_training_eligible': reg.get('commercial_training_eligible')})
        for b in listed:
            if b.name.lower().endswith(('.txt', '.yaml', '.yml', '.md')) and not '/labels/' in b.name and b.size and b.size <= 256 * 1024:
                text = download(b, 256 * 1024).decode('utf-8', errors='replace')
                provenance.append({'dataset': dataset, 'metadata_uri': f'gs://{BUCKET}/{b.name}',
                    'generation': str(b.generation), 'sha256': hashlib.sha256(text.encode()).hexdigest(), 'text': text})
    baseline_sha, baseline_dhash = set(), set()
    baseline_status = []
    for name in BASELINES:
        try:
            b = bucket.blob(name); payload = download(b, 64 * 1024 * 1024); data = json.loads(payload)
            records = data.get('records', [])
            baseline_sha.update(r['sha256'] for r in records if r.get('sha256'))
            baseline_dhash.update(r['dhash'] for r in records if r.get('dhash'))
            baseline_status.append({'uri': f'gs://{BUCKET}/{name}', 'status': 'READ', 'records': len(records),
                                    'generation': str(b.generation), 'sha256': hashlib.sha256(payload).hexdigest()})
        except Exception as exc:
            baseline_status.append({'uri': f'gs://{BUCKET}/{name}', 'status': 'UNAVAILABLE', 'error_type': type(exc).__name__})
    cached = {}
    if reuse:
        previous_sources=json.loads((reuse/'source_metadata.json').read_text())['sources']
        previous_registry={r['registry_uri']:(r['generation'],r['sha256']) for r in previous_sources if 'registry_uri' in r}
        current_registry={r['registry_uri']:(r['generation'],r['sha256']) for r in provenance if 'registry_uri' in r}
        if previous_registry != current_registry:
            raise ValueError('Registry snapshot changed; a new full audit is required')
        cached = {(r['dataset_name'],r['original_image_path'],r['expected_sha256']):r
                  for r in map(json.loads,(reuse/'dataset_inventory.jsonl').read_text().splitlines())}
        for dataset, reg in registries.items():
            for row in reg['records']:
                old = cached.get((dataset,row['original_image_path'],row['sha256']))
                name = resolve_name(reg,row['original_image_path'],SOURCE_PREFIXES[dataset],list(objects[dataset]))
                if (not old or not name or old.get('integrity_status')!='VERIFIED'
                    or old.get('image_generation')!=str(objects[dataset][name].generation)):
                    raise ValueError('Cached image generation changed; a new full byte audit is required')
    tasks = [(dataset, i, row) for dataset, reg in registries.items() for i, row in enumerate(reg['records'])]
    def audit(task):
        dataset, index, source = task
        reg = registries[dataset]; names = list(objects[dataset]); prefix = SOURCE_PREFIXES[dataset]
        rid = ('sewer' if dataset == 'Sewer Defects Public' else 'cctv') + f'-{index + 1:04d}'
        result = {'record_id': rid, 'dataset_name': dataset, 'dataset_version': reg['dataset_version'],
            'source': reg['source'], 'original_media_id': source.get('original_media_id'),
            'original_image_path': source['original_image_path'], 'expected_sha256': source['sha256'],
            'registry_width': source.get('width'), 'registry_height': source.get('height'),
            'original_labels': source.get('source_labels', []), 'original_split': source.get('split'),
            'source_family_hint': tentative_family(source.get('original_media_id', '')),
            'source_family_verified': False, 'lineage_status': 'LINEAGE_UNCERTAIN',
            'original_duplicate_status': source.get('duplicate_status'), 'registry_dhash': source.get('dhash'),
            'publisher_declared_license': reg.get('source_license'), 'upstream_rights_verified': False,
            'rights_status': 'RESEARCH_QUARANTINE', 'annotation_verification_status': 'UNVERIFIED_SOURCE_LABEL',
            'commercial_training_eligible': False, 'training_eligible': False,
            'verified_evaluation_eligible': False, 'production_validation_eligible': False,
            'research_inference_eligible': False, 'inference_blockers': ['REVIEWED_TASK_ROI_AND_LINEAGE_REQUIRED'],
            'integrity_status': 'UNRESOLVED', 'annotation_structure_valid': False}
        thumb = None
        try:
            name = resolve_name(reg, source['original_image_path'], prefix, names)
            if not name: raise ValueError('Missing or ambiguous image object')
            blob = objects[dataset][name]
            old = cached.get((dataset,source['original_image_path'],source['sha256']))
            if old:
                result.update(old)
                result['image_evidence_reused_generation_pinned'] = True
            else:
                payload = download(blob)
                actual_sha = hashlib.sha256(payload).hexdigest()
                result.update(image_uri=f'gs://{BUCKET}/{name}', image_generation=str(blob.generation),
                              image_bytes=len(payload), actual_sha256=actual_sha)
                evidence, thumb = image_evidence(payload); result.update(evidence)
                result['sha256_matches_registry'] = actual_sha == source['sha256']
                result['dimensions_match_registry'] = (result['width'], result['height']) == (source['width'], source['height'])
                result['dhash_matches_registry'] = result['dhash'] == source.get('dhash')
                result['integrity_status'] = 'VERIFIED' if result['sha256_matches_registry'] and result['dimensions_match_registry'] else 'REGISTRY_MISMATCH'
            annotation = resolve_name(reg, source['original_annotation_path'], prefix, names)
            result['registry_annotation_type'] = source.get('annotation_type')
            if (old and old['annotation_structure_valid'] and annotation
                and old.get('annotation_generation') == str(objects[dataset][annotation].generation)
                and old.get('original_labels') == source.get('source_labels')):
                result.update(cached_annotation_format(old))
            elif annotation:
                label_blob = objects[dataset][annotation]; raw = download(label_blob, 1024 * 1024)
                result.update(annotation_uri=f'gs://{BUCKET}/{annotation}', annotation_generation=str(label_blob.generation),
                              annotation_sha256=hashlib.sha256(raw).hexdigest())
                result.update(check_yolo(raw.decode('utf-8'), reg['original_classes']))
                result['annotation_labels_match_registry'] = result['decoded_annotation_labels'] == sorted(set(result['original_labels']))
            result['exact_baseline_sha256_match'] = result['actual_sha256'] in baseline_sha
            result['baseline_dhash_collision_unverified'] = result['dhash'] in baseline_dhash
        except Exception as exc:
            result['audit_error_type'] = type(exc).__name__
            result['inference_blockers'].append('INTEGRITY_OR_SOURCE_RESOLUTION_REQUIRED')
        return result, thumb
    rows, thumbs = [], {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for row, thumb in pool.map(audit, tasks):
            rows.append(row)
            if thumb is not None: thumbs[row['record_id']] = thumb
            if len(rows) % 100 == 0: print(json.dumps({'audited': len(rows), 'total': len(tasks)}), flush=True)
    pairs = duplicate_pairs(rows); leakage_groups(rows, pairs)
    seen = set(); candidate_ids = {p[k] for p in pairs if p['status'] != 'SHA256_EXACT' for k in ('left_id', 'right_id')}
    for row in rows:
        sha = row.get('actual_sha256'); row['exact_duplicate_within_imports'] = bool(sha and sha in seen)
        if sha: seen.add(sha)
        row['near_duplicate_candidate'] = row['record_id'] in candidate_ids
        row['technical_classification_candidate'] = bool(row['integrity_status'] == 'VERIFIED' and not row['exact_duplicate_within_imports'] and not row.get('exact_baseline_sha256_match'))
        # Classification candidate is not approval for the current reviewed-ROI batch runner.
    (out / 'dataset_inventory.jsonl').write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows))
    write_csv(out / 'duplicate_candidates.csv', pairs, ['left_id','right_id','status','dhash_distance','phash_distance','cross_dataset','cross_split'])
    write_csv(out / 'source_family_audit.csv', rows, ['record_id','dataset_name','original_media_id','source_family_hint','source_family_verified','lineage_status','original_split','conservative_leakage_group','candidate_group_crosses_original_splits'])
    mappings = [{'dataset_name': dataset, 'original_label': label, 'occurrences': sum(label in r.get('source_labels', []) for r in reg['records']),
        'proposed_jointinspect_label': MAPPINGS.get(label), 'mapping_status': 'PROVISIONAL' if label in MAPPINGS else 'UNSUPPORTED',
        'independently_verified_positives': 0, 'active_infiltration_confirmed': False,
        'review_note': 'Still-image Leak does not prove active infiltration' if label == 'Leak' else 'Publisher label is not adjudicated ground truth'}
        for dataset, reg in registries.items() for label in reg['original_classes']]
    write_csv(out / 'label_mapping_review.csv', mappings)
    write_csv(out / 'research_eligibility.csv', rows, ['record_id','integrity_status','technical_classification_candidate','research_inference_eligible','inference_blockers','verified_evaluation_eligible','training_eligible','commercial_training_eligible','production_validation_eligible'])
    (out / 'source_metadata.json').write_text(json.dumps({'sources': provenance, 'baselines': baseline_status}, indent=2))
    # Private contact sheets for all images. Never draw invented ROIs or approve them.
    from PIL import Image, ImageDraw
    sheet_dir = out / 'contact-sheets'; sheet_dir.mkdir()
    for start in range(0, 0 if reuse else len(rows), 20):
        sheet = Image.new('RGB', (1100, 1190), 'white'); draw = ImageDraw.Draw(sheet)
        draw.text((12, 10), 'QUARANTINE: unverified labels / lineage. No ROI approval.', fill='black')
        for pos, row in enumerate(rows[start:start+20]):
            x, y = (pos % 4) * 275 + 12, (pos // 4) * 230 + 40
            if row['record_id'] in thumbs: sheet.paste(thumbs[row['record_id']], (x, y))
            draw.text((x, y+174), row['record_id'] + ' ' + str(row.get('source_family_hint') or 'UNKNOWN'), fill='black')
            draw.text((x, y+190), '|'.join(row['original_labels'])[:38], fill='black')
            draw.text((x, y+206), row['expected_sha256'][:16], fill='black')
        sheet.save(sheet_dir / f'page-{start//20+1:03d}.jpg', quality=85)
    if reuse:
        import shutil
        shutil.copytree(reuse/'contact-sheets', sheet_dir, dirs_exist_ok=True)
    summary = {'status': 'COMPLETED' if all(r['integrity_status']=='VERIFIED' for r in rows) else 'BLOCKED_INFRASTRUCTURE',
        'created_at': datetime.now(timezone.utc).isoformat(), 'records_audited': len(rows),
        'dataset_counts': dict(Counter(r['dataset_name'] for r in rows)),
        'integrity_counts': dict(Counter(r['integrity_status'] for r in rows)),
        'image_evidence_reused_generation_pinned': sum(r.get('image_evidence_reused_generation_pinned',False) for r in rows),
        'observed_annotation_formats': dict(Counter(r.get('observed_annotation_format') for r in rows)),
        'annotation_polygon_count': sum(r.get('annotation_polygon_count',0) for r in rows),
        'annotation_structurally_valid': sum(r['annotation_structure_valid'] for r in rows),
        'annotation_label_mismatches': sum(r.get('annotation_labels_match_registry') is False for r in rows),
        'dhash_registry_mismatches': sum(r.get('dhash_matches_registry') is False for r in rows),
        'exact_duplicate_pairs': sum(p['status']=='SHA256_EXACT' for p in pairs),
        'exact_duplicate_redundant_records': sum(r['exact_duplicate_within_imports'] for r in rows),
        'exact_baseline_sha256_matches': sum(r.get('exact_baseline_sha256_match',False) for r in rows),
        'baseline_dhash_candidates': sum(r.get('baseline_dhash_collision_unverified',False) for r in rows),
        'near_duplicate_candidate_pairs': sum(p['status']!='SHA256_EXACT' for p in pairs),
        'near_duplicate_candidate_records': len(candidate_ids),
        'cross_dataset_candidate_pairs': sum(p['cross_dataset'] for p in pairs),
        'cross_split_candidate_pairs': sum(p['cross_split'] for p in pairs),
        'conservative_leakage_groups': len({r['conservative_leakage_group'] for r in rows}),
        'records_in_cross_split_candidate_groups': sum(r['candidate_group_crosses_original_splits'] for r in rows),
        'verified_lineage_records': 0, 'independently_verified_label_records': 0,
        'unverified_label_records': len(rows),
        'technical_classification_candidates': sum(r['technical_classification_candidate'] for r in rows),
        'approved_task_inference_eligible': 0, 'verified_evaluation_eligible': 0,
        'training_authorized': False, 'commercial_training_eligible': 0,
        'model_inference_executed': False, 'gpu_jobs_submitted': 0,
        'near_duplicate_policy': 'pHash64 distance <=8 OR compatible dHash64 distance <=6; candidates only',
        'baseline_status': baseline_status}
    (out / 'audit_summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--workers', type=int, choices=range(1,9), default=4)
    parser.add_argument('--gcloud', default='gcloud')
    parser.add_argument('--reuse-inventory', type=Path, help='Reuse image evidence ONLY when all object generations still match')
    args = parser.parse_args()
    import subprocess
    from google.oauth2.credentials import Credentials
    from google.cloud import storage
    token = subprocess.check_output([args.gcloud, 'auth', 'print-access-token'], text=True).strip()
    client = storage.Client(project='joint-inspection-510310', credentials=Credentials(token=token))
    print(json.dumps(run(client, args.out, args.workers, args.reuse_inventory), indent=2))

if __name__ == '__main__': main()
