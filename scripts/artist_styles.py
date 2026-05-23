"""
Art Institute of Chicago API - wikidata_search_targets.yml 작가 전체 유파 조회

흐름:
  1. scripts/data/wikidata_search_targets.yml의 creators 목록 로드
  2. 각 작가 이름으로 AIC 검색 → aic_artist_id 획득
  3. aic_artist_id로 작품 조회 → style_titles 집계 (시대 분류 제외)
  4. 결과를 scripts/data/artist_styles.csv에 저장

사용법:
  python scripts/artist_styles.py
  python scripts/artist_styles.py --output path/to/output.csv
"""

import argparse
import csv
import time
from collections import Counter
from pathlib import Path

import requests
import yaml

BASE_URL = "https://api.artic.edu/api/v1"
DEFAULT_YAML = Path(__file__).parent / "data" / "wikidata_search_targets.yml"
DEFAULT_CSV = Path(__file__).parent / "data" / "artist_styles.csv"

CSV_HEADERS = ["wikidata_id", "artist_name", "aic_artist_id", "style_name", "artwork_count"]

_TIME_PERIOD_KEYWORDS = (
    "century",
    "millennium",
    "bc",
    "bce",
    "ad ",
    "ancient",
    "prehistoric",
    "medieval",
    "early ",
    "late ",
    "mid-",
)


def _is_time_period(style: str) -> bool:
    """시대 분류 문자열(유파 아님)이면 True 반환."""
    lower = style.lower()
    return any(kw in lower for kw in _TIME_PERIOD_KEYWORDS)


def load_creators(yaml_path: Path) -> list[dict]:
    """YAML 파일에서 creators 목록 반환."""
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("creators", [])


def search_artist(name: str) -> list[dict]:
    """작가 이름으로 AIC 검색 → 후보 목록 반환."""
    params = {
        "q": name,
        "fields": "id,title,birth_date,death_date",
        "limit": 5,
    }
    resp = requests.get(f"{BASE_URL}/artists/search", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json().get("data", [])


def get_styles_by_artist_id(artist_id: int, limit: int = 100) -> Counter:
    """AIC artist_id로 작품 style_titles를 집계하여 Counter 반환. 시대 분류 제외."""
    params = {
        "query[term][artist_id]": artist_id,
        "fields": "style_titles",
        "limit": limit,
    }
    resp = requests.get(f"{BASE_URL}/artworks/search", params=params, timeout=10)
    resp.raise_for_status()

    counter: Counter = Counter()
    for artwork in resp.json().get("data", []):
        for style in artwork.get("style_titles") or []:
            if not _is_time_period(style):
                counter[style] += 1
    return counter


def collect_all(yaml_path: Path, output_csv: Path) -> None:
    """YAML의 creators 전체를 순회하여 유파를 조회하고 CSV로 저장."""
    creators = load_creators(yaml_path)
    print(f"총 {len(creators)}명 작가 유파 조사 시작\n")

    rows: list[dict] = []
    skipped: list[str] = []

    for idx, creator in enumerate(creators, 1):
        name = creator["name"]
        wikidata_id = creator["wikidata_id"]
        print(f"[{idx:02d}/{len(creators)}] {name} ... ", end="", flush=True)

        try:
            candidates = search_artist(name)
            if not candidates:
                print("AIC 검색 결과 없음 → SKIP")
                skipped.append(name)
                time.sleep(0.2)
                continue

            aic_artist = candidates[0]
            aic_id = aic_artist["id"]

            style_counter = get_styles_by_artist_id(aic_id)

            if not style_counter:
                print(f"유파 없음 (AIC ID={aic_id}) → SKIP")
                skipped.append(name)
            else:
                styles_str = ", ".join(s for s, _ in style_counter.most_common())
                print(f"→ {styles_str}")
                for style_name, count in style_counter.most_common():
                    rows.append({
                        "wikidata_id": wikidata_id,
                        "artist_name": name,
                        "aic_artist_id": aic_id,
                        "style_name": style_name,
                        "artwork_count": count,
                    })

        except Exception as e:
            print(f"오류: {e} → SKIP")
            skipped.append(name)

        time.sleep(0.15)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n=== 완료 ===")
    print(f"CSV 저장 : {output_csv}")
    print(f"저장 행수 : {len(rows)}건 ({len(creators) - len(skipped)}명 성공, {len(skipped)}명 스킵)")
    if skipped:
        print(f"스킵 목록 : {', '.join(skipped)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AIC API로 작가 유파 조회 후 CSV 저장")
    parser.add_argument("--yaml", type=Path, default=DEFAULT_YAML, help="입력 YAML 경로")
    parser.add_argument("--output", type=Path, default=DEFAULT_CSV, help="출력 CSV 경로")
    args = parser.parse_args()

    collect_all(args.yaml, args.output)
