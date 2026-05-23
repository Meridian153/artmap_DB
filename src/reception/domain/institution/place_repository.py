from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.reception.domain.institution.place import Place


class PlaceRepository(ABC):
    """Place Repository Interface (Domain Layer)"""

    @abstractmethod
    def find_by_id(self, place_id: UUID) -> Place | None:
        pass

    @abstractmethod
    def find_by_institution_id(self, institution_id: UUID) -> list[Place]:
        pass

    @abstractmethod
    def save(self, place: Place) -> Place:
        pass

    @abstractmethod
    def find_all(self, limit: int = 100, offset: int = 0) -> list[Place]:
        pass
