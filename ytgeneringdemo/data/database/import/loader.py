"""
WMS Export Loader
-----------------
Loads WMS CSV exports and the Prebook Excel file into the SQLite database.

Manual mode (AUTO_DETECT = False):
    python loader.py <path_to_csv_file>

Auto-detect mode (AUTO_DETECT = True):
    python loader.py
    Scans SCAN_FOLDER for the latest version of each known WMS export and
    the latest MG_Prebook_*.xlsx file, loads them all, and prints a summary.
    Missing files are skipped.

WMS CSV filename format:  v_ask_dispatch_pallet-20260327081028.csv
Prebook filename format:  MG_Prebook_20260325.xlsx

Column definitions for WMS tables are read from table_definitions.json.
WMS target tables are always cleared before inserting.
Prebook rows are upserted (existing rows for the same customer+date are replaced).
"""

import sys
import os
import re
import csv
import json
import sqlite3
from pathlib import Path
from datetime import datetime


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = str(Path(SCRIPT_DIR).parent.parent.parent)
DB_PATH = os.environ.get("ASSIGN_DB_PATH") or os.path.join(PROJECT_ROOT, "data", "database", "Database.db")
DEFINITIONS_PATH = os.path.join(SCRIPT_DIR, "table_definitions.json")

AUTO_DETECT = True

AUTO_DELETE = True

SCAN_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads")

KNOWN_TABLES = [
    "v_ask_order_overview",
    "v_ask_robot_orders",
    "v_ask_dispatch_pallet",
    "v_ask_customer_order_details_all",
    "v_ask_item",
]


DEFAULT_RULES: list[dict] = [
    {"column": "company", "keep": ["MG"]},
]

FILTER_RULES: dict[str, list[dict]] = {
    "v_ask_order_overview": [
        {"column": "agency_desc", "drop": ["Schenker - SYSTEM", "Schenker Lågt Värde Parcel", "Schenker - SYSTEM HOME"]},
        {"column": "pick_zone",   "drop": ["Q"]},
        {"column": "order_type",  "drop": ["HIB"]},
        {"column": "custom_desc", "drop": ["E-handelskund Bolist"]},
    ],
    "v_ask_customer_order_details_all": [
        {"column": "order_num", "ref_table": "v_ask_order_overview", "ref_column": "order_num"},
    ],
}


_TIMESTAMP_RE = re.compile(r"-(\d{14})\.csv$")


def find_latest_exports(folder: str) -> dict[str, tuple[str, datetime]]:
    """Scan folder and return the latest CSV file per known table."""
    latest: dict[str, tuple[str, datetime]] = {}
    for fname in os.listdir(folder):
        for table in KNOWN_TABLES:
            if not fname.startswith(table):
                continue
            m = _TIMESTAMP_RE.search(fname)
            if not m:
                continue
            ts = datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
            if table not in latest or ts > latest[table][1]:
                latest[table] = (os.path.join(folder, fname), ts)
    return latest


_PREBOOK_RE = re.compile(r"^MG_Prebook_(\d{8})\.xlsx$", re.IGNORECASE)


def find_latest_prebook(folder: str) -> tuple | None:
    """Return (path, date) for the most recent MG_Prebook_*.xlsx, or None."""
    latest = None
    for fname in os.listdir(folder):
        m = _PREBOOK_RE.match(fname)
        if not m:
            continue
        ts = datetime.strptime(m.group(1), "%Y%m%d")
        if latest is None or ts > latest[1]:
            latest = (os.path.join(folder, fname), ts)
    return latest


def load_prebook(filepath: str, ts: datetime):
    """Read a Prebook Excel file and upsert into the Prebook table."""
    import pandas as pd

    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    from backend.services.prebook_service import process

    df = pd.read_excel(filepath, dtype=str)
    text = df.to_csv(sep="\t", index=False)
    result = process(text)

    ts_str = ts.strftime("%Y-%m-%d")
    if "error" in result:
        print(f"prebook ({ts_str})  ERROR: {result['error']}")
        return

    filtered_note = f"  ({len(result['warnings'])} warnings)" if result.get("warnings") else ""
    print(f"prebook ({ts_str})  upserted {result['upserted']} rows{filtered_note}")
    for w in result.get("warnings", []):
        print(f"  WARNING: {w}")


_CUSTOM_RE = re.compile(r"^MASTER\s+MG", re.IGNORECASE)

_CUSTOM_COLUMN_MAP = {
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

_PREBOOK_SIGNATURE = frozenset([
    "Transportör", "Lastningsdatum", "Kundnummer",
    "Vikt (kg)", "Volym (m³)", "Balkningsbart",
])


def find_latest_custom(folder: str) -> str | None:
    """Return path to the most recently modified MASTER MG*.xlsx in folder, or None."""
    latest_path = None
    latest_mtime = 0.0
    for fname in os.listdir(folder):
        if not _CUSTOM_RE.match(fname) or not fname.lower().endswith(".xlsx"):
            continue
        fpath = os.path.join(folder, fname)
        mtime = os.path.getmtime(fpath)
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest_path = fpath
    return latest_path


def _decimal_to_hhmm(value: str) -> str:
    from datetime import timedelta
    value = value.strip()
    if ":" in value:
        return value
    try:
        frac = float(value)
        td = timedelta(seconds=int(round(frac * 86400)))
        h, rem = divmod(td.seconds, 3600)
        return f"{h:02d}:{rem // 60:02d}"
    except ValueError:
        return value


def load_custom(filepath: str):
    """Read a MASTER MG Excel file and overwrite the Custom table."""
    import pandas as pd

    df = pd.read_excel(filepath, dtype=str)
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed|^\s*$")]
    df.columns = [c.strip() for c in df.columns]

    available = [c for c in _CUSTOM_COLUMN_MAP if c in df.columns]
    missing_cols = [c for c in _CUSTOM_COLUMN_MAP if c not in df.columns]
    df = df[available].rename(columns=_CUSTOM_COLUMN_MAP)

    for col in df.columns:
        df[col] = df[col].where(df[col].isna(), df[col].str.strip())

    df.dropna(how="all", inplace=True)
    df = df[df["custom_num"].notna() & (df["custom_num"] != "")]
    df.reset_index(drop=True, inplace=True)

    fname = os.path.basename(filepath)

    if len(df) == 0:
        print(f"custom ({fname})  ERROR: No valid rows found")
        return

    if "orderstop" in df.columns:
        df["orderstop"] = df["orderstop"].where(
            df["orderstop"].isna(), df["orderstop"].apply(_decimal_to_hhmm)
        )

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("DELETE FROM Custom")
        df.to_sql("Custom", conn, if_exists="append", index=False)
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"custom ({fname})  ERROR: {e}")
        return
    finally:
        conn.close()

    missing_note = f"  ({len(missing_cols)} columns missing)" if missing_cols else ""
    print(f"custom ({fname})  inserted {len(df)} rows{missing_note}")


def detect_table(filename: str) -> str:
    basename = os.path.basename(filename)
    for table in KNOWN_TABLES:
        if table in basename:
            return table
    raise ValueError(
        f"Could not detect table from filename '{basename}'.\n"
        f"Filename must contain one of: {', '.join(KNOWN_TABLES)}"
    )


def load_definitions(table_name: str) -> list[dict]:
    with open(DEFINITIONS_PATH, encoding="utf-8") as f:
        defs = json.load(f)
    if table_name not in defs:
        raise KeyError(f"Table '{table_name}' not found in table_definitions.json")
    return defs[table_name]["columns"]


def ensure_table(conn: sqlite3.Connection, table_name: str, columns: list[dict]):
    col_defs = ", ".join(f'"{c["id"]}" {c["type"]}' for c in columns)
    conn.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({col_defs})')
    conn.commit()


def passes_filters(row_dict: dict, rules: list[dict]) -> bool:
    """Return True if the row satisfies all filter rules."""
    for rule in rules:
        col = rule["column"]
        val = row_dict.get(col)
        val_str = "" if val is None else str(val)
        keep = rule.get("keep")
        drop = rule.get("drop")
        if keep is not None and val_str not in keep:
            return False
        if drop is not None and val_str in drop:
            return False
    return True


def resolve_ref_rules(rules: list[dict], conn: sqlite3.Connection) -> list[dict]:
    """Expand ref_table rules into keep-set rules by querying the DB.
    If the referenced table is empty or missing, the rule is skipped (no filtering)."""
    resolved = []
    for rule in rules:
        if "ref_table" not in rule:
            resolved.append(rule)
            continue
        try:
            rows = conn.execute(
                f'SELECT DISTINCT "{rule["ref_column"]}" FROM "{rule["ref_table"]}"'
            ).fetchall()
            keep_set = {str(r[0]) for r in rows if r[0] is not None}
            if keep_set:
                resolved.append({"column": rule["column"], "keep": keep_set})
        except Exception:
            pass
    return resolved


def load_csv(filepath: str, table_name: str, columns: list[dict], conn: sqlite3.Connection) -> int:
    real_cols = {c["id"] for c in columns if c["type"] == "REAL"}
    col_ids = [c["id"] for c in columns]
    rules = resolve_ref_rules(DEFAULT_RULES + FILTER_RULES.get(table_name, []), conn)

    with open(filepath, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = []
        skipped = 0
        for raw_row in reader:
            row_dict = {}
            for col in columns:
                raw_val = raw_row.get(col["alias"], "").strip().strip('"')
                row_dict[col["id"]] = None if raw_val == "" else raw_val

            if rules and not passes_filters(row_dict, rules):
                skipped += 1
                continue

            row = []
            for col in columns:
                val = row_dict[col["id"]]
                if val is None:
                    row.append(None)
                elif col["id"] in real_cols:
                    try:
                        row.append(float(val.replace(",", ".")))
                    except ValueError:
                        row.append(None)
                else:
                    row.append(val)
            rows.append(tuple(row))

    placeholders = ", ".join("?" * len(col_ids))
    quoted_ids = ", ".join(f'"{c}"' for c in col_ids)
    insert_sql = f'INSERT INTO "{table_name}" ({quoted_ids}) VALUES ({placeholders})'

    conn.execute(f'DELETE FROM "{table_name}"')
    conn.executemany(insert_sql, rows)
    conn.commit()
    return len(rows), skipped


_CONTENT_DETECT_THRESHOLD = 0.5


def detect_csv_by_content(filepath: str) -> str | None:
    """Read the TSV header row and return the best-matching WMS table name, or None."""
    try:
        with open(filepath, encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f, delimiter="\t")
            header = set(next(reader))
    except (StopIteration, OSError):
        return None

    with open(DEFINITIONS_PATH, encoding="utf-8") as fdef:
        defs = json.load(fdef)

    best_table: str | None = None
    best_ratio = 0.0

    for table, tdef in defs.items():
        aliases = {col["alias"] for col in tdef["columns"]}
        if not aliases:
            continue
        ratio = len(aliases & header) / len(aliases)
        if ratio > best_ratio:
            best_ratio = ratio
            best_table = table

    return best_table if best_ratio >= _CONTENT_DETECT_THRESHOLD else None


def detect_xlsx_by_content(filepath: str) -> str | None:
    """Read XLSX column headers and return 'prebook', 'custom', or None."""
    import pandas as pd

    try:
        df = pd.read_excel(filepath, nrows=0, dtype=str)
    except Exception:
        return None

    header = {c.strip() for c in df.columns}
    custom_cols = set(_CUSTOM_COLUMN_MAP.keys())

    pb_ratio = len(_PREBOOK_SIGNATURE & header) / len(_PREBOOK_SIGNATURE)
    cu_ratio = len(custom_cols & header) / len(custom_cols)

    if pb_ratio >= _CONTENT_DETECT_THRESHOLD and pb_ratio >= cu_ratio:
        return "prebook"
    if cu_ratio >= _CONTENT_DETECT_THRESHOLD and cu_ratio > pb_ratio:
        return "custom"
    return None


def run_single(filepath: str):
    """Load one file (manual mode) — supports WMS CSV, Prebook XLSX, and Custom XLSX."""
    if not os.path.isabs(filepath):
        filepath = os.path.join(os.getcwd(), filepath)
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    fname = os.path.basename(filepath)

    m = _PREBOOK_RE.match(fname)
    if m:
        ts = datetime.strptime(m.group(1), "%Y%m%d")
        load_prebook(filepath, ts)
        return

    if _CUSTOM_RE.match(fname):
        load_custom(filepath)
        return

    ext = os.path.splitext(fname)[1].lower()

    if ext == ".csv":
        try:
            table_name = detect_table(filepath)
        except ValueError:
            table_name = detect_csv_by_content(filepath)
            if table_name is None:
                print(
                    f"Error: Could not identify '{fname}' — "
                    "filename not recognised and content did not match any known WMS format."
                )
                sys.exit(1)
            print(f"  Note: '{fname}' detected as '{table_name}' by content inspection")

        columns = load_definitions(table_name)
        conn = sqlite3.connect(DB_PATH)
        try:
            ensure_table(conn, table_name, columns)
            count, skipped = load_csv(filepath, table_name, columns, conn)
        finally:
            conn.close()

        ts_match = _TIMESTAMP_RE.search(fname)
        ts_str = datetime.strptime(ts_match.group(1), "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M") if ts_match else "?"
        filtered_note = f"  ({skipped} rows dropped by filter)" if skipped else ""
        print(f"{table_name} ({ts_str})  loaded {count} rows{filtered_note}")
        return

    if ext in (".xlsx", ".xls"):
        kind = detect_xlsx_by_content(filepath)
        if kind == "prebook":
            print(f"  Note: '{fname}' detected as Prebook by content inspection")
            load_prebook(filepath, datetime.now())
            return
        if kind == "custom":
            print(f"  Note: '{fname}' detected as Custom by content inspection")
            load_custom(filepath)
            return

    print(
        f"Error: Could not identify '{fname}' — "
        "filename not recognised and content did not match any known format."
    )
    sys.exit(1)


def run_auto(clear_missing: bool = False):
    """Scan SCAN_FOLDER and load the latest export for each known table and prebook.

    clear_missing: if True, tables with no matching file are cleared instead of left as-is.
    """
    print(f"Scanning: {SCAN_FOLDER}\n")
    found = find_latest_exports(SCAN_FOLDER)

    conn = sqlite3.connect(DB_PATH)
    try:
        for table in KNOWN_TABLES:
            if table not in found:
                if clear_missing:
                    try:
                        conn.execute(f'DELETE FROM "{table}"')
                        conn.commit()
                        print(f"{table}  no file found — cleared")
                    except Exception:
                        print(f"{table}  no file found")
                else:
                    print(f"{table}  no file found")
                continue

            filepath, ts = found[table]
            columns = load_definitions(table)
            ensure_table(conn, table, columns)
            count, skipped = load_csv(filepath, table, columns, conn)

            ts_str = ts.strftime("%Y-%m-%d %H:%M")
            filtered_note = f"  ({skipped} rows dropped by filter)" if skipped else ""
            print(f"{table} ({ts_str})  loaded {count} rows{filtered_note}")

            if AUTO_DELETE:
                os.remove(filepath)
                print(f"  Deleted: {os.path.basename(filepath)}")
    finally:
        conn.close()

    prebook = find_latest_prebook(SCAN_FOLDER)
    if prebook:
        filepath, ts = prebook
        load_prebook(filepath, ts)
        if AUTO_DELETE:
            os.remove(filepath)
            print(f"  Deleted: {os.path.basename(filepath)}")
    else:
        print("prebook  no file found")

    custom = find_latest_custom(SCAN_FOLDER)
    if custom:
        load_custom(custom)
        if AUTO_DELETE:
            os.remove(custom)
            print(f"  Deleted: {os.path.basename(custom)}")
    else:
        print("custom  no file found")


def main():
    clear_missing = "--clear-missing" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        run_single(args[0])
    elif AUTO_DETECT:
        run_auto(clear_missing=clear_missing)
    else:
        print("Usage: python loader.py <path_to_file>")
        print("       (or set AUTO_DETECT = True to scan the Downloads folder)")
        sys.exit(1)


if __name__ == "__main__":
    main()
