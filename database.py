import sqlite3
import os
import logging
from pathlib import Path

# SQLite Database file path
DATABASE_FILE = 'processed_files.db'

# Create the database and table if they don't exist
def init_db():
    try:
        db_path = os.getenv('DB_PATH', os.path.join(str(Path(__file__).parent), 'data', 'obsidian_email.db'))
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS processed_files
            (file_path TEXT PRIMARY KEY, processed_at TIMESTAMP)
        ''')
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Database initialization failed: {e}")
        return False

def is_file_processed(file_path: str) -> bool:
    db_path = os.getenv('DB_PATH', os.path.join(str(Path(__file__).parent), 'data', 'obsidian_email.db'))
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM processed_files WHERE file_path = ?", (file_path,))
        return cursor.fetchone() is not None

def mark_file_processed(file_path: str):
    db_path = os.getenv('DB_PATH', os.path.join(str(Path(__file__).parent), 'data', 'obsidian_email.db'))
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO processed_files (file_path) VALUES (?)", (file_path,))
        conn.commit()
