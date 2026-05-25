import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.db import get_connection

router = APIRouter()


@router.get("/assignments/export-ask")
def export_ask(day: int, placeholder: int = 0):
    area_set_number = day if placeholder == 0 else ((day - 2) % 5) + 1
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT CASE WHEN ? = 0 THEN l.area_num ELSE l.area_alt_num END AS area_num,"
            " a.custom_num, ag.agency_alias"
            " FROM Assignments a"
            " JOIN Locations l ON a.location = l.location"
            " LEFT JOIN Agency ag ON a.agency_num = ag.agency_num"
            " WHERE a.dispatch_day = ? AND a.agency_num IS NOT NULL",
            (placeholder, day),
        ).fetchall()
    finally:
        conn.close()

    lines = ["area_number;area_set_number;custom_num;notes"]
    for row in rows:
        alias = row["agency_alias"] or ""
        note = f"B {alias}" if placeholder == 1 else alias
        lines.append(f"{row['area_num']};{area_set_number};{row['custom_num']};{note}")
    content = "\n".join(lines) + "\n"

    filename = "dispatch_area_dispatcharea_change_customer_execute_command.csv"
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/assignments/export-tider-for-kund")
def export_tider_for_kund():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT c.custom_num, ag.agency_asn, ag.agency_depart"
            " FROM Custom c"
            " LEFT JOIN Agency ag ON c.agency_num = ag.agency_num"
        ).fetchall()
    finally:
        conn.close()

    lines = ["custom_num\tday_num\tarrive\tcompletion\tdepart\torder_time\ttime\tcompany\twareh_num"]
    for row in rows:
        arrive = f"2009-01-01  {row['agency_asn']}" if row["agency_asn"] else ""
        depart = f"2009-01-01  {row['agency_depart']}" if row["agency_depart"] else ""
        for day_num in range(1, 6):
            lines.append(f"{row['custom_num']}\t{day_num}\t{arrive}\t\t{depart}\t2009-01-01  00:00:00\t2009-01-01  00:00:00\tMG\tJKP")
    content = "\n".join(lines) + "\n"

    filename = "v_ask_dispatch_planning_register_update_departure_time_execute_command.csv"
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/assignments/export-kontrollpanel")
def export_kontrollpanel(day: int):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT a.location, a.custom_num"
            " FROM Assignments a"
            " JOIN Locations l ON a.location = l.location"
            " WHERE a.dispatch_day = ? AND a.agency_num IS NOT NULL"
            " ORDER BY l.location_seq",
            (day,),
        ).fetchall()
    finally:
        conn.close()

    lines = ["location\tday\tcustom_num"]
    for row in rows:
        lines.append(f"{row['location']}\t{day}\t{row['custom_num']}")
    content = "\n".join(lines) + "\n"

    filename = f"ytor_kontrollpanel_day({day}).csv"
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
