"""
FastAPI REST API endpoint for the Niblr Agentic Concierge.
This API can be consumed by a React frontend or any HTTP client.
"""

import os
import sys
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Handle imports for both direct execution and package installation
try:
    # Try relative import first (when run as module: python -m api)
    from .src import config
    from .src.endpoints import register_endpoints
    from .src.auth_endpoints import router as auth_router
    from .src.session_endpoints import router as session_router
    from .src.catalog_endpoints import router as catalog_router
    from .src.database import init_db
    # Import models so they're registered with Base.metadata before init_db() is called
    from .src import db_models  # noqa: F401
except ImportError:
    # Fall back to absolute import (when run directly: uv run .)
    # Add parent directory to path if not already there
    api_dir = Path(__file__).parent
    if str(api_dir) not in sys.path:
        sys.path.insert(0, str(api_dir))
    from src import config
    from src.endpoints import register_endpoints
    from src.auth_endpoints import router as auth_router
    from src.session_endpoints import router as session_router
    from src.catalog_endpoints import router as catalog_router
    from src.database import init_db
    # Import models so they're registered with Base.metadata before init_db() is called
    from src import db_models  # noqa: F401

# Initialize FastAPI app
app = FastAPI(
    title="Niblr Agentic Concierge API",
    description="REST API for the Niblr Agentic Concierge chatbot",
    version="1.0.0"
)

# Configure CORS for React frontend
# When allow_credentials=True, you cannot use allow_origins=["*"]
# Must specify exact origins
allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:8080,http://localhost:3000,http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Specific origins (no wildcard when credentials=True)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database (models must be imported before this)
init_db()

# Register all endpoints
register_endpoints(app)
app.include_router(auth_router)
app.include_router(session_router)
app.include_router(catalog_router)


def main():
    """Main entry point for the API server."""
    # Cloud Run sets PORT env var, fallback to API_PORT or 8083
    port = int(os.getenv("PORT", os.getenv("API_PORT", 8083)))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
