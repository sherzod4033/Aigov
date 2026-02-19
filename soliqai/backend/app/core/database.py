import logging
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

        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise


async def get_session() -> AsyncSession:
    """Get database session with automatic cleanup."""
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_connection() -> bool:
    """Check if database connection is working."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False
