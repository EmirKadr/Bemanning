from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.backend.database import Base
from app.backend.models import Activity, Area, Person, PersonScheduleTemplate, ScheduleCell
from app.backend.seed import ACTIVITIES, AREAS, PERSONS, remove_duplicate_persons, seed_persons


def test_seed_contains_ehandel_area_and_default_activities():
    areas_by_code = {area["code"]: area for area in AREAS}
    activity_codes = {activity["code"] for activity in ACTIVITIES}

    assert areas_by_code["EH"]["name"] == "E-Handel"
    assert {"EH_PLOCK", "EH_PACK", "EH_STOD", "EH_VAS"} <= activity_codes


def test_seed_removes_existing_duplicate_person_names():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        area = Area(code="GG", name="Granngården", sort_order=1)
        session.add(area)
        session.flush()
        activity = Activity(
            code="GG_VM",
            label="GG VM",
            area_id=area.id,
            color="#ffffff",
            category="work",
            sort_order=1,
            is_active=True,
        )
        duplicate_name = PERSONS[0]
        kept = Person(name=duplicate_name, home_area_id=area.id, competencies=[])
        duplicate = Person(name=duplicate_name, home_area_id=area.id, competencies=[])
        session.add_all(
            [
                activity,
                kept,
                duplicate,
            ]
        )
        session.flush()
        session.add_all(
            [
                ScheduleCell(
                    year=2026,
                    week=21,
                    weekday=1,
                    hour=7,
                    person_id=duplicate.id,
                    activity_id=activity.id,
                ),
                PersonScheduleTemplate(person_id=duplicate.id, weekday=1, start_hour=7, end_hour=16),
            ]
        )
        session.flush()

        remove_duplicate_persons(session)
        seed_persons(session, {"GG": area})
        session.flush()

        duplicates = session.query(Person).filter_by(name=duplicate_name).all()
        assert len(duplicates) == 1
        assert duplicates[0].id == kept.id
        assert duplicates[0].home_activity_id == activity.id
        assert session.query(ScheduleCell).filter_by(person_id=duplicate.id).count() == 0
        assert session.query(PersonScheduleTemplate).filter_by(person_id=duplicate.id).count() == 0
    finally:
        session.close()
        Base.metadata.drop_all(engine)
