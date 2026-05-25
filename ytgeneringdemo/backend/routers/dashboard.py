import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException

from backend.db import DB_PATH

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_LOADER_PATH = Path(__file__).parent.parent.parent / "data" / "database" / "import" / "loader.py"


@router.post("/import-wms")
def dashboard_import_wms():
    """Run the WMS loader (auto-detect mode)."""
    result = subprocess.run(
        [sys.executable, str(_LOADER_PATH)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise HTTPException(500, result.stderr or "Loader failed")
    return {"ok": True, "output": result.stdout}


@router.post("/clear-wms")
def clear_wms_tables():
    """Delete all rows from every table whose name starts with v_ask."""
    conn = _conn()
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master"
            " WHERE type='table' AND name LIKE 'v_ask%'"
        ).fetchall()
        cleared = []
        for t in tables:
            conn.execute(f'DELETE FROM "{t["name"]}"')
            cleared.append(t["name"])
        conn.commit()
        return {"ok": True, "cleared": cleared}
    finally:
        conn.close()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/overview")
def overview_metrics():
    try:
        conn = _conn()
        try:
            customers_unique = conn.execute(
                "SELECT COUNT(DISTINCT custom_desc) FROM v_ask_order_overview"
            ).fetchone()[0]
            wd = datetime.now().weekday()
            day_col = ["mon","tue","wed","thu","fri"][wd if wd < 5 else 4]
            customers_total = conn.execute(
                f"SELECT COUNT(*) FROM Custom WHERE {day_col} LIKE '%S%'"
            ).fetchone()[0]
            _GROUPS = (
                "COUNT(DISTINCT CASE"
                "  WHEN multi IS NOT NULL AND multi != '' THEN multi"
                "  ELSE order_num"
                " END)"
            )
            orders_a = conn.execute(
                f"SELECT COUNT(DISTINCT order_num), {_GROUPS}"
                " FROM v_ask_order_overview WHERE pick_zone = 'A'"
            ).fetchone()
            orders_o = conn.execute(
                f"SELECT COUNT(DISTINCT order_num), {_GROUPS}"
                " FROM v_ask_order_overview WHERE pick_zone = 'O'"
            ).fetchone()
            rows_a = conn.execute(
                "SELECT COUNT(*) FROM v_ask_customer_order_details_all"
                " WHERE line_status = 30 AND pick_zone = 'A'"
                "   AND NOT ("
                "     (pick_location_f_pick_location IS NULL OR pick_location_f_pick_location = '')"
                "     AND item_robot_ind = 'Y'"
                "   )"
            ).fetchone()[0]
            rows_o = conn.execute(
                "SELECT COUNT(*) FROM v_ask_customer_order_details_all"
                " WHERE line_status = 30 AND pick_zone = 'O'"
            ).fetchone()[0]
            groups_a = orders_a[1] or 0
            groups_o = orders_o[1] or 0
            avg_a = round(rows_a / groups_a, 1) if groups_a else 0
            avg_o = round(rows_o / groups_o, 1) if groups_o else 0
            return {
                "customers_unique": int(customers_unique),
                "customers_total":  int(customers_total),
                "orders_a":         int(orders_a[0]),
                "orders_o":         int(orders_o[0]),
                "avg_rows_a":       avg_a,
                "avg_rows_o":       avg_o,
            }
        finally:
            conn.close()
    except Exception:
        return {"customers": 0, "orders_a": 0, "orders_o": 0}


@router.get("/departures")
def departure_metrics():
    """
    Returns rows left per load_start time, broken down by pick zone.
    Uses the same metrics as the main zone cards:
      A: line_status = 30, excl. ungenerated Autostore rows
      O: line_status = 30
      R: line_status = 33 (genererade)
    Excludes 07:00 (ecommerce slot).

    Response format:
    [
        { "load_start": "2026-04-15 08:00:00", "zones": {"A": 89, "O": 12, "R": 5} },
        ...
    ]
    """
    _NO07 = "o.load_start NOT LIKE '%07:00%'"
    _BASE = (
        " FROM v_ask_customer_order_details_all d"
        " JOIN (SELECT DISTINCT order_num, load_start FROM v_ask_order_overview) o"
        "   ON d.order_num = o.order_num"
        " WHERE o.load_start IS NOT NULL AND o.load_start != ''"
        f"  AND {_NO07}"
    )
    try:
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT o.load_start, 'A' AS pick_zone, COUNT(*) AS rows_left"
                + _BASE +
                "  AND d.line_status = 30 AND d.pick_zone = 'A'"
                "  AND NOT ("
                "    (d.pick_location_f_pick_location IS NULL OR d.pick_location_f_pick_location = '')"
                "    AND d.item_robot_ind = 'Y'"
                "  )"
                " GROUP BY o.load_start"
                " UNION ALL"
                " SELECT o.load_start, 'O' AS pick_zone, COUNT(*) AS rows_left"
                + _BASE +
                "  AND d.line_status = 30 AND d.pick_zone = 'O'"
                " GROUP BY o.load_start"
                " UNION ALL"
                " SELECT o.load_start, 'R' AS pick_zone, COUNT(*) AS rows_left"
                + _BASE +
                "  AND d.line_status = 33 AND d.pick_zone = 'R'"
                " GROUP BY o.load_start"
                " UNION ALL"
                " SELECT o.load_start, 'H' AS pick_zone, COUNT(*) AS rows_left"
                + _BASE +
                "  AND d.line_status IN (32, 34) AND d.pick_zone = 'H'"
                " GROUP BY o.load_start"
            ).fetchall()
            from collections import defaultdict
            by_time: dict = defaultdict(dict)
            for r in rows:
                by_time[r["load_start"]][r["pick_zone"]] = int(r["rows_left"])
            return [
                {"load_start": t, "zones": z}
                for t, z in sorted(by_time.items())
            ]
        finally:
            conn.close()
    except Exception:
        return []


@router.get("/autostore")
def autostore_metrics():
    """
    Returns Autostore row counts:
    - generated:   line_status = 33 (assigned to Autostore, ready to pick)
    - ungenerated: line_status = 30, pick_zone = 'A', no pick location or item_robot_ind = 'Y'

    Response: { "generated": 342, "ungenerated": 89 }
    """
    _UGEN = (
        " line_status = 30"
        " AND pick_zone = 'A'"
        " AND (pick_location_f_pick_location IS NULL OR pick_location_f_pick_location = '')"
        " AND item_robot_ind = 'Y'"
    )
    try:
        conn = _conn()
        try:
            gen  = conn.execute(
                "SELECT COUNT(*) FROM v_ask_customer_order_details_all"
                " WHERE line_status = 33"
            ).fetchone()[0]
            ugen = conn.execute(
                f"SELECT COUNT(*) FROM v_ask_customer_order_details_all WHERE {_UGEN}"
            ).fetchone()[0]
            ecom = conn.execute(
                "SELECT COUNT(*) FROM v_ask_customer_order_details_all"
                " WHERE line_status = 33"
                " AND custom_desc LIKE 'E-handelskund%'"
            ).fetchone()[0]
            return {"generated": int(gen), "ungenerated": int(ugen), "ecommerce": int(ecom)}
        finally:
            conn.close()
    except Exception:
        return {"generated": 0, "ungenerated": 0}


@router.get("/zones")
def zone_metrics():
    """
    Returns rows left to pick and qty (kolli) per pick zone.
    Only counts lines with line_status = 30 (to pick).
    Excludes ungenerated Autostore rows from zone A (those have no pick location
    or item_robot_ind = 'Y' — they belong to the Autostore card instead).

    Response format:
    {
        "A": { "rows": 1666, "qty": 13110 },
        ...
    }
    """
    try:
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT d.pick_zone,"
                "       COUNT(*) AS rows_left,"
                "       CAST(COALESCE(SUM(d.diff), 0) AS INTEGER) AS qty_left,"
                "       CAST(COALESCE(SUM(d.diff * i.weight_gross), 0) AS INTEGER) AS weight_total"
                " FROM v_ask_customer_order_details_all d"
                " LEFT JOIN v_ask_item i ON d.item_num = i.item_desc"
                " WHERE d.line_status = 30"
                "   AND d.pick_zone IS NOT NULL AND d.pick_zone != ''"
                "   AND d.pick_zone != 'H'"
                "   AND NOT ("
                "     d.pick_zone = 'A'"
                "     AND (d.pick_location_f_pick_location IS NULL OR d.pick_location_f_pick_location = '')"
                "     AND d.item_robot_ind = 'Y'"
                "   )"
                " GROUP BY d.pick_zone"
            ).fetchall()
            h_row = conn.execute(
                "SELECT COUNT(*) AS rows_left,"
                "       COUNT(DISTINCT custom_desc) AS customers_left"
                " FROM v_ask_customer_order_details_all"
                " WHERE line_status IN (32, 34)"
                "   AND pick_zone = 'H'"
            ).fetchone()
            result = {
                r["pick_zone"]: {
                    "rows":   int(r["rows_left"]),
                    "qty":    int(r["qty_left"]),
                    "weight": int(r["weight_total"]),
                }
                for r in rows
            }
            refill_row = conn.execute(
                "SELECT COUNT(*) FROM ("
                "  SELECT pick_location_f_pick_location"
                "  FROM v_ask_customer_order_details_all"
                "  WHERE line_status = 30 AND pick_zone = 'A'"
                "    AND pick_location_f_pick_location IS NOT NULL"
                "    AND pick_location_f_pick_location != ''"
                "  GROUP BY pick_location_f_pick_location"
                "  HAVING SUM(qty_pre) > MAX(qty)"
                ")"
            ).fetchone()
            result["H"] = {
                "rows":     int(h_row["rows_left"]),
                "customers": int(h_row["customers_left"]),
                "refills":  int(refill_row[0]),
            }
            return result
        finally:
            conn.close()
    except Exception:
        return {}


@router.get("/departure-details")
def departure_details():
    """
    Returns agencies and customers grouped by departure time.
    Excludes 07:00 (ecommerce slot).

    Response format:
    [
        {
            "load_start": "10:00",
            "agencies": [
                {
                    "agency": "DHL",
                    "customers": [
                        { "custom_desc": "ICA Maxi", "rows": 42 },
                        ...
                    ]
                },
                ...
            ]
        },
        ...
    ]
    """
    try:
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT o.load_start, o.agency_desc, o.custom_desc,"
                "       d.pick_zone,"
                "       COUNT(*) AS rows_left"
                " FROM v_ask_customer_order_details_all d"
                " JOIN (SELECT DISTINCT order_num, load_start, agency_desc, custom_desc"
                "       FROM v_ask_order_overview) o"
                "   ON d.order_num = o.order_num"
                " WHERE o.load_start IS NOT NULL AND o.load_start != ''"
                "   AND o.load_start NOT LIKE '%07:00%'"
                "   AND d.line_status IN (30, 32, 33, 34)"
                "   AND d.pick_zone IN ('A','O','R','H')"
                " GROUP BY o.load_start, o.agency_desc, o.custom_desc, d.pick_zone"
                " ORDER BY o.load_start, o.agency_desc, o.custom_desc"
            ).fetchall()

            from collections import OrderedDict
            by_time: dict = OrderedDict()
            for r in rows:
                ls = r["load_start"]
                time_str = ls.split(" ")[1][:5] if " " in ls else ls[:5]
                ag = r["agency_desc"] or "Okänd"
                cd = r["custom_desc"] or "Okänd"
                zone = r["pick_zone"]
                rl = int(r["rows_left"])

                if time_str not in by_time:
                    by_time[time_str] = OrderedDict()
                if ag not in by_time[time_str]:
                    by_time[time_str][ag] = OrderedDict()
                if cd not in by_time[time_str][ag]:
                    by_time[time_str][ag][cd] = {"A": 0, "O": 0, "R": 0, "H": 0}
                by_time[time_str][ag][cd][zone] += rl

            return [
                {
                    "load_start": t,
                    "agencies": [
                        {
                            "agency": ag,
                            "customers": [
                                {"custom_desc": cd, "zones": zones}
                                for cd, zones in custs.items()
                            ],
                        }
                        for ag, custs in agencies.items()
                    ],
                }
                for t, agencies in by_time.items()
            ]
        finally:
            conn.close()
    except Exception:
        return []
