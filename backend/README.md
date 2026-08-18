# Pipe Joint Optical Measurement & Tolerance QA Backend

A high-precision, sub-pixel Computer Vision backend built with **FastAPI** and **OpenCV** for automated pipe joint inspection, circular opening annular gap profiling, and longitudinal seam QA.

---

## 🌟 Key Features

- **Multi-Joint Geometry Support**:
  - `CIRCULAR_OPENING`: Vectorized polar unwrap (`cv2.warpPolar`) with sub-pixel radial ray profiling across $360^\circ$.
  - `HORIZONTAL_SEAM` & `VERTICAL_SEAM`: Directional Sobel edge gradient filtering and sub-pixel parabolic peak fitting along scanlines.
- **Automated Image Quality Pre-Flight**:
  - Sharpness check via Laplacian variance.
  - Exposure assessment (underexposure / overexposure).
  - Specular glare and hot-spot detection on reflective metallic pipe surfaces.
  - Real-time inspector feedback recommendations.
- **Standardized Tolerance Engine**:
  - Built-in Pipe Engineering Tolerance Table:
    - `< 3.0 mm`: `REVIEW` (Gap too narrow / risk of binding)
    - `3.0 - 15.0 mm`: `PASS` (Optimal clearance)
    - `15.0 - 25.0 mm`: `REVIEW` (Marginal / wide gap)
    - `> 25.0 mm`: `FAIL` (Out of specification / seal defect)
  - Custom `ToleranceSpec` support with nominal, min, max, and warning margin buffers.
- **Sub-Pixel Precision**: Parabolic peak interpolation and outlier rejection using Median Absolute Deviation (MAD).
- **Interactive Visualization HUD**: Base64 JPEG overlay generation with color-coded measurement vectors and live HUD metrics.
- **Cloud-Ready**: Zero-config Vercel Serverless (`api/index.py` + `vercel.json`) and multi-stage production `Dockerfile`.

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- Python 3.10+ or Python 3.11
- Virtual environment tool (`venv` or `conda`)

### 2. Installation
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Run Development Server
```bash
uvicorn backend.app.main:app --reload --port 8000
```
- Interactive Swagger UI Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Interactive ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Health Check: [http://localhost:8000/cv/health](http://localhost:8000/cv/health)

---

## 🧪 Running Automated Tests

Run the full unit and integration test suite:
```bash
pytest backend/tests -v
```

---

## 📡 API Reference

### 1. `GET /cv/health`
Checks backend operational status and OpenCV library version.
**Response**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "opencv_version": "4.9.0.80",
  "timestamp": "2026-08-18T00:00:00Z"
}
```

### 2. `POST /cv/validate-photo`
Evaluates photo sharpness, luminance, and specular glare.
**Parameters** (Multipart Form):
- `file`: Uploaded inspection photo (JPEG/PNG/WebP)
- `blur_threshold`: Optional float (default: 100.0)
- `min_brightness`: Optional float (default: 45.0)
- `max_brightness`: Optional float (default: 215.0)

**Response**:
```json
{
  "blur_score": 248.5,
  "is_blurry": false,
  "mean_brightness": 124.8,
  "exposure_status": "OK",
  "glare_percentage": 0.4,
  "glare_detected": false,
  "is_acceptable": true,
  "recommendations": []
}
```

### 3. `POST /cv/measure`
Performs computer vision gap profiling and QA classification.
**Parameters** (Multipart Form):
- `file`: Uploaded inspection image (required)
- `joint_type`: `CIRCULAR_OPENING` | `HORIZONTAL_SEAM` | `VERTICAL_SEAM` (default: `CIRCULAR_OPENING`)
- `pipe_diameter_mm`: Reference pipe diameter in mm (default: `100.0`)
- `nominal_gap_mm`: Optional float (default: `10.0`)
- `min_gap_mm`: Optional float (default: `3.0`)
- `max_gap_mm`: Optional float (default: `15.0`)
- `warning_margin_mm`: Optional float (default: `2.0`)
- `return_debug_image`: boolean (default: `true`)
- `num_samples`: Optional int (rays or scanlines count)

---

## 🐳 Docker Deployment

Build and run the multi-stage container:
```bash
docker build -t pipe-cv-backend -f backend/Dockerfile .
docker run -p 8000:8000 pipe-cv-backend
```

---

## ☁️ Vercel Serverless Deployment

Deploy directly using Vercel CLI:
```bash
vercel --prod
```
The serverless bridge in `api/index.py` routes incoming `/api/*` and `/cv/*` requests directly to FastAPI.
