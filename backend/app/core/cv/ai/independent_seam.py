"""OpenCV image-boundary evidence independent of classifiers and SAM masks.

Reuses the existing rough profiler. Local normals intersect the observed edge
polylines; neither image dimensions nor a nominal diameter authorize mm.
"""
import cv2
import numpy as np

from backend.app.core.cv.experimental_rough_profile import profile_rough_seam


def _intersection(center, normal, points, side):
    choices = []
    for a, b in zip(points[:-1], points[1:]):
        matrix = np.column_stack((normal, a-b))
        if abs(np.linalg.det(matrix)) < 1e-8:
            continue
        t, u = np.linalg.solve(matrix, a-center)
        if 0 <= u <= 1 and t*side > 0:
            choices.append((abs(t), center+t*normal))
    return min(choices, key=lambda p:p[0])[1] if choices else None


def measure_image_seam(image, geometry, bbox=None, exclusion=None):
    h, w = image.shape[:2]
    box = [0, 0, w, h] if bbox is None else list(bbox)
    result = {'status':'joint_geometry_not_reliable', 'gap_estimate_px':None,
        'physical_gap_mm':None, 'geometry':geometry, 'edge_pairs':[],
        'method':'rough_profile_local_normal_v1', 'roi_bbox':box,
        'roi_source':'AUTOMATED_FULL_FRAME_SEARCH' if bbox is None else 'CALLER_OR_MODEL_PROPOSAL',
        'sam_required':False, 'joint_opening_confirmed':False,
        'perspective':'IMAGE_PLANE_ONLY', 'units':'px',
        'limitation':'Image-intensity edges may include shadow or socket lips; physical gap and defect identity are unverified.'}
    profile = profile_rough_seam(image, geometry, tuple(box))
    result['profile_status'] = profile.status
    result['profile_coverage'] = profile.coverage
    result['rejected_profile_reasons'] = profile.rejected_reasons
    if profile.status != 'PIXEL_PROFILE_CANDIDATE':
        return dict(result, reason='INSUFFICIENT_TWO_SIDED_IMAGE_EDGES')
    samples = [s for s in profile.samples if s.left_point and s.right_point]
    raw = np.array([s.width_px for s in samples],float)
    middle = float(np.median(raw)); dispersion = float(np.median(np.abs(raw-middle)))
    samples = [s for s in samples if abs(s.width_px-middle)<=max(3*dispersion,.35*middle)]
    if len(samples)<16:
        return dict(result,reason='INSUFFICIENT_CONSISTENT_PROFILE_PAIRS')
    left = np.array([s.left_point for s in samples], float)
    right = np.array([s.right_point for s in samples], float)
    centers = (left+right)/2
    vertical = geometry == 'VERTICAL_SEAM'
    scan_axis = 1 if vertical else 0
    cross_axis = 1-scan_axis
    for i in range(1, len(samples)-1):
        # Fit a bounded local tangent, rather than assuming a frontal straight seam.
        near = centers[max(0,i-7):min(len(centers),i+8)]
        x = near[:,scan_axis]-centers[i,scan_axis]
        if np.ptp(x) == 0:
            continue
        tangent_slope = np.polyfit(x, near[:,cross_axis], min(2,len(x)-1))[-2]
        normal = np.array([1., -tangent_slope]) if vertical else np.array([-tangent_slope, 1.])
        normal /= np.linalg.norm(normal)
        a = _intersection(centers[i], normal, left, -1)
        b = _intersection(centers[i], normal, right, 1)
        if a is None or b is None:
            continue
        a, b = np.rint(a).astype(int), np.rint(b).astype(int)
        count = max(2, int(np.linalg.norm(b-a))+1)
        pixels = np.rint(np.linspace(a,b,count)).astype(int)
        if (np.any(pixels[:,0]<0) or np.any(pixels[:,0]>=w) or
                np.any(pixels[:,1]<0) or np.any(pixels[:,1]>=h)):
            continue
        if exclusion is not None and np.any(exclusion[pixels[:,1],pixels[:,0]]):
            continue
        result['edge_pairs'].append({'a':a.tolist(), 'b':b.tolist(),
            'separation_px':round(float(np.linalg.norm(b-a)),3),
            'sam_nearby_support':False, 'basis':'OBSERVED_INTENSITY_EDGES_LOCAL_NORMAL'})
    widths = np.array([p['separation_px'] for p in result['edge_pairs']])
    result['accepted_cross_sections'] = len(widths)
    result['sampled_cross_sections'] = profile.sampled_rows
    if len(widths)<16 or len(widths)/profile.sampled_rows<.6:
        return dict(result,reason='INSUFFICIENT_UNOCCLUDED_NORMAL_EDGE_PAIRS')
    median = float(np.median(widths));mad = float(np.median(np.abs(widths-median)))
    result.update(width_mad_px=round(mad,3), min_width_px=float(widths.min()),
        max_width_px=float(widths.max()), p05_width_px=float(np.percentile(widths,5)),
        p95_width_px=float(np.percentile(widths,95)), measurement_direction='LOCAL_SEAM_NORMAL')
    if median<=0 or mad/median>.15:
        return dict(result, reason='BOUNDARY_WIDTH_VARIATION_REQUIRES_REVIEW')
    return dict(result,status='VISIBLE_GAP_PIXEL_CANDIDATE',gap_estimate_px=round(median,3),
        reason='IMAGE_BOUNDARY_SEPARATION_NOT_CONFIRMED_DEFECT_OR_PHYSICAL_GAP')
