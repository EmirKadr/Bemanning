"""Demo-användarens sandbox.

Demo-användaren (`username = "demo"`) får vid login en privat SQLite-snapshot
av live-databasen och en privat datakatalog. Alla skrivningar routas dit i
stället för till produktion via `get_db()` (engine-byte) och en `ContextVar`
för filsystem-IO. Vid logout raderas SQLite-filen och datakatalogen så att
nästa demo-session börjar rent.
"""
from __future__ import annotations

import contextvars
import shutil
import tempfile
import threading
import time
import uuid
from pathlib import Path

from fastapi import Request
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from .config import settings
from .models import User
from .sync_live_to_local import sync_database


DEMO_USERNAME = "demo"
DEMO_SESSIONS_ROOT = Path(tempfile.gettempdir()) / "flow_demo_sessions"

_ENGINES_LOCK = threading.Lock()
_ENGINES: dict[str, Engine] = {}

# Filsystem-override per request. Sätts av middleware utifrån sessionens
# demo_session_id, läses av coredata_service och allocation_bridge.
demo_data_root_var: contextvars.ContextVar[Path | None] = contextvars.ContextVar(
    "flow_demo_data_root", default=None
)


def is_demo_user(user: User | None) -> bool:
    if user is None:
        return False
    return str(getattr(user, "username", "") or "").strip().lower() == DEMO_USERNAME


def _session_db_path(demo_session_id: str) -> Path:
    return DEMO_SESSIONS_ROOT / f"{demo_session_id}.sqlite"


def _session_data_root(demo_session_id: str) -> Path:
    return DEMO_SESSIONS_ROOT / demo_session_id / "data"


def session_exists(demo_session_id: str | None) -> bool:
    if not demo_session_id:
        return False
    return _session_db_path(demo_session_id).is_file()


def demo_data_root(demo_session_id: str) -> Path:
    path = _session_data_root(demo_session_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_demo_engine(demo_session_id: str) -> Engine:
    with _ENGINES_LOCK:
        engine = _ENGINES.get(demo_session_id)
        if engine is not None:
            return engine
        db_path = _session_db_path(demo_session_id)
        engine = create_engine(
            f"sqlite:///{db_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        _ENGINES[demo_session_id] = engine
        return engine


def get_demo_session_local(demo_session_id: str):
    engine = get_demo_engine(demo_session_id)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _dispose_engine(demo_session_id: str) -> None:
    with _ENGINES_LOCK:
        engine = _ENGINES.pop(demo_session_id, None)
    if engine is not None:
        try:
            engine.dispose()
        except Exception:
            pass


def start_demo_session(request: Request, user: User) -> str:
    """Skapa en ny demo-session: snapshotta live till privat SQLite + datakatalog."""
    DEMO_SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)
    demo_session_id = uuid.uuid4().hex
    target_path = _session_db_path(demo_session_id)
    target_url = f"sqlite:///{target_path.as_posix()}"
    sync_database(settings.DATABASE_URL, target_url)
    _session_data_root(demo_session_id).mkdir(parents=True, exist_ok=True)
    request.session["demo_session_id"] = demo_session_id
    return demo_session_id


def end_demo_session(request: Request) -> None:
    demo_session_id = request.session.pop("demo_session_id", None)
    if not demo_session_id:
        return
    _dispose_engine(demo_session_id)
    db_path = _session_db_path(demo_session_id)
    try:
        db_path.unlink(missing_ok=True)
    except OSError:
        pass
    data_dir = DEMO_SESSIONS_ROOT / demo_session_id
    if data_dir.exists():
        try:
            shutil.rmtree(data_dir, ignore_errors=True)
        except OSError:
            pass


def cleanup_stale_demo_sessions(max_age_hours: float = 6.0) -> int:
    """Radera demo-sessioner äldre än max_age_hours. Returnerar antal raderade."""
    if not DEMO_SESSIONS_ROOT.exists():
        return 0
    cutoff = time.time() - max_age_hours * 3600.0
    removed = 0
    for entry in DEMO_SESSIONS_ROOT.iterdir():
        try:
            stat = entry.stat()
        except OSError:
            continue
        if stat.st_mtime > cutoff:
            continue
        if entry.is_file():
            try:
                entry.unlink(missing_ok=True)
                removed += 1
                # Dispose-cache så engine inte refererar borttagen fil
                _dispose_engine(entry.stem)
            except OSError:
                pass
        elif entry.is_dir():
            try:
                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
                _dispose_engine(entry.name)
            except OSError:
                pass
    return removed
