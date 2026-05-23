"""
art_movements.yml → DB 저장 스크립트

Usage:
    python scripts/ingest_art_movements.py
    python scripts/ingest_art_movements.py --dry-run   # DB 저장 없이 파싱만 확인
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

sys.path.append(str(Path(__file__).parent.parent))

from src.reception.domain.art_movement.art_movement import ArtMovement
from src.reception.infra.persistence.art_movement_repository_impl import ArtMovementRepositoryImpl
from src.shared_kernel.infra.database.connection import get_session, initialize_database
from src.shared_kernel.infra.log.logger import setup_logger

logger = setup_logger("IngestArtMovements")

DATA_PATH = Path(__file__).parent / "data" / "art_movements.yml"


def load_yml(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("art_movements", [])


def ingest_art_movements(dry_run: bool = False) -> None:
    records = load_yml(DATA_PATH)
    logger.info(f"Loaded {len(records)} records from {DATA_PATH}")

    if dry_run:
        logger.info("=== DRY RUN — DB에 저장하지 않습니다 ===")
        for r in records:
            logger.info(f"  [{r['name_en']}] ko={r.get('name_ko')} "
                        f"{r.get('period_start')}~{r.get('period_end')}")
        return

    initialize_database()

    success_count = 0
    skip_count = 0
    error_count = 0

    for record in records:
        name_en: str = record.get("name_en", "").strip()
        if not name_en:
            logger.warning("name_en이 없는 항목을 건너뜁니다.")
            continue

        try:
            with get_session() as session:
                repo = ArtMovementRepositoryImpl(session)

                existing = repo.find_by_name_en(name_en)
                if existing:
                    logger.info(f"⊙ Already exists: {name_en}")
                    skip_count += 1
                    continue

                description = record.get("description")
                if isinstance(description, str):
                    description = description.strip() or None

                movement = ArtMovement.create(
                    name_en=name_en,
                    name_ko=(record.get("name_ko") or "").strip(),
                    period_start=record.get("period_start"),
                    period_end=record.get("period_end"),
                    description=description,
                )
                repo.save(movement)
                logger.info(f"✓ Ingested: {name_en}")
                success_count += 1

        except Exception as e:
            logger.error(f"✗ Error ingesting '{name_en}': {e}")
            error_count += 1

    logger.info("\n=== Ingestion Summary ===")
    logger.info(f"Success : {success_count}")
    logger.info(f"Skipped : {skip_count}")
    logger.info(f"Errors  : {error_count}")
    logger.info(f"Total   : {len(records)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="art_movements.yml → DB 저장")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="DB에 저장하지 않고 파싱 결과만 출력",
    )
    args = parser.parse_args()
    ingest_art_movements(dry_run=args.dry_run)
