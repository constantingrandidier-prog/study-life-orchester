# Study-Life Orchestrator v6.0 (AnkiWeb Hierarchical Tree & 2. SJ Real Slides)
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from app.api.v1.endpoints import router as schedule_router
from app.core.config import settings
from app.auth import check_credentials, create_token, verify_token

STATIC_DIR = Path(__file__).resolve().parent / "static"

import os
import asyncio
from contextlib import asynccontextmanager
from app.services.curriculum_roadmap_service import generate_curriculum_roadmap

async def _anki_live_sync_background():
    """Continuously push local Anki Desktop collection progress to cloud (Render) every 20s or when DB changes."""
    if not os.environ.get("APPDATA"):
        return
    try:
        from bin.anki_sync_agent import sync_now, find_local_anki_collection
        col = find_local_anki_collection()
        last_m = 0
        await asyncio.to_thread(sync_now)
        while True:
            await asyncio.sleep(20)
            try:
                m = col.stat().st_mtime if col and col.exists() else 0
                if m != last_m:
                    last_m = m
                    await asyncio.to_thread(sync_now)
            except Exception:
                pass
    except Exception as e:
        print("Anki live background sync error:", e)

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # Non-blocking pre-warm: opens HTTP socket instantly so health checks & browser never wait
    try:
        asyncio.create_task(asyncio.to_thread(generate_curriculum_roadmap))
        asyncio.create_task(_anki_live_sync_background())
    except Exception as e:
        print("Lifespan startup note:", e)
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

# ---------------------------------------------------------------------------
# Auth middleware — protects only '/' and '/app'
# ---------------------------------------------------------------------------
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """
    Redirect unauthenticated *browser* requests for '/' and '/app' to /login.
    API clients (no text/html in Accept) are never redirected so that JSON
    responses continue to work without a session cookie.
    All other paths (/api/*, /static/*, /auth/*, /login, /docs, /health, …) are unprotected.
    """
    protected_paths = {"/", "/app"}
    path = request.url.path

    if path in protected_paths:
        accept = request.headers.get("accept", "")
        is_browser = "text/html" in accept
        if is_browser:
            token = request.cookies.get("sl_session")
            if not token or not verify_token(token):
                return RedirectResponse(url="/login", status_code=302)

    return await call_next(request)

# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str
    password: str

# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@app.post("/auth/login", tags=["Auth"])
def auth_login(payload: LoginRequest):
    """Validate credentials, set session cookie, return token."""
    if not check_credentials(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = create_token(payload.username)
    response = JSONResponse(content={"token": token})
    response.set_cookie(
        key="sl_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 days
    )
    return response


@app.get("/auth/logout", tags=["Auth"])
def auth_logout():
    """Clear session cookie and redirect to login."""
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("sl_session")
    return response

import time
APP_BOOT_TIMESTAMP = str(int(time.time()))

def no_cache_file_response(path):
    resp = FileResponse(path)
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------
@app.get("/login", tags=["Auth"])
def login_page():
    """Serve the login HTML page."""
    return no_cache_file_response(STATIC_DIR / "login.html")

# ---------------------------------------------------------------------------
# Include API v1 routes
# ---------------------------------------------------------------------------
app.include_router(schedule_router, prefix=settings.api_v1_prefix)

# Mount static frontend directory
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", tags=["Frontend"])
def root(request: Request):
    """Serve web application UI. Returns HTML for browser requests (text/html) and JSON for API clients."""
    accept = request.headers.get("accept", "")
    index_file = STATIC_DIR / "index.html"
    if "text/html" in accept:
        return no_cache_file_response(index_file)
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
    return no_cache_file_response(index_file)


@app.get("/api/v1/system/version", tags=["System"])
def get_system_version():
    """Returns app version, commit, and server boot timestamp for automatic browser reload."""
    commit = os.environ.get("RENDER_GIT_COMMIT", "") or APP_BOOT_TIMESTAMP
    return {
        "version": settings.app_version,
        "commit": commit,
        "boot_timestamp": APP_BOOT_TIMESTAMP,
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Healthcheck endpoint."""
    return {"status": "healthy"}
