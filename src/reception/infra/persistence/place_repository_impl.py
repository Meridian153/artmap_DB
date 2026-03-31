from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.reception.domain.institution.place import Place
from src.reception.domain.institution.place_repository import PlaceRepository


class PlaceRepositoryImpl(PlaceRepository):
    """Place Repository 구현체 (Infrastructure Layer)"""

    def __init__(self, session: Session):
        self._session = session

    def find_by_id(self, place_id: UUID) -> Place | None:
        return self._session.get(Place, place_id)

    def find_by_institution_id(self, institution_id: UUID) -> list[Place]:
        return list(
            self._session.execute(select(Place).where(Place.institution_id == institution_id))
            .scalars()
            .all()
        )

    def save(self, place: Place) -> Place:
        self._session.add(place)
        self._session.flush()
        return place

    def find_all(self, limit: int = 100, offset: int = 0) -> list[Place]:
        return list(
            self._session.execute(select(Place).limit(limit).offset(offset)).scalars().all()
        )
