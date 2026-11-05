import importlib.util,sys,os
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
root=Path('/workspace/JointInspect')
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,root/path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
load('backend.app.core.cv.ai.preview_gate','backend/app/core/cv/ai/preview_gate.py')
m=load('preview_endpoint_isolated','backend/app/api/v1/endpoints/engineering_preview.py')
app=FastAPI();app.include_router(m.router,prefix='/api/v1/cv');c=TestClient(app)
def post(auth=None):return c.post('/api/v1/cv/engineering-preview',files={'file':('image.png',b'bad','image/png')},headers={'Authorization':auth} if auth else {})
assert post().status_code==404
os.environ['JOINTINSPECT_PREVIEW_ENABLED']='true';os.environ['JOINTINSPECT_PREVIEW_TOKEN']='offline-test-only'
assert post().status_code==401
assert post('Bearer invalid').status_code==401
assert post('Bearer offline-test-only').status_code==422
os.environ['JOINTINSPECT_PREVIEW_MODEL_PATH']='/workspace/dataset-quarantine/r4-r5-comparison/r5-best.pt'
with open('/workspace/dataset-quarantine/r4-r5-comparison/images/00022216.png','rb') as f:
 r=c.post('/api/v1/cv/engineering-preview',files={'file':('image.png',f,'image/png')},headers={'Authorization':'Bearer offline-test-only'})
assert r.status_code==200,r.text
j=r.json();assert j['model_ready'] and j['engineering_result'] is None
assert j['classes']['INFILTRATION']['detected'] is None
assert j['classes']['OPEN_JOINT']['detected'] is None
print('Isolated HTTP smoke passed: disabled/auth/malformed/real inference/gating')
