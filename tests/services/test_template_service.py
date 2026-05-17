from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.backend.models import Activity, Area, Person, PersonScheduleTemplate
from app.backend.template_service import get_template_hours, get_template_hours_map


def make_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Area.__table__.create(engine)
    Activity.__table__.create(engine)
    Person.__table__.create(engine)
    PersonScheduleTemplate.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    return engine, session


def close_session(engine, session):
    session.close()
    PersonScheduleTemplate.__table__.drop(engine)
    Person.__table__.drop(engine)
    Activity.__table__.drop(engine)
    Area.__table__.drop(engine)
    engine.dispose()


def add_person(session, person_id: int = 1, *, has_fixed_schedule: bool = True):
    session.add(
        Person(
            id=person_id,
            name=f"Person {person_id}",
            competencies=[],
            has_fixed_schedule=has_fixed_schedule,
            is_active=True,
            sort_order=person_id,
        )
    )
    session.commit()


def test_default_template_is_weekdays_only():
    engine, session = make_session()
    try:
        add_person(session)
        assert get_template_hours(session, 1, 1) == {7, 8, 9, 10, 11, 13, 14, 15}
        assert get_template_hours(session, 1, 6) is None
        template_map = get_template_hours_map(session, [1], [1, 6])
        assert template_map[(1, 1)] == {7, 8, 9, 10, 11, 13, 14, 15}
        assert template_map[(1, 6)] is None
    finally:
        close_session(engine, session)


def test_missing_days_in_custom_template_are_off():
    engine, session = make_session()
    try:
        add_person(session)
        session.add(
            PersonScheduleTemplate(
                person_id=1,
                weekday=1,
                is_off=False,
                start_hour=7,
                end_hour=16,
            )
        )
        session.commit()

        assert get_template_hours(session, 1, 1) == {7, 8, 9, 10, 11, 13, 14, 15}
        assert get_template_hours(session, 1, 2) is None
        assert get_template_hours(session, 1, 6) is None
        template_map = get_template_hours_map(session, [1], [1, 2, 6])
        assert template_map[(1, 1)] == {7, 8, 9, 10, 11, 13, 14, 15}
        assert template_map[(1, 2)] is None
        assert template_map[(1, 6)] is None
        assert get_template_hours_map(session, [1], [2])[(1, 2)] is None
    finally:
        close_session(engine, session)


def test_hourly_worker_has_no_template_hours_without_being_off_template():
    engine, session = make_session()
    try:
        add_person(session, has_fixed_schedule=False)
        session.add(
            PersonScheduleTemplate(
                person_id=1,
                weekday=1,
                is_off=False,
                start_hour=7,
                end_hour=16,
            )
        )
        session.commit()

        assert get_template_hours(session, 1, 1) is None
        assert get_template_hours(session, 1, 6) is None
        template_map = get_template_hours_map(session, [1], [1, 6])
        assert template_map[(1, 1)] is None
        assert template_map[(1, 6)] is None
    finally:
        close_session(engine, session)
