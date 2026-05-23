"""
AIC + Wikidata 유파 CSV 병합 스크립트

입력:
  - scripts/data/artist_styles.csv          (AIC API 결과)
  - scripts/data/artist_styles_wikidata.csv (Wikidata SPARQL 결과)
  - scripts/data/wikidata_search_targets.yml (전체 작가 마스터)

출력:
  - scripts/data/artist_styles_final.csv

규칙:
  - 같은 작가에 대해 두 소스의 유파가 다르면 final_styles에 모두 기입 (사용자 직접 선택)
  - 두 소스 모두 유파 데이터가 없으면 final_styles = "Nothing"
  - final_styles 내 항목은 " | " 구분자 사용
  - 대소문자 무시 중복 제거 (동일 유파 두 번 기입 방지)

사용법:
  python scripts/merge_artist_styles.py
  python scripts/merge_artist_styles.py --aic aic.csv --wikidata wd.csv --output out.csv
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import yaml

DEFAULT_YAML = Path(__file__).parent / "data" / "wikidata_search_targets.yml"
DEFAULT_AIC_CSV = Path(__file__).parent / "data" / "artist_styles.csv"
DEFAULT_WD_CSV = Path(__file__).parent / "data" / "artist_styles_wikidata.csv"
DEFAULT_OUTPUT = Path(__file__).parent / "data" / "artist_styles_final.csv"

CSV_HEADERS = [
    "wikidata_id",
    "artist_name",
    "aic_styles_en",
    "wikidata_styles_en",
    "wikidata_styles_ko",
    "final_styles",
]

SEP = " | "


def load_creators(yaml_path: Path) -> list[dict]:
    with open(yaml_path, encoding="utf-8") as f:
        return yaml.safe_load(f).get("creators", [])


def load_aic_styles(csv_path: Path) -> dict[str, list[str]]:
    """wikidata_id → [style_name, ...] (출현 순, 중복 제거)"""
    result: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, set] = defaultdict(set)
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            qid = row["wikidata_id"]
            style = row["style_name"].strip()
            if style and style.lower() not in seen[qid]:
                result[qid].append(style)
                seen[qid].add(style.lower())
    return dict(result)


def load_wikidata_styles(csv_path: Path) -> dict[str, tuple[list[str], list[str]]]:
    """wikidata_id → ([name_en, ...], [name_ko, ...]) — 순서 유지, 중복 제거"""
    en_map: dict[str, list[str]] = defaultdict(list)
    ko_map: dict[str, list[str]] = defaultdict(list)
    seen_en: dict[str, set] = defaultdict(set)
    seen_ko: dict[str, set] = defaultdict(set)

    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            qid = row["wikidata_id"]
            en = row["movement_name_en"].strip()
            ko = row["movement_name_ko"].strip()
            if en and en.lower() not in seen_en[qid]:
                en_map[qid].append(en)
                seen_en[qid].add(en.lower())
            if ko and ko.lower() not in seen_ko[qid]:
                ko_map[qid].append(ko)
                seen_ko[qid].add(ko.lower())

    all_ids = set(en_map) | set(ko_map)
    return {qid: (en_map.get(qid, []), ko_map.get(qid, [])) for qid in all_ids}


def merge_styles(aic: list[str], wikidata_en: list[str]) -> str:
    """
    두 소스의 유파를 합쳐 final_styles 문자열 반환.
    - 대소문자 무시 중복 제거 (Wikidata 우선 유지)
    - 둘 다 비어있으면 "Nothing"
    """
    if not aic and not wikidata_en:
        return "Nothing"

    seen_lower: set[str] = set()
    merged: list[str] = []

    for style in wikidata_en + aic:
        key = style.lower()
        if key not in seen_lower:
            merged.append(style)
            seen_lower.add(key)

    return SEP.join(merged)


def run(yaml_path: Path, aic_csv: Path, wd_csv: Path, output_csv: Path) -> None:
    creators = load_creators(yaml_path)
    aic_data = load_aic_styles(aic_csv)
    wd_data = load_wikidata_styles(wd_csv)

    rows: list[dict] = []
    nothing_count = 0
    conflict_count = 0

    for creator in creators:
        qid = creator["wikidata_id"]
        name = creator["name"]

        aic_styles = aic_data.get(qid, [])
        wd_en, wd_ko = wd_data.get(qid, ([], []))

        final = merge_styles(aic_styles, wd_en)

        # 두 소스가 모두 있고 내용이 다른 경우 충돌로 표시
        aic_set = {s.lower() for s in aic_styles}
        wd_set = {s.lower() for s in wd_en}
        has_conflict = bool(aic_styles and wd_en and not aic_set.issubset(wd_set) and not wd_set.issubset(aic_set))

        if final == "Nothing":
            nothing_count += 1
        if has_conflict:
            conflict_count += 1

        rows.append({
            "wikidata_id": qid,
            "artist_name": name,
            "aic_styles": SEP.join(aic_styles) if aic_styles else "-",
            "wikidata_styles_en": SEP.join(wd_en) if wd_en else "-",
            "wikidata_styles_ko": SEP.join(wd_ko) if wd_ko else "-",
            "final_styles": final,
        })

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"=== 병합 완료 ===")
    print(f"CSV 저장     : {output_csv}")
    print(f"총 작가 수   : {len(rows)}명")
    print(f"유파 없음    : {nothing_count}명  (final_styles = 'Nothing')")
    print(f"소스 충돌    : {conflict_count}명  (AIC ≠ Wikidata — 직접 선택 필요)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AIC + Wikidata 유파 CSV 병합")
    parser.add_argument("--aic", type=Path, default=DEFAULT_AIC_CSV, help="AIC CSV 경로")
    parser.add_argument("--wikidata", type=Path, default=DEFAULT_WD_CSV, help="Wikidata CSV 경로")
    parser.add_argument("--yaml", type=Path, default=DEFAULT_YAML, help="작가 마스터 YAML")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="출력 CSV 경로")
    args = parser.parse_args()

    run(args.yaml, args.aic, args.wikidata, args.output)
