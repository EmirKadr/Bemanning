"""
Prebook import service.

Processes tab-separated prebook data (from the transport email Excel) and
upserts into the Prebook table. Called by the /api/prebook/import endpoint.
"""

import io
import sqlite3
from datetime import datetime

import pandas as pd

from backend.db import DB_PATH
from backend.config_cache import get_config
from backend.utils.pallet import calc_pall

COLUMN_MAP = {
    "Transportör":    "agency_desc",
    "Lastningsdatum": "shipment_date",
    "Kundnummer":     "custom_num",
    "Butik":          "custom_desc",
    "Vikt (kg)":      "weight_kg",
    "Volym (m³)":     "volume",
    "Balkningsbart":  "is_stackable",
}

DB_COLUMNS = [
    "agency_num", "agency_desc", "shipment_date",
    "custom_num", "custom_desc", "weight_kg", "volume",
    "pall_required", "is_stackable", "day_num", "day_desc",
    "assign_weight", "assign_pall",
]

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri"]


def _format_date(val: str) -> str:
    try:
        return datetime.strptime(val.strip(), "%Y%m%d %H:%M").strftime("%Y-%m-%d")
    except ValueError:
        return val


def process(text: str) -> dict:
    """
    Process tab-separated prebook text and upsert into Prebook table.

    Returns {"upserted": N, "warnings": [...], "missing_columns": [...]}
    or {"error": "..."} on failure.
    """
    config = get_config()
    prebook_cfg         = config.get("prebook", {})
    baseline_kg         = prebook_cfg.get("pall_baseline_kg", 300)
    franchise_overrides = prebook_cfg.get("franchise_overrides", {})

    try:
        df = pd.read_csv(io.StringIO(text), sep="\t", dtype=str, header=0)
    except Exception as e:
        return {"error": f"Could not parse input: {e}"}

    df = df.loc[:, ~df.columns.str.match(r"^Unnamed|^\s*$")]
    df.columns = [c.strip() for c in df.columns]

    available    = [c for c in COLUMN_MAP if c in df.columns]
    missing_cols = [c for c in COLUMN_MAP if c not in df.columns]

    df = df[available].rename(columns=COLUMN_MAP)

    for col in df.columns:
        df[col] = df[col].where(df[col].isna(), df[col].str.strip())

    df.dropna(how="all", inplace=True)
    df = df[df["custom_num"].notna() & (df["custom_num"] != "")]

    def is_zero_weight(v):
        try:
            return float(v) == 0
        except (TypeError, ValueError):
            return False

    df = df[~df["weight_kg"].apply(is_zero_weight)]
    df.reset_index(drop=True, inplace=True)

    if len(df) == 0:
        return {"error": "No valid rows found. Database not modified."}

    df["shipment_date"] = df["shipment_date"].apply(
        lambda v: _format_date(v) if pd.notna(v) else v
    )

    def get_day(date_str, attr):
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d")
            return (d.weekday() + 1) if attr == "num" else DAY_NAMES[d.weekday()]
        except (ValueError, TypeError):
            return None

    df["day_num"]      = df["shipment_date"].apply(lambda v: get_day(v, "num"))
    df["day_desc"]     = df["shipment_date"].apply(lambda v: get_day(v, "desc"))
    df["is_stackable"] = df["is_stackable"].map({"JA": "Y", "NEJ": "N"}).fillna(df["is_stackable"])

    conn             = sqlite3.connect(str(DB_PATH))
    agency_lookup    = dict(conn.execute("SELECT agency_desc, agency_num FROM Agency").fetchall())
    franchise_lookup = {str(k): v for k, v in conn.execute("SELECT custom_num, franchise FROM Custom").fetchall()}
    conn.close()

    df["agency_num"] = df["agency_desc"].apply(lambda v: agency_lookup.get(v) if v else None)

    df["weight_kg"] = pd.to_numeric(df["weight_kg"], errors="coerce")
    df["volume"]    = pd.to_numeric(df["volume"],    errors="coerce")

    def agg_stackable(s):
        return "N" if "N" in s.values else "Y"

    df = df.groupby(["custom_num", "shipment_date"], as_index=False).agg(
        agency_num   =("agency_num",   "first"),
        agency_desc  =("agency_desc",  "first"),
        custom_desc  =("custom_desc",  "first"),
        weight_kg    =("weight_kg",    "sum"),
        volume       =("volume",       "sum"),
        is_stackable =("is_stackable", agg_stackable),
        day_num      =("day_num",      "first"),
        day_desc     =("day_desc",     "first"),
    )

    warnings = []

    def get_pall(row):
        cnum      = str(row["custom_num"])
        franchise = franchise_lookup.get(cnum)
        if franchise is None:
            warnings.append(f"{row['custom_desc']} — customer {cnum!r} not in Custom table, using baseline {baseline_kg} kg/pall")
        threshold = franchise_overrides.get(franchise, baseline_kg) if franchise else baseline_kg
        return calc_pall(row["weight_kg"], threshold)

    df["pall_required"] = df.apply(get_pall, axis=1)
    df["assign_weight"] = df["weight_kg"]
    df["assign_pall"]   = df["pall_required"]

    for _, row in df.iterrows():
        cdesc = row.get("custom_desc", "?")
        if pd.isna(row.get("agency_num")):
            warnings.append(f"{cdesc} — agency not found: {row.get('agency_desc')!r}")
        for col in ["shipment_date", "custom_num", "weight_kg"]:
            val = row.get(col)
            if pd.isna(val) or str(val).strip() == "":
                warnings.append(f"{cdesc} — missing {col}")

    df   = df.reindex(columns=DB_COLUMNS)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        pairs = df[["custom_num", "shipment_date"]].dropna().drop_duplicates()
        conn.executemany(
            "DELETE FROM Prebook WHERE custom_num = ? AND shipment_date = ?",
            [(r.custom_num, r.shipment_date) for _, r in pairs.iterrows()]
        )
        placeholders = ", ".join("?" * len(DB_COLUMNS))
        cols         = ", ".join(DB_COLUMNS)
        conn.executemany(
            f"INSERT INTO Prebook ({cols}) VALUES ({placeholders})",
            [tuple(row) for _, row in df.iterrows()]
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return {"error": f"Database write failed: {e}"}
    finally:
        conn.close()

    return {
        "upserted":        len(df),
        "warnings":        warnings,
        "missing_columns": missing_cols,
    }
