import os
import sqlite3
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DATABASE_PATH = os.getenv('DATABASE_PATH')

@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enable column access by name
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_database():
    """Initialize database tables if they don't exist."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_user_id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL,
                alpaca_api_key TEXT,
                alpaca_secret_key TEXT,
                openrouter_api_key TEXT
            )
        """)
        
        # Tasks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                telegram_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                ticker_symbol TEXT,
                role TEXT NOT NULL,
                description TEXT NOT NULL,
                task_datetime TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                trigger_type TEXT NOT NULL,
                trigger_config TEXT,
                related_note_ids TEXT,
                related_task_ids TEXT,
                related_watchlist_ids TEXT,
                FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id)
            )
        """)
        
        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_user_active 
            ON tasks(telegram_user_id, is_active)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_active_datetime 
            ON tasks(is_active, task_datetime)
        """)
        
        # Notes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                note_id TEXT PRIMARY KEY,
                telegram_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                ticker_symbol TEXT,
                topic TEXT NOT NULL,
                role TEXT NOT NULL,
                note TEXT NOT NULL,
                related_note_ids TEXT,
                related_task_ids TEXT,
                related_watchlist_ids TEXT,
                FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id)
            )
        """)
        
        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_user 
            ON notes(telegram_user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_ticker 
            ON notes(ticker_symbol)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_topic 
            ON notes(topic)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notes_created_at 
            ON notes(created_at)
        """)
        
        # Watchlists table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlists (
                watchlist_id TEXT PRIMARY KEY,
                telegram_user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                watchlist_name TEXT NOT NULL,
                assets TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (telegram_user_id) REFERENCES users (telegram_user_id)
            )
        """)
        
        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watchlists_user 
            ON watchlists(telegram_user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_watchlists_name 
            ON watchlists(telegram_user_id, watchlist_name)
        """)
        
        # Note embeddings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS note_embeddings (
                note_id TEXT PRIMARY KEY,
                embedding BLOB NOT NULL,
                FOREIGN KEY (note_id) REFERENCES notes (note_id)
            )
        """)
        
        conn.commit()

