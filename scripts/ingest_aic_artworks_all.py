#!/usr/bin/env python3
"""
Art Institute of Chicago 작품 수집 스크립트 (MVP 화가 50명 기준)
50명 화가의 이름으로 AIC API 검색 → 작품 저장 + artwork_artists 연결
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from datetime import date

from src.reception.domain.artwork.artwork import Artwork
from src.reception.domain.artwork.artwork_artist import ArtworkArtist
from src.reception.domain.artwork.artwork_location import ArtworkLocation
from src.reception.domain.artwork.artwork_ownership import ArtworkOwnership
from src.reception.infra.external_apis import ArtInstituteChicagoClient
from src.reception.infra.persistence.artist_repository_impl import ArtistRepositoryImpl
from src.reception.infra.persistence.artwork_repository_impl import ArtworkRepositoryImpl
from src.reception.infra.persistence.institution_repository_impl import InstitutionRepositoryImpl
from src.reception.infra.persistence.place_repository_impl import PlaceRepositoryImpl
from src.shared_kernel.domain.enums import ExternalApiSource, LocationType
from src.shared_kernel.infra.database.connection import get_session, initialize_database
from src.shared_kernel.infra.log.logger import setup_logger

logger = setup_logger("IngestAICArtworksAll")

AIC_WIKIDATA_ID = "Q239303"
AIC_IIIF_BASE = "https://www.artic.edu/iiif/2"
MAX_PER_ARTIST = 5


def ingest_aic_artworks_all():
    initialize_database()

    # DB에서 화가 50명 로드
    with get_session() as session:
        artist_repo = ArtistRepositoryImpl(session)
        artists = artist_repo.find_all(limit=100)
        artist_list = [
            {"id": a.id, "name_en": a.name_en, "wikidata_id": a.wikidata_id}
            for a in artists
            if a.wikidata_id
        ]
    logger.info(f"Loaded {len(artist_list)} artists from DB")

    aic_client = ArtInstituteChicagoClient()
    success_count = 0
    skip_count = 0
    error_count = 0
    no_result_count = 0

    for artist in artist_list:
        artist_name = artist["name_en"]
        artist_db_id = artist["id"]

        logger.info(f"[{artist_name}] Searching AIC...")
        try:
            # AIC 검색 - 화가 이름으로 검색
            results = aic_client.search_artworks(query=artist_name, limit=MAX_PER_ARTIST * 3)
            if not results:
                logger.info(f"  → No results for {artist_name}")
                no_result_count += 1
                continue

            saved = 0
            for result in results:
                if saved >= MAX_PER_ARTIST:
                    break

                artwork_id = result.get("id")
                if not artwork_id:
                    continue

                # artist_display에 화가 이름이 포함된 것만 처리 (검색 오염 방지)
                artist_display = result.get("artist_display", "")
                # 성(last name)만 확인해도 충분 (e.g. "Van Gogh", "Monet")
                last_name = artist_name.split()[-1]
                if last_name.lower() not in artist_display.lower():
                    continue

                try:
                    with get_session() as session:
                        artwork_repo = ArtworkRepositoryImpl(session)
                        institution_repo = InstitutionRepositoryImpl(session)
                        place_repo = PlaceRepositoryImpl(session)

                        # 중복 확인
                        existing = artwork_repo.find_by_source(
                            ExternalApiSource.ART_INSTITUTE_CHICAGO.value, str(artwork_id)
                        )
                        if existing:
                            skip_count += 1
                            saved += 1
                            continue

                        # AIC API에서 작품 상세 정보 가져오기
                        raw = aic_client.get_artwork(artwork_id)
                        if not raw:
                            continue

                        # 이미지 URL 구성
                        image_url = raw.get("image_url", "")
                        if not image_url and raw.get("image_id"):
                            image_url = f"{AIC_IIIF_BASE}/{raw['image_id']}/full/843,/0/default.jpg"

                        # Artwork 엔티티 생성
                        artwork = Artwork.create_from_external_source(
                            source_api=ExternalApiSource.ART_INSTITUTE_CHICAGO.value,
                            source_id=str(artwork_id),
                            title_en=raw.get("title", "Untitled"),
                            title_ko=raw.get("title", "Untitled"),
                            year_created=raw.get("date_start") or 0,
                            year_end=raw.get("date_end"),
                            medium_en=raw.get("medium_display", ""),
                            medium_ko=raw.get("medium_display", ""),
                            dimensions=raw.get("dimensions", ""),
                            image_url=image_url,
                            image_source="Art Institute of Chicago",
                            is_public_domain=raw.get("is_public_domain", False),
                        )
                        artwork = artwork_repo.save(artwork)

                        # Artwork ↔ Artist 연결
                        session.merge(ArtworkArtist(artwork_id=artwork.id, artist_id=artist_db_id))

                        # AIC 찾기 → 소유권 + 위치 저장
                        aic_museum = institution_repo.find_by_wikidata_id(AIC_WIKIDATA_ID)
                        if aic_museum:
                            session.merge(
                                ArtworkOwnership(
                                    artwork_id=artwork.id,
                                    institution_id=aic_museum.id,
                                    is_primary_owner=True,
                                )
                            )
                            places = place_repo.find_by_institution_id(aic_museum.id)
                            if places:
                                session.add(
                                    ArtworkLocation.create(
                                        artwork_id=artwork.id,
                                        place_id=places[0].id,
                                        location_type=LocationType.PERMANENT_COLLECTION,
                                        start_date=date.today(),
                                        source="Art Institute of Chicago API",
                                    )
                                )

                        logger.info(f"  ✓ [{artist_name}] {artwork.title_en} ({artwork_id})")
                        success_count += 1
                        saved += 1

                except Exception as e:
                    logger.error(f"  ✗ Error on artwork_id {artwork_id}: {e}")
                    error_count += 1

        except Exception as e:
            logger.error(f"  ✗ Search error for {artist_name}: {e}")
            error_count += 1

        time.sleep(1.0)  # AIC rate limit

    logger.info("\n=== AIC Ingestion Summary ===")
    logger.info(f"Success: {success_count}")
    logger.info(f"Skipped (duplicate): {skip_count}")
    logger.info(f"No results: {no_result_count}")
    logger.info(f"Errors: {error_count}")


if __name__ == "__main__":
    ingest_aic_artworks_all()
