"""
artist_styles_final.csv → art_movements.yml 변환 스크립트

입력:
  scripts/data/artist_styles_final.csv  (final_styles, wikidata_styles_en, wikidata_styles_ko 컬럼 사용)

출력:
  scripts/data/art_movements.yml

규칙:
  - final_styles 컬럼의 모든 분파 추출 ( | 구분자)
  - 중복 제거 (대소문자 무시)
  - "romantic" → "Romanticism" 정규화
  - wikidata_styles_en/ko 매핑으로 name_ko 자동 채움
  - 미매핑 분파의 name_ko는 빈 문자열("")
  - YAML key는 ArtMovement 엔티티 필드와 동일: name_en, name_ko, period_start, period_end, description

사용법:
  python scripts/export_movements_yml.py
  python scripts/export_movements_yml.py --input other.csv --output other.yml
"""

import argparse
import csv
from pathlib import Path

import yaml

DEFAULT_CSV = Path(__file__).parent / "data" / "artist_styles_final.csv"
DEFAULT_WD_CSV = Path(__file__).parent / "data" / "artist_styles_wikidata.csv"
DEFAULT_OUTPUT = Path(__file__).parent / "data" / "art_movements.yml"

SEP = " | "

NORMALIZATIONS: dict[str, str] = {
    "romantic": "Romanticism",
}


def normalize(name: str) -> str:
    """정규화 테이블 적용."""
    return NORMALIZATIONS.get(name, name)


def build_ko_map(wd_csv_path: Path) -> dict[str, str]:
    """
    artist_styles_wikidata.csv의 movement_name_en / movement_name_ko 컬럼을
    행별로 읽어 소문자 영문명 → 한글명 매핑 딕셔너리 반환.
    원본 CSV는 분파마다 한 행씩 저장되므로 zip 오정렬 문제가 없다.
    """
    ko_map: dict[str, str] = {}
    with open(wd_csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            en = row.get("movement_name_en", "").strip()
            ko = row.get("movement_name_ko", "").strip()
            if not en or not ko:
                continue
            key = normalize(en).lower()
            if key not in ko_map:
                ko_map[key] = ko
    return ko_map


def collect_movements(csv_path: Path) -> list[str]:
    """
    final_styles 컬럼에서 분파명을 모두 수집.
    정규화 + 대소문자 무시 중복 제거 후 정렬된 리스트 반환.
    """
    seen_lower: set[str] = set()
    movements: list[str] = []

    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            final = row.get("final_styles", "").strip()
            if not final or final == "Nothing":
                continue
            for raw in final.split(SEP):
                raw = raw.strip()
                if not raw:
                    continue
                name = normalize(raw)
                key = name.lower()
                if key not in seen_lower:
                    movements.append(name)
                    seen_lower.add(key)

    return sorted(movements, key=lambda s: s.lower())


def build_records(movements: list[str], ko_map: dict[str, str]) -> list[dict]:
    """ArtMovement 엔티티 필드 구조로 레코드 리스트 생성."""
    records = []
    for name_en in movements:
        name_ko = ko_map.get(name_en.lower(), "")
        records.append({
            "name_en": name_en,
            "name_ko": name_ko,
            "period_start": None,
            "period_end": None,
            "description": None,
        })
    return records


def run(csv_path: Path, wd_csv_path: Path, output_path: Path) -> None:
    ko_map = build_ko_map(wd_csv_path)
    movements = collect_movements(csv_path)
    records = build_records(movements, ko_map)

    data = {"art_movements": records}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    unmapped = [r["name_en"] for r in records if not r["name_ko"]]
    print(f"=== 완료 ===")
    print(f"YAML 저장    : {output_path}")
    print(f"총 분파 수   : {len(records)}개")
    print(f"한글명 매핑  : {len(records) - len(unmapped)}개")
    if unmapped:
        print(f"미매핑 목록  ({len(unmapped)}개):")
        for name in unmapped:
            print(f"  - {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="final_styles CSV → art_movements.yml 변환")
    parser.add_argument("--input", type=Path, default=DEFAULT_CSV, help="입력 CSV 경로 (artist_styles_final.csv)")
    parser.add_argument("--wikidata", type=Path, default=DEFAULT_WD_CSV, help="Wikidata CSV 경로 (artist_styles_wikidata.csv)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="출력 YAML 경로")
    args = parser.parse_args()

    run(args.input, args.wikidata, args.output)
