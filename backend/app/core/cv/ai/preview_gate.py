"""Offline preview response policy; classification cannot authorize engineering PASS."""
import math

EVALUATED = frozenset({'NORMAL','JOINT_DISPLACEMENT','BROKEN_PIPE','SURFACE_DAMAGE','DEFORMATION'})
UNRELIABLE = frozenset({'INFILTRATION','OBSTACLE'})


def gate_preview(probabilities, thresholds, *, model_version, model_loaded,
                 checksum_verified, geometry_reliable=False):
    ready = bool(model_loaded and checksum_verified)
    classes = {}
    for label in sorted(set(probabilities) | set(thresholds)):
        p, t = probabilities.get(label), thresholds.get(label)
        valid = (isinstance(p, (int,float)) and not isinstance(p,bool) and math.isfinite(p)
                 and 0 <= p <= 1 and isinstance(t,(int,float)) and not isinstance(t,bool)
                 and math.isfinite(t) and 0 <= t <= 1)
        status = ('MODEL_UNAVAILABLE' if not ready else
                  'UNRELIABLE' if label in UNRELIABLE else
                  'UNVALIDATED' if label not in EVALUATED else
                  'INVALID_OUTPUT' if not valid else 'EXPLORATORY')
        classes[label] = {'status':status,'probability':float(p) if ready and valid else None,
                          'detected':bool(p>=t) if status=='EXPLORATORY' else None}
    return {'model_version':model_version,'model_ready':ready,'research_preview':True,
            'review_required':True,'production_approved':False,'classes':classes,
            'geometry_status':'REQUIRES_MEASUREMENT_PIPELINE' if geometry_reliable else 'joint_geometry_not_reliable',
            'engineering_result':None}
