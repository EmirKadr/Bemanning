import sqlite3
from fastapi import APIRouter

from backend.db import DB_PATH

router = APIRouter(prefix="/picking", tags=["picking"])


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/zones")
def get_zone_picks():
    """Return rows_unpicked and qty_unpicked summed per pick_zone."""
    try:
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT pick_zone,"
                " SUM(COALESCE(rows_unpicked, 0)) AS rows_left,"
                " SUM(COALESCE(qty_unpicked,  0)) AS qty_left"
                " FROM v_ask_order_overview"
                " GROUP BY pick_zone"
            ).fetchall()
            return {
                r["pick_zone"]: {
                    "rows": int(r["rows_left"]),
                    "qty":  int(r["qty_left"]),
                }
                for r in rows
                if r["pick_zone"] is not None
            }
        finally:
            conn.close()
    except Exception:
        return {}
