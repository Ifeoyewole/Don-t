"""Research pixel boundary evidence, never calibrated geometry or defect proof.

Reuse the existing seam and projected-ring algorithms. SAM support is recorded
separately: the intensity edges are not relabelled as SAM-generated material
edges. Nominal diameters and client metadata cannot establish physical scale.
"""
from dataclasses import asdict

import cv2
import numpy as np

from backend.app.core.cv.experimental_ellipse import audit_projected_pipe_rings
from backend.app.core.cv.experimental_rough_profile import profile_rough_seam


def mask_band_pairs(mask, bbox):
    """Opposing *mask* edges along distance ridges; never infer a material gap.

    Partial annular bands need not form complete ellipses. Reject crop/image
    boundaries and broad filled regions. Preserve every sampled image-plane
    segment so engineers can see exactly what the pixel statistic represents.
    """
    x0, y0, x1, y1 = bbox
    crop = mask[y0:y1, x0:x1]
    distance = cv2.distanceTransform(crop, cv2.DIST_L2, 5)
    maxima = (distance >= cv2.dilate(distance, np.ones((3, 3), np.uint8))-.01) & (distance >= 2)
    points = np.argwhere(maxima)
    if len(points) < 16:
        return []
    contours, _ = cv2.findContours(crop, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    boundaries = np.concatenate(contours).reshape(-1, 2) if contours else np.empty((0, 2))
    if len(boundaries) < 30:
        return []
    pairs = []
    for y, x in points[::max(1, len(points)//80)][:80]:
        delta = boundaries-np.array([x, y])
        nearest = boundaries[np.argmin(np.sum(delta*delta, axis=1))]
        normal = np.array([x, y], dtype=float)-nearest
        radius = float(np.linalg.norm(normal))
        if radius < 2:
            continue
        normal /= radius
        end = None
        for step in np.arange(1, min(x1-x0, y1-y0)*.5, .5):
            p = np.rint(np.array([x, y])+normal*step).astype(int)
            if not 2 <= p[0] < x1-x0-2 or not 2 <= p[1] < y1-y0-2:
                break
            if not crop[p[1], p[0]]:
                end = p
                break
        if end is None or not (2 <= nearest[0] < x1-x0-2 and 2 <= nearest[1] < y1-y0-2):
            continue
        width = float(np.linalg.norm(end-nearest))
        if not 4 <= width <= min(x1-x0, y1-y0)*.35:
            continue
        pairs.append({'a': [int(nearest[0]+x0), int(nearest[1]+y0)],
                      'b': [int(end[0]+x0), int(end[1]+y0)],
                      'separation_px': round(width, 3), 'sam_nearby_support': True})
    return pairs


def boundary_evidence(image, mask, bbox, geometry):
    result = {'status': 'joint_geometry_not_reliable', 'units': 'px',
              'candidate_separation_px': None, 'physical_gap_mm': None,
              'calibration_status': 'UNVERIFIED_NO_PHYSICAL_SCALE',
              'perspective': 'IMAGE_PLANE_ONLY_NO_METRIC_RECTIFICATION',
              'joint_opening_confirmed': False, 'edge_pairs': []}
    if (not isinstance(mask, np.ndarray) or mask.shape != image.shape[:2]
            or mask.dtype != np.uint8 or not np.isin(mask, [0, 255]).all()
            or np.count_nonzero(mask) < 50):
        return dict(result, reason='ACTUAL_SAME_IMAGE_MASK_REQUIRED')
    h, w = image.shape[:2]
    if (len(bbox) != 4 or any(type(v) is not int for v in bbox)
            or not 0 <= bbox[0] < bbox[2] <= w or not 0 <= bbox[1] < bbox[3] <= h):
        return dict(result, reason='INVALID_ORIGINAL_COORDINATES')
    if geometry in ('VERTICAL_SEAM', 'HORIZONTAL_SEAM'):
        profile = profile_rough_seam(image, geometry, tuple(bbox))
        result['method'] = profile.method
        result['profile'] = asdict(profile)
        if profile.status != 'PIXEL_PROFILE_CANDIDATE':
            return dict(result, reason='INSUFFICIENT_TWO_SIDED_EDGE_SUPPORT')
        pairs = []
        for sample in profile.samples:
            if sample.left_point is None or sample.right_point is None:
                continue
            a, b = sample.left_point, sample.right_point
            # Mask must support the same local structure, not just any ROI.
            mid = ((a[0]+b[0])//2, (a[1]+b[1])//2)
            ys = slice(max(0, mid[1]-3), min(h, mid[1]+4))
            xs = slice(max(0, mid[0]-3), min(w, mid[0]+4))
            pairs.append({'a': list(a), 'b': list(b), 'separation_px': sample.width_px,
                          'sam_nearby_support': bool(np.any(mask[ys, xs]))})
        supported = [p for p in pairs if p['sam_nearby_support']]
        result['edge_pairs'] = pairs
        if len(supported) < 16 or len(supported)/max(1, len(pairs)) < .6:
            return dict(result, reason='MASK_AND_INTENSITY_BOUNDARIES_DISAGREE')
        widths = np.asarray([p['separation_px'] for p in supported])
        return dict(result, status='PRELIMINARY_PIXEL_BOUNDARY_SEPARATION',
                    candidate_separation_px=round(float(np.median(widths)), 3),
                    width_mad_px=round(float(np.median(np.abs(widths-np.median(widths)))), 3),
                    reason='DARK_BAND_EDGE_PAIRS_NOT_VERIFIED_AXIAL_JOINT_GAP')
    if geometry == 'CIRCULAR_OPENING':
        audit = audit_projected_pipe_rings(image, tuple(bbox))
        result['method'] = audit.method
        result['projected_ring_evidence'] = asdict(audit)
        # Nested rings may be sockets/perspective, not an opening. Keep the
        # projected spacing separately named and never return it as joint gap.
        result['projected_ring_spacing_px'] = audit.projected_semiaxis_spacing_px
        if audit.inner_ring and audit.outer_ring:
            for ring in (audit.inner_ring, audit.outer_ring):
                result.setdefault('ellipse_edges', []).append(asdict(ring))
        pairs = mask_band_pairs(mask, bbox)
        result['edge_pairs'] = pairs
        if len(pairs) >= 16:
            widths = np.asarray([p['separation_px'] for p in pairs])
            median = float(np.median(widths))
            mad = float(np.median(np.abs(widths-median)))
            result['sampled_mask_band_width_px'] = {
                'sample_count': len(pairs), 'median': round(median, 3),
                'mad': round(mad, 3), 'min': round(float(widths.min()), 3),
                'max': round(float(widths.max()), 3),
                'meaning': 'DESCRIPTIVE_MASK_WIDTHS_NOT_A_JOINT_GAP_MEASUREMENT'}
            if mad <= .35*median:
                return dict(result, status='PRELIMINARY_SEGMENTED_BAND_SEPARATION',
                            candidate_separation_px=round(median, 3), width_mad_px=round(mad, 3),
                            reason='PROJECTED_SAM_BAND_WIDTH_NOT_VERIFIED_AXIAL_JOINT_GAP')
        return dict(result, reason='PROJECTED_RINGS_DO_NOT_ESTABLISH_AXIAL_GAP')
    return dict(result, reason='NO_SUPPORTED_JOINT_GEOMETRY')


def draw_boundaries(canvas, evidence):
    for pair in evidence.get('edge_pairs', [])[::3]:
        if pair['sam_nearby_support']:
            cv2.line(canvas, tuple(pair['a']), tuple(pair['b']), (0, 255, 255), 1)
            cv2.circle(canvas, tuple(pair['a']), 2, (255, 100, 30), -1)
            cv2.circle(canvas, tuple(pair['b']), 2, (30, 255, 100), -1)
    for ring in evidence.get('ellipse_edges', []):
        ellipse = (tuple(ring['center_xy']), tuple(ring['axes_px']), ring['angle_deg'])
        cv2.ellipse(canvas, ellipse, (255, 0, 255), 1)
    return canvas
