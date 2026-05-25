import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DB_PATH = Path(os.environ["ASSIGN_DB_PATH"]) if "ASSIGN_DB_PATH" in os.environ else BASE_DIR / "data" / "database" / "Database.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def trim_changelog(keep: int = 800) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM LocChangelog WHERE rowid NOT IN"
            " (SELECT rowid FROM LocChangelog ORDER BY rowid DESC LIMIT ?)",
            (keep,),
        )
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_assignments_day
                ON Assignments(dispatch_day);
            CREATE INDEX IF NOT EXISTS idx_assignments_loc_day
                ON Assignments(location, dispatch_day);
            CREATE INDEX IF NOT EXISTS idx_changelog_day_ts
                ON LocChangelog(dispatch_day, timestamp);
            CREATE INDEX IF NOT EXISTS idx_prebook_custom_day
                ON Prebook(custom_num, day_num);
            CREATE INDEX IF NOT EXISTS idx_prebook_day
                ON Prebook(day_num);
        """)
        conn.commit()
    finally:
        conn.close()
