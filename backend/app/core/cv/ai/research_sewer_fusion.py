"""One research-only r5 + sewer RT-DETR + SAM2 path; no engineering acceptance.

Classifiers, detector confidence and mask quality stay independent. Automatic
boxes are explicitly unverified prompts. No active infiltration diagnosis or
physical scale is inferred from a mask, a still image, or Gemini.
"""
from __future__ import annotations

import base64
import hashlib
import io
import threading
from collections import OrderedDict

import cv2
import numpy as np
from PIL import Image

from backend.app.core.cv.ai.research_sewer_detector import overlap
from backend.app.core.cv.ai.research_inspect_view_sam2_fusion import combine_inspect_view_and_sam2
from backend.app.core.cv.ai.signed_gemini_receipt import verify_signed_semantic_receipt


def png(array):
    ok, encoded = cv2.imencode('.png', array)
    if not ok:
        raise ValueError('PNG encoding failed')
    return base64.b64encode(encoded.tobytes()).decode('ascii')


def decode(payload):
    if not isinstance(payload, bytes) or not payload or len(payload) > 8*1024*1024:
        raise ValueError('Nonempty image up to 8 MiB required')
    with Image.open(io.BytesIO(payload)) as image:
        if image.width*image.height > 16_000_000:
            raise ValueError('Image dimensions exceed research limit')
        image.load()
        return cv2.cvtColor(np.array(image.convert('RGB')), cv2.COLOR_RGB2BGR)


class RegionTracker:
    """Bounded same-sequence box association, not verified video lineage or flow."""
    def __init__(self):
        self.sequences = OrderedDict()
        self.lock = threading.Lock()

    def update(self, sequence, index, digest, rows):
        if not isinstance(sequence, str) or not 1 <= len(sequence) <= 128 or type(index) is not int or index < 0:
            raise ValueError('Bounded sequence ID and nonnegative frame index required')
        with self.lock:
            prior = self.sequences.get(sequence)
            # Reject replay/out-of-order input without corrupting chronological state.
            if prior and index <= prior['index']:
                return [dict(r, temporal_observations=1, temporal_status='OUT_OF_ORDER_NOT_FUSED') for r in rows]
            adjacent = prior and 0 < index-prior['index'] <= 5 and digest != prior['digest']
            used = set(); output = []
            for row in rows:
                matches = [(i, old) for i, old in enumerate(prior['rows'])
                           if adjacent and i not in used and row['source_label'] == old['source_label']
                           and overlap(row['bbox'], old['bbox']) >= .5] if prior else []
                count = 1
                if matches:
                    match, old = max(matches, key=lambda pair: overlap(row['bbox'], pair[1]['bbox']))
                    used.add(match); count = min(100, old['temporal_observations']+1)
                output.append(dict(row, temporal_observations=count,
                                   temporal_status='CONSISTENT_REGION_CANDIDATE' if count >= 2 else 'SINGLE_FRAME'))
            self.sequences[sequence] = {'index': index, 'digest': digest, 'rows': output}
            self.sequences.move_to_end(sequence)
            while len(self.sequences) > 32:
                self.sequences.popitem(last=False)
            return output


class SewerFusion:
    def __init__(self, *, classifier, detector=None, segmenter=None, receipt_secret=None):
        self.classifier, self.detector, self.segmenter = classifier, detector, segmenter
        self.receipt_secret = receipt_secret
        self.tracker = RegionTracker()
        # SAM2ImagePredictor holds mutable set_image state. Serialize shared use.
        self.segment_lock = threading.Lock()

    def infer(self, payload, *, rois=(), task='OBJECT_SEGMENTATION', geometry=None,
              receipt=None, sequence_id=None, frame_index=None):
        if task not in ('OBJECT_SEGMENTATION', 'JOINT_GEOMETRY', 'INFILTRATION_REVIEW'):
            raise ValueError('Unsupported research task')
        if geometry not in (None, 'VERTICAL_SEAM', 'HORIZONTAL_SEAM', 'CIRCULAR_OPENING'):
            raise ValueError('Unsupported geometry')
        if task != 'JOINT_GEOMETRY' and geometry is not None:
            raise ValueError('Object/infiltration tasks cannot request joint geometry')
        if len(rois) > 8:
            raise ValueError('At most eight explicit region prompts')
        image = decode(payload); h, w = image.shape[:2]
        digest = hashlib.sha256(payload).hexdigest()
        pixel_digest = hashlib.sha256(np.ascontiguousarray(image).tobytes()).hexdigest()
        regions = []
        for box in rois:
            if (len(box) != 4 or any(type(v) is not int for v in box)
                    or not 0 <= box[0] < box[2] <= w or not 0 <= box[1] < box[3] <= h
                    or box[2]-box[0] < 24 or box[3]-box[1] < 24):
                raise ValueError('Invalid original-image ROI')
            regions.append({'bbox': list(box), 'source': 'EXPLICIT_RESEARCH_ROI', 'source_label': 'UNVERIFIED_TARGET',
                            'target_identity_verified': False})
        reasons = []; components = {}
        try:
            baseline = self.classifier(payload)
            if (not isinstance(baseline, dict) or baseline.get('image_sha256') != digest
                    or baseline.get('model_version') != 'repr-convnext-masked-r5-20261104'
                    or baseline.get('model_ready') is not True or baseline.get('research_preview') is not True):
                raise ValueError('Classifier provenance mismatch')
            components['inspect_view'] = {'status': 'AVAILABLE', 'evidence': baseline}
        except Exception:
            baseline = None
            components['inspect_view'] = {'status': 'UNAVAILABLE', 'reason': 'CLASSIFIER_FAILURE_OR_SOURCE_MISMATCH'}
        detections = []
        try:
            if self.detector is None:
                raise RuntimeError('Not configured')
            detections = [row.json() for row in self.detector.predict(image)]
            components['sewer_detector'] = {'status': 'AVAILABLE', 'detections': detections,
                                           'provenance': self.detector.provenance()}
        except Exception:
            components['sewer_detector'] = {'status': 'UNAVAILABLE', 'reason': 'DETECTOR_FAILURE_OR_CONTRACT_UNVERIFIED'}
        if sequence_id is not None:
            detections = self.tracker.update(sequence_id, frame_index, digest, detections)
            components['sewer_detector']['detections'] = detections
        for row in detections:
            if any(overlap(row['bbox'], region['bbox']) >= .8 for region in regions):
                continue
            if len(regions) >= 12:
                break
            regions.append(dict(row, source='ISWDS_AUTOMATIC_UNVERIFIED_PROMPT', target_identity_verified=False))
        semantic = {'status': 'NOT_PROVIDED', 'authoritative': False}
        gate = None
        if receipt is not None:
            try:
                clean = verify_signed_semantic_receipt(receipt, original_image_sha256=digest,
                                                       signing_secret=self.receipt_secret)
                gate = clean['semantic_gate']
                if gate['model'] != 'gemini-3.1-pro-preview':
                    raise ValueError('Unexpected semantic model')
                semantic = {'status': 'AUTHENTICATED_ADVISORY', 'authoritative': False, 'evidence': gate}
            except Exception:
                semantic = {'status': 'INVALID_REJECTED', 'authoritative': False}
                reasons.append('GEMINI_INVALID_RECEIPT')
        if gate is not None and (gate['pipe_visible'] is not True or gate['quality'] != 'OK'
                                 or gate['prompt_image_conflict'] is True):
            reasons.append('SEMANTIC_SCENE_CONFLICT')
        mask_reports = []; overlay = image.copy()
        for index, region in enumerate(regions):
            row = dict(region, region_id=index, mask_status='UNAVAILABLE', geometry={'physical_gap_mm': None})
            try:
                if self.segmenter is None:
                    raise RuntimeError('Not configured')
                with self.segment_lock:
                    evidence = self.segmenter(image, tuple(region['bbox']))
                mask = evidence.mask
                if (evidence.status != 'MASK_CANDIDATE_RESEARCH' or evidence.image_sha256 != pixel_digest
                        or not isinstance(mask, np.ndarray) or mask.shape != (h, w)
                        or not np.isfinite(mask).all() or not np.isin(mask, [0, 255]).all()
                        or evidence.mask_quality_score is None or not np.isfinite(evidence.mask_quality_score)
                        or not .7 <= evidence.mask_quality_score <= 1):
                    raise ValueError('Missing, rejected or cross-image mask')
                ys, xs = np.where(mask > 0)
                if len(xs) < 50 or len(xs) > .75*h*w:
                    raise ValueError('Unsupported mask area')
                box = (int(xs.min()), int(ys.min()), int(xs.max())+1, int(ys.max())+1)
                if evidence.mask_bbox != box or overlap(box, region['bbox']) <= 0:
                    raise ValueError('Mask pixels disagree with region')
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                row.update(mask_status='ACTUAL_MASK_CANDIDATE', mask_png_base64=png(mask),
                           mask_quality_score=evidence.mask_quality_score,
                           mask_sha256=hashlib.sha256(mask.tobytes()).hexdigest(),
                           pixel_geometry={'foreground_area_px': int(len(xs)), 'bbox_extent_px': [box[2]-box[0], box[3]-box[1]],
                                           'contour_perimeter_px': round(sum(cv2.arcLength(c, True) for c in contours), 3),
                                           'meaning': 'SEGMENTED_REGION_EXTENT_NOT_JOINT_GAP_OR_INTRUSION_DEPTH'})
                # Strict signed semantic joint gate; never turn automatic detector
                # proposals into approved joint geometry assignments.
                if (task == 'JOINT_GEOMETRY' and geometry and region['source'] == 'EXPLICIT_RESEARCH_ROI'
                        and gate and gate['processing_allowed'] is True and gate['joint_visible'] is True
                        and gate['domain_status'] == 'PIPE_JOINT_INSPECTION'
                        and gate['quality'] == 'OK' and gate['prompt_image_conflict'] is False):
                    result = combine_inspect_view_and_sam2(image, geometry=geometry,
                                                          inspect_view_payload=baseline, sam2_evidence=evidence)
                    row['geometry'].update(status=result.cv_status, pixel_candidate=result.cv_pixel_candidate,
                                           type=geometry, calibration_verified=False)
                else:
                    row['geometry']['status'] = 'joint_geometry_not_reliable'
                tinted = overlay.copy(); tinted[mask > 0] = (0, 180, 255)
                overlay = cv2.addWeighted(overlay, .65, tinted, .35, 0)
                cv2.drawContours(overlay, contours, -1, (0, 255, 255), 1)
            except Exception:
                row['mask_status'] = 'UNAVAILABLE_OR_REJECTED'
                row['reason'] = 'SEGMENTATION_FAILURE_OR_INVALID_MASK'
            x0, y0, x1, y1 = region['bbox']
            cv2.rectangle(overlay, (x0, y0), (x1-1, y1-1), (255, 150, 0), 1)
            mask_reports.append(row)
        findings = []
        for row in detections:
            label = row.get('jointinspect_candidate')
            if label:
                findings.append({'label': label, 'status': 'PRELIMINARY_RESEARCH_CANDIDATE',
                                 'detector_score': row['score'], 'bbox': row['bbox'],
                                 'active_infiltration_confirmed': False, 'source_label': row['source_label']})
                cls = (baseline or {}).get('classes', {}).get(label, {})
                if cls.get('detected') is False:
                    reasons.append('CLASSIFIER_DETECTOR_DISAGREEMENT:'+label)
        if findings and (baseline or {}).get('classes', {}).get('NORMAL', {}).get('detected') is True:
            reasons.append('NORMAL_CLASSIFIER_DEFECT_DETECTOR_DISAGREEMENT')
        if any(r.get('jointinspect_candidate') == 'INFILTRATION' for r in detections):
            reasons.append('INFILTRATION_REQUIRES_TEMPORAL_OR_FIELD_ADJUDICATION')
        if not regions:
            reasons.append('NO_SUITABLE_REGION_PROPOSAL')
        cv2.putText(overlay, 'RESEARCH / REVIEW REQUIRED / NO MM', (5, 18), cv2.FONT_HERSHEY_SIMPLEX, .4, (0, 0, 255), 1)
        return {'schema_version': '1.0', 'engine': 'jointinspect-sewer-unified-research-v1',
                'image_sha256': digest, 'dimensions': [w, h], 'task': task,
                'decision': 'REVIEW_REQUIRED', 'research_only': True, 'production_eligible': False,
                'engineering_result': None, 'physical_gap_mm': None,
                'components': components, 'gemini': semantic, 'regions': mask_reports,
                'preliminary_findings': findings, 'disagreements_and_limits': sorted(set(reasons)),
                'weak_class_validation': {'OPEN_JOINT': 'UNSUPPORTED', 'PROTRUDING_LATERAL': 'UNSUPPORTED',
                                          'INFILTRATION': 'SOURCE_MODEL_REQUIRES_VERIFIED_CLASS_MAP_AND_JOINTINSPECT_VALIDATION'},
                'baseline_comparison': {'baseline_preserved': baseline is not None,
                                        'additional_detector_regions': len(detections),
                                        'actual_mask_count': sum(r['mask_status'] == 'ACTUAL_MASK_CANDIDATE' for r in mask_reports),
                                        'accuracy_improvement': None, 'verified_ground_truth_available': False},
                'overlay_png_base64': png(overlay)}
