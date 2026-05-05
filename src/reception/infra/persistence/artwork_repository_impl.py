from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.reception.domain.artwork import Artwork, ArtworkRepository
from src.reception.domain.artwork.exceptions import (
    ArtworkNotFoundException,
    DuplicateArtworkException,
)


class ArtworkRepositoryImpl(ArtworkRepository):
    """Artwork Repository 구현체 (Infrastructure Layer)"""

    def __init__(self, session: Session):
        self._session = session

    def find_by_id(self, artwork_id: UUID) -> Artwork | None:
        return self._session.get(Artwork, artwork_id)

    def find_by_source(self, source_api: str, source_id: str) -> Artwork | None:
        return self._session.execute(
            select(Artwork).where(Artwork.source_api == source_api, Artwork.source_id == source_id)
        ).scalar_one_or_none()

    def save(self, artwork: Artwork) -> Artwork:
        existing = self.find_by_source(artwork.source_api, artwork.source_id)
        if existing and existing.id != artwork.id:
            raise DuplicateArtworkException(artwork.source_api, artwork.source_id)

        self._session.add(artwork)
        self._session.flush()
        return artwork

    def find_all(self, limit: int = 100, offset: int = 0) -> list[Artwork]:
        return list(
            self._session.execute(select(Artwork).limit(limit).offset(offset)).scalars().all()
        )

    def delete(self, artwork_id: UUID) -> bool:
        artwork = self.find_by_id(artwork_id)
        if not artwork:
            raise ArtworkNotFoundException(str(artwork_id))

        self._session.delete(artwork)
        self._session.flush()
        return True

    def find_by_status(self, status: str, limit: int = 100) -> list[Artwork]:
        return list(
            self._session.execute(select(Artwork).where(Artwork.status == status).limit(limit))
            .scalars()
            .all()
        )
