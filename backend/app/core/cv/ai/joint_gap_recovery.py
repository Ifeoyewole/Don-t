"""Image-edge gap candidates; segmentation extent is never a gap measurement."""
import cv2
import numpy as np

from backend.app.core.cv.experimental_rough_profile import profile_rough_seam
from backend.app.core.cv.experimental_ellipse import audit_projected_pipe_rings


def text_exclusion_candidates(image):
    """Conservative border-caption candidates, not an OCR identity assertion.

    Group similarly sized bright stroke components in horizontal rows near the
    frame border. Retain original pixels; exclusions are an explicit mask.
    """
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    bright = ((hsv[:, :, 2] > 200) & ((hsv[:, :, 1] < 70) |
               ((hsv[:, :, 0] >= 15) & (hsv[:, :, 0] <= 40)))).astype(np.uint8)*255
    count, _, stats, _ = cv2.connectedComponentsWithStats(bright)
    glyphs = []
    for x, y, cw, ch, area in stats[1:count]:
        if (2 <= cw <= max(28, w*.08) and 5 <= ch <= max(28, h*.075)
                and .1 <= area/(cw*ch) <= .95 and (y > .65*h or y < .12*h)):
            glyphs.append((int(x), int(y), int(cw), int(ch)))
    exclusion = np.zeros((h, w), np.uint8); boxes = []
    for x, y, cw, ch in glyphs:
        group = [g for g in glyphs if abs(g[1]-y) < max(5, ch*.6)
                 and abs(g[0]-x) < .4*w]
        clusters = []
        for glyph in sorted(group):
            if not clusters or glyph[0]-(clusters[-1][-1][0]+clusters[-1][-1][2]) > max(10, ch*1.2):
                clusters.append([])
            clusters[-1].append(glyph)
        group = next((c for c in clusters if (x, y, cw, ch) in c), [])
        if len(group) < 4:
            continue
        a = max(0, min(g[0] for g in group)-4); b = max(0, min(g[1] for g in group)-4)
        c = min(w, max(g[0]+g[2] for g in group)+4); d = min(h, max(g[1]+g[3] for g in group)+4)
        exclusion[b:d, a:c] = 255
        if [a, b, c, d] not in boxes: boxes.append([a, b, c, d])
    # Short codes (e.g. a three-letter CCTV caption) need a neighbouring
    # established caption row, rather than interpreting every bright patch.
    established = list(boxes)
    for x, y, cw, ch in glyphs:
        if any(a <= x <= c and 0 < b-(y+ch) < 2*ch for a, b, c, d in established):
            a, b, c, d = max(0,x-3), max(0,y-3), min(w,x+cw+3), min(h,y+ch+3)
            exclusion[b:d,a:c] = 255
            if [a,b,c,d] not in boxes: boxes.append([a,b,c,d])
    return exclusion, boxes


def recover_joint_gap(image, mask, bbox, geometry):
    excluded, boxes = text_exclusion_candidates(image)
    result = {'status': 'joint_geometry_not_reliable', 'gap_estimate_px': None,
              'candidate_separation_px': None, 'physical_gap_mm': None, 'units': 'px',
              'method': 'opposing_intensity_edges_v2', 'edge_pairs': [],
              'text_exclusion_boxes': boxes, 'excluded_mask_pixels': 0,
              'joint_opening_confirmed': False, 'geometry': geometry,
              'calibration_status': 'UNVERIFIED', 'perspective': 'PROJECTED_IMAGE_PLANE_ONLY'}
    if (not isinstance(mask, np.ndarray) or mask.shape != image.shape[:2]
            or mask.dtype != np.uint8 or not np.isin(mask, [0, 255]).all()):
        return dict(result, reason='INVALID_SAME_FRAME_MASK')
    result['excluded_mask_pixels'] = int(np.count_nonzero((mask > 0) & (excluded > 0)))
    clean = mask.copy(); clean[excluded > 0] = 0
    if geometry == 'CIRCULAR_OPENING':
        ring = audit_projected_pipe_rings(image, tuple(bbox))
        if ring.inner_ring is None or ring.outer_ring is None:
            return dict(result, reason='CURVED_JOINT_STEP_OR_SOCKET_NOT_IDENTIFIABLE_AS_AXIAL_OPENING',
                        required_evidence=['Opposing visible opening edges, not socket lips or mask perimeter',
                                           'Independent view or adjacent frames resolving depth/perspective'])
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY); h, w = gray.shape
        def ellipse_point(ellipse, t):
            angle = np.deg2rad(ellipse.angle_deg)
            u, v = np.asarray(ellipse.axes_px)*.5*np.array([np.cos(t), np.sin(t)])
            return np.asarray(ellipse.center_xy)+np.array([u*np.cos(angle)-v*np.sin(angle), u*np.sin(angle)+v*np.cos(angle)])
        for t in np.linspace(0, 2*np.pi, 48, endpoint=False):
            a = ellipse_point(ring.inner_ring, t); b = ellipse_point(ring.outer_ring, t)
            normal = b-a; width = float(np.linalg.norm(normal))
            if width < 4: continue
            normal /= width
            points = np.rint([a-5*normal, (a+b)/2, b+5*normal, a, b]).astype(int)
            if any(not (0 <= x < w and 0 <= y < h) for x, y in points): continue
            if any(excluded[y, x] for x, y in points): continue
            left, middle, right, pa, pb = points
            if min(int(gray[left[1], left[0]]), int(gray[right[1], right[0]]))-int(gray[middle[1], middle[0]]) < 16: continue
            if not clean[middle[1], middle[0]]: continue
            result['edge_pairs'].append({'a': pa.tolist(), 'b': pb.tolist(), 'separation_px': round(width, 3),
                                         'sam_nearby_support': True, 'basis': 'IMAGE_RING_EDGES_WITH_DARK_OPENING'})
        sampled_rows = 48
    elif geometry not in ('VERTICAL_SEAM', 'HORIZONTAL_SEAM'):
        return dict(result, reason='JOINT_ORIENTATION_REQUIRED')
    else:
        profile = profile_rough_seam(image, geometry, tuple(bbox))
        if profile.status != 'PIXEL_PROFILE_CANDIDATE':
            return dict(result, reason='INSUFFICIENT_TWO_SIDED_INTENSITY_EDGES')
        sampled_rows = profile.sampled_rows
        for sample in profile.samples:
            if not sample.left_point or not sample.right_point: continue
            a, b = sample.left_point, sample.right_point
            xs = np.linspace(a[0], b[0], max(2, int(sample.width_px)+1)).astype(int)
            ys = np.linspace(a[1], b[1], len(xs)).astype(int)
            if np.any(excluded[ys, xs]) or np.mean(clean[ys, xs] > 0) < .5: continue
            result['edge_pairs'].append({'a': list(a), 'b': list(b), 'separation_px': sample.width_px,
                                         'sam_nearby_support': True, 'basis': 'IMAGE_INTENSITY_EDGES'})
    widths = np.array([p['separation_px'] for p in result['edge_pairs']])
    result['accepted_cross_sections'] = len(widths)
    if len(widths) < 16 or len(widths)/sampled_rows < .6:
        return dict(result, reason='INSUFFICIENT_UNOCCLUDED_MASK_SUPPORTED_EDGE_PAIRS')
    median = float(np.median(widths)); mad = float(np.median(np.abs(widths-median)))
    result['width_mad_px'] = mad
    if mad/max(median, 1) > .15 or np.percentile(widths, 95)-np.percentile(widths, 5) > .4*median:
        return dict(result, reason='OPPOSING_EDGES_UNSTABLE')
    return dict(result, status='VISIBLE_GAP_PIXEL_CANDIDATE', gap_estimate_px=median,
                reason='VISIBLE_DARK_OPENING_EDGE_CANDIDATE_REQUIRES_SCENE_CORROBORATION',
                limitation='Image-plane opening width; physical axial separation is not established')
