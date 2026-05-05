from __future__ import annotations

from abc import ABC, abstractmethod


class IMetMuseumPort(ABC):
    @abstractmethod
    def get_artwork(self, object_id: int) -> dict | None:
        """Met Museum에서 작품 데이터 조회"""
        ...

    @abstractmethod
    def search_artworks(self, query: str, limit: int = 10) -> list[int]:
        """Met Museum에서 작품 검색, object_id 목록 반환"""
        ...


class IArtInstituteChicagoPort(ABC):
    @abstractmethod
    def get_artwork(self, artwork_id: int) -> dict | None:
        """Art Institute of Chicago에서 작품 데이터 조회"""
        ...

    @abstractmethod
    def search_artworks(self, query: str, limit: int = 10) -> list[dict]:
        """Art Institute of Chicago에서 작품 검색"""
        ...


class IWikidataPort(ABC):
    @abstractmethod
    def get_artwork_details(self, wikidata_id: str) -> dict | None:
        """Wikidata에서 작품 상세 정보 조회"""
        ...

    @abstractmethod
    def search_artworks(self, query: str, limit: int = 10) -> list[dict]:
        """Wikidata에서 작품 검색"""
        ...

    @abstractmethod
    def search_artworks_by_collection(
        self, collection_id: str, limit: int = 100
    ) -> list[dict]:
        """소장처(institution) 기준으로 작품 검색 (SPARQL)"""
        ...

    @abstractmethod
    def search_artworks_by_creator(
        self, creator_id: str, limit: int = 100
    ) -> list[dict]:
        """제작자(artist) 기준으로 작품 검색 (SPARQL)"""
        ...

    @abstractmethod
    def search_artworks_by_collection_and_creator(
        self, collection_id: str, creator_id: str, limit: int = 100
    ) -> list[dict]:
        """소장처 + 제작자 동시 조건으로 작품 검색 (SPARQL)"""
        ...
