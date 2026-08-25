"""FastAPI entry point.

Run with:
    uvicorn app.api.main:app --reload --port 8000

CORS is open to the Vite dev server origins by default; set
FRONTEND_ORIGIN in .env for a deployed frontend.
"""

import os
from contextlib import asynccontextmanager

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import service, service_livespace
from app.api.routers import companies, import_, leads, livespace
from app.core.config import settings
from app.core.database import SessionLocal

load_dotenv()

_DEFAULT_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One-shot schema fixes + legacy status migration, same as the Streamlit
    # app's queries.bootstrap(). Logged, not fatal — individual endpoints
    # still fail loudly on their own if the DB is truly unreachable.
    db = SessionLocal()
    try:
        service.bootstrap(db)
    except Exception as e:
        print(f"[startup] bootstrap skipped: {e}")
    finally:
        db.close()

    # Shared client: one AsyncClient (connection pooling) for both the
    # manual "Odśwież" refresh endpoint and the background sweep below, so
    # total concurrency against Livespace is bounded by one semaphore
    # regardless of which path triggered a call (see service_livespace.py).
    app.state.livespace_client = httpx.AsyncClient()

    scheduler = None
    if settings.livespace_enabled:
        async def _livespace_sweep():
            db = SessionLocal()
            try:
                result = await service_livespace.sync_stale_leads_batch(db, app.state.livespace_client)
                print(f"[livespace-sweep] {result}")
            except Exception as e:
                print(f"[livespace-sweep] failed: {e}")
            finally:
                db.close()

        scheduler = AsyncIOScheduler()
        scheduler.add_job(_livespace_sweep, "interval", minutes=settings.livespace_sweep_interval_minutes)
        scheduler.start()

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await app.state.livespace_client.aclose()


app = FastAPI(title="SALES BOT API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "")] + _DEFAULT_ORIGINS if os.getenv("FRONTEND_ORIGIN") else _DEFAULT_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leads.router)
app.include_router(companies.router)
app.include_router(import_.router)
app.include_router(livespace.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
