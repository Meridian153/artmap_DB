#!/usr/bin/env python3
"""
미술관별 Wikidata SPARQL 작품 검색 → 미술관별 CSV 파일 저장

사용법:
  python3 scripts/fetch_wikidata_by_museum.py                        # 전체 미술관 검색
  python3 scripts/fetch_wikidata_by_museum.py --outdir results       # 출력 폴더 지정
  python3 scripts/fetch_wikidata_by_museum.py --targets custom.yml   # 입력 파일 지정
  python3 scripts/fetch_wikidata_by_museum.py --limit 100            # 미술관당 최대 작품 수
  python3 scripts/fetch_wikidata_by_museum.py --batch-size 5 --batch-pause 60  # 5개마다 60초 대기

결과:
  <outdir>/
    01_Musee_du_Louvre.csv
    02_Musee_dOrsay.csv
    ...
    _summary.csv          ← 전체 요약
"""

import argparse
import csv
import re
import sys
import time
from pathlib import Path

import yaml

sys.path.append(str(Path(__file__).parent.parent))

from src.reception.infra.external_apis.wikidata_client import WikidataClient
from src.shared_kernel.infra.log.logger import setup_logger

logger = setup_logger("FetchWikidataByMuseum")

DEFAULT_TARGETS = Path(__file__).parent / "data" / "wikidata_search_targets.yml"
DEFAULT_OUTDIR = Path(__file__).parent.parent / "db data" / "wikidata_by_museum"

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
]


def load_targets(path: Path) -> dict:
    """YAML 타겟 파일 로드"""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data


def sanitize_filename(name: str) -> str:
    """파일명에 사용할 수 없는 문자 제거"""
    name = re.sub(r"[^\w\s\-]", "", name)
    name = re.sub(r"\s+", "_", name.strip())
    return name


def save_museum_csv(results: list[dict], filepath: Path):
    """단일 미술관 결과를 CSV 파일로 저장"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)


def save_summary_csv(summary: list[dict], filepath: Path):
    """전체 요약 CSV 저장"""
    headers = ["no", "museum_name", "wikidata_id", "artwork_count", "file"]
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(summary)


def main():
    parser = argparse.ArgumentParser(description="미술관별 Wikidata 작품 검색 → 개별 CSV 저장")
    parser.add_argument(
        "--targets",
        type=Path,
        default=DEFAULT_TARGETS,
        help="검색 대상 YAML 파일 경로",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=DEFAULT_OUTDIR,
        help="결과 CSV 저장 폴더 (기본: db data/wikidata_by_museum/)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="미술관당 최대 작품 수 (미지정 시 YAML의 default_limit 사용)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="한 배치에 처리할 미술관 수 (기본: 5)",
    )
    parser.add_argument(
        "--batch-pause",
        type=int,
        default=60,
        help="배치 간 대기 시간(초) (기본: 60)",
    )
    args = parser.parse_args()

    # 1) YAML 로드
    if not args.targets.exists():
        logger.error(f"Targets file not found: {args.targets}")
        sys.exit(1)

    data = load_targets(args.targets)
    collections = data.get("collections", [])
    default_limit = args.limit or data.get("default_limit", 50)

    batch_size = args.batch_size
    batch_pause = args.batch_pause

    logger.info(f"Loaded {len(collections)} museums, limit={default_limit} per museum")
    logger.info(f"Batch: {batch_size}개마다 {batch_pause}초 대기")

    # 2) 출력 폴더 생성
    args.outdir.mkdir(parents=True, exist_ok=True)

    # 3) 미술관별 SPARQL 검색
    client = WikidataClient()
    summary = []
    total_artworks = 0

    try:
        for idx, col in enumerate(collections, start=1):
            wid = col["wikidata_id"]
            name = col.get("name", wid)
            safe_name = sanitize_filename(name)
            filename = f"{idx:02d}_{safe_name}.csv"
            filepath = args.outdir / filename

            logger.info(f"\n[{idx}/{len(collections)}] {name} ({wid})")

            try:
                results = client.search_artworks_by_collection(wid, limit=default_limit)
            except Exception as e:
                logger.error(f"  ✗ SPARQL failed: {e}")
                summary.append({
                    "no": idx,
                    "museum_name": name,
                    "wikidata_id": wid,
                    "artwork_count": 0,
                    "file": f"ERROR: {e}",
                })
                time.sleep(3)
                continue

            if results:
                save_museum_csv(results, filepath)
                logger.info(f"  ✓ {len(results)} artworks → {filename}")
            else:
                logger.info(f"  → 0 artworks found")

            summary.append({
                "no": idx,
                "museum_name": name,
                "wikidata_id": wid,
                "artwork_count": len(results),
                "file": filename if results else "",
            })
            total_artworks += len(results)

            # Wikidata rate limit 준수 (개별 요청 간 대기)
            time.sleep(2)

            # 배치 단위 대기
            if idx % batch_size == 0 and idx < len(collections):
                remaining = len(collections) - idx
                logger.info(
                    f"\n>>> 배치 {idx // batch_size} 완료 "
                    f"({idx}/{len(collections)}). "
                    f"남은 미술관: {remaining}곳. "
                    f"{batch_pause}초 대기 중..."
                )
                time.sleep(batch_pause)

    finally:
        client.close()

    # 4) 전체 요약 CSV 저장
    summary_path = args.outdir / "_summary.csv"
    save_summary_csv(summary, summary_path)

    # 5) 결과 출력
    logger.info(f"\n{'='*60}")
    logger.info(f"  검색 완료!")
    logger.info(f"  미술관: {len(collections)}곳")
    logger.info(f"  총 작품: {total_artworks}점")
    logger.info(f"  저장 위치: {args.outdir}/")
    logger.info(f"  요약 파일: {summary_path}")
    logger.info(f"{'='*60}")

    # 콘솔 요약 테이블
    logger.info(f"\n{'No':<4} {'Museum':<45} {'Artworks':>8}")
    logger.info(f"{'-'*4} {'-'*45} {'-'*8}")
    for s in summary:
        logger.info(f"{s['no']:<4} {s['museum_name']:<45} {s['artwork_count']:>8}")
    logger.info(f"{'':4} {'TOTAL':<45} {total_artworks:>8}")


if __name__ == "__main__":
    main()
