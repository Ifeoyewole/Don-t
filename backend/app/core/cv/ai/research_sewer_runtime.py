"""Trusted, cloud-only staging and existing loader reuse. No implicit downloads."""
import os
from functools import lru_cache
from pathlib import Path
import tempfile

from backend.app.core.cv.ai.research_sewer_detector import SewerOnnxDetector, CHECKPOINT_SHA256
from backend.app.core.cv.ai.research_sewer_fusion import SewerFusion

SAM_SHA = '7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69'
R5_SHA = '659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7'


@lru_cache(maxsize=1)
def cloud_service():
    if os.name == 'nt' or os.getenv('JOINTINSPECT_CLOUD_RESEARCH_WORKER') != 'true':
        raise RuntimeError('Dedicated cloud research worker required')
    # This operational acknowledgement cannot establish legal permission.
    if os.getenv('JOINTINSPECT_ISWDS_NONCOMMERCIAL_RESEARCH_ALLOWED') != 'true':
        raise RuntimeError('ISWDS use requires documented noncommercial research permission')
    from google.cloud import storage
    from scripts.cloud.inspect_view_sam2_vertex import stage_verified
    from backend.app.api.v1.endpoints.engineering_preview import infer, load_preview
    from backend.app.core.cv.ai.research_sam2_adapter import propose_sam2_mask, _sam2_predictor
    client = storage.Client(project='joint-inspection-510310')
    temporary = tempfile.TemporaryDirectory(prefix='jointinspect-sewer-research-')
    root = Path(temporary.name)
    failures = {}

    def stage(key, filename, digest):
        uri = os.environ[key]
        if not uri.startswith('gs://joint-inspection-510310-data/models/'):
            raise ValueError('Only existing project model objects allowed')
        path = root/filename
        stage_verified(client, uri, path, digest, max_bytes=512*1024*1024)
        return path

    classifier = infer
    try:
        path = stage('JOINTINSPECT_RESEARCH_R5_URI', 'r5.pt', R5_SHA)
        os.environ['JOINTINSPECT_PREVIEW_MODEL_PATH'] = str(path)
        load_preview.cache_clear()
    except Exception:
        failures['inspect_view'] = 'R5_STAGING_UNAVAILABLE'
        def classifier(_payload):
            raise RuntimeError('R5 staging unavailable')
    detector = None
    try:
        path = stage('JOINTINSPECT_RESEARCH_SEWER_ONNX_URI', 'iswds.onnx', CHECKPOINT_SHA256)
        detector = SewerOnnxDetector.from_verified_cloud_checkpoint(path, cloud_worker=True,
                    threshold=float(os.getenv('JOINTINSPECT_SEWER_DETECTION_THRESHOLD', '.35')),
                    max_regions=int(os.getenv('JOINTINSPECT_SEWER_MAX_REGIONS', '8')))
    except Exception:
        failures['sewer_detector'] = 'CHECKPOINT_OR_EXPORT_CONTRACT_UNAVAILABLE'
    segmenter = None
    try:
        path = stage('JOINTINSPECT_RESEARCH_SAM_URI', 'sam.pt', SAM_SHA)
        predictor = _sam2_predictor(path)
        # Bind the SAM path now; later configuration must not redirect it.
        sam_path = path
        def segmenter(image, box):
            return propose_sam2_mask(image, box, enabled=True, checkpoint_path=sam_path,
                                     expected_sha256=SAM_SHA, predictor_factory=lambda _path: predictor)
        def joint_segmenter(image, box):
            from backend.app.core.cv.ai.joint_gap_recovery import text_exclusion_candidates
            excluded, _ = text_exclusion_candidates(image)
            return propose_sam2_mask(image, box, enabled=True, checkpoint_path=sam_path,
                expected_sha256=SAM_SHA, exclusion_mask=excluded, predictor_factory=lambda _path: predictor)
    except Exception:
        failures['sam2'] = 'SAM_STAGING_OR_INITIALIZATION_UNAVAILABLE'
    secret = None
    resource = os.getenv('JOINTINSPECT_RESEARCH_HMAC_SECRET_RESOURCE')
    if resource:
        try:
            from scripts.cloud.research_semantic_receipts import read_signing_secret
            secret = read_signing_secret(resource)
        except Exception:
            failures['gemini'] = 'RECEIPT_SECRET_UNAVAILABLE'
    service = SewerFusion(classifier=classifier, detector=detector, segmenter=segmenter, receipt_secret=secret)
    if segmenter is not None:
        service.joint_segmenter = joint_segmenter
    service.cloud_temporary_directory = temporary  # retain only for worker lifetime
    service.initialization_failures = failures
    return service


@lru_cache(maxsize=1)
def cloud_reconciler():
    """Vertex-only advisory loader. Never stages classifier/detector/SAM weights."""
    import json
    from backend.app.core.cv.ai.research_gemini_reconciliation import VertexEvidenceReconciler
    from scripts.cloud.research_semantic_receipts import GcsCreateOnlyStore, make_isolated_gate, read_signing_secret
    from scripts.cloud.inspect_view_sam2_vertex import stage_verified
    from google.cloud import storage
    if os.getenv('JOINTINSPECT_PHASE1_VERTEX_ENABLED') != 'true' or os.getenv('JOINTINSPECT_CLOUD_RESEARCH_WORKER') != 'true':
        raise RuntimeError('Dedicated Vertex research worker required')
    uri = os.environ['JOINTINSPECT_PHASE1_SCOPE_URI']
    if not uri.startswith('gs://joint-inspection-510310-data/models/inspect-view/research-results/'):
        raise ValueError('Server-provisioned isolated research scope required')
    client = storage.Client(project='joint-inspection-510310')
    with tempfile.TemporaryDirectory() as tmp:
        target=Path(tmp)/'scope.json'
        stage_verified(client,uri,target,os.environ['JOINTINSPECT_PHASE1_SCOPE_SHA256'],max_bytes=64*1024)
        scope=json.loads(target.read_text())
    store=GcsCreateOnlyStore(client.bucket('joint-inspection-510310-data'),scope['receipt_prefix'])
    secret=read_signing_secret(os.environ['JOINTINSPECT_RESEARCH_HMAC_SECRET_RESOURCE'])
    return VertexEvidenceReconciler(gate=make_isolated_gate(),store=store,scope=scope,secret=secret)


@lru_cache(maxsize=1)
def cloud_phase1_service():
    from backend.app.core.cv.ai.phase1_unified import Phase1Unified
    fusion=cloud_service()
    reconciler=cloud_reconciler() if os.getenv('JOINTINSPECT_PHASE1_VERTEX_ENABLED') == 'true' else None
    return Phase1Unified(fusion=fusion,reconciler=reconciler,
                         max_analysis_passes=reconciler.scope.get('max_analysis_passes',2) if reconciler else 2)
