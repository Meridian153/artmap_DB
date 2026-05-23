from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.reception.domain.art_movement.art_movement import ArtMovement
from src.reception.domain.art_movement.repository import ArtMovementRepository


class ArtMovementRepositoryImpl(ArtMovementRepository):
    """ArtMovement Repository 구현체 (Infrastructure Layer)"""

    def __init__(self, session: Session):
        self._session = session

    def find_by_id(self, art_movement_id: UUID) -> ArtMovement | None:
        return self._session.get(ArtMovement, art_movement_id)

    def find_by_name_en(self, name_en: str) -> ArtMovement | None:
        return self._session.execute(
            select(ArtMovement).where(ArtMovement.name_en == name_en)
        ).scalar_one_or_none()

    def save(self, art_movement: ArtMovement) -> ArtMovement:
        self._session.add(art_movement)
        self._session.flush()
        return art_movement

    def find_all(self) -> list[ArtMovement]:
        return list(
            self._session.execute(select(ArtMovement)).scalars().all()
        )
