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
    session = db
    owns_session = session is None
    warmed = 0
    try:
        if owns_session:
            session = SessionLocal()  # 세션 생성 실패도 아래 except가 삼킨다(비치명적).
        try:
            if response_cache.warm(
                "geojson", {"gu_name": None}, lambda: build_district_geojson(session, None)
            ):
                warmed += 1
        except Exception:
            logger.warning("geojson 캐시 워밍 실패", exc_info=True)
            # 워밍 중 db.execute()가 실패하면 세션이 aborted-transaction 상태로 남는다.
            # 주입된 세션(점수 훅 등)이 이후 재사용될 수 있으므로 롤백해 clean 상태로 되돌린다.
            try:
                session.rollback()
            except Exception:
                logger.warning("워밍 실패 후 세션 롤백 실패", exc_info=True)
        return warmed
    except Exception:
        # 세션 생성 등 예기치 못한 실패도 호출 경로(CLI/인제스천/점수 잡)를 실패시키지 않는다.
        logger.warning("캐시 워밍 세션 처리 실패", exc_info=True)
        return warmed
    finally:
        if owns_session and session is not None:
            try:
                session.close()  # 정리 실패도 전파하지 않는다(비치명적 계약).
            except Exception:
                logger.warning("워밍 세션 close 실패", exc_info=True)
