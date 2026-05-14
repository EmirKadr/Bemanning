from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..audit import log as audit_log
from ..deps import get_current_user, get_db
from ..models import Person, User
from ..schemas import PersonCreate, PersonOut, PersonUpdate

router = APIRouter(prefix="/api/persons", tags=["persons"])


def _person_snapshot(person: Person) -> dict:
    return {
        "id": person.id,
        "name": person.name,
        "home_area_id": person.home_area_id,
        "home_activity_id": person.home_activity_id,
        "competencies": person.competencies,
        "comment": person.comment,
        "is_active": person.is_active,
        "sort_order": person.sort_order,
    }


@router.get("", response_model=list[PersonOut])
def list_persons(
    include_inactive: bool = False,
    area_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> list[Person]:
    q = db.query(Person)
    if not include_inactive:
        q = q.filter(Person.is_active.is_(True))
    if area_id is not None:
        q = q.filter(Person.home_area_id == area_id)
    return q.order_by(Person.sort_order, Person.name).all()


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
def create_person(
    payload: PersonCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Person:
    person = Person(**payload.model_dump())
    db.add(person)
    db.flush()
    audit_log(
        db,
        entity_type="person",
        entity_id=person.id,
        action="create",
        old_value=None,
        new_value=_person_snapshot(person),
        user_id=user.id,
    )
    db.commit()
    db.refresh(person)
    return person


@router.get("/{person_id}", response_model=PersonOut)
def get_person(person_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)) -> Person:
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person hittades inte")
    return person


@router.put("/{person_id}", response_model=PersonOut)
def update_person(
    person_id: int,
    payload: PersonUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Person:
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person hittades inte")
    before = _person_snapshot(person)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(person, key, value)
    audit_log(
        db,
        entity_type="person",
        entity_id=person.id,
        action="update",
        old_value=before,
        new_value=_person_snapshot(person),
        user_id=user.id,
    )
    db.commit()
    db.refresh(person)
    return person


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(
    person_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person hittades inte")
    before = _person_snapshot(person)
    person.is_active = False
    audit_log(
        db,
        entity_type="person",
        entity_id=person.id,
        action="deactivate",
        old_value=before,
        new_value=_person_snapshot(person),
        user_id=user.id,
    )
    db.commit()
