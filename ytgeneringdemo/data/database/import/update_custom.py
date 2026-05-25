"""
update_custom.py
----------------
Reads the Master MG Excel data from clipboard and overwrites the Custom table in Database.db.

Usage:
  1. Copy the full Master MG sheet (including header row) to clipboard in Excel.
  2. Run: python update_custom.py
"""

import sqlite3
import os
from datetime import timedelta

import pandas as pd


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Database.db")

COLUMN_MAP = {
    "Zon":          "zone",
    "Län":          "county",
    "Postnr":       "zip_code",
    "Ort":          "city",
    "Orderstopp":   "orderstop",
    "Kundnr":       "custom_num",
    "Trpt nummer":  "agency_num",
    "Butik":        "custom_desc",
    "Måndag":       "mon",
    "Tisdag":       "tue",
    "Onsdag":       "wed",
    "Torsdag":      "thu",
    "Fredag":       "fri",
    "Kejda":        "franchise",
}


def decimal_to_hhmm(value: str) -> str:
    """Convert an Excel time decimal string (e.g. '0.5') to 'HH:MM'.
    Leaves strings that already look like 'HH:MM' unchanged."""
    value = value.strip()
    if ":" in value:
        return value
    try:
        frac = float(value)
        total_seconds = int(round(frac * 86400))
        td = timedelta(seconds=total_seconds)
        hours, remainder = divmod(td.seconds, 3600)
        minutes = remainder // 60
        return f"{hours:02d}:{minutes:02d}"
    except ValueError:
        return value


def main():
    try:
        df = pd.read_clipboard(sep="\t", dtype=str, header=0)
    except Exception as e:
        print(f"ERROR: Could not read clipboard: {e}")
        return

    df = df.loc[:, ~df.columns.str.match(r"^Unnamed|^\s*$")]
    df.columns = [c.strip() for c in df.columns]

    available = [c for c in COLUMN_MAP if c in df.columns]
    missing_cols = [c for c in COLUMN_MAP if c not in df.columns]
    if missing_cols:
        print(f"WARNING: Expected columns not found in clipboard: {missing_cols}")

    df = df[available].rename(columns=COLUMN_MAP)

    for col in df.columns:
        df[col] = df[col].where(df[col].isna(), df[col].str.strip())

    df.dropna(how="all", inplace=True)
    mask_no_custnum = df["custom_num"].isna() | (df["custom_num"] == "")
    df = df[~mask_no_custnum]
    df.reset_index(drop=True, inplace=True)

    if len(df) == 0:
        print("ERROR: No valid rows found. Aborting — database not modified.")
        return

    if "orderstop" in df.columns:
        df["orderstop"] = df["orderstop"].where(
            df["orderstop"].isna(), df["orderstop"].apply(decimal_to_hhmm)
        )

    DAY_COLS = {"mon", "tue", "wed", "thu", "fri"}
    NON_DAY_COLS = [c for c in df.columns if c not in DAY_COLS]
    DELIVERY_CODES = ["L", "S", "O"]

    def is_valid_zone(v):
        try:
            return 1 <= int(float(v)) <= 25
        except (ValueError, TypeError):
            return False

    def has_code(row, code):
        """Return True if the code appears in any day column for this customer."""
        for day in DAY_COLS:
            val = row.get(day)
            if val and not pd.isna(val) and code in str(val).upper().split("/"):
                return True
        return False

    warnings = []
    for _, row in df.iterrows():
        cnum = row.get("custom_num", "?")
        cdesc = row.get("custom_desc", "?")

        for col in NON_DAY_COLS:
            val = row[col]
            if pd.isna(val) or str(val).strip() == "":
                warnings.append((cnum, cdesc, f"missing {col}"))
            elif col == "zone" and not is_valid_zone(val):
                warnings.append((cnum, cdesc, f"invalid zone ({val!r})"))

        for code in DELIVERY_CODES:
            if not has_code(row, code):
                warnings.append((cnum, cdesc, f"{code} | {cdesc} does not have {code} scheduled"))

    if warnings:
        print(f"\nWARNING: {len(warnings)} issue(s) found:")
        for cnum, cdesc, msg in warnings:
            if msg.startswith(("L |", "S |", "O |")):
                print(f"  {msg}")
            else:
                print(f"  {cnum} ({cdesc}) — {msg}")

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Custom")
        df.to_sql("Custom", conn, if_exists="append", index=False)
        conn.commit()
        print(f"\nInserted {len(df)} rows.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR during database write: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
