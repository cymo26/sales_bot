"""
Asynchronous Database Connection Setup for SALES_BOT
Configures async PostgreSQL engine and session management for FastAPI
"""

import os
import ssl
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from fastapi import Depends


# Load environment variables from .env file
load_dotenv()

# Environment configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://user:password@localhost:5432/sales_bot"
)



# Remove ?sslmode=require from URL if present (asyncpg handles SSL via connect_args)
if "?sslmode=" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?")[0]

# SSL context for Neon connections
# For development: disable certificate verification
# For production: use verify_mode=ssl.CERT_REQUIRED with proper certificates
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Create async engine for PostgreSQL
# Using asyncpg driver for true async support
# NullPool prevents connection pooling issues in async contexts
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "False").lower() == "true",  # Enable SQL logging if needed
    future=True,
    pool_pre_ping=True,  # Test connections before using them
    poolclass=NullPool,  # Avoids connection pooling overhead in async
    connect_args={"ssl": ssl_context},  # SSL configuration for Neon
)


# Create async sessionmaker
# This factory will create AsyncSession instances
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevents lazy-loading issues in async
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncSession:
    """
    Dependency function for FastAPI to inject AsyncSession into routes.
    
    Usage in routes:
        @app.get("/")
        async def my_route(session: AsyncSession = Depends(get_session)):
            # Use session for queries
            pass
    
    Yields:
        AsyncSession: An async database session
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


# ============================================================================
# SYNCHRONOUS DATABASE SETUP (for Streamlit and other sync contexts)
# ============================================================================
DATABASE_URL_SYNC = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

engine_sync = create_engine(
    DATABASE_URL_SYNC,
    echo=os.getenv("SQL_ECHO", "False").lower() == "true",
    pool_pre_ping=True,
    connect_args={"sslmode": "require"} if "neon" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(
    bind=engine_sync,
    autocommit=False,
    autoflush=False,
)


def get_session_sync():
    """
    Synchronous session generator for Streamlit and other sync contexts.
    
    Usage in Streamlit:
        session = next(get_session_sync())
        try:
            # Use session for queries
            pass
        finally:
            session.close()
    
    Yields:
        Session: A synchronous database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
