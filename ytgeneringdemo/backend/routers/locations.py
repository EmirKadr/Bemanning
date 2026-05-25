from fastapi import APIRouter
from backend.db import get_connection

router = APIRouter()


@router.get("/locations")
def get_locations():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT location, x, y, w, h FROM Locations WHERE x IS NOT NULL"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
