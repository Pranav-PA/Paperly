import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.database import migrate
import app.models  # Ensure all SQLAlchemy models are registered
from app.api.v1 import api_v1_router

APP_VERSION = "1.3.0"

logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("paperly")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database tables exist
    migrate()
    settings.ensure_directories()
    if settings.ai_enabled:
        logger.info("Gemini enabled, model: %s", settings.GEMINI_MODEL)
    else:
        logger.warning("GEMINI_API_KEY not set: running in OFFLINE DEMO mode (sample papers only)")
    yield
    # Shutdown logic if needed


app = FastAPI(
    title=settings.APP_NAME,
    description="Paperly — AI-powered question-paper generation and document workspace for educators",
    version=APP_VERSION,
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include v1 endpoints
app.include_router(api_v1_router)

static_path = Path(__file__).resolve().parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    @app.get("/", tags=["UI"])
    @app.get("/preview", tags=["UI"])
    def get_preview():
        """Serve the interactive Paperly rich UI simulator."""
        return FileResponse(str(static_path / "index.html"))


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint to verify backend status and version."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": APP_VERSION,
        "ai_mode": "gemini" if settings.ai_enabled else "demo",
        "model": settings.GEMINI_MODEL if settings.ai_enabled else None,
    }
