#!/usr/bin/env python3
"""
미술관별 CSV 파일을 읽어 Artwork 엔티티로 변환 → DB 저장

사용법:
  venv/bin/python scripts/import_museum_csv_to_db.py                         # 전체 CSV 파일 DB 저장
  venv/bin/python scripts/import_museum_csv_to_db.py --dry-run               # 미리보기 (DB 저장 안 함)
  venv/bin/python scripts/import_museum_csv_to_db.py --csv-dir custom_dir    # CSV 폴더 지정
  venv/bin/python scripts/import_museum_csv_to_db.py --file 03_Louvre.csv    # 특정 파일만 처리

CSV 헤더 (fetch_wikidata_by_museum.py 출력 형식):
  wikidata_id, title_en, title_ko, creator, creator_id, inception, image, collection, material
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text

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

logger = setup_logger("ImportMuseumCSV")

DEFAULT_CSV_DIR = Path(__file__).parent.parent / "db data" / "wikidata_by_museum"


# ── 유틸리티 ──────────────────────────────────────────────

def extract_year(wikidata_time: str) -> int:
    """Wikidata 날짜 문자열에서 연도 추출. e.g. '+1889-01-01T00:00:00Z' → 1889"""
    if not wikidata_time:
        return 0
    match = re.search(r"[+-]?(\d{4})-", wikidata_time)
    return int(match.group(1)) if match else 0


def normalize_image_url(raw_url: str) -> str:
    """이미지 URL 정규화"""
    if not raw_url:
        return ""
    if raw_url.startswith("http"):
        return raw_url
    encoded = quote(raw_url.replace(" ", "_"), safe="")
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{encoded}"


# ── DB 매핑 로드 ──────────────────────────────────────────

def load_artist_map() -> dict:
    """DB에 등록된 작가 목록을 {wikidata_id: {id, name_en}} 형태로 로드"""
    with get_session() as session:
        repo = ArtistRepositoryImpl(session)
        artists = repo.find_all(limit=500)
        return {
            a.wikidata_id: {"id": a.id, "name_en": a.name_en}
            for a in artists if a.wikidata_id
        }


def load_museum_map() -> dict:
    """DB에 등록된 미술관 목록을 {wikidata_id: {id, name_en}} 형태로 로드"""
    with get_session() as session:
        repo = InstitutionRepositoryImpl(session)
        museums = repo.find_all(limit=200)
        return {
            m.wikidata_id: {"id": m.id, "name_en": m.name_en}
            for m in museums if m.wikidata_id
        }


# ── CSV 읽기 ─────────────────────────────────────────────

def read_csv_file(filepath: Path) -> list[dict]:
    """CSV 파일을 읽어 dict 리스트로 반환"""
    rows = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def find_csv_files(csv_dir: Path, specific_file: str | None = None) -> list[Path]:
    """CSV 폴더에서 처리할 파일 목록 반환 (_summary.csv 제외)"""
    if specific_file:
        target = csv_dir / specific_file
        if not target.exists():
            logger.error(f"File not found: {target}")
            return []
        return [target]

    files = sorted(csv_dir.glob("*.csv"))
    return [f for f in files if not f.name.startswith("_")]


# ── DB 저장 ──────────────────────────────────────────────

def import_csv_to_db(
    filepath: Path,
    artist_map: dict,
    museum_map: dict,
    dry_run: bool,
) -> dict:
    """단일 CSV 파일의 작품들을 DB에 저장. 결과 통계 반환."""
    rows = read_csv_file(filepath)
    stats = {"file": filepath.name, "total": len(rows), "created": 0, "skipped": 0, "error": 0}

    if not rows:
        return stats

    if dry_run:
        logger.info(f"  [DRY-RUN] {len(rows)}건 미리보기:")
        for r in rows[:5]:
            logger.info(f"    - {r.get('title_en', '?')} ({r.get('wikidata_id', '?')})")
        if len(rows) > 5:
            logger.info(f"    ... 외 {len(rows) - 5}건")
        stats["created"] = len(rows)
        return stats

    for row in rows:
        wikidata_id = row.get("wikidata_id", "").strip()
        if not wikidata_id or not wikidata_id.startswith("Q"):
            stats["error"] += 1
            continue

        title_en = row.get("title_en", "").strip() or "Untitled"
        title_ko = row.get("title_ko", "").strip() or title_en
        year_created = extract_year(row.get("inception", ""))
        image_url = normalize_image_url(row.get("image", ""))
        medium = row.get("material", "").strip()
        creator_id = row.get("creator_id", "").strip()
        collection_label = row.get("collection", "").strip()

        try:
            with get_session() as session:
                artwork_repo = ArtworkRepositoryImpl(session)
                place_repo = PlaceRepositoryImpl(session)

                # 중복 확인
                existing = artwork_repo.find_by_source(
                    ExternalApiSource.WIKIDATA.value, wikidata_id
                )
                if existing:
                    stats["skipped"] += 1
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
                    stats["created"] += 1

                # Artwork ↔ Artist 연결
                if creator_id and creator_id in artist_map:
                    artist_db_id = artist_map[creator_id]["id"]
                    session.merge(
                        ArtworkArtist(artwork_id=artwork.id, artist_id=artist_db_id)
                    )

                # Artwork ↔ Institution 소유권 연결
                for museum_wid, museum_info in museum_map.items():
                    if museum_info["name_en"] and collection_label and (
                        museum_info["name_en"].lower() in collection_label.lower()
                        or collection_label.lower() in museum_info["name_en"].lower()
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
                                        source="Wikidata CSV import",
                                    )
                                )
                        break

        except Exception as e:
            logger.error(f"    ✗ {wikidata_id}: {e}")
            stats["error"] += 1

    return stats


# ── 메인 ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="미술관별 CSV → DB 저장")
    parser.add_argument(
        "--csv-dir",
        type=Path,
        default=DEFAULT_CSV_DIR,
        help="CSV 파일들이 있는 폴더 (기본: db data/wikidata_by_museum/)",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="특정 CSV 파일만 처리 (예: 03_Musée_du_Louvre.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 저장하지 않고 미리보기만",
    )
    args = parser.parse_args()

    # 1) CSV 파일 목록
    csv_files = find_csv_files(args.csv_dir, args.file)
    if not csv_files:
        logger.error("처리할 CSV 파일이 없습니다.")
        sys.exit(1)

    logger.info(f"처리할 CSV 파일: {len(csv_files)}개")
    if args.dry_run:
        logger.info("[DRY-RUN 모드] DB에 저장하지 않습니다.")

    # 2) DB 초기화 + 매핑 로드
    if not args.dry_run:
        initialize_database()

    artist_map = {} if args.dry_run else load_artist_map()
    museum_map = {} if args.dry_run else load_museum_map()

    if not args.dry_run:
        logger.info(f"DB 매핑 로드: Artist {len(artist_map)}명, Museum {len(museum_map)}곳")

    # 3) 파일별 처리
    all_stats = []
    for filepath in csv_files:
        logger.info(f"\n── {filepath.name} ──")
        stats = import_csv_to_db(filepath, artist_map, museum_map, args.dry_run)
        all_stats.append(stats)

    # 4) 전체 요약
    total_rows = sum(s["total"] for s in all_stats)
    total_created = sum(s["created"] for s in all_stats)
    total_skipped = sum(s["skipped"] for s in all_stats)
    total_error = sum(s["error"] for s in all_stats)

    logger.info(f"\n{'='*60}")
    logger.info(f"  {'DRY-RUN ' if args.dry_run else ''}Import 완료!")
    logger.info(f"  파일: {len(csv_files)}개")
    logger.info(f"  전체 행: {total_rows}")
    logger.info(f"  신규 저장: {total_created}")
    logger.info(f"  중복 건너뜀: {total_skipped}")
    logger.info(f"  오류: {total_error}")
    logger.info(f"{'='*60}")

    # 파일별 상세
    logger.info(f"\n{'File':<50} {'Total':>6} {'New':>6} {'Skip':>6} {'Err':>5}")
    logger.info(f"{'-'*50} {'-'*6} {'-'*6} {'-'*6} {'-'*5}")
    for s in all_stats:
        logger.info(
            f"{s['file']:<50} {s['total']:>6} {s['created']:>6} "
            f"{s['skipped']:>6} {s['error']:>5}"
        )


if __name__ == "__main__":
    main()
