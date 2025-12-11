import os
import json
import logging
import asyncpg
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
DATABASE_URL = os.getenv('DATABASE_URL')

# Connection pool for async operations (shared across the application)
_pool = None

async def init_connection(conn):
    """Initialize connection with JSONB codec for automatic serialization/deserialization."""
    await conn.set_type_codec(
        'jsonb',
        encoder=json.dumps,
        decoder=json.loads,
        schema='pg_catalog'
    )

async def get_pool():
    """Get or create the connection pool for async operations."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30.0,
            init=init_connection
        )
    return _pool

@asynccontextmanager
async def get_async_db_connection():
    """Async context manager for database connections using connection pool."""
    pool = await get_pool()
    conn = await pool.acquire()
    transaction = conn.transaction()
    await transaction.start()
    try:
        yield conn
        await transaction.commit()
    except Exception:
        await transaction.rollback()
        raise
    finally:
        await pool.release(conn)

async def init_database():
    """Initialize database tables if they don't exist."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Users table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_user_id BIGINT PRIMARY KEY,
                telegram_username TEXT,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                alpaca_api_key TEXT,
                alpaca_secret_key TEXT,
                openrouter_api_key TEXT,
                operating_framework TEXT
            )
        """)
        
        # Tasks table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                telegram_user_id BIGINT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                ticker_symbol TEXT,
                role TEXT NOT NULL,
                description TEXT NOT NULL,
                task_datetime TIMESTAMP WITH TIME ZONE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                trigger_type TEXT NOT NULL,
                trigger_config JSONB,
                related_note_ids JSONB,
                related_task_ids JSONB,
                related_watchlist_ids JSONB,
                FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id) ON DELETE CASCADE
            )
        """)
        
        # Notes table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                note_id TEXT PRIMARY KEY,
                telegram_user_id BIGINT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                ticker_symbol TEXT,
                topic TEXT NOT NULL,
                role TEXT NOT NULL,
                note TEXT NOT NULL,
                related_note_ids JSONB,
                related_task_ids JSONB,
                related_watchlist_ids JSONB,
                FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id) ON DELETE CASCADE
            )
        """)
        
        # Watchlists table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlists (
                watchlist_id TEXT PRIMARY KEY,
                telegram_user_id BIGINT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                watchlist_name TEXT NOT NULL,
                assets JSONB NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
                FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id) ON DELETE CASCADE
            )
        """)
        
        # Note embeddings table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS note_embeddings (
                note_id TEXT PRIMARY KEY,
                embedding BYTEA NOT NULL,
                FOREIGN KEY (note_id) REFERENCES notes (note_id) ON DELETE CASCADE
            )
        """)

async def close_pool():
    """Close the connection pool on shutdown."""
    global _pool
    if _pool is not None:
        try:
            await _pool.close()
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
        finally:
            _pool = None
