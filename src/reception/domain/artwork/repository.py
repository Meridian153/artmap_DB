from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from src.reception.domain.artwork.artwork import Artwork


class ArtworkRepository(ABC):
    """
    Artwork Repository Interface (Domain Layer)
    구현체는 infra 레이어에 위치
    """

    @abstractmethod
    def find_by_id(self, artwork_id: UUID) -> Artwork | None:
        """ID로 작품 조회"""
        pass

    @abstractmethod
    def find_by_source(self, source_api: str, source_id: str) -> Artwork | None:
        """외부 소스로 작품 조회"""
        pass

    @abstractmethod
    def save(self, artwork: Artwork) -> Artwork:
        """작품 저장"""
        pass

    @abstractmethod
    def find_all(self, limit: int = 100, offset: int = 0) -> list[Artwork]:
        """모든 작품 조회 (페이징)"""
        pass

    @abstractmethod
    def delete(self, artwork_id: UUID) -> bool:
        """작품 삭제"""
        pass

    @abstractmethod
    def find_by_status(self, status: str, limit: int = 100) -> list[Artwork]:
        """상태별 작품 조회"""
        pass
