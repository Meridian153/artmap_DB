from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.reception.application.ports import (
    IArtInstituteChicagoPort,
    IMetMuseumPort,
    IWikidataPort,
)
from src.reception.domain.artwork import Artwork, ArtworkRepository
from src.reception.domain.artwork.exceptions import ArtworkNotFoundException
from src.shared_kernel.domain.enums import ExternalApiSource
from src.shared_kernel.infra.log.logger import setup_logger


@dataclass
class IngestArtworkCommand:
    """작품 수집 커맨드"""

    source_api: str
    source_id: str


@dataclass
class PublishArtworkCommand:
    """작품 전시 커맨드"""

    artwork_id: UUID


class ArtworkService:
    """
    Artwork Application Service
    Use Case들을 aggregate 기준으로 묶음
    """

    def __init__(
        self,
        artwork_repository: ArtworkRepository,
        met_client: IMetMuseumPort,
        aic_client: IArtInstituteChicagoPort,
        wikidata_client: IWikidataPort,
    ):
        self.artwork_repo = artwork_repository
        self.met_client = met_client
        self.aic_client = aic_client
        self.wikidata_client = wikidata_client
        self.logger = setup_logger("ArtworkService")

    def ingest_artwork(self, command: IngestArtworkCommand) -> Artwork | None:
        """작품 수집 (Command)"""
        existing = self.artwork_repo.find_by_source(command.source_api, command.source_id)

        if existing:
            self.logger.info(f"Artwork already exists: {command.source_api}:{command.source_id}")
            return existing

        if command.source_api == ExternalApiSource.MET_MUSEUM.value:
            return self._ingest_from_met(command.source_id)
        elif command.source_api == ExternalApiSource.ART_INSTITUTE_CHICAGO.value:
            return self._ingest_from_aic(command.source_id)
        elif command.source_api == ExternalApiSource.WIKIDATA.value:
            return self._ingest_from_wikidata(command.source_id)

        self.logger.warning(f"Unknown source API: {command.source_api}")
        return None

    def publish_artwork(self, command: PublishArtworkCommand) -> Artwork:
        """작품 전시 (Command)"""
        artwork = self.artwork_repo.find_by_id(command.artwork_id)
        if not artwork:
            raise ArtworkNotFoundException(str(command.artwork_id))

        artwork.publish_to_display()
        return self.artwork_repo.save(artwork)

    def move_to_storage(self, artwork_id: UUID) -> Artwork:
        """작품 보관 (Command)"""
        artwork = self.artwork_repo.find_by_id(artwork_id)
        if not artwork:
            raise ArtworkNotFoundException(str(artwork_id))

        artwork.move_to_storage()
        return self.artwork_repo.save(artwork)

    def _ingest_from_met(self, object_id: str) -> Artwork | None:
        data = self.met_client.get_artwork(int(object_id))
        if not data:
            return None

        artwork = Artwork.create_from_external_source(
            source_api=ExternalApiSource.MET_MUSEUM.value,
            source_id=data.get("source_id"),
            title_en=data.get("title", "Untitled"),
            title_ko=data.get("title", "Untitled"),
            year_created=data.get("object_begin_date") or 0,
            year_end=data.get("object_end_date"),
            medium_en=data.get("medium", ""),
            medium_ko=data.get("medium", ""),
            dimensions=data.get("dimensions", ""),
            image_url=data.get("primary_image", ""),
            image_source="Met Museum",
            is_public_domain=data.get("is_public_domain", False),
        )

        return self.artwork_repo.save(artwork)

    def _ingest_from_aic(self, artwork_id: str) -> Artwork | None:
        data = self.aic_client.get_artwork(int(artwork_id))
        if not data:
            return None

        artwork = Artwork.create_from_external_source(
            source_api=ExternalApiSource.ART_INSTITUTE_CHICAGO.value,
            source_id=data.get("source_id"),
            title_en=data.get("title", "Untitled"),
            title_ko=data.get("title", "Untitled"),
            year_created=data.get("date_start") or 0,
            year_end=data.get("date_end"),
            medium_en=data.get("medium_display", ""),
            medium_ko=data.get("medium_display", ""),
            dimensions=data.get("dimensions", ""),
            image_url=data.get("image_url", ""),
            image_source="Art Institute of Chicago",
            is_public_domain=data.get("is_public_domain", False),
        )

        return self.artwork_repo.save(artwork)

    def _ingest_from_wikidata(self, wikidata_id: str) -> Artwork | None:
        data = self.wikidata_client.get_artwork_details(wikidata_id)
        if not data:
            return None

        inception_year = 0
        if data.get("inception"):
            try:
                inception_year = int(data["inception"][:4])
            except (ValueError, TypeError):
                pass

        artwork = Artwork.create_from_external_source(
            source_api=ExternalApiSource.WIKIDATA.value,
            source_id=wikidata_id,
            title_en=data.get("title_en", "Untitled"),
            title_ko=data.get("title_ko", "Untitled"),
            year_created=inception_year,
            medium_en=data.get("material", ""),
            medium_ko=data.get("material", ""),
            image_url=data.get("image", ""),
            image_source="Wikidata",
            is_public_domain=True,
        )

        return self.artwork_repo.save(artwork)
