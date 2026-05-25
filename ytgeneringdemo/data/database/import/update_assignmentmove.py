"""
update_assignmentmove.py
------------------------
Reads AskViewAssignmentMove data from clipboard and replaces all rows
in the AskViewAssignmentMove table in Database.db.

agency_num and agency_desc are looked up from the Custom + Agency tables
using custom_num from the clipboard data.

Usage:
  1. Copy the data (no header row) to clipboard in Excel.
  2. Run: python update_assignmentmove.py
"""

import sqlite3
import os

import pandas as pd


DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Database.db")

CLIPBOARD_COLUMNS = [
    "pall_num", "status", "order_num", "areas", "custom_num", "custom_desc",
    "qty", "item_num", "item_desc", "packing_class", "timestamp", "user_id",
    "que_num", "priority", "location", "zone", "company", "wareh_num",
    "batch_num", "shipment_id", "date_outgo", "picking_qty", "diff", "sscc",
    "name", "crane_id",
]

DROP_COLUMNS = {"packing_class", "wareh_num", "batch_num", "date_outgo", "sscc", "crane_id"}

DB_COLUMNS = [
    "pall_num", "status", "order_num", "areas",
    "agency_num", "agency_desc",
    "custom_num", "custom_desc", "qty", "item_num", "item_desc",
    "timestamp", "user_id", "que_num", "priority", "location", "zone", "company",
    "shipment_id", "picking_qty", "diff", "name",
]


def normalize(val) -> str:
    """Normalize a key value to a plain integer string.
    Handles DB integers (110), clipboard floats ('110.0'), and plain strings ('110')."""
    try:
        return str(int(float(str(val).strip())))
    except (ValueError, TypeError):
        return str(val).strip()


def main():
    try:
        df = pd.read_clipboard(sep="\t", dtype=str, header=None)
    except Exception as e:
        print(f"ERROR: Could not read clipboard: {e}")
        return

    if df.shape[1] != len(CLIPBOARD_COLUMNS):
        print(
            f"ERROR: Expected {len(CLIPBOARD_COLUMNS)} columns, got {df.shape[1]}. "
            "Aborting — database not modified."
        )
        return

    df.columns = CLIPBOARD_COLUMNS
    df.drop(columns=list(DROP_COLUMNS), inplace=True)

    df = df[df["company"].str.strip().str.upper() == "MG"]

    for col in df.columns:
        df[col] = df[col].where(df[col].isna(), df[col].str.strip())

    df.dropna(how="all", inplace=True)
    df.reset_index(drop=True, inplace=True)

    if len(df) == 0:
        print("ERROR: No valid rows found. Aborting — database not modified.")
        return

    conn = sqlite3.connect(DB_PATH)
    agency_num_lookup = {normalize(k): v for k, v in conn.execute(
        "SELECT custom_num, agency_num FROM Custom"
    ).fetchall()}
    agency_desc_lookup = {normalize(k): v for k, v in conn.execute(
        "SELECT agency_num, agency_desc FROM Agency"
    ).fetchall()}
    conn.close()

    warnings = []

    def lookup_agency_num(cnum):
        val = agency_num_lookup.get(normalize(cnum))
        if val is None:
            warnings.append(f"  custom_num {cnum!r} not found in Custom table")
        return val

    def lookup_agency_desc(anum):
        if anum is None:
            return None
        val = agency_desc_lookup.get(normalize(anum))
        if val is None:
            warnings.append(f"  agency_num {anum!r} not found in Agency table")
        return val

    df["agency_num"] = df["custom_num"].apply(lookup_agency_num)
    df["agency_desc"] = df["agency_num"].apply(lookup_agency_desc)

    if warnings:
        seen = set()
        unique_warnings = [w for w in warnings if not (w in seen or seen.add(w))]
        print(f"\nWARNING: {len(unique_warnings)} lookup issue(s):")
        for w in unique_warnings:
            print(w)

    df = df.reindex(columns=DB_COLUMNS)

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM AskViewAssignmentMove")
        df.to_sql("AskViewAssignmentMove", conn, if_exists="append", index=False)
        conn.commit()
        print(f"\nInserted {len(df)} rows into AskViewAssignmentMove.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR during database write: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
