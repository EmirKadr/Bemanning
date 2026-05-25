import csv
import io
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from backend.db import get_connection
from backend.config_cache import get_config
from backend.models.assignment import AssignmentResult
from backend.services import assign_service

router = APIRouter()


@router.post("/assignments/run", response_model=AssignmentResult)
def run_assignments(day: int, orderstop: str, lock: bool = False):
    try:
        return assign_service.run(day, orderstop, lock)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/assignments")
def get_assignments(day: int):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT a.location, a.agency_num, a.custom_num, ag.agency_alias, c.custom_desc"
            " FROM Assignments a"
            " LEFT JOIN Agency ag ON a.agency_num = ag.agency_num"
            " LEFT JOIN Custom c ON a.custom_num = c.custom_num"
            " LEFT JOIN Locations l ON a.location = l.location"
            " WHERE a.dispatch_day = ? AND a.agency_num IS NOT NULL"
            " ORDER BY l.location_seq",
            (day,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


class ReleaseRequest(BaseModel):
    locations: List[str]
    day: int


@router.post("/assignments/release")
def release_assignments(body: ReleaseRequest):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        lp = ",".join("?" * len(body.locations))
        before_rows = conn.execute(
            f"SELECT location, status_id, agency_num, custom_num FROM Assignments"
            f" WHERE location IN ({lp}) AND dispatch_day = ?",
            (*body.locations, body.day),
        ).fetchall()

        conn.execute(
            f"UPDATE Assignments SET agency_num=NULL, custom_num=NULL, status_id=1"
            f" WHERE location IN ({lp}) AND dispatch_day = ?",
            (*body.locations, body.day),
        )

        changelog = [
            (r["location"], r["status_id"], r["custom_num"], r["agency_num"], ts, body.day)
            for r in before_rows
            if r["agency_num"] is not None or r["custom_num"] is not None
        ]
        if changelog:
            conn.executemany(
                "INSERT INTO LocChangelog (location, status_id, custom_num, agency_num, timestamp, dispatch_day)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                changelog,
            )
        conn.commit()
        return {"released": len(body.locations)}
    finally:
        conn.close()


@router.post("/assignments/clear")
def clear_assignments(day: int):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        before_rows = conn.execute(
            "SELECT location, status_id, agency_num, custom_num FROM Assignments"
            " WHERE dispatch_day = ? AND agency_num IS NOT NULL",
            (day,),
        ).fetchall()

        conn.execute(
            "UPDATE Assignments SET agency_num=NULL, custom_num=NULL, status_id=1"
            " WHERE dispatch_day = ? AND agency_num IS NOT NULL",
            (day,),
        )

        if before_rows:
            conn.executemany(
                "INSERT INTO LocChangelog (location, status_id, custom_num, agency_num, timestamp, dispatch_day)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [(r["location"], r["status_id"], r["custom_num"], r["agency_num"], ts, day)
                 for r in before_rows],
            )
        conn.commit()
        return {"cleared": len(before_rows)}
    finally:
        conn.close()


@router.post("/assignments/undo")
def undo_assignments(day: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT MAX(timestamp) as ts FROM LocChangelog WHERE dispatch_day = ?",
            (day,),
        ).fetchone()
        ts = row["ts"] if row else None

        if not ts:
            return {"undone": 0}

        entries = conn.execute(
            "SELECT location, status_id, agency_num, custom_num FROM LocChangelog"
            " WHERE dispatch_day = ? AND timestamp = ?",
            (day, ts),
        ).fetchall()

        conn.executemany(
            "UPDATE Assignments SET agency_num=?, custom_num=?, status_id=?"
            " WHERE location=? AND dispatch_day=?",
            [(e["agency_num"], e["custom_num"], e["status_id"], e["location"], day)
             for e in entries],
        )

        conn.execute(
            "DELETE FROM LocChangelog WHERE dispatch_day = ? AND timestamp = ?",
            (day, ts),
        )
        conn.commit()
        return {"undone": len(entries)}
    finally:
        conn.close()


class SwapRequest(BaseModel):
    loc_a: str
    loc_b: str
    day: int


@router.post("/assignments/swap")
def swap_assignments(body: SwapRequest):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        row_a = conn.execute(
            "SELECT status_id, agency_num, custom_num FROM Assignments WHERE location=? AND dispatch_day=?",
            (body.loc_a, body.day),
        ).fetchone()
        row_b = conn.execute(
            "SELECT status_id, agency_num, custom_num FROM Assignments WHERE location=? AND dispatch_day=?",
            (body.loc_b, body.day),
        ).fetchone()

        if not row_a or not row_b:
            raise HTTPException(status_code=404, detail="Location not found")

        for loc, row in [(body.loc_a, row_a), (body.loc_b, row_b)]:
            conn.execute(
                "INSERT INTO LocChangelog (location, status_id, custom_num, agency_num, timestamp, dispatch_day)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (loc, row["status_id"], row["custom_num"], row["agency_num"], ts, body.day),
            )

        conn.execute(
            "UPDATE Assignments SET agency_num=?, custom_num=?, status_id=?"
            " WHERE location=? AND dispatch_day=?",
            (row_a["agency_num"], row_a["custom_num"], row_a["status_id"], body.loc_b, body.day),
        )
        conn.execute(
            "UPDATE Assignments SET agency_num=?, custom_num=?, status_id=?"
            " WHERE location=? AND dispatch_day=?",
            (row_b["agency_num"], row_b["custom_num"], row_b["status_id"], body.loc_a, body.day),
        )
        conn.commit()
        return {"swapped": [body.loc_a, body.loc_b]}
    finally:
        conn.close()


class ManualAssignRequest(BaseModel):
    locations: List[str]
    day: int
    custom_num: int


@router.post("/assignments/manual")
def manual_assign(body: ManualAssignRequest):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT agency_num FROM Custom WHERE custom_num = ?",
            (body.custom_num,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Customer not found")
        agency_num = row["agency_num"]

        lp = ",".join("?" * len(body.locations))
        before_rows = conn.execute(
            f"SELECT location, status_id, agency_num, custom_num FROM Assignments"
            f" WHERE location IN ({lp}) AND dispatch_day = ?",
            (*body.locations, body.day),
        ).fetchall()

        conn.executemany(
            "UPDATE Assignments SET agency_num=?, custom_num=?, status_id=2"
            " WHERE location=? AND dispatch_day=?",
            [(agency_num, body.custom_num, loc, body.day) for loc in body.locations],
        )

        changelog = [
            (r["location"], r["status_id"], r["custom_num"], r["agency_num"], ts, body.day)
            for r in before_rows
        ]
        if changelog:
            conn.executemany(
                "INSERT INTO LocChangelog (location, status_id, custom_num, agency_num, timestamp, dispatch_day)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                changelog,
            )
        conn.commit()
        return {"assigned": len(body.locations)}
    finally:
        conn.close()


@router.post("/assignments/import-ask")
async def import_from_ask(day: int, file: UploadFile = File(...)):
    """Import assignments from an uploaded WMS dispatch_area CSV."""
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.reader(io.StringIO(content), delimiter="\t")
    next(reader)
    csv_rows = list(reader)

    conn = get_connection()
    try:
        loc_rows = conn.execute(
            "SELECT location, area_num, area_alt_num FROM Locations"
        ).fetchall()
        area_to_loc = {}
        for r in loc_rows:
            area_to_loc[r["area_num"]] = r["location"]
            area_to_loc[r["area_alt_num"]] = r["location"]

        cust_rows = conn.execute(
            "SELECT custom_num, agency_num FROM Custom"
        ).fetchall()
        custom_to_agency = {}
        for r in cust_rows:
            custom_to_agency[r["custom_num"]] = r["agency_num"]

        placeholder_dag = ((day - 2) % 5) + 1

        assignments = []
        skipped = 0
        seen_locs = set()

        for row in csv_rows:
            if len(row) < 18:
                continue
            area_nr = row[0].strip()
            kund_raw = row[4].strip()
            dispatch_dag_raw = row[16].strip()

            if not kund_raw:
                continue

            try:
                custom_num = int(kund_raw)
            except ValueError:
                skipped += 1
                continue

            try:
                csv_day = int(dispatch_dag_raw)
            except ValueError:
                skipped += 1
                continue

            if csv_day == placeholder_dag:
                if not area_nr.endswith("B"):
                    continue
            elif csv_day != day:
                continue

            location = area_to_loc.get(area_nr)
            if not location:
                skipped += 1
                continue

            if location in seen_locs:
                skipped += 1
                continue
            seen_locs.add(location)

            agency_num = custom_to_agency.get(custom_num)
            if not agency_num:
                skipped += 1
                continue

            assignments.append((location, agency_num, custom_num))

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        import_locs = {loc for loc, _, _ in assignments}
        assigned_rows = conn.execute(
            "SELECT location, status_id, agency_num, custom_num FROM Assignments"
            " WHERE dispatch_day = ? AND agency_num IS NOT NULL",
            (day,),
        ).fetchall()
        assigned_locs = {r["location"] for r in assigned_rows}

        new_locs = import_locs - assigned_locs
        empty_rows = []
        if new_locs:
            lp = ",".join("?" * len(new_locs))
            empty_rows = conn.execute(
                f"SELECT location, status_id, agency_num, custom_num FROM Assignments"
                f" WHERE location IN ({lp}) AND dispatch_day = ?",
                (*new_locs, day),
            ).fetchall()

        all_before = list(assigned_rows) + list(empty_rows)
        if all_before:
            conn.executemany(
                "INSERT INTO LocChangelog (location, status_id, custom_num, agency_num, timestamp, dispatch_day)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [(r["location"], r["status_id"], r["custom_num"], r["agency_num"], ts, day)
                 for r in all_before],
            )

        conn.execute(
            "UPDATE Assignments SET agency_num=NULL, custom_num=NULL, status_id=1"
            " WHERE dispatch_day = ? AND agency_num IS NOT NULL",
            (day,),
        )

        if assignments:
            conn.executemany(
                "UPDATE Assignments SET agency_num=?, custom_num=?, status_id=2"
                " WHERE location=? AND dispatch_day=?",
                [(ag, cn, loc, day) for loc, ag, cn in assignments],
            )

        conn.commit()
        return {
            "imported": len(assignments),
            "skipped": skipped,
            "file": file.filename,
        }
    finally:
        conn.close()


@router.get("/assignments/all")
def get_all_assignments(day: int):
    config = get_config()
    zones = config.get("zones", [])
    zone_cond = " OR ".join("(l.location_seq BETWEEN ? AND ?)" for _ in zones)
    zone_params = [v for z in zones for v in (z["seq_min"], z["seq_max"])]

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT l.location, l.location_seq, a.agency_num, a.custom_num,"
            " ag.agency_alias, c.custom_desc, p.assign_weight, p.assign_pall"
            " FROM Locations l"
            " LEFT JOIN Assignments a ON l.location = a.location AND a.dispatch_day = ?"
            " LEFT JOIN Agency ag ON a.agency_num = ag.agency_num"
            " LEFT JOIN Custom c ON a.custom_num = c.custom_num"
            " LEFT JOIN Prebook p ON a.custom_num = p.custom_num AND p.day_num = ?"
            f" WHERE l.location IS NOT NULL AND ({zone_cond})"
            " ORDER BY l.location_seq",
            (day, day, *zone_params),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
