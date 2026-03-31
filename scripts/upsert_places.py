#!/usr/bin/env python3
"""
db data/places.csv의 데이터를 places 테이블에 upsert합니다.
id 값을 기준으로 이미 존재하면 UPDATE, 없으면 INSERT합니다.

Usage:
    # 실제 DB에 반영
    venv/bin/python scripts/upsert_places.py

    # 미리보기 (DB 수정 없음)
    venv/bin/python scripts/upsert_places.py --dry-run
"""

import argparse
import csv
import os
import sys
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.reception.domain.institution.place import Place
from src.shared_kernel.infra.database.connection import get_session


def parse_decimal(value: str) -> Decimal | None:
    if not value or value.strip() in ("", "null", "NULL"):
        return None
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        return None


def parse_uuid(value: str) -> uuid.UUID | None:
    if not value or value.strip() in ("", "null", "NULL"):
        return None
    try:
        return uuid.UUID(value.strip())
    except ValueError:
        return None


def parse_nullable_str(value: str) -> str | None:
    if not value or value.strip() in ("", "null", "NULL"):
        return None
    return value.strip()


def parse_datetime(value: str) -> datetime | None:
    if not value or value.strip() in ("", "null", "NULL"):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def load_csv(csv_path: str) -> list[dict]:
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            place_id = parse_uuid(row.get("id", ""))
            if place_id is None:
                print(f"  [SKIP] id 파싱 실패: {row.get('id')}")
                continue

            rows.append(
                {
                    "id": place_id,
                    "institution_id": parse_uuid(row.get("institution_id", "")),
                    "name_en": row.get("name_en", "").strip(),
                    "name_ko": row.get("name_ko", "").strip(),
                    "country": row.get("country", "").strip(),
                    "city": row.get("city", "").strip(),
                    "address": parse_nullable_str(row.get("address", "")),
                    "latitude": parse_decimal(row.get("latitude", "")),
                    "longitude": parse_decimal(row.get("longitude", "")),
                    "opening_hours": None,  # CSV의 "null" 문자열 → DB NULL
                    "admission": None,
                    "created_at": parse_datetime(row.get("created_at", "")) or datetime.now(),
                    "updated_at": datetime.now(),
                    "deleted_at": parse_datetime(row.get("deleted_at", "")),
                }
            )
    return rows


def upsert_places(rows: list[dict], dry_run: bool):
    print(f"총 {len(rows)}개 행을 처리합니다.")

    if dry_run:
        print("[DRY-RUN] DB에 반영하지 않습니다.\n")
        for r in rows:
            print(f"  - {r['name_en']} (id={r['id']})")
            print(f"      address   : {r['address']}")
            print(f"      lat/lng   : {r['latitude']}, {r['longitude']}")
        print(f"\n[DRY-RUN] {len(rows)}개 행을 upsert할 예정입니다.")
        return

    with get_session() as session:
        stmt = (
            pg_insert(Place)
            .values(rows)
            .on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "institution_id": pg_insert(Place).excluded.institution_id,
                    "name_en": pg_insert(Place).excluded.name_en,
                    "name_ko": pg_insert(Place).excluded.name_ko,
                    "country": pg_insert(Place).excluded.country,
                    "city": pg_insert(Place).excluded.city,
                    "address": pg_insert(Place).excluded.address,
                    "latitude": pg_insert(Place).excluded.latitude,
                    "longitude": pg_insert(Place).excluded.longitude,
                    "opening_hours": pg_insert(Place).excluded.opening_hours,
                    "admission": pg_insert(Place).excluded.admission,
                    "updated_at": pg_insert(Place).excluded.updated_at,
                    "deleted_at": pg_insert(Place).excluded.deleted_at,
                },
            )
        )
        session.execute(stmt)

    print(f"✅  {len(rows)}개 행이 places 테이블에 upsert되었습니다.")


def main():
    parser = argparse.ArgumentParser(description="places.csv → DB upsert")
    parser.add_argument("--dry-run", action="store_true", help="DB에 반영하지 않고 미리 확인")
    parser.add_argument("--csv", default="db data/places.csv", help="CSV 파일 경로")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    csv_path = project_root / args.csv if not os.path.isabs(args.csv) else Path(args.csv)

    if not csv_path.exists():
        print(f"[ERROR] 파일을 찾을 수 없습니다: {csv_path}", file=sys.stderr)
        sys.exit(1)

    rows = load_csv(str(csv_path))
    upsert_places(rows, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
