"""Opt-in, token-protected engineering research inference; never measurement authority."""
import hashlib
import hmac
import io
import os
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool
from backend.app.core.cv.ai.preview_gate import gate_preview

router = APIRouter()
EXPECTED_SHA = '659b56baa3e04c30b611c21de85d7ba00abeadc7e2c40dcf801a475719e74ed7'
MODEL_VERSION = 'repr-convnext-masked-r5-20261104'


@lru_cache(maxsize=1)
def load_preview():
    import torch
    from torchvision.models import convnext_tiny
    path = Path(os.environ['JOINTINSPECT_PREVIEW_MODEL_PATH'])
    if hashlib.sha256(path.read_bytes()).hexdigest() != EXPECTED_SHA:
        raise ValueError('Preview checkpoint checksum mismatch')
    checkpoint = torch.load(path, map_location='cpu', weights_only=True)
    if checkpoint['metrics']['architecture'] != 'convnext_tiny':
        raise ValueError('Unexpected architecture')
    labels = checkpoint['labels']
    model = convnext_tiny(weights=None)
    model.classifier[2] = torch.nn.Linear(model.classifier[2].in_features, len(labels))
    model.load_state_dict(checkpoint['model'], strict=True)
    model.eval()
    return model, labels, checkpoint['metrics']['thresholds']


def infer(payload):
    import torch
    from PIL import Image, UnidentifiedImageError
    from torchvision import transforms
    try:
        with Image.open(io.BytesIO(payload)) as image:
            if image.width * image.height > 16_000_000:
                raise HTTPException(413, 'Image dimensions exceed preview limit')
            image.load()
            image = image.convert('RGB')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, 'Unreadable image; review required')
    model, labels, thresholds = load_preview()
    transform = transforms.Compose([transforms.Resize((224,224)), transforms.ToTensor(),
        transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
    with torch.inference_mode():
        probabilities = torch.sigmoid(model(transform(image).unsqueeze(0)))[0].tolist()
    result = gate_preview(dict(zip(labels,probabilities)), thresholds,
        model_version=MODEL_VERSION,model_loaded=True,checksum_verified=True)
    result['image_sha256'] = hashlib.sha256(payload).hexdigest()
    return result


@router.post('/engineering-preview')
async def preview(file: UploadFile = File(...), authorization: str | None = Header(default=None)):
    if os.getenv('JOINTINSPECT_PREVIEW_ENABLED','false').lower() != 'true':
        raise HTTPException(404, 'Engineering preview is disabled')
    token = os.getenv('JOINTINSPECT_PREVIEW_TOKEN','')
    if not token:
        raise HTTPException(503, 'Engineering preview access is not configured')
    if not authorization or not hmac.compare_digest(authorization, 'Bearer '+token):
        raise HTTPException(401, 'Engineering preview authentication required')
    payload = await file.read(8 * 1024 * 1024 + 1)
    if len(payload) > 8 * 1024 * 1024:
        raise HTTPException(413, 'Preview image exceeds 8 MiB')
    try:
        return await run_in_threadpool(infer, payload)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Preview model unavailable; review required')
