from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..models import Person
from ..schemas import PersonCreate, PersonOut, PersonUpdate

router = APIRouter(prefix="/api/persons", tags=["persons"])


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
    _=Depends(get_current_user),
) -> Person:
    person = Person(**payload.model_dump())
    db.add(person)
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
    _=Depends(get_current_user),
) -> Person:
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person hittades inte")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(person, key, value)
    db.commit()
    db.refresh(person)
    return person


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(
    person_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
) -> None:
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Person hittades inte")
    person.is_active = False
    db.commit()
