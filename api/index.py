"""Vercel Serverless Function entry point for Python FastAPI runtime."""

import sys
from pathlib import Path

# Ensure root and backend package are accessible in serverless environment
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

for path_str in [str(ROOT_DIR), str(BACKEND_DIR)]:
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

try:
    from backend.app.main import app
except ImportError:
    from app.main import app

# Export for ASGI handler
__all__ = ["app"]
