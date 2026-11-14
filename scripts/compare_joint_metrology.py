"""Reproduce CPU-only geometry on original images; no models or cloud calls."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
from backend.app.core.cv.ai.independent_seam import measure_image_seam
from backend.app.core.cv.ai.joint_gap_recovery import text_exclusion_candidates
from backend.app.core.cv.ai.research_joint_boundaries import draw_boundaries
from backend.app.core.cv.experimental_rough_profile import profile_rough_seam
from backend.app.core.cv.seam_detector import measure_seam_gap
from backend.app.schemas.domain import JointType


def compare(image_path,geometry,nominal,output):
    original=Path(image_path).read_bytes();image=cv2.imread(str(image_path))
    if image is None:raise ValueError('Original image cannot be decoded')
    h,w=image.shape[:2];excluded,boxes=text_exclusion_candidates(image)
    result=measure_image_seam(image,geometry,exclusion=excluded);result['text_exclusion_boxes']=boxes
    rough=profile_rough_seam(image,geometry,(0,0,w,h))
    try:
        legacy=measure_seam_gap(image,joint_type=JointType(geometry),roi_bbox=(0,0,w,h))
        baseline={'status':str(legacy.result_status),'mean_gap_px':legacy.mean_gap_px,'physical_gap_mm':None}
    except ValueError as exc:baseline={'status':'REJECTED','reason':str(exc),'physical_gap_mm':None}
    report={'image_sha256':hashlib.sha256(original).hexdigest(),'dimensions':[w,h],
        'nominal_pipe_diameter_mm':nominal,'scene_validation':'NOT_RUN_NO_MODELS',
        'execution':'CPU_GEOMETRY_ONLY_NOT_FIVE_MODEL_INFERENCE',
        'physical_gap_mm':None,'calibration_status':'NO_VERIFIED_IMAGE_SCALE',
        'baseline':baseline,'rough_profile':{'status':rough.status,'median_width_px':rough.median_width_px,'coverage':rough.coverage},
        'improved':result,'defect_identity':'UNVERIFIED','engineering_result':'REVIEW_REQUIRED'}
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    (out/'geometry-report.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    canvas=draw_boundaries(image.copy(),result)
    cv2.putText(canvas,'PIXEL DIAGNOSTICS - NO VERIFIED MM SCALE',(8,28),cv2.FONT_HERSHEY_SIMPLEX,.55,(0,0,255),2)
    cv2.imwrite(str(out/'boundary-overlay.png'),canvas)
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True);parser.add_argument('--geometry',choices=['VERTICAL_SEAM','HORIZONTAL_SEAM'],required=True)
    parser.add_argument('--nominal-pipe-diameter-mm',type=float,required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();r=compare(args.image,args.geometry,args.nominal_pipe_diameter_mm,args.output)
    print(json.dumps({'pixel_candidate':r['improved']['gap_estimate_px'],'physical_gap_mm':None,'baseline':r['baseline']}))
