"""FastAPI Application Entry Point for Pipe Joint Computer Vision QA System."""

import sys
from pathlib import Path
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure proper module resolution across local dev, Docker, and Vercel serverless
CURRENT_FILE = Path(__file__).resolve()
APP_DIR = CURRENT_FILE.parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

for p in [str(PROJECT_ROOT), str(BACKEND_DIR), str(APP_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from backend.app.config import settings
    from backend.app.api.v1.api_router import api_router
except ImportError:
    from app.config import settings
    from app.api.v1.api_router import api_router

# Initialize FastAPI App
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Sub-pixel computer vision inspection API for industrial pipe joints, "
        "circular openings, annular gaps, and seam alignments."
    ),
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure CORS for frontend integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router)  # Also expose directly for convenience


@app.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError):
    """Handle custom value validation errors with clean 400 response."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc), "type": "ValueError"},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected server errors gracefully."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": f"Internal server error: {str(exc)}", "type": "InternalServerError"},
    )


@app.get("/", tags=["Root"])
async def root():
    """Service landing endpoint with API discovery links."""
    return {
        "service": "Pipe Joint Optical Measurement CV Engine",
        "status": "online",
        "docs": "/docs",
        "endpoints": {
            "health": "/cv/health",
            "validate_photo": "/cv/validate-photo",
            "measure": "/cv/measure",
        },
    }
