#!/usr/bin/env python3
"""
전체 데이터 수집 마스터 스크립트
MVP 문서의 Phase 순서대로 데이터를 수집합니다.

실행 순서:
1. Museums (미술관 30곳 - 우선 15곳)
2. Artists (화가 50명 - 우선 20명)
3. Artworks from Met Museum (5점)
4. Artworks from Art Institute of Chicago (5점)

총 예상 시간: 약 5-10분
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from ingest_aic_artworks import ingest_aic_artworks
from ingest_artists import ingest_artists
from ingest_met_artworks import ingest_met_artworks
from ingest_museums import ingest_museums

from src.shared_kernel.infra.log.logger import setup_logger

logger = setup_logger("IngestAll")


def main():
    """전체 데이터 수집 실행"""
    logger.info("=" * 80)
    logger.info("ArtMap MVP 데이터 수집 시작")
    logger.info("=" * 80)

    try:
        # Phase 1: 미술관 수집
        logger.info("\n[Phase 1/4] 미술관 정보 수집 중...")
        logger.info("-" * 80)
        ingest_museums()
        logger.info("✓ Phase 1 완료\n")

        # Phase 2: 작가 수집
        logger.info("\n[Phase 2/4] 작가 정보 수집 중...")
        logger.info("-" * 80)
        ingest_artists()
        logger.info("✓ Phase 2 완료\n")

        # Phase 3: Met Museum 작품 수집
        logger.info("\n[Phase 3/4] Met Museum 작품 수집 중...")
        logger.info("-" * 80)
        met_object_ids = [
            436535,  # Wheat Field with Cypresses (Van Gogh)
            436528,  # The Starry Night drawing (Van Gogh)
            437853,  # Cypresses (Van Gogh)
            459123,  # Irises (Van Gogh)
            437112,  # Self-Portrait with a Straw Hat (Van Gogh)
        ]
        ingest_met_artworks(met_object_ids)
        logger.info("✓ Phase 3 완료\n")

        # Phase 4: Art Institute of Chicago 작품 수집
        logger.info("\n[Phase 4/4] Art Institute of Chicago 작품 수집 중...")
        logger.info("-" * 80)
        aic_artwork_ids = [
            27992,  # A Sunday on La Grande Jatte (Seurat)
            28560,  # The Bedroom (Van Gogh)
            80607,  # Nighthawks (Hopper)
            16568,  # American Gothic (Wood)
            111628,  # The Old Guitarist (Picasso)
        ]
        ingest_aic_artworks(aic_artwork_ids)
        logger.info("✓ Phase 4 완료\n")

        # 완료 메시지
        logger.info("=" * 80)
        logger.info("✓ 전체 데이터 수집 완료!")
        logger.info("=" * 80)
        logger.info("\n수집된 데이터:")
        logger.info("  - 미술관: 15곳 (Met, AIC, Louvre, Orsay, Van Gogh Museum 등)")
        logger.info("  - 작가: 20명 (Leonardo, Monet, Van Gogh, Rembrandt 등)")
        logger.info("  - 작품: 10점 (Met 5점 + AIC 5점)")
        logger.info("\n다음 단계:")
        logger.info("  1. 데이터 확인: psql -U postgres -d artmap")
        logger.info("  2. 데이터 백업: pg_dump -U postgres artmap > backup.sql")
        logger.info("  3. 추가 작품 수집: 각 스크립트에 작품 ID 추가 후 재실행")

    except Exception as e:
        logger.error(f"\n✗ 데이터 수집 중 오류 발생: {str(e)}")
        raise


if __name__ == "__main__":
    main()
