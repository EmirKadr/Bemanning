from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

from app.backend.database import Base
from app.backend.models import Activity, Area, Person, User
from app.backend.sync_live_to_local import sync_database, sync_from_env


def sqlite_url(path):
    return f"sqlite:///{path.as_posix()}"


def test_sync_database_copies_live_rows_to_local_sqlite_file(tmp_path):
    source_path = tmp_path / "live.db"
    target_path = tmp_path / "local.db"
    source_engine = create_engine(sqlite_url(source_path))
    Base.metadata.create_all(source_engine)
    SessionLocal = sessionmaker(bind=source_engine)

    with SessionLocal() as session:
        area = Area(code="MG", name="Mestergruppen", sort_order=1, is_active=True)
        activity = Activity(
            code="MG_LKON",
            label="MG Lkon",
            area=area,
            color="#ffffff",
            category="work",
            sort_order=1,
            is_active=True,
        )
        session.add_all([area, activity])
        session.flush()
        person = Person(
            name="Anton Holmqvist",
            home_area=area,
            home_activity_id=activity.id,
            competencies=[],
            is_active=False,
            sort_order=7,
        )
        user = User(username="admin", role="admin", roles=["admin"], is_active=True)
        session.add_all([person, user])
        session.commit()

    stats = sync_database(sqlite_url(source_path), sqlite_url(target_path))

    assert stats["persons"] == 1
    target_engine = create_engine(sqlite_url(target_path))
    TargetSession = sessionmaker(bind=target_engine)
    with TargetSession() as session:
        copied = session.query(Person).one()
        copied.name = "Lokal ändring"
        session.commit()

    with SessionLocal() as session:
        assert session.query(Person).one().name == "Anton Holmqvist"


def test_sync_database_refuses_non_sqlite_target(tmp_path):
    source_path = tmp_path / "live.db"

    with pytest.raises(ValueError, match="SQLite"):
        sync_database(sqlite_url(source_path), "postgresql+psycopg://postgres:postgres@localhost/flow")


def test_sync_from_env_skips_when_live_database_url_is_missing(monkeypatch):
    monkeypatch.delenv("LIVE_DATABASE_URL", raising=False)
    monkeypatch.delenv("BEMANNING_LIVE_DATABASE_URL", raising=False)

    assert sync_from_env() is False
