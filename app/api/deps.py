"""Request-scoped dependencies for the FastAPI app."""

from typing import Generator

import httpx
from fastapi import Request
from sqlalchemy.orm import Session

from app.core.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """One session per request; always closed, never committed on error."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_livespace_client(request: Request) -> httpx.AsyncClient:
    """The single shared AsyncClient created in main.py's lifespan — reused
    across requests for connection pooling, not constructed per-request."""
    return request.app.state.livespace_client
