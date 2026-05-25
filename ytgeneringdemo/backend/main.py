import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from backend.routers import assignments, locations, config_router, prebook, agencies, exports, database, picking, dashboard
from backend.db import init_db, trim_changelog

BASE_DIR = Path(__file__).parent.parent


async def _daily_trim():
    trim_changelog()
    while True:
        await asyncio.sleep(24 * 60 * 60)
        trim_changelog()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(_daily_trim())
    yield
    task.cancel()


app = FastAPI(title="Location Assigner", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=500)

app.mount("/static", StaticFiles(directory=BASE_DIR / "frontend" / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "frontend" / "templates")

app.include_router(assignments.router, prefix="/api")
app.include_router(locations.router, prefix="/api")
app.include_router(config_router.router, prefix="/api")
app.include_router(prebook.router, prefix="/api")
app.include_router(agencies.router, prefix="/api")
app.include_router(exports.router, prefix="/api")
app.include_router(database.router, prefix="/api")
app.include_router(picking.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/map")
def map_page(request: Request):
    return templates.TemplateResponse(request, "map.html")


@app.get("/database")
def database_page(request: Request):
    return templates.TemplateResponse(request, "database.html")
