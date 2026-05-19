from pathlib import Path
import threading

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from . import allocation_bridge
from .config import settings
from .routers import (
    activities,
    allocation,
    areas,
    audit_logs,
    auth,
    bulk,
    overview,
    person_schedules,
    persons,
    productivity,
    public,
    schedule,
    settings as app_settings,
    users,
)

app = FastAPI(title="Bemanningssystem", version="0.1.2")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="bemanning_session",
    https_only=settings.is_production,
    same_site="lax",
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.ENVIRONMENT}


def _sync_allocation_observations_background() -> None:
    try:
        engine_module, _flows_module = allocation_bridge.require_available()
        engine_module.fetch_observations_from_github()
    except Exception:
        return


@app.on_event("startup")
def sync_allocation_observations_on_startup() -> None:
    threading.Thread(
        target=_sync_allocation_observations_background,
        name="AllocationObservationsSync",
        daemon=True,
    ).start()


app.include_router(auth.router)
app.include_router(allocation.router)
app.include_router(areas.router)
app.include_router(activities.router)
app.include_router(audit_logs.router)
app.include_router(persons.router)
app.include_router(person_schedules.router)
app.include_router(schedule.router)
app.include_router(bulk.router)
app.include_router(overview.router)
app.include_router(productivity.router)
app.include_router(app_settings.router)
app.include_router(users.router)
app.include_router(public.router)


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
