import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from data.museums_data import MUSEUMS_DATA

from src.reception.domain.institution.institution import Institution
from src.reception.domain.institution.place import Place
from src.reception.infra.persistence.institution_repository_impl import InstitutionRepositoryImpl
from src.reception.infra.persistence.place_repository_impl import PlaceRepositoryImpl
from src.shared_kernel.domain.enums import InstitutionType
from src.shared_kernel.infra.database.connection import get_session, initialize_database
from src.shared_kernel.infra.log.logger import setup_logger

logger = setup_logger("IngestMuseums")


def ingest_museums():
    """미술관 30곳 데이터 수집 (MVP 문서 전체)"""
    initialize_database()

    logger.info(f"Starting ingestion of {len(MUSEUMS_DATA)} museums...")

    success_count = 0
    skip_count = 0
    error_count = 0

    for museum_data in MUSEUMS_DATA:
        try:
            with get_session() as session:
                institution_repo = InstitutionRepositoryImpl(session)
                place_repo = PlaceRepositoryImpl(session)

                # 이미 존재하는지 확인
                existing = institution_repo.find_by_wikidata_id(museum_data["wikidata_id"])
                if existing:
                    logger.info(f"⊙ Museum already exists: {museum_data['name_en']}")
                    skip_count += 1
                    continue

                # Institution 생성
                institution = Institution.create(
                    institution_type=InstitutionType.MUSEUM,
                    country_code=museum_data["country_code"],
                    name_en=museum_data["name_en"],
                    name_ko=museum_data["name_ko"],
                    website=museum_data.get("website"),
                    description_en=museum_data.get("description_en"),
                    description_ko=museum_data.get("description_ko"),
                    wikidata_id=museum_data["wikidata_id"],
                )
                institution = institution_repo.save(institution)

                # Place 생성 (좌표 정보 포함)
                place = Place.create(
                    name_en=museum_data["name_en"],
                    name_ko=museum_data["name_ko"],
                    country=museum_data["country_code"],
                    city=museum_data["city"],
                    institution_id=institution.id,
                    latitude=museum_data.get("latitude"),
                    longitude=museum_data.get("longitude"),
                )
                place_repo.save(place)

                logger.info(f"✓ Ingested museum: {museum_data['name_en']} ({museum_data['city']})")
                success_count += 1

        except Exception as e:
            logger.error(f"✗ Error ingesting museum {museum_data['name_en']}: {str(e)}")
            error_count += 1

    logger.info("\n=== Ingestion Summary ===")
    logger.info(f"Success: {success_count}")
    logger.info(f"Skipped (already exists): {skip_count}")
    logger.info(f"Errors: {error_count}")
    logger.info(f"Total: {len(MUSEUMS_DATA)}")


if __name__ == "__main__":
    ingest_museums()
