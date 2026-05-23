"""
art_movements.yml 빈 필드 자동 보충 스크립트

적용 순서 (필드별):
  name_ko       → ① Wikidata 한글 레이블  → ② OpenAI 번역 (선택)
  period_start  → ① Wikidata P571 (inception)
  period_end    → ① Wikidata P582 (dissolved)
  description   → ① Wikipedia 요약        → ② OpenAI 생성 (선택)

OpenAI 사용 조건:
  - `pip install openai` 설치 필요
  - 환경변수 OPENAI_API_KEY 설정 필요
  - --llm 플래그 명시해야 활성화됨

사용법:
  python scripts/enrich_movements_yml.py
  python scripts/enrich_movements_yml.py --llm              # OpenAI fallback 활성화
  python scripts/enrich_movements_yml.py --dry-run          # 변경 내용 미리보기 (파일 저장 안 함)
  python scripts/enrich_movements_yml.py --input other.yml --output other_enriched.yml
"""

from __future__ import annotations

import argparse
import os
import re
import time
from pathlib import Path

import requests
import yaml

DEFAULT_YML = Path(__file__).parent / "data" / "art_movements.yml"

WD_API = "https://www.wikidata.org/w/api.php"
WP_API = "https://en.wikipedia.org/api/rest_v1/page/summary"
HEADERS = {"User-Agent": "artmap-db/1.0 python-requests"}

DESCRIPTION_MAX_LEN = 400


# ---------------------------------------------------------------------------
# Wikidata helpers
# ---------------------------------------------------------------------------

def _wd_search(name: str) -> str | None:
    """영문명으로 Wikidata 엔티티 ID(Q번호) 검색. 첫 결과 반환."""
    try:
        resp = requests.get(
            WD_API,
            params={
                "action": "wbsearchentities",
                "search": name,
                "language": "en",
                "type": "item",
                "limit": 3,
                "format": "json",
            },
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("search", [])
        return results[0]["id"] if results else None
    except Exception:
        return None


def _wd_entity(qid: str) -> dict:
    """엔티티 상세 정보(labels, claims) 조회."""
    try:
        resp = requests.get(
            WD_API,
            params={
                "action": "wbgetentities",
                "ids": qid,
                "format": "json",
                "languages": "en|ko",
                "props": "labels|claims",
            },
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("entities", {}).get(qid, {})
    except Exception:
        return {}


def _parse_year(time_str: str) -> int | None:
    """'+1874-01-01T00:00:00Z' → 1874"""
    m = re.search(r"[+-](\d{4})", time_str)
    return int(m.group(1)) if m else None


def _wd_claim_year(entity: dict, prop: str) -> int | None:
    """claims에서 연도 추출. P571=inception, P582=end."""
    claims = entity.get("claims", {}).get(prop, [])
    for claim in claims:
        try:
            time_str = claim["mainsnak"]["datavalue"]["value"]["time"]
            return _parse_year(time_str)
        except (KeyError, TypeError):
            continue
    return None


def enrich_from_wikidata(name_en: str) -> dict:
    """Wikidata에서 name_ko, period_start, period_end 수집."""
    result: dict = {}
    qid = _wd_search(name_en)
    if not qid:
        return result

    entity = _wd_entity(qid)
    if not entity:
        return result

    ko_label = entity.get("labels", {}).get("ko", {}).get("value", "")
    if ko_label:
        result["name_ko"] = ko_label

    start = _wd_claim_year(entity, "P571")
    if start:
        result["period_start"] = start

    end = _wd_claim_year(entity, "P582")
    if end:
        result["period_end"] = end

    return result


# ---------------------------------------------------------------------------
# Wikipedia helpers
# ---------------------------------------------------------------------------

def enrich_from_wikipedia(name_en: str) -> str | None:
    """Wikipedia 요약 첫 문단을 description으로 반환."""
    try:
        slug = name_en.replace(" ", "_")
        resp = requests.get(
            f"{WP_API}/{slug}",
            headers=HEADERS,
            timeout=10,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        extract = resp.json().get("extract", "").strip()
        if not extract:
            return None
        return extract[:DESCRIPTION_MAX_LEN] + ("..." if len(extract) > DESCRIPTION_MAX_LEN else "")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# OpenAI helpers (optional)
# ---------------------------------------------------------------------------

def _get_openai_client():
    try:
        from openai import OpenAI  # type: ignore
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)
    except ImportError:
        return None


def enrich_from_llm(client, name_en: str, need_ko: bool, need_desc: bool) -> dict:
    """OpenAI로 name_ko, description 생성."""
    result: dict = {}
    if not client:
        return result

    if need_ko:
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an art history expert."},
                    {"role": "user", "content": (
                        f"What is the Korean name for the art movement '{name_en}'? "
                        "Reply with only the Korean name (2~10 characters). "
                        "If there is no established Korean term, reply with an empty string."
                    )},
                ],
                max_tokens=30,
                temperature=0,
            )
            ko = resp.choices[0].message.content.strip().strip('"').strip("'")
            if ko:
                result["name_ko"] = ko
        except Exception:
            pass

    if need_desc:
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an art history expert. Be factual and concise."},
                    {"role": "user", "content": (
                        f"Describe the art movement '{name_en}' in 2-3 sentences in English."
                    )},
                ],
                max_tokens=120,
                temperature=0,
            )
            desc = resp.choices[0].message.content.strip()
            if desc:
                result["description"] = desc
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def enrich(input_path: Path, output_path: Path, use_llm: bool, dry_run: bool) -> None:
    with open(input_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    movements: list[dict] = data.get("art_movements", [])
    llm_client = _get_openai_client() if use_llm else None

    if use_llm and llm_client is None:
        print("[경고] --llm 옵션이 지정됐지만 openai 패키지 미설치 또는 OPENAI_API_KEY 미설정. LLM 단계 건너뜀.\n")

    updated = 0
    for i, mv in enumerate(movements, 1):
        name = mv["name_en"]
        needs_ko = not mv.get("name_ko")
        needs_period = mv.get("period_start") is None or mv.get("period_end") is None
        needs_desc = mv.get("description") is None

        if not (needs_ko or needs_period or needs_desc):
            print(f"[{i:02d}/{len(movements)}] {name:<35} ✓ 이미 완성")
            continue

        print(f"[{i:02d}/{len(movements)}] {name:<35}", end=" ", flush=True)
        changes: list[str] = []

        # ── 1. Wikidata ──────────────────────────────────────────────
        if needs_ko or needs_period:
            wd = enrich_from_wikidata(name)
            if wd.get("name_ko") and needs_ko:
                mv["name_ko"] = wd["name_ko"]
                changes.append(f"name_ko={wd['name_ko']}")
                needs_ko = False
            if wd.get("period_start") is not None and mv.get("period_start") is None:
                mv["period_start"] = wd["period_start"]
                changes.append(f"start={wd['period_start']}")
            if wd.get("period_end") is not None and mv.get("period_end") is None:
                mv["period_end"] = wd["period_end"]
                changes.append(f"end={wd['period_end']}")
            time.sleep(0.3)

        # ── 2. Wikipedia ─────────────────────────────────────────────
        if needs_desc:
            desc = enrich_from_wikipedia(name)
            if desc:
                mv["description"] = desc
                changes.append("description=✓")
                needs_desc = False
            time.sleep(0.2)

        # ── 3. OpenAI fallback ────────────────────────────────────────
        if (needs_ko or needs_desc) and llm_client:
            llm = enrich_from_llm(llm_client, name, needs_ko, needs_desc)
            if llm.get("name_ko"):
                mv["name_ko"] = llm["name_ko"]
                changes.append(f"name_ko(LLM)={llm['name_ko']}")
            if llm.get("description"):
                mv["description"] = llm["description"]
                changes.append("description(LLM)=✓")
            time.sleep(0.5)

        if changes:
            print(f"→ {', '.join(changes)}")
            updated += 1
        else:
            print("→ 데이터 없음 (수동 입력 필요)")

    print(f"\n=== {'미리보기' if dry_run else '완료'} ===")
    print(f"처리 분파  : {len(movements)}개")
    print(f"업데이트   : {updated}개")

    if dry_run:
        print("(--dry-run 모드: 파일 저장 안 함)")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(
            {"art_movements": movements},
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
    print(f"저장 경로  : {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="art_movements.yml 빈 필드 자동 보충")
    parser.add_argument("--input", type=Path, default=DEFAULT_YML, help="입력 YAML 경로")
    parser.add_argument("--output", type=Path, default=DEFAULT_YML, help="출력 YAML 경로 (기본: 덮어쓰기)")
    parser.add_argument("--llm", action="store_true", help="OpenAI fallback 활성화 (OPENAI_API_KEY 필요)")
    parser.add_argument("--dry-run", action="store_true", help="파일 저장 없이 결과 미리보기")
    args = parser.parse_args()

    enrich(args.input, args.output, args.llm, args.dry_run)
