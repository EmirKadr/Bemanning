from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.db import get_connection

router = APIRouter()

ALLOWED_FIELDS = {
    "agency_asn", "agency_arrive", "agency_depart",
    "cluster_group", "start_seq", "end_seq", "color",
}


@router.get("/agencies")
def get_agencies():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT agency_alias, color, start_seq, end_seq, cluster_group, assignment_order, agency_asn, agency_arrive, agency_depart"
            " FROM Agency"
            " WHERE agency_alias IS NOT NULL"
            " ORDER BY assignment_order",
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


class AgencyFieldUpdate(BaseModel):
    alias: str
    field: str
    value: Optional[str]


@router.patch("/agencies")
def patch_agency(body: AgencyFieldUpdate):
    if body.field not in ALLOWED_FIELDS:
        raise HTTPException(status_code=400, detail=f"Field '{body.field}' is not editable")
    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE Agency SET {body.field} = ? WHERE agency_alias = ?",
            (body.value, body.alias),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.get("/customers")
def get_customers():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT c.custom_num, c.custom_desc, ag.agency_alias"
            " FROM Custom c"
            " LEFT JOIN Agency ag ON c.agency_num = ag.agency_num"
            " WHERE c.custom_desc IS NOT NULL"
            " ORDER BY ag.assignment_order, c.custom_desc",
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


class ReorderBody(BaseModel):
    aliases: list[str]


@router.post("/agencies/reorder")
def reorder_agencies(body: ReorderBody):
    conn = get_connection()
    try:
        conn.executemany(
            "UPDATE Agency SET assignment_order = ? WHERE agency_alias = ?",
            [(i, alias) for i, alias in enumerate(body.aliases)],
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
