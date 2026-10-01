import logging
import sys
import uuid
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

logger = logging.getLogger("pipe_joint_api")
logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)

# Initialize FastAPI App with conditional documentation in production
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Sub-pixel computer vision inspection API for industrial pipe joints, "
        "circular openings, annular gaps, and seam alignments."
    ),
    version=settings.VERSION,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_DOCS else None,
)

# Configure CORS - Explicit origins only (wildcard strictly disallowed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Attach unique request correlation ID to request state and response headers."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Mount API Routers
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router)  # Also expose directly for backward compatibility


@app.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError):
    """Handle custom value validation errors with clean 400 response."""
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc), "type": "ValueError", "request_id": req_id},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected server errors gracefully without leaking raw exception or system internals."""
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error(f"[REQ-{req_id}] Unhandled server exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "request_id": req_id},
    )


@app.get("/", tags=["Root"])
async def root():
    """Service landing endpoint with operational status."""
    return {
        "service": "Pipe Joint Optical Measurement CV Engine",
        "status": "online",
        "endpoints": {
            "health": "/cv/health",
            "validate_photo": "/cv/validate-photo",
            "measure": "/cv/measure",
        },
    }
