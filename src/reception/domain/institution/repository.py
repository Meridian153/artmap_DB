from abc import ABC, abstractmethod
from uuid import UUID

from src.reception.domain.institution.institution import Institution


class InstitutionRepository(ABC):
    """Institution Repository Interface (Domain Layer)"""

    @abstractmethod
    def find_by_id(self, institution_id: UUID) -> Institution | None:
        pass

    @abstractmethod
    def find_by_wikidata_id(self, wikidata_id: str) -> Institution | None:
        pass

    @abstractmethod
    def save(self, institution: Institution) -> Institution:
        pass

    @abstractmethod
    def find_all(self, limit: int = 100, offset: int = 0) -> list[Institution]:
        pass

    @abstractmethod
    def search_by_name(self, name: str, limit: int = 20) -> list[Institution]:
        pass
