import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from datetime import date

from src.reception.application.artwork_service import ArtworkService, IngestArtworkCommand
from src.reception.domain.artwork.artwork_location import ArtworkLocation
from src.reception.domain.artwork.artwork_ownership import ArtworkOwnership
from src.reception.infra.external_apis import (
    ArtInstituteChicagoClient,
    MetMuseumClient,
    WikidataClient,
)
from src.reception.infra.persistence.artwork_repository_impl import ArtworkRepositoryImpl
from src.reception.infra.persistence.institution_repository_impl import InstitutionRepositoryImpl
from src.reception.infra.persistence.place_repository_impl import PlaceRepositoryImpl
from src.shared_kernel.domain.enums import ExternalApiSource, LocationType
from src.shared_kernel.infra.database.connection import get_session, initialize_database
from src.shared_kernel.infra.log.logger import setup_logger

logger = setup_logger("IngestAICartworks")


def ingest_aic_artworks(artwork_ids: list[int]):
    initialize_database()

    for artwork_id in artwork_ids:
        try:
            with get_session() as session:
                artwork_repo = ArtworkRepositoryImpl(session)
                institution_repo = InstitutionRepositoryImpl(session)
                place_repo = PlaceRepositoryImpl(session)

                service = ArtworkService(
                    artwork_repository=artwork_repo,
                    met_client=MetMuseumClient(),
                    aic_client=ArtInstituteChicagoClient(),
                    wikidata_client=WikidataClient(),
                )
                command = IngestArtworkCommand(
                    source_api=ExternalApiSource.ART_INSTITUTE_CHICAGO.value,
                    source_id=str(artwork_id),
                )
                artwork = service.ingest_artwork(command)

                if artwork:
                    # Art Institute of Chicago 미술관 찾기 (Wikidata ID: Q239303)
                    aic_museum = institution_repo.find_by_wikidata_id("Q239303")
                    if aic_museum:
                        # 소유권 정보 저장
                        ownership = ArtworkOwnership(
                            artwork_id=artwork.id,
                            institution_id=aic_museum.id,
                            is_primary_owner=True,
                        )
                        session.add(ownership)

                        # AIC의 장소 찾기
                        places = place_repo.find_by_institution_id(aic_museum.id)
                        if places:
                            # 위치 정보 저장 (영구 소장)
                            location = ArtworkLocation.create(
                                artwork_id=artwork.id,
                                place_id=places[0].id,
                                location_type=LocationType.PERMANENT_COLLECTION,
                                start_date=date.today(),
                                source="Art Institute of Chicago API",
                            )
                            session.add(location)

                    logger.info(f"✓ Ingested artwork: {artwork.title_en} (ID: {artwork_id})")
                else:
                    logger.warning(f"✗ Failed to ingest artwork ID: {artwork_id}")

        except Exception as e:
            logger.error(f"Error ingesting artwork {artwork_id}: {str(e)}")


if __name__ == "__main__":
    sample_artwork_ids = [
        27992,  # A Sunday on La Grande Jatte
        28560,  # The Bedroom
        80607,  # Nighthawks
        16568,  # American Gothic
        111628,  # The Old Guitarist
    ]

    logger.info(
        f"Starting ingestion of {len(sample_artwork_ids)} artworks from Art Institute of Chicago..."
    )
    ingest_aic_artworks(sample_artwork_ids)
    logger.info("Ingestion complete!")
