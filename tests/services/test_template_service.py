from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.backend.models import PersonScheduleTemplate
from app.backend.template_service import get_template_hours, get_template_hours_map


def make_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    PersonScheduleTemplate.__table__.create(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    return engine, session


def close_session(engine, session):
    session.close()
    PersonScheduleTemplate.__table__.drop(engine)
    engine.dispose()


def test_default_template_is_weekdays_only():
    engine, session = make_session()
    try:
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
    finally:
        close_session(engine, session)
