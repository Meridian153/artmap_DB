#!/usr/bin/env python3
"""
Met Museum 작품 수집 스크립트 (MVP 화가 50명 기준)
50명 화가의 이름으로 Met API 검색 → 작품 저장 + artwork_artists 연결
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
from src.reception.infra.external_apis import MetMuseumClient
from src.reception.infra.persistence.artist_repository_impl import ArtistRepositoryImpl
from src.reception.infra.persistence.artwork_repository_impl import ArtworkRepositoryImpl
from src.reception.infra.persistence.institution_repository_impl import InstitutionRepositoryImpl
from src.reception.infra.persistence.place_repository_impl import PlaceRepositoryImpl
from src.shared_kernel.domain.enums import ExternalApiSource, LocationType
from src.shared_kernel.infra.database.connection import get_session, initialize_database
from src.shared_kernel.infra.log.logger import setup_logger

logger = setup_logger("IngestMetArtworksAll")

MET_WIKIDATA_ID = "Q160236"
MAX_PER_ARTIST = 5
SEARCH_DELAY = 2.0  # 화가 검색 간 딜레이 (초)
RETRY_DELAYS = [5, 15, 30]  # 403 발생 시 재시도 대기 시간 (초)


def _extract_wikidata_id(wikidata_url: str) -> str:
    """Met API 응답의 wikidata URL에서 Q-ID 추출. e.g. https://www.wikidata.org/wiki/Q5582 → Q5582"""
    if not wikidata_url:
        return ""
    return wikidata_url.rstrip("/").split("/")[-1]


def _search_with_retry(met_client, artist_name: str, limit: int) -> list:
    """403/에러 시 backoff 재시도"""
    for attempt, delay in enumerate([0] + RETRY_DELAYS):
        if delay:
            logger.info(f"  ⏳ Waiting {delay}s before retry {attempt}...")
            time.sleep(delay)
        try:
            return met_client.search_artworks(query=artist_name, limit=limit, has_images=True)
        except Exception as e:
            if attempt == len(RETRY_DELAYS):
                raise
            logger.warning(f"  ⚠ Search failed ({e}), will retry...")
    return []


def _get_artwork_with_retry(met_client, object_id: int) -> dict:
    """403/에러 시 backoff 재시도"""
    for attempt, delay in enumerate([0] + RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        try:
            return met_client.get_artwork(object_id) or {}
        except Exception as e:
            if attempt == len(RETRY_DELAYS):
                return {}
            logger.warning(f"  ⚠ get_artwork({object_id}) failed ({e}), will retry...")
    return {}


def ingest_met_artworks_all():
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

    met_client = MetMuseumClient()
    success_count = 0
    skip_count = 0
    error_count = 0
    no_result_count = 0

    for artist in artist_list:
        artist_name = artist["name_en"]
        artist_wikidata_id = artist["wikidata_id"]
        artist_db_id = artist["id"]

        logger.info(f"[{artist_name}] Searching Met Museum...")
        try:
            object_ids = _search_with_retry(met_client, artist_name, limit=MAX_PER_ARTIST * 3)
            if not object_ids:
                logger.info(f"  → No results for {artist_name}")
                no_result_count += 1
                continue

            saved = 0
            for object_id in object_ids:
                if saved >= MAX_PER_ARTIST:
                    break
                try:
                    with get_session() as session:
                        artwork_repo = ArtworkRepositoryImpl(session)
                        institution_repo = InstitutionRepositoryImpl(session)
                        place_repo = PlaceRepositoryImpl(session)

                        # 중복 확인
                        existing = artwork_repo.find_by_source(
                            ExternalApiSource.MET_MUSEUM.value, str(object_id)
                        )
                        if existing:
                            skip_count += 1
                            saved += 1
                            continue

                        # Met API에서 작품 상세 정보 가져오기
                        raw = _get_artwork_with_retry(met_client, object_id)
                        if not raw:
                            continue

                        # 화가 일치 검증 (wikidata URL로 확인)
                        artwork_artist_wikidata = _extract_wikidata_id(
                            raw.get("artist_wikidata_url", "")
                        )
                        if (
                            artwork_artist_wikidata
                            and artwork_artist_wikidata != artist_wikidata_id
                        ):
                            # 다른 화가의 작품이면 건너뜀
                            continue

                        # Artwork 엔티티 생성
                        artwork = Artwork.create_from_external_source(
                            source_api=ExternalApiSource.MET_MUSEUM.value,
                            source_id=str(object_id),
                            title_en=raw.get("title", "Untitled"),
                            title_ko=raw.get("title", "Untitled"),
                            year_created=raw.get("object_begin_date") or 0,
                            year_end=raw.get("object_end_date"),
                            medium_en=raw.get("medium", ""),
                            medium_ko=raw.get("medium", ""),
                            dimensions=raw.get("dimensions", ""),
                            image_url=raw.get("primary_image", "")
                            or raw.get("primary_image_small", ""),
                            image_source="Met Museum",
                            is_public_domain=raw.get("is_public_domain", False),
                        )
                        artwork = artwork_repo.save(artwork)

                        # Artwork ↔ Artist 연결
                        session.merge(ArtworkArtist(artwork_id=artwork.id, artist_id=artist_db_id))

                        # Met Museum 찾기 → 소유권 + 위치 저장
                        met_museum = institution_repo.find_by_wikidata_id(MET_WIKIDATA_ID)
                        if met_museum:
                            session.merge(
                                ArtworkOwnership(
                                    artwork_id=artwork.id,
                                    institution_id=met_museum.id,
                                    is_primary_owner=True,
                                )
                            )
                            places = place_repo.find_by_institution_id(met_museum.id)
                            if places:
                                session.add(
                                    ArtworkLocation.create(
                                        artwork_id=artwork.id,
                                        place_id=places[0].id,
                                        location_type=LocationType.PERMANENT_COLLECTION,
                                        start_date=date.today(),
                                        source="Met Museum API",
                                    )
                                )

                        logger.info(f"  ✓ [{artist_name}] {artwork.title_en} ({object_id})")
                        success_count += 1
                        saved += 1

                except Exception as e:
                    logger.error(f"  ✗ Error on object_id {object_id}: {e}")
                    error_count += 1

        except Exception as e:
            logger.error(f"  ✗ Search error for {artist_name}: {e}")
            error_count += 1

        time.sleep(SEARCH_DELAY)

    logger.info("\n=== Met Museum Ingestion Summary ===")
    logger.info(f"Success: {success_count}")
    logger.info(f"Skipped (duplicate): {skip_count}")
    logger.info(f"No results: {no_result_count}")
    logger.info(f"Errors: {error_count}")


if __name__ == "__main__":
    ingest_met_artworks_all()
