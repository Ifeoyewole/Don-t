"""One Phase 1 research transaction: existing models, pixels, Vertex, one result.

No model loaders, production gates or classifier thresholds are duplicated.
Gemini can request one targeted pass, not an unbounded model/tool loop.
"""
from __future__ import annotations

import base64
from collections import OrderedDict
import io
import json
import threading
from time import perf_counter

import cv2
import numpy as np
from PIL import Image

from backend.app.core.cv.ai.research_joint_boundaries import draw_boundaries
from backend.app.core.cv.ai.joint_gap_recovery import recover_joint_gap, text_exclusion_candidates
from backend.app.core.cv.ai.independent_seam import measure_image_seam
from backend.app.core.cv.ai.unified_calibration import calibrated_gap, UNAVAILABLE
from backend.app.core.cv.ai.research_sewer_fusion import decode, png
from backend.app.core.cv.ai.research_sewer_detector import overlap
from backend.app.core.cv.ai.signed_gemini_receipt import verify_signed_semantic_receipt


class Phase1Unified:
    def __init__(self, *, fusion, reconciler, max_analysis_passes=2):
        if type(max_analysis_passes) is not int or max_analysis_passes not in (1, 2):
            raise ValueError('One initial pass and at most one targeted pass')
        self.max_analysis_passes = max_analysis_passes
        self.fusion, self.reconciler = fusion, reconciler
        self.initialization_failures = getattr(fusion, 'initialization_failures', {})
        self.history = OrderedDict()
        self.lock = threading.Lock()

    def _geometry(self, image, result, geometry, task, context=None, rois=()):
        if task == 'JOINT_GEOMETRY' and geometry in ('VERTICAL_SEAM','HORIZONTAL_SEAM'):
            excluded, boxes = text_exclusion_candidates(image)
            for box in (rois or [None]):
                evidence = measure_image_seam(image, geometry, box, exclusion=excluded)
                evidence['text_exclusion_boxes'] = boxes
                result['regions'].append({'region_id':len(result['regions']),
                    'bbox':evidence['roi_bbox'], 'source':'OPENCV_INDEPENDENT_SEAM',
                    'mask_status':'NOT_REQUIRED_FOR_OPENCV',
                    'boundary_evidence':evidence, 'geometry':{'physical_gap_mm':None}})
        for region in result['regions']:
            if region.get('source') == 'OPENCV_INDEPENDENT_SEAM' or task != 'JOINT_GEOMETRY' or not geometry or 'mask_png_base64' not in region:
                continue
            mask = cv2.imdecode(np.frombuffer(base64.b64decode(region['mask_png_base64']), np.uint8), cv2.IMREAD_GRAYSCALE)
            region['boundary_evidence'] = recover_joint_gap(image, mask, region['bbox'], geometry)
            region['boundary_evidence']['server_calibration'] = calibrated_gap(region['boundary_evidence'],
                image_sha256=result['image_sha256'], dimensions=result['dimensions'], context=context or {}, geometry=geometry)

    def _context(self, payload, result, metadata, previous):
        with Image.open(io.BytesIO(payload)) as image:
            mime = Image.MIME.get(image.format)
        if mime not in ('image/jpeg', 'image/png', 'image/webp'):
            raise ValueError('Phase 1 supports JPEG, PNG and WebP evidence')
        # Exact byte masks/overlay are sent separately. Text preserves provenance
        # and a bounded sample of geometry rather than megabytes of image data.
        regions = []
        for region in result['regions']:
            row = {k: v for k, v in region.items() if k != 'mask_png_base64'}
            if 'boundary_evidence' in row:
                row['boundary_evidence'] = dict(row['boundary_evidence'])
                profile = row['boundary_evidence'].get('profile')
                if profile:
                    row['boundary_evidence']['profile'] = {k: v for k, v in profile.items() if k != 'samples'}
                row['boundary_evidence']['edge_pairs'] = row['boundary_evidence']['edge_pairs'][::4]
            regions.append(row)
        return {'image_sha256': result['image_sha256'], 'dimensions': result['dimensions'],
                'mime_type': mime, 'task': result['task'], 'components': result['components'],
                'regions': regions, 'declared_context_unverified': {k:v for k,v in metadata.items() if k != 'image_id'},
                'provided_mask_region_ids': [r['region_id'] for r in result['regions']
                                             if 'mask_png_base64' in r][:4],
                'previous_frame_advisory': previous, 'calibration_authority': 'UNVERIFIED',
                'production_authority': False, 'physical_measurements': None}

    def infer(self, payload, *, rois=(), task='OBJECT_SEGMENTATION', geometry=None,
              receipt=None, sequence_id=None, frame_index=None, context=None):
        started = perf_counter()
        context = {} if context is None else context
        if not isinstance(context, dict) or len(json.dumps(context, allow_nan=False).encode()) > 4096:
            raise ValueError('Bounded advisory metadata required; cannot authorize calibration')
        image = decode(payload)
        # Use the exact existing orchestrator for classifier/detector/SAM paths.
        # An incoming receipt remains subject to its existing verification.
        result = self.fusion.infer(payload, rois=rois, task=task, geometry=geometry,
                                   receipt=receipt, sequence_id=sequence_id, frame_index=frame_index)
        first_elapsed = perf_counter()-started
        self._geometry(image, result, geometry, task, context, rois)
        overlay = cv2.imdecode(np.frombuffer(base64.b64decode(result['overlay_png_base64']), np.uint8), cv2.IMREAD_COLOR)
        for region in result['regions']:
            draw_boundaries(overlay, region.get('boundary_evidence', {}))
        previous = None
        if sequence_id is not None:
            with self.lock:
                prior = self.history.get(sequence_id)
                if (prior and prior.get('dimensions') == result['dimensions'] and 0 < frame_index-prior['frame_index'] <= 5
                        and prior['image_sha256'] != result['image_sha256']):
                    previous = dict(prior)
        analyses = []
        passes = 1
        semantic_allowed = False
        gemini_started = perf_counter()
        for pass_index in range(self.max_analysis_passes):
            if self.reconciler is None:
                result['gemini'] = {'status': 'UNAVAILABLE', 'reason': 'RESEARCH_VERTEX_NOT_CONFIGURED', 'authoritative': False}
                break
            try:
                masks = [base64.b64decode(r['mask_png_base64']) for r in result['regions'] if 'mask_png_base64' in r][:4]
                response = self.reconciler.reconcile(payload, self._context(payload, result, context, previous),
                                                     overlay_png=base64.b64decode(png(overlay)),
                                                     masks=masks, pass_index=pass_index)
                gate = verify_signed_semantic_receipt(response['semantic_receipt'],
                    original_image_sha256=result['image_sha256'], signing_secret=self.fusion.receipt_secret)['semantic_gate']
                semantic_allowed = (gate['processing_allowed'] and gate['joint_visible'] and gate['pipe_visible']
                                    and gate['quality'] == 'OK' and not gate['prompt_image_conflict'])
                result['gemini'] = response
                analyses.append({'pass_index': pass_index, 'receipt': response['receipt'], 'usage': response['usage']})
                proposals = response['analysis']['additional_regions']
                if (pass_index+1 == self.max_analysis_passes or not proposals
                        or not gate['pipe_visible'] or gate['prompt_image_conflict']):
                    break
                proposal = proposals[0]
                # An AI proposal is explicitly unverified. It is neither human
                # review nor a calibration/defect annotation approval.
                extra_geometry = proposal['geometry'] if task == 'JOINT_GEOMETRY' and proposal['geometry'] != 'NONE' else None
                extra = self.fusion.infer(payload, rois=[proposal['bbox']],
                    task='JOINT_GEOMETRY' if extra_geometry else 'OBJECT_SEGMENTATION', geometry=extra_geometry, proposal_only=True)
                candidates = [r for r in extra['regions'] if r['source'] == 'EXPLICIT_RESEARCH_ROI']
                for region in candidates[:1]:
                    region['region_id'] = len(result['regions'])
                    region['source'] = 'GEMINI_TARGETED_UNVERIFIED_PROMPT'
                    region['proposal_reason'] = proposal['reason']
                    result['regions'].append(region)
                    if 'mask_png_base64' in region:
                        mask = cv2.imdecode(np.frombuffer(base64.b64decode(region['mask_png_base64']), np.uint8), cv2.IMREAD_GRAYSCALE)
                        tint = overlay.copy(); tint[mask > 0] = (220, 120, 20)
                        overlay = cv2.addWeighted(overlay, .65, tint, .35, 0)
                        if task == 'JOINT_GEOMETRY' and proposal['geometry'] != 'NONE':
                            region['boundary_evidence'] = recover_joint_gap(image, mask, region['bbox'], proposal['geometry'])
                            draw_boundaries(overlay, region['boundary_evidence'])
                    if task == 'JOINT_GEOMETRY' and proposal['geometry'] in ('VERTICAL_SEAM','HORIZONTAL_SEAM'):
                        excluded, boxes = text_exclusion_candidates(image)
                        region['boundary_evidence'] = measure_image_seam(image, proposal['geometry'], proposal['bbox'],exclusion=excluded)
                        region['boundary_evidence']['text_exclusion_boxes'] = boxes
                        draw_boundaries(overlay,region['boundary_evidence'])
                passes = 2
            except Exception as exc:
                # Failed second call must not retain a stale first-pass gate
                # as if it authenticated the enlarged evidence bundle.
                semantic_allowed = False
                result['gemini'] = {'status': 'UNAVAILABLE_OR_INVALID', 'authoritative': False,
                                    'reason': 'VERTEX_REQUEST_OR_AUTHENTICATED_CONTRACT_FAILED',
                                    'failure_type': type(exc).__name__,
                                    'http_status': getattr(exc, 'code', None),
                                    'provider_reason': getattr(exc, 'provider_reason', None),
                                    'previous_analysis_count': len(analyses)}
                break
        candidates = []; physical_candidates = []
        scene_status = 'PIPE_JOINT_CONFIRMED' if semantic_allowed else 'UNVERIFIED_OR_UNSUITABLE'
        result['scene_validation'] = {'status':scene_status,'measurement_authorized':semantic_allowed}
        for region in result['regions']:
            evidence = region.get('boundary_evidence', {})
            value = evidence.get('gap_estimate_px')
            # Geometry diagnostics do not require an OPEN_JOINT classification.
            # Scene identity and metrology authority remain separate from pixels.
            suitable = evidence.get('status') == 'VISIBLE_GAP_PIXEL_CANDIDATE'
            if suitable and value is not None:
                candidates.append({'region_id': region['region_id'], 'value': value, 'units': 'px',
                    'bbox': region['bbox'], 'geometry': evidence.get('geometry', geometry),
                    'meaning': 'VISIBLE_IMAGE_EDGE_OPENING_CANDIDATE_NOT_PHYSICAL_AXIAL_GAP'})
            region['geometry'] = {'status': 'PRELIMINARY_PIXEL_EVIDENCE' if suitable and value is not None
                                  else 'joint_geometry_not_reliable',
                                  'pixel_candidate': value if suitable else None,
                                  'physical_gap_mm': None, 'calibration_verified': False}
            region['geometry']['interpretation'] = ('IMAGE_BOUNDARY_CANDIDATE_DEFECT_UNDETERMINED' if suitable else
                'INSUFFICIENT_GEOMETRIC_EVIDENCE')
            calibration = calibrated_gap(evidence if suitable else {}, image_sha256=result['image_sha256'],
                dimensions=result['dimensions'], context=context, geometry=evidence.get('geometry', geometry))
            if not semantic_allowed:
                scale_reason = calibration.get('reason')
                calibration = dict(calibration, physical_gap_mm=None,
                    calibration_authority_verified=False,
                    reason='AUTHENTICATED_SUITABLE_PIPE_JOINT_SCENE_REQUIRED',
                    scale_rejection_reason=scale_reason,
                    measurement_message=UNAVAILABLE)
            region['geometry'].update(calibration)
            region['geometry']['calibration_verified'] = calibration['calibration_authority_verified']
            if calibration['physical_gap_mm'] is not None:
                physical_candidates.append(dict(calibration, bbox=region['bbox'], region_id=region['region_id']))
        result['joint_measurement'] = {'status': 'PRELIMINARY_PIXEL_EVIDENCE' if candidates else 'joint_geometry_not_reliable',
                                       'candidates': candidates, 'physical_gap_mm': None,
                                       'calibration_status': 'UNVERIFIED', 'engineering_acceptance': False}
        result['joint_measurement']['geometry_independent_of_classification'] = True
        result['joint_measurement']['scene_status'] = scene_status
        result['joint_measurement']['rejection_reasons'] = sorted(set(
            reason for r in result['regions'] for reason in
            [r['geometry'].get('reason','UNSPECIFIED'), r['geometry'].get('scale_rejection_reason')] if reason
            if r['geometry'].get('physical_gap_mm') is None))
        if not semantic_allowed:
            result['joint_measurement']['rejection_reasons'].append('PIPE_JOINT_SCENE_NOT_AUTHENTICATED_OR_UNSUITABLE')
        result['primary_measurement_unit'] = 'mm'
        result['joint_measurement']['unit'] = 'mm'
        result['joint_measurement']['measurement_message'] = UNAVAILABLE
        result['joint_measurement']['calibration_authority_verified'] = False
        if physical_candidates:
            chosen = min(physical_candidates, key=lambda p: p['repeatability_mad_mm'])
            if all(overlap(p['bbox'], chosen['bbox']) >= .5 and
                   abs(p['physical_gap_mm']-chosen['physical_gap_mm']) <= .1*chosen['physical_gap_mm']
                   for p in physical_candidates):
                result['joint_measurement'].update(chosen, status='CALIBRATED_RESEARCH_GAP_ESTIMATE')
                result['physical_gap_mm'] = chosen['physical_gap_mm']
            else:
                result['joint_measurement']['status'] = 'CONFLICTING_CALIBRATED_REGIONS'
        analysis = result['gemini'].get('analysis', {})
        advisory = [{'label': h['label'], 'status': 'GEMINI_VISUAL_HYPOTHESIS_NOT_CONFIRMED',
                     'explanation': h['explanation'], 'region_ids': h['region_ids'],
                     'active_infiltration_confirmed': False}
                    for h in analysis.get('hypotheses', []) if h['status'] == 'POSSIBLE']
        result['preliminary_findings'].extend(advisory)
        result['disagreements_and_limits'] = sorted(set(result['disagreements_and_limits']+
            analysis.get('contradictions', [])+([] if result['physical_gap_mm'] is not None else ['NO_VERIFIED_PHYSICAL_MEASUREMENT'])+[
                'SPECIALIST_CLASS_IDS_UNMAPPED_WHERE_UNAVAILABLE', 'NO_TARGET_CLASS_ACCURACY_ESTABLISHED']))
        result['gemini_analyses'] = analyses
        result['phase1'] = {'model_passes': passes, 'gemini_required': True,
                           'geometry_path_complete':bool(candidates),
                           'physical_measurement_available':result['physical_gap_mm'] is not None,
                           'functional_path_complete': all(result['components'].get(k, {}).get('status') == 'AVAILABLE'
                               for k in ('inspect_view', 'sewer_detector'))
                               and any(r['mask_status'] == 'ACTUAL_MASK_CANDIDATE' for r in result['regions'])
                               and result['gemini']['status'] == 'AUTHENTICATED_ADVISORY',
                           'accuracy_improvement': None, 'engineering_acceptance': False}
        result['latency_seconds'] = {'initial_model_path': round(first_elapsed, 4),
                                     'reconciliation_and_optional_pass': round(perf_counter()-gemini_started, 4),
                                     'total': round(perf_counter()-started, 4)}
        result['baseline_comparison']['actual_mask_count'] = sum(r['mask_status'] == 'ACTUAL_MASK_CANDIDATE' for r in result['regions'])
        result['engine'] = 'jointinspect-phase1-unified-v1'
        result['source_context'] = context
        result['summary'] = analysis.get('summary', 'Partial evidence retained; Gemini interpretation unavailable.')
        caption = (f"CALIBRATED RESEARCH GAP: {result['physical_gap_mm']:.2f} mm" if result['physical_gap_mm'] is not None
                   else 'MEASUREMENT UNAVAILABLE - CALIBRATION / JOINT EDGES REQUIRED')
        cv2.putText(overlay, caption, (5, overlay.shape[0]-8), cv2.FONT_HERSHEY_SIMPLEX, .32, (0, 0, 255), 1)
        result['overlay_png_base64'] = png(overlay)
        result['temporal_geometry'] = {'status': 'SINGLE_FRAME_OR_UNCORROBORATED', 'physical_gap_mm': None}
        if (previous and candidates and previous.get('pixel_candidates')
                and candidates[0]['geometry'] == previous['pixel_candidates'][0]['geometry']
                and overlap(candidates[0]['bbox'], previous['pixel_candidates'][0]['bbox']) >= .5):
            old, new = previous['pixel_candidates'][0]['value'], candidates[0]['value']
            result['temporal_geometry'] = {'status': 'CONSISTENT_PIXEL_CANDIDATES' if abs(new-old)/max(old, new, 1) <= .2
                                          else 'PIXEL_GEOMETRY_DISAGREEMENT',
                                          'previous_image_sha256': previous['image_sha256'],
                                          'relative_change': abs(new-old)/max(old, new, 1),
                                          'physical_gap_mm': None, 'verified_video_lineage': False}
        if sequence_id is not None:
            with self.lock:
                prior = self.history.get(sequence_id)
                if prior is None or frame_index > prior['frame_index']:
                    self.history[sequence_id] = {'frame_index': frame_index, 'image_sha256': result['image_sha256'],
                        'dimensions': result['dimensions'],
                        'summary': result['summary'][:1800], 'pixel_candidates': candidates,
                        'source_lineage': 'CALLER_DECLARED_NOT_VERIFIED'}
                    self.history.move_to_end(sequence_id)
                    while len(self.history) > 32:
                        self.history.popitem(last=False)
        return result
