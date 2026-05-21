"""Copy a live Bemanning database into the local SQLite preview database.

The copy is deliberately one-way: source is opened for reads, and the target
must be a SQLite file. Local edits can therefore never write back to live.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, insert, select
from sqlalchemy.engine import make_url

from . import models  # noqa: F401  -- register models on Base.metadata
from .config import settings
from .database import Base, _normalize_url
from .models import Activity, AppSetting, Area, AuditLog, Person, PersonScheduleTemplate, ScheduleCell, User


SOURCE_ENV_NAMES = ("LIVE_DATABASE_URL", "BEMANNING_LIVE_DATABASE_URL")
TABLE_COPY_ORDER = (
    Area,
    User,
    Activity,
    Person,
    ScheduleCell,
    PersonScheduleTemplate,
    AuditLog,
    AppSetting,
)


def _sqlite_database_path(database_url: str) -> Path:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite"):
        raise ValueError("Lokal sync får bara skriva till SQLite, inte till live/Postgres.")
    if not url.database or url.database == ":memory:":
        raise ValueError("Lokal sync kräver en SQLite-fil, inte en minnesdatabas.")
    return Path(url.database).resolve()


def _column_default(column) -> Any:
    default = column.default
    if default is None:
        return None
    value = default.arg
    if callable(value):
        return value()
    return value


def _table_rows(source_connection, model) -> list[dict[str, Any]]:
    table = model.__table__
    source_columns = {
        column["name"]
        for column in inspect(source_connection).get_columns(table.name)
    }
    selected_columns = [column for column in table.columns if column.name in source_columns]
    if not selected_columns:
        return []

    order_columns = [column for column in table.primary_key.columns if column.name in source_columns]
    statement = select(*selected_columns)
    if order_columns:
        statement = statement.order_by(*order_columns)

    rows: list[dict[str, Any]] = []
    for source_row in source_connection.execute(statement).mappings():
        row = dict(source_row)
        for column in table.columns:
            if column.name in row or column.server_default is not None:
                continue
            if column.default is not None:
                row[column.name] = _column_default(column)
            elif column.nullable:
                row[column.name] = None
        rows.append(row)
    return rows


def sync_database(source_database_url: str, target_database_url: str) -> dict[str, int]:
    """Replace the local SQLite target with a fresh copy from source."""
    source_url = _normalize_url(source_database_url)
    target_path = _sqlite_database_path(target_database_url)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    if make_url(source_url).drivername.startswith("sqlite"):
        source_path = _sqlite_database_path(source_url)
        if source_path == target_path:
            raise ValueError("Källa och mål är samma SQLite-fil.")

    temp_path = target_path.with_name(f"{target_path.name}.syncing")
    if temp_path.exists():
        temp_path.unlink()

    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(f"sqlite:///{temp_path.as_posix()}")
    stats: dict[str, int] = {}
    try:
        Base.metadata.create_all(target_engine)
        with source_engine.connect() as source_connection, target_engine.begin() as target_connection:
            source_transaction = source_connection.begin()
            try:
                if source_engine.dialect.name == "postgresql":
                    source_connection.exec_driver_sql("SET TRANSACTION READ ONLY")

                for model in TABLE_COPY_ORDER:
                    table = model.__table__
                    rows = _table_rows(source_connection, model)
                    if model is Person:
                        for row in rows:
                            row["is_active"] = True
                    if rows:
                        target_connection.execute(insert(table), rows)
                    stats[table.name] = len(rows)
                source_transaction.commit()
            except Exception:
                source_transaction.rollback()
                raise
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
    finally:
        source_engine.dispose()
        target_engine.dispose()

    temp_path.replace(target_path)
    return stats


def sync_from_env() -> bool:
    source_url = next((os.getenv(name) for name in SOURCE_ENV_NAMES if os.getenv(name)), "")
    if not source_url:
        return False

    target_url = os.getenv("DATABASE_URL") or settings.DATABASE_URL
    stats = sync_database(source_url, target_url)
    total_rows = sum(stats.values())
    table_summary = ", ".join(f"{table}={count}" for table, count in stats.items())
    print(f"Kopierade live-data till lokal SQLite ({total_rows} rader).")
    print(table_summary)
    return True


def main() -> None:
    if not sync_from_env():
        print("LIVE_DATABASE_URL saknas. Ingen live-kopia gjordes.")


if __name__ == "__main__":
    main()
