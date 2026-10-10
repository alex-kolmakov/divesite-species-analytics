"""Dive Diversity — FastAPI application."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import close_db, init_db
from .routers import divesites, species

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# The tables are loaded once at startup, so an API answer stays the same until the next deploy.
# An hour lets browsers (and Cloudflare, with a cache rule for /api/) skip the 5 MB dive site list.
API_CACHE_CONTROL = "public, max-age=3600"


def resolve_static(static_dir: Path, requested: str) -> Path | None:
    """The file inside static_dir that a request path names, or None.

    The path comes straight from the URL: `..` segments and a leading `/` (which replaces the
    base in a Path join) must not reach files outside static_dir.
    """
    candidate = (static_dir / requested).resolve()
    if candidate.is_relative_to(static_dir.resolve()) and candidate.is_file():
        return candidate
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup: load Parquet → DuckDB.  Shutdown: close connection."""
    logger.info("Starting up — loading data into DuckDB…")
    init_db()
    logger.info("Data loaded — ready to serve requests")
    yield
    close_db()


app = FastAPI(
    title="Dive Diversity",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def cache_api_answers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    response = await call_next(request)
    path = request.url.path
    if request.method == "GET" and response.status_code == 200 and path.startswith("/api/") and path != "/api/health":
        response.headers["Cache-Control"] = API_CACHE_CONTROL
    return response


# --- API routers -------------------------------------------------------
app.include_router(species.router)
app.include_router(divesites.router)


@app.get("/api/health")
def health() -> dict:
    """Simple liveness check."""
    return {"status": "ok"}


# --- Static / SPA fallback ---------------------------------------------
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        """Serve index.html for any non-API route (SPA client-side routing)."""
        file_path = resolve_static(STATIC_DIR, full_path)
        if file_path:
            return FileResponse(file_path)
        return FileResponse(
            STATIC_DIR / "index.html",
            headers={"Cache-Control": "no-cache, must-revalidate"},
        )
