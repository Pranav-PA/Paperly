from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.database import engine, Base
import app.models  # Ensure all SQLAlchemy models are registered
from app.api.v1 import api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure database tables exist
    Base.metadata.create_all(bind=engine)
    settings.ensure_directories()
    yield
    # Shutdown logic if needed


app = FastAPI(
    title=settings.APP_NAME,
    description="Paperly — AI-powered question-paper generation and document workspace for educators",
    version="1.0.0",
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
        "version": "1.0.0"
    }
