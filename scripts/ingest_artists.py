import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from data.artists_data import ARTISTS_DATA

from src.reception.domain.artist.artist import Artist
from src.reception.infra.persistence.artist_repository_impl import ArtistRepositoryImpl
from src.shared_kernel.infra.database.connection import get_session, initialize_database
from src.shared_kernel.infra.log.logger import setup_logger

logger = setup_logger("IngestArtists")


def ingest_artists():
    """화가 50명 데이터 수집 (MVP 문서 전체)"""
    initialize_database()

    logger.info(f"Starting ingestion of {len(ARTISTS_DATA)} artists...")

    success_count = 0
    skip_count = 0
    error_count = 0

    for artist_data in ARTISTS_DATA:
        try:
            with get_session() as session:
                artist_repo = ArtistRepositoryImpl(session)

                # 이미 존재하는지 확인
                existing = artist_repo.find_by_wikidata_id(artist_data["wikidata_id"])
                if existing:
                    logger.info(f"⊙ Artist already exists: {artist_data['name_en']}")
                    skip_count += 1
                    continue

                # Artist 생성
                artist = Artist.create(
                    name_en=artist_data["name_en"],
                    name_ko=artist_data["name_ko"],
                    birth_year=artist_data["birth_year"],
                    nationality=artist_data["nationality"],
                    bio_en=artist_data.get("bio_en", ""),
                    bio_ko=artist_data.get("bio_ko", ""),
                    death_year=artist_data.get("death_year"),
                    wikidata_id=artist_data["wikidata_id"],
                )
                artist_repo.save(artist)

                logger.info(
                    f"✓ Ingested artist: {artist_data['name_en']} ({artist_data['birth_year']}-{artist_data.get('death_year', 'present')})"
                )
                success_count += 1

        except Exception as e:
            logger.error(f"✗ Error ingesting artist {artist_data['name_en']}: {str(e)}")
            error_count += 1

    logger.info("\n=== Ingestion Summary ===")
    logger.info(f"Success: {success_count}")
    logger.info(f"Skipped (already exists): {skip_count}")
    logger.info(f"Errors: {error_count}")
    logger.info(f"Total: {len(ARTISTS_DATA)}")


if __name__ == "__main__":
    ingest_artists()
