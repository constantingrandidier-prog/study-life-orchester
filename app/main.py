# Study-Life Orchestrator v6.0 (AnkiWeb Hierarchical Tree & 2. SJ Real Slides)
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.api.v1.endpoints import router as schedule_router
from app.core.config import settings

STATIC_DIR = Path(__file__).resolve().parent / "static"

from contextlib import asynccontextmanager
from app.services.curriculum_roadmap_service import generate_curriculum_roadmap

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # Pre-warm curriculum roadmap in background so requests respond in <5ms
    try:
        generate_curriculum_roadmap()
    except Exception as e:
        print("Roadmap pre-warm note:", e)
    yield

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Student Daily Orchestrator API & Web Application.\n\n"
        "Analyzes university calendar schedules, parses iCal/ICS & Google Calendar formats, "
        "manages manual activities, analyzes local Anki Desktop decks & AnkiWeb, and orchestrates optimal study sessions."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for frontend clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 routes
app.include_router(schedule_router, prefix=settings.api_v1_prefix)

# Mount static frontend directory
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", tags=["Frontend"])
def root(request: Request):
    """Serve web application UI to browsers or API status to API clients."""
    accept = request.headers.get("accept", "")
    ua = request.headers.get("user-agent", "").lower()
    index_file = STATIC_DIR / "index.html"
    is_browser = any(b in ua for b in ["mozilla", "safari", "chrome", "edge", "iphone", "android", "mobile"])
    if index_file.exists() and (("text/html" in accept or "text/*" in accept) or (is_browser and "application/json" not in accept)):
        return FileResponse(index_file)
    return {
        "status": "online",
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "quick_test": f"{settings.api_v1_prefix}/schedule/today",
    }


@app.get("/app", tags=["Frontend"])
def app_view():
    """Direct URL to open the Web UI in any browser."""
    index_file = STATIC_DIR / "index.html"
    return FileResponse(index_file)


@app.get("/health", tags=["Health"])
def health_check():
    """Healthcheck endpoint."""
    return {"status": "healthy"}
