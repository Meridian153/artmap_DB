#!/usr/bin/env python3
"""
Wikidata SPARQL 작품 수집 스크립트 (Met, AIC 제외 나머지 28개 미술관)
50명 화가 × 28개 미술관 조합으로 SPARQL 쿼리하여 작품 저장
"""

import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.append(str(Path(__file__).parent.parent))

from datetime import date

from src.reception.domain.artwork.artwork import Artwork
from src.reception.domain.artwork.artwork_artist import ArtworkArtist
from src.reception.domain.artwork.artwork_location import ArtworkLocation
from src.reception.domain.artwork.artwork_ownership import ArtworkOwnership
from src.reception.infra.persistence.artist_repository_impl import ArtistRepositoryImpl
from src.reception.infra.persistence.artwork_repository_impl import ArtworkRepositoryImpl
from src.reception.infra.persistence.institution_repository_impl import InstitutionRepositoryImpl
from src.reception.infra.persistence.place_repository_impl import PlaceRepositoryImpl
from src.shared_kernel.domain.enums import ExternalApiSource, LocationType
from src.shared_kernel.infra.database.connection import get_session, initialize_database
from src.shared_kernel.infra.log.logger import setup_logger

logger = setup_logger("IngestWikidataArtworks")

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
SPARQL_HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "ArtMap/1.0 (Educational Project; https://github.com/artmap)",
}

# Met(Q160236), AIC(Q239303)는 전용 API 스크립트로 처리하므로 제외
EXCLUDED_WIKIDATA_IDS = {"Q160236", "Q239303"}
MAX_PER_MUSEUM = 5


def _sparql_query(query: str) -> list:
    """Wikidata SPARQL 쿼리 실행"""
    try:
        time.sleep(1.5)  # Wikidata rate limit 준수
        response = requests.get(
            SPARQL_ENDPOINT,
            params={"query": query, "format": "json"},
            headers=SPARQL_HEADERS,
            timeout=60,
        )
        response.raise_for_status()
        return response.json().get("results", {}).get("bindings", [])
    except Exception as e:
        logger.error(f"SPARQL query failed: {e}")
        return []


def _extract_year(wikidata_time: str) -> int:
    """Wikidata 날짜 문자열에서 연도 추출. e.g. '+1889-01-01T00:00:00Z' → 1889"""
    if not wikidata_time:
        return 0
    match = re.search(r"[+-]?(\d{4})-", wikidata_time)
    if match:
        return int(match.group(1))
    return 0


def _wikidata_image_url(filename: str) -> str:
    """Wikidata 이미지 파일명을 Wikimedia Commons URL로 변환"""
    if not filename:
        return ""
    encoded = quote(filename.replace(" ", "_"), safe="")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded}"


def _build_artist_values(artist_wikidata_ids: list) -> str:
    """SPARQL VALUES 절 생성"""
    return " ".join(f"wd:{qid}" for qid in artist_wikidata_ids)


def ingest_wikidata_artworks():
    initialize_database()

    # DB에서 화가 50명 로드
    with get_session() as session:
        artist_repo = ArtistRepositoryImpl(session)
        artists = artist_repo.find_all(limit=100)
        artist_map = {
            a.wikidata_id: {"id": a.id, "name_en": a.name_en} for a in artists if a.wikidata_id
        }
    artist_wikidata_ids = list(artist_map.keys())
    logger.info(f"Loaded {len(artist_wikidata_ids)} artists from DB")

    # DB에서 미술관 로드 (Met, AIC 제외)
    with get_session() as session:
        institution_repo = InstitutionRepositoryImpl(session)
        all_museums = institution_repo.find_all(limit=100)
        museums = [
            {"id": m.id, "name_en": m.name_en, "wikidata_id": m.wikidata_id}
            for m in all_museums
            if m.wikidata_id and m.wikidata_id not in EXCLUDED_WIKIDATA_IDS
        ]
    logger.info(f"Loaded {len(museums)} museums for Wikidata ingestion (Met/AIC excluded)")

    artist_values_str = _build_artist_values(artist_wikidata_ids)

    total_success = 0
    total_skip = 0
    total_error = 0

    for museum in museums:
        museum_wikidata_id = museum["wikidata_id"]
        museum_name = museum["name_en"]
        museum_db_id = museum["id"]

        logger.info(f"\n[{museum_name}] Querying Wikidata SPARQL...")

        # SPARQL 쿼리: 이 미술관에 소장된 50명 화가의 작품
        query = f"""
SELECT DISTINCT ?artwork ?artworkLabel ?artworkLabelKo ?artist ?inception ?imageUrl ?mediumLabel WHERE {{
  VALUES ?artist {{ {artist_values_str} }}
  VALUES ?museum {{ wd:{museum_wikidata_id} }}
  {{
    {{ ?artwork wdt:P276 ?museum . }}
    UNION
    {{ ?artwork wdt:P195 ?museum . }}
  }}
  ?artwork wdt:P170 ?artist .
  OPTIONAL {{ ?artwork wdt:P571 ?inception . }}
  OPTIONAL {{ ?artwork wdt:P18 ?imageUrl . }}
  OPTIONAL {{
    ?artwork wdt:P186 ?medium .
    ?medium rdfs:label ?mediumLabel .
    FILTER(LANG(?mediumLabel) = "en")
  }}
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "ko,en" .
    ?artwork rdfs:label ?artworkLabelKo .
  }}
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en" .
    ?artwork rdfs:label ?artworkLabel .
  }}
}}
LIMIT {MAX_PER_MUSEUM}
"""
        results = _sparql_query(query)

        if not results:
            logger.info(f"  → No artworks found in Wikidata for {museum_name}")
            continue

        logger.info(f"  Found {len(results)} artworks")

        for row in results:
            try:
                # Wikidata 작품 ID 추출 (e.g. http://www.wikidata.org/entity/Q12345)
                artwork_wikidata_id = row.get("artwork", {}).get("value", "").split("/")[-1]
                if not artwork_wikidata_id or not artwork_wikidata_id.startswith("Q"):
                    continue

                # 화가 Wikidata ID 추출
                artist_wikidata_id = row.get("artist", {}).get("value", "").split("/")[-1]

                # 제목
                title_en = row.get("artworkLabel", {}).get("value", "Untitled")
                title_ko = row.get("artworkLabelKo", {}).get("value", title_en)

                # 연도
                year_created = _extract_year(row.get("inception", {}).get("value", ""))

                # 이미지 URL (Wikidata는 파일명만 줌 → Wikimedia URL로 변환)
                raw_image = row.get("imageUrl", {}).get("value", "")
                # Wikidata P18은 URL이나 파일명으로 올 수 있음
                if raw_image.startswith("http"):
                    image_url = raw_image
                else:
                    image_url = _wikidata_image_url(raw_image)

                # 재료
                medium = row.get("mediumLabel", {}).get("value", "")

                with get_session() as session:
                    artwork_repo = ArtworkRepositoryImpl(session)
                    place_repo = PlaceRepositoryImpl(session)

                    # 중복 확인
                    existing = artwork_repo.find_by_source(
                        ExternalApiSource.WIKIDATA.value, artwork_wikidata_id
                    )
                    if existing:
                        # 이미 있는 작품이라도 이 미술관과의 연결은 추가
                        artwork = existing
                        total_skip += 1
                    else:
                        # 새 작품 저장
                        artwork = Artwork.create_from_external_source(
                            source_api=ExternalApiSource.WIKIDATA.value,
                            source_id=artwork_wikidata_id,
                            title_en=title_en,
                            title_ko=title_ko,
                            year_created=year_created,
                            medium_en=medium,
                            medium_ko=medium,
                            image_url=image_url,
                            image_source="Wikidata",
                            is_public_domain=True,
                        )
                        artwork = artwork_repo.save(artwork)

                        # Artwork ↔ Artist 연결
                        if artist_wikidata_id in artist_map:
                            artist_db_id = artist_map[artist_wikidata_id]["id"]
                            session.merge(
                                ArtworkArtist(artwork_id=artwork.id, artist_id=artist_db_id)
                            )

                    # 소유권 저장 (이 미술관과 연결)
                    session.merge(
                        ArtworkOwnership(
                            artwork_id=artwork.id,
                            institution_id=museum_db_id,
                            is_primary_owner=True,
                        )
                    )

                    # 위치 저장
                    places = place_repo.find_by_institution_id(museum_db_id)
                    if places:
                        # 중복 위치 방지
                        from sqlalchemy import text

                        existing_loc = session.execute(
                            text(
                                "SELECT id FROM artwork_locations WHERE artwork_id = :aid AND place_id = :pid"
                            ),
                            {"aid": artwork.id, "pid": places[0].id},
                        ).fetchone()
                        if not existing_loc:
                            session.add(
                                ArtworkLocation.create(
                                    artwork_id=artwork.id,
                                    place_id=places[0].id,
                                    location_type=LocationType.PERMANENT_COLLECTION,
                                    start_date=date.today(),
                                    source="Wikidata SPARQL",
                                )
                            )

                    artist_name = artist_map.get(artist_wikidata_id, {}).get(
                        "name_en", artist_wikidata_id
                    )
                    logger.info(f"  ✓ [{artist_name}] {title_en} → {museum_name}")
                    total_success += 1

            except Exception as e:
                logger.error(f"  ✗ Error saving artwork {row}: {e}")
                total_error += 1

    logger.info("\n=== Wikidata Ingestion Summary ===")
    logger.info(f"Success: {total_success}")
    logger.info(f"Skipped (duplicate artwork, added museum link): {total_skip}")
    logger.info(f"Errors: {total_error}")


if __name__ == "__main__":
    ingest_wikidata_artworks()
