"""무거운 응답 캐시를 미리 계산해 채운다(pre-warm).

인제스천/점수재계산 완료 훅(invalidate_all 직후)과 CLI(warm-cache)에서 호출한다.
현재 대상: 전체 서울 geojson(gu_name=None). 개별 대상 실패는 로그만 남기고 계속한다.
"""

import logging

from sqlalchemy.orm import Session

from app.core import response_cache
from app.database import SessionLocal
from app.services.geojson_service import build_district_geojson

logger = logging.getLogger(__name__)


def warm_cache(db: Session | None = None) -> int:
    """워밍 대상을 순회하며 캐시를 채운다. 워밍 성공한 항목 수를 반환한다.

    db=None이면 자체 세션을 생성·종료한다(세션 소유권 패턴). 개별 대상의 계산/저장
    실패는 잡아서 로그만 남기고 계속한다(비치명적).
    """
    owns_session = db is None
    if owns_session:
        db = SessionLocal()
    warmed = 0
    try:
        try:
            if response_cache.warm(
                "geojson", {"gu_name": None}, lambda: build_district_geojson(db, None)
            ):
                warmed += 1
        except Exception:
            logger.warning("geojson 캐시 워밍 실패", exc_info=True)
        return warmed
    finally:
        if owns_session:
            db.close()
