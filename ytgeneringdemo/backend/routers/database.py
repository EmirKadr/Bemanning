import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from backend.db import DB_PATH

router = APIRouter(prefix="/db", tags=["database"])


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _safe_name(name: str) -> str:
    """Reject anything that isn't a plain identifier."""
    if not name.isidentifier():
        raise HTTPException(400, f"Invalid identifier: {name}")
    return name


_LOADER_PATH = Path(__file__).parent.parent.parent / "data" / "database" / "import" / "loader.py"


@router.post("/import-wms")
def import_wms():
    result = subprocess.run(
        [sys.executable, str(_LOADER_PATH)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise HTTPException(500, result.stderr or "Loader failed")
    return {"ok": True, "output": result.stdout}


@router.post("/import-wms-upload")
async def import_wms_upload(files: list[UploadFile] = File(...)):
    output_parts = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for upload in files:
            tmp_path = os.path.join(tmpdir, upload.filename)
            content = await upload.read()
            with open(tmp_path, "wb") as f:
                f.write(content)
            result = subprocess.run(
                [sys.executable, str(_LOADER_PATH), tmp_path],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                output_parts.append(f"ERROR ({upload.filename}): {result.stderr.strip() or 'Load failed'}")
            else:
                output_parts.append(result.stdout.strip())
    return {"ok": True, "output": "\n".join(filter(None, output_parts))}


@router.get("/tables")
def list_tables():
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [r["name"] for r in rows]
    finally:
        conn.close()


@router.get("/tables/{table}/schema")
def table_schema(table: str):
    table = _safe_name(table)
    conn = _conn()
    try:
        cols = conn.execute(f"PRAGMA table_info([{table}])").fetchall()
        if not cols:
            raise HTTPException(404, "Table not found")
        return [
            {"cid": c["cid"], "name": c["name"], "type": c["type"],
             "notnull": c["notnull"], "pk": c["pk"]}
            for c in cols
        ]
    finally:
        conn.close()


def _parse_filters(raw: Optional[str]):
    if not raw:
        return "", []
    try:
        filters = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return "", []
    clauses = []
    params = []
    for col, val in filters.items():
        if not col.isidentifier():
            continue
        if val is None:
            clauses.append(f"[{col}] IS NULL")
        elif isinstance(val, str) and val.startswith("~"):
            clauses.append(f"[{col}] LIKE ?")
            params.append(f"%{val[1:]}%")
        else:
            clauses.append(f"[{col}] = ?")
            params.append(val)
    if not clauses:
        return "", []
    return " WHERE " + " AND ".join(clauses), params


@router.get("/tables/{table}/distinct/{column}")
def distinct_values(
    table: str,
    column: str,
    filters: Optional[str] = Query(None),
):
    table = _safe_name(table)
    column = _safe_name(column)
    where, params = _parse_filters(filters)
    conn = _conn()
    try:
        rows = conn.execute(
            f"SELECT DISTINCT [{column}] FROM [{table}]{where} ORDER BY [{column}] LIMIT 500",
            params,
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


@router.get("/tables/{table}/rows")
def get_rows(
    table: str,
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    filters: Optional[str] = Query(None),
):
    table = _safe_name(table)
    where, fparams = _parse_filters(filters)
    conn = _conn()
    try:
        total = conn.execute(f"SELECT COUNT(*) AS c FROM [{table}]{where}", fparams).fetchone()["c"]
        rows = conn.execute(
            f"SELECT rowid AS __rid__, * FROM [{table}]{where} LIMIT ? OFFSET ?",
            fparams + [limit, offset],
        ).fetchall()
        def to_row(r):
            d = dict(r)
            d["rowid"] = d.pop("__rid__")
            return d
        return {"total": total, "rows": [to_row(r) for r in rows]}
    finally:
        conn.close()


class InsertBody(BaseModel):
    values: dict


@router.post("/tables/{table}/rows")
def insert_row(table: str, body: InsertBody):
    table = _safe_name(table)
    cols = [_safe_name(k) for k in body.values]
    placeholders = ", ".join("?" for _ in cols)
    col_list = ", ".join(f"[{c}]" for c in cols)
    vals = [body.values[c] for c in cols]
    conn = _conn()
    try:
        cur = conn.execute(
            f"INSERT INTO [{table}] ({col_list}) VALUES ({placeholders})", vals
        )
        conn.commit()
        return {"ok": True, "rowid": cur.lastrowid}
    finally:
        conn.close()


class UpdateBody(BaseModel):
    rowid: int
    column: str
    value: object


@router.patch("/tables/{table}/rows")
def update_cell(table: str, body: UpdateBody):
    table = _safe_name(table)
    col = _safe_name(body.column)
    conn = _conn()
    try:
        conn.execute(
            f"UPDATE [{table}] SET [{col}] = ? WHERE rowid = ?",
            (body.value, body.rowid),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


class DeleteBody(BaseModel):
    rowids: list[int]


@router.delete("/tables/{table}/rows")
def delete_rows(table: str, body: DeleteBody):
    table = _safe_name(table)
    conn = _conn()
    try:
        placeholders = ", ".join("?" for _ in body.rowids)
        conn.execute(
            f"DELETE FROM [{table}] WHERE rowid IN ({placeholders})", body.rowids
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/tables/{table}/rows/all")
def clear_table(table: str):
    table = _safe_name(table)
    conn = _conn()
    try:
        conn.execute(f"DELETE FROM [{table}]")
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


class AddColumnBody(BaseModel):
    name: str
    type: str = "TEXT"


@router.post("/tables/{table}/columns")
def add_column(table: str, body: AddColumnBody):
    table = _safe_name(table)
    col = _safe_name(body.name)
    col_type = body.type.upper()
    if col_type not in ("TEXT", "INTEGER", "REAL", "BLOB", "NUMERIC"):
        raise HTTPException(400, "Invalid column type")
    conn = _conn()
    try:
        conn.execute(f"ALTER TABLE [{table}] ADD COLUMN [{col}] {col_type}")
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


class RenameColumnBody(BaseModel):
    old_name: str
    new_name: str


@router.patch("/tables/{table}/columns")
def rename_column(table: str, body: RenameColumnBody):
    table = _safe_name(table)
    old = _safe_name(body.old_name)
    new = _safe_name(body.new_name)
    conn = _conn()
    try:
        conn.execute(
            f"ALTER TABLE [{table}] RENAME COLUMN [{old}] TO [{new}]"
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@router.delete("/tables/{table}/columns/{column}")
def drop_column(table: str, column: str):
    table = _safe_name(table)
    col = _safe_name(column)
    conn = _conn()
    try:
        conn.execute(f"ALTER TABLE [{table}] DROP COLUMN [{col}]")
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()
