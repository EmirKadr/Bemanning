from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .config import settings


HOURS = tuple(range(6, 24))


class ProductivitySourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceFileSpec:
    key: str
    label: str
    prefix: str


@dataclass(frozen=True)
class SectionSpec:
    id: str
    group_id: str
    title: str
    source: str
    process: str
    target_company: str
    target_metric: str
    total_source: str
    predicate: Callable[[dict[str, Any]], bool]


SOURCE_SPECS = (
    SourceFileSpec("pick", "Plocklogg", "v_ask_pick_log_full"),
    SourceFileSpec("trans", "Translogg", "v_ask_trans_log"),
    SourceFileSpec("pallet", "Palllastningslogg", "v_ask_palletloading_log"),
    SourceFileSpec("kpi", "KPI-Mål", "v_ask_kpi_target"),
)

GROUPS = (
    {"id": "gg", "title": "Granngården"},
    {"id": "autostore", "title": "Autostore och e-handel"},
    {"id": "mg", "title": "Mestergruppen"},
)

GROUP_TITLES = {group["id"]: group["title"] for group in GROUPS}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_reference_dir() -> Path:
    configured = (settings.PRODUCTIVITY_REFERENCE_DIR or "").strip()
    if configured:
        return Path(configured)
    return _repo_root() / "referens"


def _latest_file(reference_dir: Path, prefix: str) -> Path:
    matches = [
        path
        for path in reference_dir.glob(f"{prefix}*.csv")
        if path.is_file() and not path.name.startswith("~$")
    ]
    if not matches:
        raise ProductivitySourceError(f"Saknar referensfil med prefix {prefix} i {reference_dir}")
    return max(matches, key=lambda path: (path.stat().st_mtime_ns, path.name))


def find_source_files(reference_dir: Path) -> dict[str, Path]:
    if not reference_dir.exists():
        raise ProductivitySourceError(f"Referensmappen finns inte: {reference_dir}")
    return {spec.key: _latest_file(reference_dir, spec.prefix) for spec in SOURCE_SPECS}


def _detect_dialect(sample: str) -> csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters="\t;,")
    except csv.Error:
        class Fallback(csv.excel):
            delimiter = "\t" if sample.count("\t") >= sample.count(";") else ";"

        return Fallback


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        dialect = _detect_dialect(sample)
        return list(csv.DictReader(handle, dialect=dialect))


def _get(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value is not None:
            return str(value).strip()
    return ""


def _number(value: Any) -> float:
    text = str(value or "").strip().replace("\xa0", "").replace(" ", "")
    if not text:
        return 0.0
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y%m%d %H:%M:%S", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _company_contains(event: dict[str, Any], company: str) -> bool:
    return company.upper() in str(event.get("company", "")).upper()


def _company_is(event: dict[str, Any], company: str) -> bool:
    return str(event.get("company", "")).strip().upper() == company.upper()


def _clean_user(value: str) -> str:
    return value.strip()


def _parse_pick_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        user = _clean_user(_get(row, "Användare", "Anvandare"))
        if not user:
            continue
        picked = _number(_get(row, "Plockat"))
        weight = _number(_get(row, "Vikt"))
        events.append(
            {
                "user": user,
                "zone": _get(row, "Zon").upper(),
                "company": _get(row, "Bolag"),
                "timestamp": _timestamp(_get(row, "Ändrad", "Andrad")),
                "kolli": picked,
                "vikt": weight,
            }
        )
    return events


def _parse_trans_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        user = _clean_user(_get(row, "Användare", "Anvandare"))
        if not user:
            continue
        amount = _number(_get(row, "Antal"))
        events.append(
            {
                "user": user,
                "company": _get(row, "Bolag"),
                "to": _get(row, "Till"),
                "timestamp": _timestamp(_get(row, "Timestamp")),
                "antal": amount,
            }
        )
    return events


def _parse_pallet_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in rows:
        user = _clean_user(_get(row, "Användare", "Anvandare"))
        if not user:
            continue
        events.append(
            {
                "user": user,
                "company": _get(row, "Bolag"),
                "type": _get(row, "Typ"),
                "timestamp": _timestamp(_get(row, "Ändrad", "Andrad")),
            }
        )
    return events


def _parse_kpi_rows(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
    targets: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        company = _get(row, "Bolag").upper()
        process = _get(row, "Processnamn").upper()
        if not company or not process:
            continue
        targets[(company, process)] = {
            "description": _get(row, "Beskrivning"),
            "rader": _number(_get(row, "Rader")),
            "kollin": _number(_get(row, "Kollin", "Kolli")),
            "pallar": _number(_get(row, "Pallar")),
        }
    return targets


def _target_value(
    targets: dict[tuple[str, str], dict[str, Any]],
    company: str,
    process: str,
    metric: str,
) -> float | None:
    target = targets.get((company.upper(), process.upper()))
    if not target:
        return None
    value = target.get(metric.lower())
    return float(value) if value else None


def _parse_report_date(value: date | str | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _event_date(event: dict[str, Any]) -> date | None:
    timestamp = event.get("timestamp")
    return timestamp.date() if isinstance(timestamp, datetime) else None


def _available_dates(*event_sets: list[dict[str, Any]]) -> list[date]:
    dates = {
        event_date
        for events in event_sets
        for event in events
        if (event_date := _event_date(event)) is not None
    }
    return sorted(dates)


def _totals_for_date(
    *,
    pick_events: list[dict[str, Any]],
    trans_events: list[dict[str, Any]],
    report_date: date,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
    pick_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"kolli": 0.0, "vikt": 0.0})
    trans_totals: dict[str, dict[str, float]] = defaultdict(lambda: {"antal": 0.0})

    for event in pick_events:
        if _event_date(event) != report_date:
            continue
        user = str(event["user"])
        pick_totals[user]["kolli"] += float(event.get("kolli") or 0)
        pick_totals[user]["vikt"] += float(event.get("vikt") or 0)

    for event in trans_events:
        if _event_date(event) != report_date:
            continue
        user = str(event["user"])
        trans_totals[user]["antal"] += float(event.get("antal") or 0)

    return pick_totals, trans_totals


def _section_specs() -> tuple[SectionSpec, ...]:
    excluded_gg = {"FILI10", "SEBA80"}
    excluded_mg = {"ANTO87", "HUGO49"}

    return (
        SectionSpec(
            "gg_pick_ab",
            "gg",
            "Plockzon A/B",
            "pick",
            "Manual_Pick",
            "GG",
            "rader",
            "pick",
            lambda event: (
                _company_contains(event, "GG")
                and event.get("zone") in {"A", "B"}
                and event.get("user") not in excluded_gg
            ),
        ),
        SectionSpec(
            "gg_pick_s",
            "gg",
            "Plockzon S",
            "pick",
            "Bulky_Pick",
            "GG",
            "rader",
            "pick",
            lambda event: (
                _company_contains(event, "GG")
                and event.get("zone") == "S"
                and event.get("user") not in excluded_gg
            ),
        ),
        SectionSpec(
            "as_store_pick",
            "autostore",
            "Butik Plock AS - GG + MG",
            "pick",
            "Autostore",
            "GG",
            "rader",
            "pick",
            lambda event: event.get("zone") == "R",
        ),
        SectionSpec(
            "gg_decanting",
            "autostore",
            "Granngården Dekantering",
            "trans",
            "Decanting",
            "GG",
            "rader",
            "trans",
            lambda event: _company_is(event, "GG") and str(event.get("to", "")).upper().startswith("AS"),
        ),
        SectionSpec(
            "gg_ecom_pick",
            "autostore",
            "Granngården E-Handel Plock",
            "pick",
            "E_Commerce",
            "GG",
            "rader",
            "pick",
            lambda event: _company_contains(event, "GG") and event.get("zone") == "E",
        ),
        SectionSpec(
            "gg_ecom_pack",
            "autostore",
            "Granngården E-Handel Pack",
            "pallet",
            "Ecom_pack",
            "GG",
            "pallar",
            "none",
            lambda event: (
                _company_is(event, "GG")
                and str(event.get("type", "")).strip() == "220"
                and event.get("user") != "swisslogautostoreintegration"
            ),
        ),
        SectionSpec(
            "mg_decanting",
            "autostore",
            "Mestergruppen Dekantering",
            "trans",
            "Decanting",
            "MG",
            "rader",
            "trans",
            lambda event: _company_is(event, "MG") and str(event.get("to", "")).upper().startswith("AS"),
        ),
        SectionSpec(
            "mg_ecom_pick",
            "autostore",
            "Mestergruppen E-Handel Plock",
            "pick",
            "E_Commerce",
            "MG",
            "rader",
            "pick",
            lambda event: _company_contains(event, "MG") and event.get("zone") == "Q",
        ),
        SectionSpec(
            "mg_ecom_pack",
            "autostore",
            "Mestergruppen E-Handel Pack",
            "pallet",
            "Ecom_pack",
            "MG",
            "pallar",
            "none",
            lambda event: (
                _company_is(event, "MG")
                and str(event.get("type", "")).strip() == "220"
                and event.get("user") != "swisslogautostoreintegration"
            ),
        ),
        SectionSpec(
            "mg_pick_abn",
            "mg",
            "Plockzon A/B/N",
            "pick",
            "Manual_Pick",
            "MG",
            "rader",
            "pick",
            lambda event: (
                _company_contains(event, "MG")
                and event.get("zone") in {"A", "B", "N"}
                and event.get("user") not in excluded_mg
            ),
        ),
        SectionSpec(
            "mg_pick_o",
            "mg",
            "Plockzon O",
            "pick",
            "Bulky_Pick",
            "MG",
            "rader",
            "pick",
            lambda event: (
                _company_contains(event, "MG")
                and event.get("zone") == "O"
                and event.get("user") not in excluded_mg
            ),
        ),
    )


def _bucketed_rows(
    *,
    spec: SectionSpec,
    events: list[dict[str, Any]],
    targets: dict[tuple[str, str], dict[str, Any]],
    pick_totals: dict[str, dict[str, float]],
    trans_totals: dict[str, dict[str, float]],
    report_date: date,
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[int, int]] = defaultdict(lambda: {hour: 0 for hour in HOURS})

    for event in events:
        if not spec.predicate(event):
            continue
        timestamp = event.get("timestamp")
        if not isinstance(timestamp, datetime):
            continue
        if timestamp.date() != report_date:
            continue
        hour = timestamp.hour
        if hour not in HOURS:
            continue
        buckets[str(event["user"])][hour] += 1

    target = _target_value(targets, spec.target_company, spec.process, spec.target_metric)
    rows: list[dict[str, Any]] = []
    for user in sorted(buckets, key=lambda value: value.upper()):
        hourly = buckets[user]
        total_rows = sum(hourly.values())
        if total_rows <= 0:
            continue
        correction = 0
        worked_hours = max(0, sum(1 for value in hourly.values() if value > 0) - correction)
        rows_per_hour = total_rows / worked_hours if worked_hours else None
        productivity_pct = rows_per_hour / target if rows_per_hour is not None and target else None

        total_kolli: float | None = None
        total_weight: float | None = None
        if spec.total_source == "pick":
            total_kolli = pick_totals.get(user, {}).get("kolli", 0.0)
            total_weight = pick_totals.get(user, {}).get("vikt", 0.0)
        elif spec.total_source == "trans":
            total_kolli = trans_totals.get(user, {}).get("antal", 0.0)

        rows.append(
            {
                "user": user,
                "hourly": {str(hour): count for hour, count in hourly.items() if count},
                "total_rows": total_rows,
                "total_kolli": total_kolli,
                "total_weight": total_weight,
                "worked_hours": worked_hours,
                "rows_per_hour": rows_per_hour,
                "correction": correction,
                "target_per_hour": target,
                "target_metric": spec.target_metric,
                "productivity_pct": productivity_pct,
            }
        )
    return rows


def _source_payload(path: Path, label: str, rows: int) -> dict[str, Any]:
    stat = path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).astimezone()
    return {
        "label": label,
        "name": path.name,
        "path": str(path),
        "rows": rows,
        "modified_at": modified.isoformat(timespec="seconds"),
    }


def _cache_key(files: dict[str, Path], report_date: date | None) -> tuple[tuple[str, str, int, int] | tuple[str, str], ...]:
    key = []
    for name, path in sorted(files.items()):
        stat = path.stat()
        key.append((name, str(path.resolve()), stat.st_mtime_ns, stat.st_size))
    key.append(("date", report_date.isoformat() if report_date else "latest"))
    return tuple(key)


_REPORT_CACHE: dict[tuple[tuple[str, str, int, int] | tuple[str, str], ...], dict[str, Any]] = {}


def build_productivity_report(
    reference_dir: Path | str | None = None,
    report_date: date | str | None = None,
) -> dict[str, Any]:
    base_dir = Path(reference_dir) if reference_dir is not None else default_reference_dir()
    files = find_source_files(base_dir)
    requested_date = _parse_report_date(report_date)
    key = _cache_key(files, requested_date)
    if requested_date is not None and key in _REPORT_CACHE:
        return _REPORT_CACHE[key]

    pick_raw = _read_csv(files["pick"])
    trans_raw = _read_csv(files["trans"])
    pallet_raw = _read_csv(files["pallet"])
    kpi_raw = _read_csv(files["kpi"])

    pick_events = _parse_pick_rows(pick_raw)
    trans_events = _parse_trans_rows(trans_raw)
    pallet_events = _parse_pallet_rows(pallet_raw)
    targets = _parse_kpi_rows(kpi_raw)
    dates = _available_dates(pick_events, trans_events, pallet_events)
    if not dates:
        raise ProductivitySourceError("Produktivitetsunderlagen saknar datum")
    selected_date = requested_date or dates[-1]
    if selected_date not in dates:
        raise ProductivitySourceError(f"Saknar produktivitetsdata för {selected_date.isoformat()}")
    pick_totals, trans_totals = _totals_for_date(
        pick_events=pick_events,
        trans_events=trans_events,
        report_date=selected_date,
    )
    key = _cache_key(files, selected_date)
    if key in _REPORT_CACHE:
        return _REPORT_CACHE[key]
    raw_counts = {
        "pick": len(pick_raw),
        "trans": len(trans_raw),
        "pallet": len(pallet_raw),
        "kpi": len(kpi_raw),
    }

    events_by_source = {
        "pick": pick_events,
        "trans": trans_events,
        "pallet": pallet_events,
    }
    sections_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    section_count = 0
    total_rows = 0
    total_worked_hours = 0
    productivity_values: list[float] = []

    for spec in _section_specs():
        rows = _bucketed_rows(
            spec=spec,
            events=events_by_source[spec.source],
            targets=targets,
            pick_totals=pick_totals,
            trans_totals=trans_totals,
            report_date=selected_date,
        )
        section_total_rows = sum(row["total_rows"] for row in rows)
        section_worked_hours = sum(row["worked_hours"] for row in rows)
        section_target = _target_value(targets, spec.target_company, spec.process, spec.target_metric)
        section_rows_per_hour = (
            section_total_rows / section_worked_hours if section_worked_hours else None
        )
        section_productivity = (
            section_rows_per_hour / section_target
            if section_rows_per_hour is not None and section_target
            else None
        )
        if section_productivity is not None:
            productivity_values.append(section_productivity)
        total_rows += section_total_rows
        total_worked_hours += section_worked_hours
        section_count += 1

        sections_by_group[spec.group_id].append(
            {
                "id": spec.id,
                "title": spec.title,
                "source": spec.source,
                "process": spec.process,
                "target_company": spec.target_company,
                "target_metric": spec.target_metric,
                "target_per_hour": section_target,
                "total_rows": section_total_rows,
                "worked_hours": section_worked_hours,
                "rows_per_hour": section_rows_per_hour,
                "productivity_pct": section_productivity,
                "rows": rows,
            }
        )

    groups = [
        {
            "id": group["id"],
            "title": GROUP_TITLES[group["id"]],
            "sections": sections_by_group.get(group["id"], []),
        }
        for group in GROUPS
    ]
    users = {
        row["user"]
        for group in groups
        for section in group["sections"]
        for row in section["rows"]
    }

    report = {
        "generated_at": datetime.now(tz=timezone.utc).astimezone().isoformat(timespec="seconds"),
        "date": selected_date.isoformat(),
        "available_dates": [item.isoformat() for item in dates],
        "hours": list(HOURS),
        "sources": {
            spec.key: _source_payload(files[spec.key], spec.label, raw_counts[spec.key])
            for spec in SOURCE_SPECS
        },
        "summary": {
            "sections": section_count,
            "users": len(users),
            "total_rows": total_rows,
            "worked_hours": total_worked_hours,
            "rows_per_hour": total_rows / total_worked_hours if total_worked_hours else None,
            "average_productivity_pct": (
                sum(productivity_values) / len(productivity_values)
                if productivity_values
                else None
            ),
        },
        "groups": groups,
    }
    _REPORT_CACHE.clear()
    _REPORT_CACHE[key] = report
    return report
