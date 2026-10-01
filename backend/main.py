from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import cv2
import numpy as np
from typing import Dict, Any

from classifier import is_pipe
from cv_measurement import run_cv_measurement

app = FastAPI(title="Pipe Measurement API")

# Configure CORS so the React frontend can communicate with it
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Pipe Measurement API is running"}

@app.post("/process-image")
async def process_image(file: UploadFile = File(...)) -> Dict[str, Any]:
    # 1. Read the uploaded image
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image.")

    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
             raise ValueError("Could not decode image.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image format: {str(e)}")

    # 2. Phase 2 - AI Pipe Classification
    if not is_pipe(img):
        raise HTTPException(status_code=400, detail="Invalid image: No pipe detected.")

    # 3. Phase 3 - OpenCV Logic
    # Defaulting to 225mm pipe diameter, this would normally be passed as a query param or form data
    pipe_diameter_mm = 225.0 
    measurements = run_cv_measurement(img, pipe_diameter_mm)

    return {
        "status": "success",
        "message": "Image processed successfully.",
        "measurements": measurements,
        "image_shape": img.shape
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
