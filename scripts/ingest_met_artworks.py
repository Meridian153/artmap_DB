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

logger = setup_logger("IngestMetArtworks")


def ingest_met_artworks(object_ids: list[int]):
    initialize_database()

    for object_id in object_ids:
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
                    source_api=ExternalApiSource.MET_MUSEUM.value, source_id=str(object_id)
                )
                artwork = service.ingest_artwork(command)

                if artwork:
                    # Met Museum 미술관 찾기 (Wikidata ID: Q160236)
                    met_museum = institution_repo.find_by_wikidata_id("Q160236")
                    if met_museum:
                        # 소유권 정보 저장
                        ownership = ArtworkOwnership(
                            artwork_id=artwork.id,
                            institution_id=met_museum.id,
                            is_primary_owner=True,
                        )
                        session.add(ownership)

                        # Met Museum의 장소 찾기
                        places = place_repo.find_by_institution_id(met_museum.id)
                        if places:
                            # 위치 정보 저장 (영구 소장)
                            location = ArtworkLocation.create(
                                artwork_id=artwork.id,
                                place_id=places[0].id,
                                location_type=LocationType.PERMANENT_COLLECTION,
                                start_date=date.today(),
                                source="Met Museum API",
                            )
                            session.add(location)

                    logger.info(f"✓ Ingested artwork: {artwork.title_en} (ID: {object_id})")
                else:
                    logger.warning(f"✗ Failed to ingest artwork ID: {object_id}")

        except Exception as e:
            logger.error(f"Error ingesting artwork {object_id}: {str(e)}")


if __name__ == "__main__":
    sample_object_ids = [
        436535,  # Wheat Field with Cypresses
        436528,  # The Starry Night (drawing)
        437853,  # Cypresses
        459123,  # Irises
        437112,  # Self-Portrait with a Straw Hat
    ]

    logger.info(f"Starting ingestion of {len(sample_object_ids)} artworks from Met Museum...")
    ingest_met_artworks(sample_object_ids)
    logger.info("Ingestion complete!")
