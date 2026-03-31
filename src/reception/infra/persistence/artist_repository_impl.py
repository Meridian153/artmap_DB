from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.reception.domain.artist import Artist, ArtistRepository


class ArtistRepositoryImpl(ArtistRepository):
    """Artist Repository 구현체 (Infrastructure Layer)"""

    def __init__(self, session: Session):
        self._session = session

    def find_by_id(self, artist_id: UUID) -> Artist | None:
        return self._session.get(Artist, artist_id)

    def find_by_wikidata_id(self, wikidata_id: str) -> Artist | None:
        return self._session.execute(
            select(Artist).where(Artist.wikidata_id == wikidata_id)
        ).scalar_one_or_none()

    def save(self, artist: Artist) -> Artist:
        self._session.add(artist)
        self._session.flush()
        return artist

    def find_all(self, limit: int = 100, offset: int = 0) -> list[Artist]:
        return list(
            self._session.execute(select(Artist).limit(limit).offset(offset)).scalars().all()
        )

    def search_by_name(self, name: str, limit: int = 20) -> list[Artist]:
        return list(
            self._session.execute(
                select(Artist)
                .where(Artist.name_en.ilike(f"%{name}%") | Artist.name_ko.ilike(f"%{name}%"))
                .limit(limit)
            )
            .scalars()
            .all()
        )
