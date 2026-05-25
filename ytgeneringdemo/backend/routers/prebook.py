from fastapi import APIRouter
from pydantic import BaseModel

from backend.db import get_connection
from backend.config_cache import get_config
from backend.utils.pallet import parse_pall, calc_pall
from backend.services import prebook_service

router = APIRouter()


class PrebookWeightUpdate(BaseModel):
    custom_num: int
    day_num: int
    assign_weight: float


@router.get("/prebook")
def get_prebook(day: int):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT ag.agency_alias, p.custom_num, p.day_num, p.custom_desc, p.weight_kg, p.assign_weight, p.pall_required, p.assign_pall, c.orderstop"
            " FROM Prebook p"
            " LEFT JOIN Agency ag ON p.agency_num = ag.agency_num"
            " LEFT JOIN Custom c ON p.custom_num = c.custom_num"
            " WHERE p.day_num = ?"
            " ORDER BY p.assign_weight ASC",
            (day,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.patch("/prebook")
def patch_prebook_weight(body: PrebookWeightUpdate):
    cfg             = get_config()
    prebook_cfg     = cfg.get("prebook", {})
    baseline        = prebook_cfg.get("pall_baseline_kg", 300)
    overrides       = prebook_cfg.get("franchise_overrides", {})

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT franchise FROM Custom WHERE custom_num = ?", (body.custom_num,)
        ).fetchone()
        franchise = row["franchise"] if row else None
        threshold = overrides.get(franchise, baseline) if franchise else baseline

        pall = calc_pall(body.assign_weight, threshold)

        conn.execute(
            "UPDATE Prebook SET assign_weight = ?, assign_pall = ? WHERE custom_num = ? AND day_num = ?",
            (body.assign_weight, pall, body.custom_num, body.day_num),
        )
        conn.commit()
        return {"ok": True, "pall_required": pall}
    finally:
        conn.close()


@router.get("/prebook/missing")
def get_missing_prebook(day: int):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT p.custom_num, p.custom_desc, ag.agency_alias, ag.color,"
            " p.assign_weight, p.assign_pall, c.orderstop,"
            " SUM(CASE WHEN a.location IS NOT NULL THEN COALESCE(l.pall_capacity, 1.0) ELSE 0 END) AS assigned_cap,"
            " GROUP_CONCAT(a.location) AS assigned_locs"
            " FROM Prebook p"
            " JOIN Agency ag ON p.agency_num = ag.agency_num"
            " JOIN Custom c ON p.custom_num = c.custom_num"
            " LEFT JOIN Assignments a ON a.custom_num = p.custom_num AND a.dispatch_day = ? AND a.agency_num IS NOT NULL"
            " LEFT JOIN Locations l ON a.location = l.location"
            " WHERE p.day_num = ?"
            " GROUP BY p.custom_num",
            (day, day),
        ).fetchall()
        result = []
        for r in rows:
            assign_pall = parse_pall(r["assign_pall"])
            assigned_cap = float(r["assigned_cap"] or 0)
            if assigned_cap < assign_pall:
                raw_locs = r["assigned_locs"]
                result.append({
                    "custom_num": r["custom_num"],
                    "custom_desc": r["custom_desc"],
                    "agency_alias": r["agency_alias"],
                    "color": r["color"],
                    "assign_weight": r["assign_weight"],
                    "assign_pall": r["assign_pall"],
                    "orderstop": r["orderstop"],
                    "pall_missing": assign_pall - assigned_cap,
                    "assigned_locs": raw_locs.split(",") if raw_locs else [],
                })
        result.sort(key=lambda x: x["pall_missing"], reverse=True)
        return result
    finally:
        conn.close()


class PrebookImportBody(BaseModel):
    text: str


@router.post("/prebook/import")
def import_prebook(body: PrebookImportBody):
    try:
        return prebook_service.process(body.text)
    except Exception:
        import traceback
        return {"error": traceback.format_exc()}


@router.delete("/prebook")
def clear_prebook(day: int):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM Prebook WHERE day_num = ?", (day,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
