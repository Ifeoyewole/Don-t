"""Small research artifacts: actual runtime counters, never invented mask evidence."""
from pathlib import Path
import hashlib


def runtime_diagnostics(torch_module=None):
    result={'process_peak_rss_kib':None,'cuda_available':False,'gpu_memory':None,'gpu_memory_scope':'PROCESS_SINCE_CUDA_INITIALIZATION'}
    try:
        import resource
        result['process_peak_rss_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except ImportError: pass
    try:
        if torch_module is None:import torch as torch_module
        result['torch_version']=str(torch_module.__version__)
        result['cuda_available']=bool(torch_module.cuda.is_available())
        if result['cuda_available']:
            result['gpu_memory']={'device':str(torch_module.cuda.get_device_name(0)),
                'allocated_bytes':int(torch_module.cuda.memory_allocated()),
                'reserved_bytes':int(torch_module.cuda.memory_reserved()),
                'peak_allocated_bytes':int(torch_module.cuda.max_memory_allocated())}
    except Exception as exc:result['diagnostic_error_type']=type(exc).__name__
    return result


def write_verified_candidate_mask(sam,image,path,accepted):
    """Export only same-frame pixel evidence already accepted as research candidate."""
    import cv2,numpy as np
    from scripts.task_aware_unified_review import mask_matches_source_pixels
    if not accepted or not mask_matches_source_pixels(sam,image):return None
    mask=((sam.mask>0).astype(np.uint8)*255)
    ok,encoded=cv2.imencode('.png',mask)
    if not ok:raise ValueError('Mask encoding failed')
    payload=encoded.tobytes()
    with Path(path).open('xb') as stream:stream.write(payload)
    return {'kind':'UNVERIFIED_RESEARCH_SEGMENTATION_CANDIDATE','sha256':hashlib.sha256(payload).hexdigest(),
            'width':int(mask.shape[1]),'height':int(mask.shape[0]),'nonzero_pixels':int(np.count_nonzero(mask)),
            'defect_identity_verified':False,'physical_measurement_authorized':False}
