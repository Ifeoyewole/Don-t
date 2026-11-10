"""ISWDS RT-DETR v2 ONNX research adapter. Never production/engineering authority.

Only graph-embedded label IDs are used. The model card's table order is not
an inference class map. Weights must already be checksum-verified in a cloud
worker; constructor never downloads checkpoints or guesses output layouts.
"""
from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import threading

import cv2
import numpy as np

MODEL_ID = 'ISWDS_RT-DETR_v2_model.onnx'
REVISION = 'ffe32890eee1fba794d7a22486289562b118e574'
CHECKPOINT_SHA256 = '1afdfd5b1f39dcd9f927b3ac25662487d3ac2e7fe823d7322b1065a7e887bb3b'
SOURCE = 'https://huggingface.co/mogurlu/Istanbul_Sewer_Defect_Dataset_ISWDS_Models'
# Exact textual mappings only; absent/ambiguous labels remain unmapped.
LABELS = {'infiltration': 'INFILTRATION', 'displaced joint': 'JOINT_DISPLACEMENT',
          'pipe surface damage': 'SURFACE_DAMAGE', 'roots': 'OBSTACLE',
          'intruding sealing material': 'OBSTACLE', 'attached deposits': 'OBSTACLE',
          'settled deposits': 'OBSTACLE'}


def overlap(a, b):
    area = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    union = (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-area
    return area/union if union else 0.0


@dataclass(frozen=True)
class SewerDetection:
    bbox: tuple[int, int, int, int]
    score: float
    source_class_id: int
    source_label: str
    jointinspect_candidate: str | None

    def json(self):
        return asdict(self)


class SewerOnnxDetector:
    def __init__(self, session, *, threshold=.35, max_regions=8):
        if type(threshold) not in (float, int) or not np.isfinite(threshold) or not 0 < threshold <= 1:
            raise ValueError('Invalid confidence threshold')
        if type(max_regions) is not int or not 1 <= max_regions <= 12:
            raise ValueError('Invalid region limit')
        inputs = session.get_inputs()
        by_name = {item.name: item for item in inputs}
        self.export_layout = 'RAW_NORMALIZED'
        self.target_size_input = None
        if len(inputs) == 2 and set(by_name) == {'images', 'orig_target_sizes'}:
            self.export_layout = 'POSTPROCESSED_ABSOLUTE'
            image_input = by_name['images']
            target = by_name['orig_target_sizes']
            if target.type not in ('tensor(int64)', 'tensor(int32)') or target.shape[-1:] != [2]:
                raise ValueError('Unsupported target-size input')
            self.target_size_input = target
            if {out.name for out in session.get_outputs()} != {'labels', 'boxes', 'scores'}:
                raise ValueError('Unsupported postprocessed outputs')
        elif len(inputs) == 1:
            image_input = inputs[0]
        else:
            raise ValueError('Unsupported ONNX input contract')
        if image_input.type != 'tensor(float)':
            raise ValueError('Float32 image tensor required')
        shape = image_input.shape
        if len(shape) != 4 or (shape[0] != 1 and not isinstance(shape[0], str)) or shape[1] != 3 or any(type(v) is not int or not 32 <= v <= 2048 for v in shape[2:]):
            raise ValueError('Unsupported ONNX image contract')
        meta = session.get_modelmeta().custom_metadata_map
        raw_names = meta.get('names')
        names = {}
        if raw_names is not None:
            if not isinstance(raw_names, str) or len(raw_names) > 8192:
                raise ValueError('Invalid graph label metadata')
            try:
                names = ast.literal_eval(raw_names)
            except (ValueError, SyntaxError) as exc:
                raise ValueError('Unverified graph class IDs') from exc
            if (not isinstance(names, dict) or len(names) != 8 or set(names) != set(range(8))
                    or any(not isinstance(v, str) or not v or len(v) > 150 for v in names.values())):
                raise ValueError('Expected eight graph-declared defect classes')
        if self.export_layout == 'RAW_NORMALIZED' and not names:
            raise ValueError('Raw export requires verified graph class count and labels')
        self.session, self.names = session, names
        self.input_name = image_input.name
        self.input_height, self.input_width = shape[2:]
        self.threshold, self.max_regions = float(threshold), max_regions
        self.lock = threading.Lock()

    @classmethod
    def from_verified_cloud_checkpoint(cls, path, *, cloud_worker=False, **kwargs):
        import os
        if not cloud_worker or os.name == 'nt':
            raise ValueError('Cloud research worker required; no workstation weight loading')
        path = Path(path)
        hasher = hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda: handle.read(1024*1024), b''):
                hasher.update(block)
        if hasher.hexdigest() != CHECKPOINT_SHA256:
            raise ValueError('ISWDS official checkpoint SHA-256 mismatch')
        import onnxruntime as ort
        session = ort.InferenceSession(str(path), providers=['CPUExecutionProvider'])
        return cls(session, **kwargs)

    def predict(self, image_bgr):
        if (not isinstance(image_bgr, np.ndarray) or image_bgr.dtype != np.uint8
                or image_bgr.ndim != 3 or image_bgr.shape[2] != 3):
            raise ValueError('Expected original BGR uint8 frame')
        height, width = image_bgr.shape[:2]
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        # RT-DETR exported predictor uses scale-fill, not YOLO letterboxing.
        resized = cv2.resize(rgb, (self.input_width, self.input_height), interpolation=cv2.INTER_LINEAR)
        tensor = np.ascontiguousarray(resized.transpose(2, 0, 1)[None], dtype=np.float32)/255.0
        feed = {self.input_name: tensor}
        if self.target_size_input is not None:
            dtype = np.int64 if self.target_size_input.type == 'tensor(int64)' else np.int32
            feed[self.target_size_input.name] = np.array([[height, width]], dtype=dtype)
        with self.lock:
            outputs = self.session.run(None, feed)
        candidates = []
        if self.export_layout == 'POSTPROCESSED_ABSOLUTE':
            result = dict(zip([out.name for out in self.session.get_outputs()], outputs))
            labels, boxes, scores = [np.asarray(result[key]) for key in ('labels', 'boxes', 'scores')]
            if (len(outputs) != 3 or labels.ndim != 2 or labels.shape[0] != 1
                    or scores.shape != labels.shape or boxes.shape != (*labels.shape, 4)
                    or labels.shape[1] > 10000):
                raise ValueError('Unsupported postprocessed detector dimensions')
            if not all(np.isfinite(v).all() for v in (labels, boxes, scores)):
                raise ValueError('Nonfinite detector output')
            for cls, box, score in zip(labels[0], boxes[0], scores[0]):
                if int(cls) != cls or cls < 0 or cls > 10000 or not 0 <= score <= 1:
                    raise ValueError('Invalid class ID or probability')
                candidates.append((int(cls), box, float(score)))
        else:
            if len(outputs) != 1:
                raise ValueError('Unsupported export output count')
            raw = np.asarray(outputs[0])
            if raw.ndim != 3 or raw.shape[0] != 1 or raw.shape[2] != 4+len(self.names) or raw.shape[1] > 10000:
                raise ValueError('Unsupported RT-DETR export layout; do not guess')
            if not np.isfinite(raw).all() or np.any(raw[..., 4:] < 0) or np.any(raw[..., 4:] > 1):
                raise ValueError('Invalid detector probability output')
            for row in raw[0]:
                cls = int(np.argmax(row[4:])); score = float(row[4+cls])
                cx, cy, bw, bh = map(float, row[:4])
                if not all(0 <= v <= 1 for v in (cx, cy, bw, bh)) or bw <= 0 or bh <= 0:
                    continue
                candidates.append((cls, [(cx-bw/2)*width, (cy-bh/2)*height,
                                         (cx+bw/2)*width, (cy+bh/2)*height], score))
        detections = []
        for cls, raw_box, score in candidates:
            if score < self.threshold:
                continue
            box = (max(0, int(np.floor(raw_box[0]))), max(0, int(np.floor(raw_box[1]))),
                   min(width, int(np.ceil(raw_box[2]))), min(height, int(np.ceil(raw_box[3]))))
            if box[2]-box[0] < 24 or box[3]-box[1] < 24:
                continue
            name = self.names.get(cls, 'UNVERIFIED_SOURCE_CLASS_ID_'+str(cls))
            detections.append(SewerDetection(box, score, cls, name, LABELS.get(name.casefold().strip())))
        selected = []
        for row in sorted(detections, key=lambda d: (-d.score, d.source_class_id, d.bbox)):
            if any(row.source_class_id == other.source_class_id and overlap(row.bbox, other.bbox) >= .7 for other in selected):
                continue
            selected.append(row)
            if len(selected) == self.max_regions:
                break
        return selected

    def provenance(self):
        return {'model_id': MODEL_ID, 'source': SOURCE, 'revision': REVISION,
                'checkpoint_sha256': CHECKPOINT_SHA256, 'source_classes': self.names,
                'threshold': self.threshold, 'license': 'fair-noncommercial-research-license',
                'production_eligible': False, 'class_order_source': 'ONNX_GRAPH_METADATA' if self.names else 'UNAVAILABLE_NO_CLASS_MAPPING',
                'output_contract': self.export_layout,
                'preprocessing': 'RGB_SCALE_FILL_FLOAT32_0_1',
                'open_joint_supported': False, 'protruding_lateral_supported': False,
                'infiltration': 'VISUAL_CANDIDATE_ONLY_NOT_ACTIVE_INGRESS_PROOF'}
