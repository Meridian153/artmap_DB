from abc import ABC, abstractmethod
from uuid import UUID

from src.reception.domain.artist.artist import Artist


class ArtistRepository(ABC):
    """Artist Repository Interface (Domain Layer)"""

    @abstractmethod
    def find_by_id(self, artist_id: UUID) -> Artist | None:
        pass

    @abstractmethod
    def find_by_wikidata_id(self, wikidata_id: str) -> Artist | None:
        pass

    @abstractmethod
    def save(self, artist: Artist) -> Artist:
        pass

    @abstractmethod
    def find_all(self, limit: int = 100, offset: int = 0) -> list[Artist]:
        pass

    @abstractmethod
    def search_by_name(self, name: str, limit: int = 20) -> list[Artist]:
        pass
