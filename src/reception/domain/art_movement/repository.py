from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.reception.domain.art_movement.art_movement import ArtMovement


class ArtMovementRepository(ABC):
    """ArtMovement Repository Interface (Domain Layer)"""

    @abstractmethod
    def find_by_id(self, art_movement_id: UUID) -> ArtMovement | None:
        pass

    @abstractmethod
    def find_by_name_en(self, name_en: str) -> ArtMovement | None:
        pass

    @abstractmethod
    def save(self, art_movement: ArtMovement) -> ArtMovement:
        pass

    @abstractmethod
    def find_all(self) -> list[ArtMovement]:
        pass
