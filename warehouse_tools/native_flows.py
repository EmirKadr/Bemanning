from __future__ import annotations

from pathlib import Path

from .native_tables import SimpleTable


def _read_text_lines(path: Path) -> list[str]:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("utf-8", errors="replace")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _chunk_values(values: list[str], chunk_size: int) -> SimpleTable:
    chunks = [values[index:index + chunk_size] for index in range(0, len(values), chunk_size)]
    columns = [f"Kolumn {index + 1}" for index in range(len(chunks))]
    row_count = max((len(chunk) for chunk in chunks), default=0)
    rows = [
        [chunk[row_index] if row_index < len(chunk) else "" for chunk in chunks]
        for row_index in range(row_count)
    ]
    return SimpleTable(columns=columns, rows=rows)


def flow_split_values(files: dict, params: dict) -> dict:
    if "values_file" in files:
        values = _read_text_lines(Path(files["values_file"]))
    else:
        raw = params.get("values") or ""
        values = [line.strip() for line in raw.splitlines() if line.strip()]
    if not values:
        raise ValueError("Inga värden angivna - klistra in eller ladda upp en textfil.")
    try:
        chunk_size = int(params.get("chunk_size") or 2000)
    except ValueError:
        chunk_size = 2000
    chunk_size = max(1, chunk_size)
    table = _chunk_values(values, chunk_size)
    return {
        "summary": {
            "Antal värden": len(values),
            "Antal kolumner": len(table.columns),
            "Per kolumn": chunk_size,
        },
        "tables": [("report", "Delade värden", table)],
        "log": [],
    }


FLOW_BY_ID: dict[str, dict] = {
    "split-values": {"handler": flow_split_values},
}
