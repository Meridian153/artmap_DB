"""
artist_styles_final.csv → artist_movements 연결 테이블 저장 스크립트

전략:
  1. DB에서 {wikidata_id → artist.id} 캐시 구성
  2. DB에서 {name_en.lower() → movement.id} 캐시 구성
  3. CSV의 final_styles 컬럼을 " | " 로 분리해 매핑 생성
  4. ArtistMovement(artist_id, movement_id) 삽입 (복합 PK 충돌 시 skip)

Usage:
    python scripts/ingest_artist_movements.py
    python scripts/ingest_artist_movements.py --dry-run
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert

sys.path.append(str(Path(__file__).parent.parent))

from src.reception.domain.artist.artist import Artist
from src.reception.domain.artist.artist_movement import ArtistMovement
from src.reception.domain.art_movement.art_movement import ArtMovement
from src.shared_kernel.infra.database.connection import get_session, initialize_database
from src.shared_kernel.infra.log.logger import setup_logger

logger = setup_logger("IngestArtistMovements")

CSV_PATH = Path(__file__).parent / "data" / "artist_styles_final.csv"
STYLE_SEP = " | "


def build_artist_cache(session) -> dict[str, UUID]:
    """wikidata_id → artist.id"""
    rows = session.execute(
        select(Artist.wikidata_id, Artist.id).where(Artist.wikidata_id.isnot(None))
    ).all()
    return {wid: aid for wid, aid in rows}


def build_movement_cache(session) -> dict[str, UUID]:
    """name_en.lower() → movement.id"""
    rows = session.execute(select(ArtMovement.name_en, ArtMovement.id)).all()
    return {name.lower(): mid for name, mid in rows}


def load_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def ingest_artist_movements(dry_run: bool = False) -> None:
    rows = load_csv(CSV_PATH)
    logger.info(f"Loaded {len(rows)} rows from {CSV_PATH}")

    if dry_run:
        logger.info("=== DRY RUN — DB에 저장하지 않습니다 ===")

    initialize_database()

    success_count = 0
    skip_count = 0
    missing_artist: list[str] = []
    missing_movement: list[str] = []

    with get_session() as session:
        artist_cache = build_artist_cache(session)
        movement_cache = build_movement_cache(session)
        logger.info(
            f"Cache: {len(artist_cache)} artists, {len(movement_cache)} movements"
        )

        pairs_to_insert: list[dict] = []
        seen: set[tuple[UUID, UUID]] = set()

        for row in rows:
            wikidata_id = (row.get("wikidata_id") or "").strip()
            final_styles = (row.get("final_styles") or "").strip()

            if not wikidata_id or not final_styles or final_styles == "-":
                continue

            artist_id = artist_cache.get(wikidata_id)
            if artist_id is None:
                missing_artist.append(f"{wikidata_id} ({row.get('artist_name')})")
                continue

            for raw_style in final_styles.split(STYLE_SEP):
                style_key = raw_style.strip().lower()
                if not style_key:
                    continue

                movement_id = movement_cache.get(style_key)
                if movement_id is None:
                    missing_movement.append(raw_style.strip())
                    continue

                pair = (artist_id, movement_id)
                if pair in seen:
                    continue
                seen.add(pair)
                pairs_to_insert.append(
                    {"artist_id": artist_id, "movement_id": movement_id}
                )

        logger.info(f"Pairs to insert: {len(pairs_to_insert)}")

        if dry_run:
            for p in pairs_to_insert:
                logger.info(f"  {p['artist_id']} ↔ {p['movement_id']}")
        else:
            for pair in pairs_to_insert:
                existing = session.execute(
                    select(ArtistMovement).where(
                        ArtistMovement.artist_id == pair["artist_id"],
                        ArtistMovement.movement_id == pair["movement_id"],
                    )
                ).scalar_one_or_none()

                if existing:
                    skip_count += 1
                    continue

                session.add(
                    ArtistMovement(
                        artist_id=pair["artist_id"],
                        movement_id=pair["movement_id"],
                    )
                )
                success_count += 1

            session.flush()

    if missing_artist:
        logger.warning(
            f"\n[미매칭 Artist {len(set(missing_artist))}건] — "
            "artists 테이블에 없는 wikidata_id:"
        )
        for m in sorted(set(missing_artist)):
            logger.warning(f"  {m}")

    if missing_movement:
        unique_missing = sorted(set(missing_movement))
        logger.warning(
            f"\n[미매칭 Movement {len(unique_missing)}건] — "
            "art_movements 테이블에 없는 스타일명:"
        )
        for m in unique_missing:
            logger.warning(f"  {m}")

    logger.info("\n=== Ingestion Summary ===")
    logger.info(f"Inserted : {success_count}")
    logger.info(f"Skipped  : {skip_count}")
    logger.info(f"Total pairs prepared : {len(pairs_to_insert)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="artist ↔ art_movement 연결 테이블 저장")
    parser.add_argument("--dry-run", action="store_true", help="DB 저장 없이 결과만 출력")
    args = parser.parse_args()
    ingest_artist_movements(dry_run=args.dry_run)
