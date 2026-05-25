import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.backend.database import Base
from app.backend.models import Area, Business, Person, User
from app.backend.routers.persons import reorder_person_sort_order
from app.backend.schemas import PersonSortOrderUpdate
from app.backend.user_access import can_access_view, can_sort_person_order


@pytest.fixture()
def person_sort_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def add_scope(session):
    business = Business(code="STIGAMO", name="Stigamo", sort_order=1)
    mg = Area(business=business, code="MG", name="Mestergruppen", sort_order=1)
    gg = Area(business=business, code="GG", name="Granngarden", sort_order=2)
    session.add_all([business, mg, gg])
    session.flush()
    return business, mg, gg


def make_user(role, *, business_id, area_id, roles=None):
    return User(
        username=f"{role}-user",
        role=role,
        roles=roles or [role],
        business_id=business_id,
        area_id=area_id,
        is_active=True,
    )


def test_person_sort_order_defaults_only_allow_staffing_admin_and_super_user():
    staffing = User(username="staffing", role="staffing_manager", roles=["staffing_manager"], is_active=True)
    admin = User(username="admin", role="admin", roles=["admin"], is_active=True)
    leader = User(username="leader", role="leader", roles=["leader"], is_active=True)
    super_user = User(username="super", role="super_user", roles=["super_user"], is_active=True)

    assert can_access_view(staffing, {}, "personSortOrder", "edit")
    assert can_access_view(admin, {}, "personSortOrder", "edit")
    assert can_access_view(super_user, {}, "personSortOrder", "edit")
    assert not can_access_view(leader, {}, "personSortOrder", "edit")
    assert can_sort_person_order(staffing)
    assert can_sort_person_order(admin)
    assert can_sort_person_order(super_user)
    assert not can_sort_person_order(leader)


def test_reorder_person_sort_order_swaps_sort_slots_inside_user_area(person_sort_db):
    business, mg, gg = add_scope(person_sort_db)
    user = make_user("staffing_manager", business_id=business.id, area_id=mg.id)
    first = Person(business_id=business.id, name="Anna", home_area_id=mg.id, competencies=[], sort_order=10)
    other_area = Person(business_id=business.id, name="Goran", home_area_id=gg.id, competencies=[], sort_order=20)
    second = Person(business_id=business.id, name="Bo", home_area_id=mg.id, competencies=[], sort_order=30)
    third = Person(business_id=business.id, name="Cia", home_area_id=mg.id, competencies=[], sort_order=50)
    person_sort_db.add_all([user, first, other_area, second, third])
    person_sort_db.flush()

    result = reorder_person_sort_order(
        PersonSortOrderUpdate(person_ids=[second.id, first.id, third.id]),
        db=person_sort_db,
        user=user,
    )

    assert [person.id for person in result] == [second.id, first.id, third.id]
    assert second.sort_order == 10
    assert first.sort_order == 30
    assert third.sort_order == 50
    assert other_area.sort_order == 20


def test_reorder_person_sort_order_rejects_unallowed_role_even_if_view_was_granted(person_sort_db):
    business, mg, _gg = add_scope(person_sort_db)
    user = make_user("leader", business_id=business.id, area_id=mg.id)
    first = Person(business_id=business.id, name="Anna", home_area_id=mg.id, competencies=[], sort_order=1)
    second = Person(business_id=business.id, name="Bo", home_area_id=mg.id, competencies=[], sort_order=2)
    person_sort_db.add_all([user, first, second])
    person_sort_db.flush()

    with pytest.raises(HTTPException) as exc:
        reorder_person_sort_order(
            PersonSortOrderUpdate(person_ids=[second.id, first.id]),
            db=person_sort_db,
            user=user,
        )

    assert exc.value.status_code == 403


def test_reorder_person_sort_order_rejects_person_from_other_area(person_sort_db):
    business, mg, gg = add_scope(person_sort_db)
    user = make_user("admin", business_id=business.id, area_id=mg.id)
    first = Person(business_id=business.id, name="Anna", home_area_id=mg.id, competencies=[], sort_order=1)
    other = Person(business_id=business.id, name="Goran", home_area_id=gg.id, competencies=[], sort_order=2)
    person_sort_db.add_all([user, first, other])
    person_sort_db.flush()

    with pytest.raises(HTTPException) as exc:
        reorder_person_sort_order(
            PersonSortOrderUpdate(person_ids=[other.id, first.id]),
            db=person_sort_db,
            user=user,
        )

    assert exc.value.status_code == 403
    assert "hemomrade" in exc.value.detail.lower() or "hemområde" in exc.value.detail.lower()


def test_reorder_person_sort_order_requires_user_area(person_sort_db):
    business, mg, _gg = add_scope(person_sort_db)
    user = make_user("admin", business_id=business.id, area_id=None)
    first = Person(business_id=business.id, name="Anna", home_area_id=mg.id, competencies=[], sort_order=1)
    second = Person(business_id=business.id, name="Bo", home_area_id=mg.id, competencies=[], sort_order=2)
    person_sort_db.add_all([user, first, second])
    person_sort_db.flush()

    with pytest.raises(HTTPException) as exc:
        reorder_person_sort_order(
            PersonSortOrderUpdate(person_ids=[second.id, first.id]),
            db=person_sort_db,
            user=user,
        )

    assert exc.value.status_code == 403
