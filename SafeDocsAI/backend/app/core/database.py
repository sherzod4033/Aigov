import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from app.core.config import settings

logger = logging.getLogger(__name__)

# Echo SQL queries only in development
engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=settings.ENVIRONMENT == "development",
    future=True,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=300,  # Recycle connections after 5 minutes
)

async_session_factory = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db():
    """Initialize database tables."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

            # Backward-compatible schema update for deployments that already
            # have the chunk table without this column.
            await conn.execute(
                text(
                    """
                    ALTER TABLE IF EXISTS chunk
                    ADD COLUMN IF NOT EXISTS chunk_index INTEGER
                    """
                )
            )

            await conn.execute(
                text(
                    """
                    ALTER TABLE IF EXISTS document
                    ADD COLUMN IF NOT EXISTS notebook_id INTEGER REFERENCES notebook(id)
                    """
                )
            )

            await conn.execute(
                text(
                    """
                    ALTER TABLE IF EXISTS log
                    ADD COLUMN IF NOT EXISTS notebook_id INTEGER REFERENCES notebook(id)
                    """
                )
            )

            await conn.execute(
                text(
                    """
                    ALTER TABLE IF EXISTS log
                    ADD COLUMN IF NOT EXISTS domain_profile VARCHAR(50)
                    """
                )
            )

            # Fill missing chunk indexes for old rows so ordering-dependent
            # features continue working after upgrades.
            await conn.execute(
                text(
                    """
                    WITH ranked AS (
                        SELECT
                            id,
                            ROW_NUMBER() OVER (PARTITION BY doc_id ORDER BY id) - 1 AS rn
                        FROM chunk
                    )
                    UPDATE chunk c
                    SET chunk_index = ranked.rn
                    FROM ranked
                    WHERE c.id = ranked.id AND c.chunk_index IS NULL
                    """
                )
            )

            await conn.execute(
                text(
                    """
                    INSERT INTO notebook (name, description, domain_profile, owner_id, created_at)
                    SELECT 'Imported Tax Notebook', 'Migrated default notebook for existing sources', 'tax', NULL, NOW()
                    WHERE NOT EXISTS (SELECT 1 FROM notebook)
                    """
                )
            )

            await conn.execute(
                text(
                    """
                    WITH default_notebook AS (
                        SELECT id FROM notebook ORDER BY id LIMIT 1
                    )
                    UPDATE document
                    SET notebook_id = (SELECT id FROM default_notebook)
                    WHERE notebook_id IS NULL
                    """
                )
            )

            await conn.execute(
                text(
                    """
                    UPDATE log
                    SET domain_profile = COALESCE(domain_profile, 'tax')
                    WHERE domain_profile IS NULL
                    """
                )
            )

            await conn.execute(
                text(
                    """
                    ALTER TABLE IF EXISTS note
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE
                    """
                )
            )

            await conn.execute(
                text(
                    """
                    UPDATE note
                    SET updated_at = COALESCE(updated_at, created_at, NOW())
                    WHERE updated_at IS NULL
                    """
                )
            )

            await conn.execute(
                text(
                    """
                    ALTER TABLE IF EXISTS insight
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE
                    """
                )
            )

            await conn.execute(
                text(
                    """
                    UPDATE insight
                    SET updated_at = COALESCE(updated_at, created_at, NOW())
                    WHERE updated_at IS NULL
                    """
                )
            )

        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise


@asynccontextmanager
async def session_context() -> AsyncIterator[AsyncSession]:
    """Get database session with automatic cleanup."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency for request-scoped database sessions."""
    async with session_context() as session:
        yield session


async def check_database_connection() -> bool:
    """Check if database connection is working."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
