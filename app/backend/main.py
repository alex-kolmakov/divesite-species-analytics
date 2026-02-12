"""Marine Species Explorer — FastAPI application."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .db import close_db, init_db
from .routers import divesites, species

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Startup: load Parquet → DuckDB.  Shutdown: close connection."""
    logger.info("Starting up — loading data into DuckDB…")
    init_db()
    logger.info("Data loaded — ready to serve requests")
    yield
    close_db()


app = FastAPI(
    title="Marine Species Explorer",
    version="1.0.0",
    lifespan=lifespan,
)

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
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(
            STATIC_DIR / "index.html",
            headers={"Cache-Control": "no-cache, must-revalidate"},
        )
