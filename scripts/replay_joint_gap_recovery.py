"""Reproduce geometry on cached actual Phase 1 outputs; never run any model."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2

from backend.app.core.cv.ai.joint_gap_recovery import recover_joint_gap
from backend.app.core.cv.ai.research_joint_boundaries import draw_boundaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frame-directory', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(); source = Path(args.frame_directory); out = Path(args.output)
    out.mkdir(parents=True, exist_ok=False)
    report = json.loads((source/'unified-report.json').read_text())
    original = (source/'original.jpg').read_bytes()
    if hashlib.sha256(original).hexdigest() != report['image_sha256']:
        raise ValueError('Original source identity mismatch')
    image = cv2.imread(str(source/'original.jpg')); overlay = image.copy(); results = []
    for region in report['regions']:
        path = source/f'mask-{region["region_id"]}.png'
        if not path.exists(): continue
        mask = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if hashlib.sha256(mask.tobytes()).hexdigest() != region['mask_sha256']:
            raise ValueError('Recorded actual SAM mask identity mismatch')
        evidence = recover_joint_gap(image, mask, region['bbox'], 'CIRCULAR_OPENING')
        draw_boundaries(overlay, evidence)
        results.append({'region_id': region['region_id'], 'evidence': evidence})
    cv2.imwrite(str(out/'geometry-overlay.png'), overlay)
    (out/'recovery.json').write_text(json.dumps({'source_image_sha256': report['image_sha256'],
        'mode': 'CACHED_REAL_MASK_GEOMETRY_REPLAY_NO_NEW_MODEL_INFERENCE',
        'gemini_evidence': 'PREVIOUS_AUTHENTICATED_ADVISORY_NOT_A_NEW_REQUEST',
        'findings': results, 'physical_gap_mm': None}, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == '__main__': main()
