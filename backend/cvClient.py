from typing import Optional, Dict, Any
from fastapi import HTTPException
import requests
import numpy as np

# Constants
CV_WORKER_WARMUP_TIMEOUT_MS = 30000
CV_WORKER_MEASURE_TIMEOUT_MS = 30000

# Type definitions
class CvWorkerRequest:
    def __init__(self, image_id: str, file_name: str, order_index: int, blob: Optional[bytes] = None, pipe_diameter_mm: Optional[float] = None):
        self.image_id = image_id
        self.file_name = file_name
        self.order_index = order_index
        self.blob = blob
        self.pipe_diameter_mm = pipe_diameter_mm

class CvWorkerResponse:
    def __init__(self, image_id: str, original_gap_mm: float, status: str, confidence: float, measurement_source: str, measurement_note: Optional[str] = None, cv_debug: Optional[Dict[str, Any]] = None, overlay_hints: Optional[Dict[str, Any]] = None):
        self.image_id = image_id
        self.original_gap_mm = original_gap_mm
        self.status = status
        self.confidence = confidence
        self.measurement_source = measurement_source
        self.measurement_note = measurement_note
        self.cv_debug = cv_debug
        self.overlay_hints = overlay_hints

async def measure_with_cv(request: CvWorkerRequest) -> CvWorkerResponse:
    """
    Simulates the TypeScript measureWithCv function by calling the FastAPI backend.
    """
    if not request.blob:
        raise ValueError("No image data provided for measurement.")

    try:
        # Prepare the request to the FastAPI backend
        files = {
            'file': (request.file_name, request.blob, 'image/jpeg')
        }
        data = {
            'pipeDiameterMm': str(request.pipe_diameter_mm) if request.pipe_diameter_mm else None
        }

        # Call the FastAPI endpoint
        response = requests.post(
            'http://localhost:8000/process-image',
            files=files,
            data=data,
            timeout=CV_WORKER_WARMUP_TIMEOUT_MS / 1000 + CV_WORKER_MEASURE_TIMEOUT_MS / 1000
        )

        if not response.ok:
            error_data = response.json()
            raise HTTPException(status_code=response.status_code, detail=error_data.get('detail', 'API rejected the image. No pipe detected.'))

        data = response.json()

        # Check if the API successfully processed the measurement
        if data.get('status') == 'success' and data.get('measurements'):
            measurements = data['measurements']
            return CvWorkerResponse(
                image_id=request.image_id,
                original_gap_mm=measurements['originalGapMm'],
                status=measurements['status'],
                confidence=measurements['confidence'],
                measurement_source=measurements['measurementSource'],
                measurement_note=measurements.get('measurementNote'),
                cv_debug=measurements.get('cvDebug'),
                overlay_hints=measurements.get('overlayHints')
            )

        raise HTTPException(status_code=400, detail='API returned unexpected format.')

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f'Backend API is unreachable. Is the Python server running? Error: {str(e)}')
