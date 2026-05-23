#!/usr/bin/env python3
"""
YAML 리스트 기반 Wikidata SPARQL 작품 수집 스크립트

사용법:
  python3 scripts/ingest_wikidata_by_list.py                          # 실행 (DB 저장 + CSV 저장)
  python3 scripts/ingest_wikidata_by_list.py --dry-run                # 미리보기 (CSV만 저장, DB 저장 안 함)
  python3 scripts/ingest_wikidata_by_list.py --output results.csv     # CSV 경로 지정
  python3 scripts/ingest_wikidata_by_list.py --targets custom.yml     # 입력 파일 지정
"""

import argparse
import csv
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote

import yaml

sys.path.append(str(Path(__file__).parent.parent))

from src.reception.domain.artwork.artwork import Artwork
from src.reception.domain.artwork.artwork_artist import ArtworkArtist
from src.reception.domain.artwork.artwork_location import ArtworkLocation
from src.reception.domain.artwork.artwork_ownership import ArtworkOwnership
from src.reception.infra.external_apis.wikidata_client import WikidataClient
from src.reception.infra.persistence.artist_repository_impl import ArtistRepositoryImpl
from src.reception.infra.persistence.artwork_repository_impl import ArtworkRepositoryImpl
from src.reception.infra.persistence.institution_repository_impl import InstitutionRepositoryImpl
from src.reception.infra.persistence.place_repository_impl import PlaceRepositoryImpl
from src.shared_kernel.domain.enums import ExternalApiSource, LocationType
from src.shared_kernel.infra.database.connection import get_session, initialize_database
from src.shared_kernel.infra.log.logger import setup_logger

logger = setup_logger("IngestWikidataByList")

DEFAULT_TARGETS = Path(__file__).parent / "data" / "wikidata_search_targets.yml"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "db data" / "wikidata_search_results.csv"

CSV_HEADERS = [
    "wikidata_id",
    "title_en",
    "title_ko",
    "creator",
    "creator_id",
    "inception",
    "image",
    "collection",
    "material",
    "search_type",
    "search_key",
]


def load_targets(path: Path) -> dict:
    """YAML 타겟 파일 로드"""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    collections = data.get("collections", [])
    creators = data.get("creators", [])
    default_limit = data.get("default_limit", 50)

    logger.info(f"Loaded targets: {len(collections)} collections, {len(creators)} creators")
    return {
        "collections": collections,
        "creators": creators,
        "default_limit": default_limit,
    }


def _extract_year(wikidata_time: str) -> int:
    """Wikidata 날짜 문자열에서 연도 추출. e.g. '+1889-01-01T00:00:00Z' → 1889"""
    if not wikidata_time:
        return 0
    match = re.search(r"[+-]?(\d{4})-", wikidata_time)
    if match:
        return int(match.group(1))
    return 0


def _wikidata_image_url(raw_url: str) -> str:
    """이미지 URL 정규화 (Wikimedia Commons 파일명 → 전체 URL)"""
    if not raw_url:
        return ""
    if raw_url.startswith("http"):
        return raw_url
    encoded = quote(raw_url.replace(" ", "_"), safe="")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded}"


def search_all(client: WikidataClient, targets: dict) -> list[dict]:
    """모든 타겟에 대해 SPARQL 검색 실행, 결과 리스트 반환"""
    all_results = []
    seen_ids = set()
    default_limit = targets["default_limit"]

    # 1) 소장처별 검색
    for col in targets["collections"]:
        wid = col["wikidata_id"]
        name = col.get("name", wid)
        logger.info(f"\n=== Collection: {name} ({wid}) ===")

        try:
            results = client.search_artworks_by_collection(wid, limit=default_limit)
        except Exception as e:
            logger.error(f"Failed to search collection {name}: {e}")
            time.sleep(3)
            continue

        for r in results:
            rid = r.get("wikidata_id", "")
            if rid and rid not in seen_ids:
                r["search_type"] = "collection"
                r["search_key"] = name
                all_results.append(r)
                seen_ids.add(rid)

        logger.info(f"  → {len(results)} found, {len(seen_ids)} unique total")
        time.sleep(1)

    # 2) 제작자별 검색
    for crt in targets["creators"]:
        wid = crt["wikidata_id"]
        name = crt.get("name", wid)
        logger.info(f"\n=== Creator: {name} ({wid}) ===")

        try:
            results = client.search_artworks_by_creator(wid, limit=default_limit)
        except Exception as e:
            logger.error(f"Failed to search creator {name}: {e}")
            time.sleep(3)
            continue

        for r in results:
            rid = r.get("wikidata_id", "")
            if rid and rid not in seen_ids:
                r["search_type"] = "creator"
                r["search_key"] = name
                all_results.append(r)
                seen_ids.add(rid)

        logger.info(f"  → {len(results)} found, {len(seen_ids)} unique total")
        time.sleep(1)

    return all_results


def save_csv(results: list[dict], output_path: Path):
    """검색 결과를 CSV 파일로 저장"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"CSV saved: {output_path} ({len(results)} rows)")


def save_to_db(results: list[dict]):
    """검색 결과를 DB에 저장 (기존 ingest_wikidata_artworks.py 패턴 활용)"""
    initialize_database()

    # DB에서 작가 매핑 로드
    with get_session() as session:
        artist_repo = ArtistRepositoryImpl(session)
        artists = artist_repo.find_all(limit=200)
        artist_map = {
            a.wikidata_id: {"id": a.id, "name_en": a.name_en}
            for a in artists
            if a.wikidata_id
        }

    # DB에서 미술관 매핑 로드
    with get_session() as session:
        institution_repo = InstitutionRepositoryImpl(session)
        all_museums = institution_repo.find_all(limit=200)
        museum_map = {
            m.wikidata_id: {"id": m.id, "name_en": m.name_en}
            for m in all_museums
            if m.wikidata_id
        }

    total_success = 0
    total_skip = 0
    total_error = 0

    for row in results:
        wikidata_id = row.get("wikidata_id", "")
        if not wikidata_id or not wikidata_id.startswith("Q"):
            continue

        title_en = row.get("title_en", "Untitled")
        title_ko = row.get("title_ko", "") or title_en
        year_created = _extract_year(row.get("inception", ""))
        image_url = _wikidata_image_url(row.get("image", ""))
        medium = row.get("material", "")
        creator_id = row.get("creator_id", "")
        collection_name = row.get("collection", "")

        try:
            with get_session() as session:
                artwork_repo = ArtworkRepositoryImpl(session)
                place_repo = PlaceRepositoryImpl(session)

                # 중복 확인
                existing = artwork_repo.find_by_source(
                    ExternalApiSource.WIKIDATA.value, wikidata_id
                )
                if existing:
                    total_skip += 1
                    artwork = existing
                else:
                    artwork = Artwork.create_from_external_source(
                        source_api=ExternalApiSource.WIKIDATA.value,
                        source_id=wikidata_id,
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
                    total_success += 1

                # Artwork ↔ Artist 연결
                if creator_id and creator_id in artist_map:
                    artist_db_id = artist_map[creator_id]["id"]
                    session.merge(
                        ArtworkArtist(artwork_id=artwork.id, artist_id=artist_db_id)
                    )

                # Artwork ↔ Institution 소유권 연결
                # collection_name으로 매칭 시도 (SPARQL 결과의 collectionLabel)
                for museum_wid, museum_info in museum_map.items():
                    if museum_info["name_en"] and collection_name and (
                        museum_info["name_en"].lower() in collection_name.lower()
                        or collection_name.lower() in museum_info["name_en"].lower()
                    ):
                        session.merge(
                            ArtworkOwnership(
                                artwork_id=artwork.id,
                                institution_id=museum_info["id"],
                                is_primary_owner=True,
                            )
                        )

                        # 위치 저장
                        places = place_repo.find_by_institution_id(museum_info["id"])
                        if places:
                            from sqlalchemy import text

                            existing_loc = session.execute(
                                text(
                                    "SELECT id FROM artwork_locations "
                                    "WHERE artwork_id = :aid AND place_id = :pid"
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
                                        source="Wikidata SPARQL (list-based)",
                                    )
                                )
                        break

                logger.info(f"  ✓ {title_en} ({wikidata_id})")

        except Exception as e:
            logger.error(f"  ✗ Error saving {wikidata_id}: {e}")
            total_error += 1

    logger.info("\n=== DB Ingestion Summary ===")
    logger.info(f"New artworks saved: {total_success}")
    logger.info(f"Skipped (already exists): {total_skip}")
    logger.info(f"Errors: {total_error}")


def main():
    parser = argparse.ArgumentParser(description="YAML 리스트 기반 Wikidata 작품 검색/수집")
    parser.add_argument(
        "--targets",
        type=Path,
        default=DEFAULT_TARGETS,
        help="검색 대상 YAML 파일 경로 (기본: scripts/data/wikidata_search_targets.yml)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="결과 CSV 파일 경로 (기본: db data/wikidata_search_results.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="CSV 저장만 하고 DB에는 저장하지 않음",
    )
    args = parser.parse_args()

    # 1) YAML 로드
    if not args.targets.exists():
        logger.error(f"Targets file not found: {args.targets}")
        sys.exit(1)
    targets = load_targets(args.targets)

    # 2) SPARQL 검색
    client = WikidataClient()
    try:
        results = search_all(client, targets)
    finally:
        client.close()

    if not results:
        logger.warning("No artworks found. Exiting.")
        return

    logger.info(f"\n=== Total unique artworks found: {len(results)} ===")

    # 3) CSV 저장 (항상)
    save_csv(results, args.output)

    # 4) DB 저장 (dry-run이 아닌 경우)
    if args.dry_run:
        logger.info("Dry-run mode: skipping DB ingestion.")
    else:
        save_to_db(results)

    logger.info("Done!")


if __name__ == "__main__":
    main()
