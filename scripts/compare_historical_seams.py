"""Offline forensic comparison; historical code runs with current dependencies.
No performance ranking or physical accuracy claim follows from this smoke test.
"""
import subprocess,types,inspect,json,cv2,hashlib
from pathlib import Path
from backend.app.schemas.domain import JointType
from backend.app.core.cv.ai.independent_seam import measure_image_seam
from backend.app.core.cv.experimental_rough_profile import profile_rough_seam
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--case-root',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
base=args.case_root;out=[]
for case,g,d in [('concrete900','VERTICAL_SEAM',900),('pipe150','HORIZONTAL_SEAM',150)]:
 p=base/case/'original.jpg'
 if not p.exists():
  out.append({'case':case,'status':'ORIGINAL_UNAVAILABLE_NOT_SUBSTITUTED_WITH_OVERLAY'});continue
 im=cv2.imread(str(p))
 if im is None:continue
 h,w=im.shape[:2]
 common={'image_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'dimensions':[w,h],'opencv_version':cv2.__version__}
 for sha in ['abc6810','3d696bf','HEAD']:
  row={**common,'case':case,'commit':sha,'geometry':g,'scope':'HISTORICAL_CODE_WITH_CURRENT_DEPENDENCIES','physical_accuracy_verified':False}
  try:
   source=subprocess.check_output(['git','show',sha+':backend/app/core/cv/seam_detector.py'],text=True)
   module=types.ModuleType('historical_seam');exec(compile(source,'historical_seam','exec'),module.__dict__)
   call_args={'image_bgr':im,'joint_type':JointType(g),'pipe_diameter_mm':d}
   if 'roi_bbox' in inspect.signature(module.measure_seam_gap).parameters:call_args['roi_bbox']=(0,0,w,h)
   result=module.measure_seam_gap(**call_args)
   pixels=result.mean_gap_px
   scale=getattr(result,'pixels_per_mm',None)
   if pixels is None and scale and result.debug_info:
    raw=getattr(result.debug_info,'raw_mean_gap_mm',None)
    if raw is not None:pixels=round(raw*scale,3)
   row.update(status='RETURNED',pixels=pixels,legacy_reported_mm_unverified=result.mean_gap_mm,
       legacy_scale_px_per_mm=scale,physical_scale_verified=False)
  except Exception as e:row.update(status='REJECTED_OR_INCOMPATIBLE',reason=str(e)[:300])
  out.append(row)
 rough=profile_rough_seam(im,g,(0,0,w,h));improved=measure_image_seam(im,g)
 out.extend([{**common,'case':case,'method':'rough_profile','pixels':rough.median_width_px,'status':rough.status},{**common,'case':case,'method':'local_normal','pixels':improved['gap_estimate_px'],'status':improved['status']}])
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
