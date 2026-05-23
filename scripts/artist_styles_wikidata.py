"""
Wikidata SPARQL - wikidata_search_targets.yml 작가 전체 유파(P135) 조회

흐름:
  1. scripts/data/wikidata_search_targets.yml의 creators 목록 로드
  2. Wikidata SPARQL로 각 작가의 P135(movement) 속성 배치 조회
  3. 영문·한글 유파명 함께 수집
  4. 결과를 scripts/data/artist_styles_wikidata.csv에 저장

사용법:
  python scripts/artist_styles_wikidata.py
  python scripts/artist_styles_wikidata.py --output path/to/output.csv
  python scripts/artist_styles_wikidata.py --batch-size 10
"""

import argparse
import csv
import time
from pathlib import Path

import requests
import yaml

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
DEFAULT_YAML = Path(__file__).parent / "data" / "wikidata_search_targets.yml"
DEFAULT_CSV = Path(__file__).parent / "data" / "artist_styles_wikidata.csv"
DEFAULT_BATCH_SIZE = 20

CSV_HEADERS = [
    "wikidata_id",
    "artist_name",
    "movement_wikidata_id",
    "movement_name_en",
    "movement_name_ko",
]

SPARQL_HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "artmap-db/1.0 (data pipeline) python-requests",
}


def load_creators(yaml_path: Path) -> list[dict]:
    """YAML 파일에서 creators 목록 반환."""
    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("creators", [])


def build_sparql_query(wikidata_ids: list[str]) -> str:
    """
    VALUES 절에 여러 작가 ID를 넣어 P135(movement) 속성을 한 번에 조회하는
    SPARQL 쿼리 생성. 영문·한글 레이블 모두 요청.
    """
    values = " ".join(f"wd:{qid}" for qid in wikidata_ids)
    return f"""
SELECT ?artist ?movement ?movementLabelEn ?movementLabelKo WHERE {{
  VALUES ?artist {{ {values} }}
  ?artist wdt:P135 ?movement.
  OPTIONAL {{
    ?movement rdfs:label ?movementLabelEn.
    FILTER(LANG(?movementLabelEn) = "en")
  }}
  OPTIONAL {{
    ?movement rdfs:label ?movementLabelKo.
    FILTER(LANG(?movementLabelKo) = "ko")
  }}
}}
ORDER BY ?artist ?movement
"""


def run_sparql(query: str, retries: int = 3) -> list[dict]:
    """SPARQL 쿼리 실행 후 bindings 반환. 실패 시 재시도."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                SPARQL_ENDPOINT,
                params={"query": query, "format": "json"},
                headers=SPARQL_HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["results"]["bindings"]
        except Exception as e:
            print(f"  [재시도 {attempt}/{retries}] SPARQL 오류: {e}")
            if attempt < retries:
                time.sleep(2 * attempt)
    return []


def _qid_from_uri(uri: str) -> str:
    """'http://www.wikidata.org/entity/Q123' → 'Q123'"""
    return uri.rsplit("/", 1)[-1]


def collect_all(yaml_path: Path, output_csv: Path, batch_size: int) -> None:
    """creators 전체를 배치 단위로 SPARQL 조회하여 CSV 저장."""
    creators = load_creators(yaml_path)
    id_to_name = {c["wikidata_id"]: c["name"] for c in creators}
    all_ids = list(id_to_name.keys())

    print(f"총 {len(all_ids)}명 작가 유파 조사 시작 (배치 크기: {batch_size})\n")

    rows: list[dict] = []
    found_ids: set[str] = set()

    for batch_start in range(0, len(all_ids), batch_size):
        batch = all_ids[batch_start: batch_start + batch_size]
        batch_end = min(batch_start + batch_size, len(all_ids))
        print(f"배치 [{batch_start + 1}–{batch_end}/{len(all_ids)}] 조회 중...", end=" ", flush=True)

        query = build_sparql_query(batch)
        bindings = run_sparql(query)

        batch_rows: dict[str, list] = {}
        for b in bindings:
            artist_uri = b.get("artist", {}).get("value", "")
            movement_uri = b.get("movement", {}).get("value", "")
            qid = _qid_from_uri(artist_uri)
            movement_qid = _qid_from_uri(movement_uri)
            name_en = b.get("movementLabelEn", {}).get("value", "")
            name_ko = b.get("movementLabelKo", {}).get("value", "")

            if qid not in batch_rows:
                batch_rows[qid] = []
            batch_rows[qid].append((movement_qid, name_en, name_ko))

        for qid in batch:
            artist_name = id_to_name[qid]
            movements = batch_rows.get(qid, [])
            if movements:
                found_ids.add(qid)
                styles_preview = ", ".join(
                    m[1] or m[0] for m in movements[:3]
                )
                if len(movements) > 3:
                    styles_preview += f" 외 {len(movements) - 3}개"
                print(f"\n  ✓ {artist_name:<35} → {styles_preview}", end="")
                for movement_qid, name_en, name_ko in movements:
                    rows.append({
                        "wikidata_id": qid,
                        "artist_name": artist_name,
                        "movement_wikidata_id": movement_qid,
                        "movement_name_en": name_en,
                        "movement_name_ko": name_ko,
                    })
            else:
                print(f"\n  ✗ {artist_name:<35} → P135 데이터 없음", end="")

        print()
        time.sleep(1.0)

    skipped = [id_to_name[qid] for qid in all_ids if qid not in found_ids]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n=== 완료 ===")
    print(f"CSV 저장 : {output_csv}")
    print(f"저장 행수 : {len(rows)}건 ({len(found_ids)}명 성공, {len(skipped)}명 스킵)")
    if skipped:
        print(f"스킵 목록 : {', '.join(skipped)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wikidata SPARQL로 작가 유파(P135) 조회 후 CSV 저장")
    parser.add_argument("--yaml", type=Path, default=DEFAULT_YAML, help="입력 YAML 경로")
    parser.add_argument("--output", type=Path, default=DEFAULT_CSV, help="출력 CSV 경로")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="SPARQL 배치 크기 (기본: 20)")
    args = parser.parse_args()

    collect_all(args.yaml, args.output, args.batch_size)
