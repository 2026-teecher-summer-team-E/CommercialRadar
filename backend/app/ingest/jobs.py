"""인제스천 오케스트레이션.

각 job은 fetch(E) → transform(T) → load(L)을 조합하고,
ingestion_run 테이블에 실행 이력을 남긴다.
크론(CLI)과 관리자 엔드포인트(admin router)가 이 함수를 공유 호출한다.

Job 실행 순서 ("all" 타겟):
  1. seoul_commercial — 상권 영역(TbgisTrdarRelm) → commercial_district
  2. seoul_population — 길단위인구(VwsmTrdarFlpopQq) → population_heatmap
  3. seoul_business   — 추정매출+점포 병합 → business_category
  4. seoul_foreign    — 외국인/내국인 생활인구 3개 서비스 → foreign_population
  5. seoul_rent       — R-ONE 상가임대료 3개 상가유형 → rent_stats

자식 job(2~5)은 commercial_district_id 조인이 필요하므로
seoul_commercial이 먼저 완료돼 있어야 한다.
JOBS dict 순서가 "all" 실행 순서를 결정한다(Python 3.7+ dict 삽입 순서 보장).
"""

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.database import SessionLocal
from app.ingest.clients.seoul_client import SeoulClient
from app.ingest.clients.reb_client import RebClient, STATBL_FLOOR_TYPE
from app.ingest.clients.naver_datalab_client import fetch_buzz
from app.ingest.transformers.buzz_transformer import transform_datalab_response
from app.ingest.loaders.buzz_loader import upsert_all as upsert_buzz
from app.ingest.loaders import commercial_loader, population_loader, business_loader
from app.ingest.loaders import foreign_loader, rent_loader, population_timeseries_loader
from app.ingest.loaders.resolver import load_trdar_map, load_adstrd_map, load_district_name_map
from app.ingest.transformers import (
    commercial_transformer,
    population_transformer,
    business_transformer,
)
from app.ingest.transformers import foreign_transformer, rent_transformer
from app.models.ingestion_run import IngestionRun

logger = logging.getLogger(__name__)

# 서울 열린데이터광장 서비스명 상수
_SVC_COMMERCIAL = "TbgisTrdarRelm"   # 상권 영역 (~1,650건)
_SVC_POPULATION = "VwsmTrdarFlpopQq" # 길단위인구 (~34,600건 전체 / ~1,650건 최신 분기)
_SVC_SALES      = "VwsmTrdarSelngQq" # 추정매출 (~460k건 전체 / ~21k건 최신 분기)
_SVC_STORE      = "VwsmTrdarStorQq"  # 점포 (~1.6M건 전체 / ~76k건 최신 분기)

# 서울 생활인구 서비스 (기준일 필터 사용, ~10,176건/일)
_SVC_FP_LONG  = "SPOP_FORN_LONG_RESD_DONG"  # 외국인 장기체류 생활인구
_SVC_FP_TEMP  = "SPOP_FORN_TEMP_RESD_DONG"  # 외국인 단기체류 생활인구
_SVC_FP_LOCAL = "SPOP_LOCAL_RESD_DONG"       # 내국인 생활인구 (총계용)

# business 백필: 최신 분기부터 과거로 몇 개 분기를 수집할지 (5년=20, 버퍼 포함 24).
# 데이터 없는 분기(범위 밖)는 자동 스킵된다.
BUSINESS_BACKFILL_QUARTERS = 24

# rent 백필: R-ONE은 전 분기를 한 번에 반환 → 최신부터 이 개수만큼만 남긴다 (business와 정렬).
RENT_BACKFILL_QUARTERS = 24


def _start_run(db: Session, source: str) -> IngestionRun:
    """ingestion_run에 running 상태로 새 레코드를 생성한다."""
    run = IngestionRun(source=source, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _prev_quarters(latest: str, n: int) -> list[str]:
    """분기코드 latest('YYYYQ')에서 과거로 n개 분기코드 생성 (최신→과거).

    예: _prev_quarters('20254', 3) → ['20254', '20253', '20252']
    """
    year, q = int(latest[:4]), int(latest[4])
    out: list[str] = []
    for _ in range(n):
        out.append(f"{year}{q}")
        q -= 1
        if q == 0:
            q, year = 4, year - 1
    return out


def _wrttime_minus_quarters(wrttime: str, n: int) -> str:
    """R-ONE 기준시점 'YYYYQQ'에서 n분기 이전 값 반환 (2자리 분기).

    예: _wrttime_minus_quarters('202601', 4) → '202501'
    """
    year, q = int(wrttime[:4]), int(wrttime[4:])
    for _ in range(n):
        q -= 1
        if q == 0:
            q, year = 4, year - 1
    return f"{year}{q:02d}"


# ──────────────────────────────────────────────────────────────────────────────
# Job 1: 상권 영역
# ──────────────────────────────────────────────────────────────────────────────

def ingest_seoul_commercial(db: Session | None = None) -> IngestionRun:
    """서울 상권영역(TbgisTrdarRelm) → commercial_district 인제스천.

    전체 ~1,650건을 페이지네이션하며 수신 후 upsert한다.
    geometry는 폴리곤 수동 적재 정책에 따라 건드리지 않는다.
    db를 주입하지 않으면 자체 세션을 만든다(크론에서 이렇게 호출).
    """
    owns_session = db is None
    db = db or SessionLocal()
    source = "seoul_commercial"
    run = _start_run(db, source)

    try:
        rows: list[dict] = []
        failed = 0

        with SeoulClient(_SVC_COMMERCIAL) as client:
            for raw in client.iter_rows():
                transformed = commercial_transformer.transform_record(raw)
                if transformed is not None:
                    rows.append(transformed)
                else:
                    failed += 1

        upserted = commercial_loader.upsert_all(db, rows)

        run.status = "success"
        run.fetched_count = len(rows) + failed
        run.upserted_count = upserted
        run.failed_count = failed
        run.finished_at = func.now()
        db.commit()
        logger.info(
            "인제스천 완료 [%s]: fetched=%d upserted=%d failed=%d",
            source, run.fetched_count, upserted, failed,
        )
        return run

    except Exception as exc:
        db.rollback()
        run.status = "failed"
        run.error_message = str(exc)[:2000]
        run.finished_at = func.now()
        db.commit()
        logger.exception("인제스천 실패 [%s]", source)
        raise
    finally:
        if owns_session:
            db.close()


# ──────────────────────────────────────────────────────────────────────────────
# Job 2: 유동인구
# ──────────────────────────────────────────────────────────────────────────────

def ingest_seoul_population(db: Session | None = None) -> IngestionRun:
    """길단위인구(VwsmTrdarFlpopQq) → population_heatmap + population_timeseries 인제스천.

    전체 분기를 한 번의 스캔으로 수신해 두 테이블에 동시 적재한다:
      - population_heatmap:    최신 분기의 시간대×요일 언피벗 (대시보드 스냅샷)
      - population_timeseries: 전체 분기의 성별·연령 marginal (딥러닝 학습용 히스토리)

    최신 분기만 받던 기존 동작과 달리, 딥러닝 시계열을 위해 전체 분기를 수신한다
    (분기 갱신은 월 1회이므로 full 스캔 비용은 허용 범위).
    seoul_commercial 선행 완료 필요 (commercial_district_id 조인).
    """
    owns_session = db is None
    db = db or SessionLocal()
    source = "seoul_population"
    run = _start_run(db, source)

    try:
        # 상권코드 → DB id 매핑을 한 번 로드
        trdar_map = load_trdar_map(db)

        # 전체 분기 수신 (히스토리 포함) — 한 번의 스캔으로 두 테이블 적재
        with SeoulClient(_SVC_POPULATION) as client:
            raws = list(client.iter_rows())
        fetched = len(raws)

        # 최신 분기 결정 (heatmap 스냅샷용) — 수신 데이터에서 직접 산출
        quarters = [r.get("STDR_YYQU_CD") for r in raws if r.get("STDR_YYQU_CD")]
        latest_quarter = max(quarters) if quarters else None
        logger.info("[%s] 수신 %d건, 최신 분기: %s", source, fetched, latest_quarter)

        heatmap_rows: list[dict] = []
        ts_rows: list[dict] = []
        failed = 0

        for raw in raws:
            # 딥러닝 시계열: 전체 분기 (성별·연령 marginal)
            ts_rows.extend(population_transformer.transform_timeseries_record(raw, trdar_map))

            # 히트맵: 최신 분기만 (시간대×요일)
            if raw.get("STDR_YYQU_CD") == latest_quarter:
                unpivoted = population_transformer.transform_record(raw, trdar_map)
                if unpivoted:
                    heatmap_rows.extend(unpivoted)
                else:
                    # 검증 실패 또는 상권코드 미매핑
                    failed += 1

        upserted_hm = population_loader.upsert_all(db, heatmap_rows)
        upserted_ts = population_timeseries_loader.upsert_all(db, ts_rows)
        upserted = upserted_hm + upserted_ts

        run.status = "success"
        run.fetched_count = fetched
        run.upserted_count = upserted
        run.failed_count = failed
        run.finished_at = func.now()
        db.commit()
        logger.info(
            "인제스천 완료 [%s]: fetched=%d heatmap=%d timeseries=%d upserted=%d failed=%d",
            source, fetched, upserted_hm, upserted_ts, upserted, failed,
        )
        return run

    except Exception as exc:
        db.rollback()
        run.status = "failed"
        run.error_message = str(exc)[:2000]
        run.finished_at = func.now()
        db.commit()
        logger.exception("인제스천 실패 [%s]", source)
        raise
    finally:
        if owns_session:
            db.close()


# ──────────────────────────────────────────────────────────────────────────────
# Job 3: 추정매출 + 점포 병합
# ──────────────────────────────────────────────────────────────────────────────

def ingest_seoul_business(db: Session | None = None) -> IngestionRun:
    """추정매출(VwsmTrdarSelngQq) + 점포(VwsmTrdarStorQq) → business_category 인제스천.

    최신 분기부터 과거로 BUSINESS_BACKFILL_QUARTERS개 분기를 **분기 단위로** 백필한다.
    각 분기마다 두 서비스를 수신해 (TRDAR_CD, SVC_INDUTY_CD)로 병합(같은 분기 내 유일)
    후 upsert하고 다음 분기로 넘어간다 → 시계열/딥러닝 학습용 히스토리 확보.
    분기 단위 처리로 메모리를 바운드한다(매출 ~460k·점포 ~1.6M 전체를 한 번에 안 올림).
    데이터 없는 분기(범위 밖)는 자동 스킵. seoul_commercial 선행 완료 필요.
    """
    owns_session = db is None
    db = db or SessionLocal()
    source = "seoul_business"
    run = _start_run(db, source)

    try:
        # 상권코드 → DB id 매핑을 한 번 로드
        trdar_map = load_trdar_map(db)

        fetched = 0
        failed = 0
        upserted = 0
        merged_total = 0
        quarters_with_data = 0

        # 매출·점포 클라이언트를 각각 한 번 열고, 최신 분기부터 과거로 백필
        with SeoulClient(_SVC_SALES) as selng_client, \
             SeoulClient(_SVC_STORE) as stor_client:
            latest = selng_client.find_latest_quarter()
            quarters = _prev_quarters(latest, BUSINESS_BACKFILL_QUARTERS)
            logger.info("[%s] 백필 분기 %d개: %s..%s",
                        source, len(quarters), quarters[0], quarters[-1])

            for q in quarters:
                selng_raws = list(selng_client.iter_rows(quarter_filter=q))
                stor_raws = list(stor_client.iter_rows(quarter_filter=q))
                if not selng_raws and not stor_raws:
                    continue  # 데이터 없는 분기 → 스킵
                quarters_with_data += 1
                fetched += len(selng_raws) + len(stor_raws)

                # 같은 분기 내 (TRDAR_CD, SVC_INDUTY_CD)는 유일 → 2-튜플 병합
                selng_index, sf = business_transformer.build_selng_index(selng_raws)
                stor_index, tf = business_transformer.build_stor_index(stor_raws)
                merged_rows, skipped = business_transformer.merge_and_transform(
                    selng_index, stor_index, trdar_map
                )
                failed += sf + tf + skipped
                merged_total += len(merged_rows)

                # 분기 단위 upsert (메모리 바운드) — 다음 분기로 넘어가며 해제
                upserted += business_loader.upsert_all(db, merged_rows)
                logger.info("[%s] 분기 %s: fetched=%d merged=%d",
                            source, q, len(selng_raws) + len(stor_raws), len(merged_rows))

        run.status = "success"
        run.fetched_count = fetched
        run.upserted_count = upserted
        run.failed_count = failed
        run.finished_at = func.now()
        db.commit()
        logger.info(
            "인제스천 완료 [%s]: 분기 %d개, fetched=%d merged=%d upserted=%d failed=%d",
            source, quarters_with_data, fetched, merged_total, upserted, failed,
        )
        return run

    except Exception as exc:
        db.rollback()
        run.status = "failed"
        run.error_message = str(exc)[:2000]
        run.finished_at = func.now()
        db.commit()
        logger.exception("인제스천 실패 [%s]", source)
        raise
    finally:
        if owns_session:
            db.close()


# ──────────────────────────────────────────────────────────────────────────────
# Job 4: 외국인/내국인 생활인구 (3개 서비스 통합)
# ──────────────────────────────────────────────────────────────────────────────

def _find_available_dates(
    service: str,
    n: int = 14,
    max_candidates: int = 25,
) -> list[str]:
    """기준일 필터로 생활인구 서비스의 데이터 유효 날짜 목록을 탐색한다.

    오늘-2일부터 역순으로 candidate를 1건 조회해 데이터가 있는 날짜를 최대 n개 수집한다.
    최대 max_candidates일을 시도 후 중단(약 2개월 롤링 윈도우 가정).
    1건 요청으로 probe하므로 API 부하가 낮다.

    Args:
        service: 탐색에 사용할 서비스명 (어느 서비스든 날짜 집합이 동일).
        n: 목표 날짜 수 (기본 14일).
        max_candidates: 최대 탐색 일수 (기본 25일).

    Returns:
        데이터가 있는 날짜 YYYYMMDD 문자열 목록 (최신→오래된 순).
    """
    today = date.today()
    available: list[str] = []

    with SeoulClient(service) as client:
        for offset in range(2, 2 + max_candidates):
            if len(available) >= n:
                break
            candidate = (today - timedelta(days=offset)).strftime("%Y%m%d")
            try:
                if client.check_date(candidate):
                    available.append(candidate)
                    logger.debug("생활인구 유효 기준일 확인: %s", candidate)
                else:
                    logger.debug("생활인구 데이터 없음: %s", candidate)
            except RuntimeError as exc:
                # 네트워크 오류는 경고 후 계속 (다음 날짜 시도)
                logger.warning("기준일 %s 조회 실패, 스킵: %s", candidate, exc)

    logger.info(
        "생활인구 유효 기준일 탐색 완료: %d일 확보 (서비스=%s, 탐색범위=오늘-%d일~오늘-2일)",
        len(available), service, 2 + max_candidates - 1,
    )
    return available


def _fetch_service_rows(service: str, dates: list[str]) -> tuple[list[dict], int]:
    """서비스의 여러 기준일에 대해 full 페이지네이션 수신. (raw rows, 페이지 호출 수)."""
    all_rows: list[dict] = []
    call_count = 0
    with SeoulClient(service) as client:
        for date_str in dates:
            for row in client.iter_rows(quarter_filter=date_str):
                all_rows.append(row)
            call_count += 1  # 날짜 단위로 집계 (실제 페이지 수는 iter_rows 내부에서 로깅)
    logger.info(
        "생활인구 서비스 수신 완료: service=%s dates=%d rows=%d",
        service, len(dates), len(all_rows),
    )
    return all_rows, call_count


def ingest_seoul_foreign(db: Session | None = None) -> IngestionRun:
    """외국인/내국인 생활인구(3개 SPOP_* 서비스) → foreign_population 인제스천.

    최근 14일치 기준일 데이터를 탐색(오늘-2일부터 역순)한 후 각 서비스를 날짜별로
    full 페이지네이션 수신한다. 세 서비스를 (행정동, 날짜, 시간) 기준으로 정렬해
    foreigner/total을 산출, 시간대×요일 슬롯 평균 후 상권(adstrd_code)으로 팬아웃한다.

    seoul_commercial 선행 완료 필요 (commercial_district.adstrd_code 조인).

    API 호출 수 (근사):
      probe:  최대 25회 (날짜 탐색, 1건씩)
      fetch:  3서비스 × 14일 × ~11회/일 ≈ 462회
      합계:   ~487회
    """
    owns_session = db is None
    db = db or SessionLocal()
    source = "seoul_foreign"
    run = _start_run(db, source)

    try:
        # 행정동코드 → 상권 ID 리스트 매핑 로드
        adstrd_map = load_adstrd_map(db)

        # 기준일 탐색 (외국인 장기체류 서비스 기준 — 세 서비스 날짜 집합 동일)
        available_dates = _find_available_dates(_SVC_FP_LONG)
        if not available_dates:
            raise RuntimeError(
                "생활인구 유효 기준일을 찾지 못했습니다. "
                "데이터 롤링 윈도우를 벗어났거나 API 접속 불가."
            )
        logger.info("[%s] 수신 기준일 %d개: %s..%s", source,
                    len(available_dates), available_dates[-1], available_dates[0])

        # 세 서비스 full 수신
        long_rows,  _ = _fetch_service_rows(_SVC_FP_LONG,  available_dates)
        temp_rows,  _ = _fetch_service_rows(_SVC_FP_TEMP,  available_dates)
        local_rows, _ = _fetch_service_rows(_SVC_FP_LOCAL, available_dates)
        fetched = len(long_rows) + len(temp_rows) + len(local_rows)

        # 서비스별 인덱스 빌드 (Pydantic 검증 포함)
        long_index,  long_failed  = foreign_transformer.build_service_index(long_rows,  "long")
        temp_index,  temp_failed  = foreign_transformer.build_service_index(temp_rows,  "temp")
        local_index, local_failed = foreign_transformer.build_service_index(local_rows, "local")
        failed = long_failed + temp_failed + local_failed

        # 정렬·집계·팬아웃
        upsert_rows, skipped = foreign_transformer.aggregate_and_fanout(
            long_index, temp_index, local_index, adstrd_map
        )
        failed += skipped

        # DB 적재
        upserted = foreign_loader.upsert_all(db, upsert_rows)

        run.status = "success"
        run.fetched_count = fetched
        run.upserted_count = upserted
        run.failed_count = failed
        run.finished_at = func.now()
        db.commit()
        logger.info(
            "인제스천 완료 [%s]: dates=%d fetched=%d upserted=%d failed=%d",
            source, len(available_dates), fetched, upserted, failed,
        )
        return run

    except Exception as exc:
        db.rollback()
        run.status = "failed"
        run.error_message = str(exc)[:2000]
        run.finished_at = func.now()
        db.commit()
        logger.exception("인제스천 실패 [%s]", source)
        raise
    finally:
        if owns_session:
            db.close()


# ──────────────────────────────────────────────────────────────────────────────
# Job 5: 상가 임대료 (한국부동산원 R-ONE)
# ──────────────────────────────────────────────────────────────────────────────

def ingest_seoul_rent(db: Session | None = None) -> IngestionRun:
    """R-ONE 상가임대료(SttsApiTblData) → rent_stats 인제스천.

    소규모·중대형·집합 3개 STATBL_ID를 순차 조회해 최신 분기 서울 말단 상권만
    필터하고, commercial_district.district_name 이름 매칭 후 upsert한다.
    매칭된 상권명은 여러 서울 상권에 팬아웃된다.

    seoul_commercial 선행 완료 필요 (commercial_district.district_name 조인).
    인증키는 settings.REB_API_KEY에서 읽는다 (환경변수 REB_API_KEY).
    """
    owns_session = db is None
    db = db or SessionLocal()
    source = "seoul_rent"
    run = _start_run(db, source)

    try:
        # 상권명 → DB id 매핑 (이름 매칭용)
        name_to_ids = load_district_name_map(db)
        # external_code → DB id 매핑 (MANUAL_MAP external_code 변환용)
        code_to_id = load_trdar_map(db)

        all_rows: list[dict] = []
        failed = 0
        fetched = 0
        min_wrttime: str | None = None

        # 3개 상가유형 STATBL_ID를 순차 처리
        for statbl_id, floor_type in STATBL_FLOOR_TYPE.items():
            with RebClient(statbl_id) as client:
                # 첫 번째 테이블에서 최신 분기를 탐색 → 백필 시작 분기 산출, 나머지 테이블에 재사용
                if min_wrttime is None:
                    latest_wrttime = client.find_latest_wrttime()
                    min_wrttime = _wrttime_minus_quarters(latest_wrttime, RENT_BACKFILL_QUARTERS - 1)
                    logger.info("[%s] 최신 %s → 백필 시작 %s (%d분기)",
                                source, latest_wrttime, min_wrttime, RENT_BACKFILL_QUARTERS)

                for raw in client.iter_rows():
                    fetched += 1
                    transformed = rent_transformer.transform_record(
                        raw, floor_type, min_wrttime, name_to_ids, code_to_id
                    )
                    if transformed:
                        all_rows.extend(transformed)
                    # 변환 결과 없음(미통과/미매칭)은 failed로 집계하지 않음 —
                    # 타 지역 상권·집계행 등 정상 스킵이 대부분임

        upserted = rent_loader.upsert_all(db, all_rows)

        run.status = "success"
        run.fetched_count = fetched
        run.upserted_count = upserted
        run.failed_count = failed
        run.finished_at = func.now()
        db.commit()
        logger.info(
            "인제스천 완료 [%s]: fetched=%d transformed=%d upserted=%d failed=%d",
            source, fetched, len(all_rows), upserted, failed,
        )
        return run

    except Exception as exc:
        db.rollback()
        run.status = "failed"
        run.error_message = str(exc)[:2000]
        run.finished_at = func.now()
        db.commit()
        logger.exception("인제스천 실패 [%s]", source)
        raise
    finally:
        if owns_session:
            db.close()


# ──────────────────────────────────────────────────────────────────────────────
# Job 6: 네이버 데이터랩 buzz_stats
# ──────────────────────────────────────────────────────────────────────────────

def ingest_buzz(db: Session | None = None) -> IngestionRun:
    """네이버 데이터랩 검색어 트렌드 → buzz_stats 적재 (3개 상권 1회 호출)."""
    owns_session = db is None
    db = db or SessionLocal()
    source = "buzz"
    run: IngestionRun | None = None

    try:
        run = _start_run(db, source)
        response = fetch_buzz()
        rows = transform_datalab_response(response)
        upserted = upsert_buzz(db, rows)

        # transform이 빈 그룹을 스킵하므로 진단용 fetched_count는 raw results 기준으로 기록한다.
        fetched = len(response.get("results", []))

        run.status = "success"
        run.fetched_count = fetched
        run.upserted_count = upserted
        run.failed_count = 0
        run.finished_at = func.now()
        db.commit()
        logger.info(
            "인제스천 완료 [%s]: fetched=%d upserted=%d",
            source, fetched, upserted,
        )
        return run

    except Exception as exc:
        db.rollback()
        # run이 None이면 _start_run 자체가 실패한 것 → 업데이트할 레코드가 없다.
        if run is not None:
            fetched = len(rows) if "rows" in locals() else 0
            run.status = "failed"
            run.error_message = str(exc)[:2000]
            run.fetched_count = fetched
            run.upserted_count = 0
            run.failed_count = fetched
            run.finished_at = func.now()
            db.commit()
        logger.exception("인제스천 실패 [%s]", source)
        raise
    finally:
        if owns_session:
            db.close()


# ──────────────────────────────────────────────────────────────────────────────
# 디스패치 테이블
# ──────────────────────────────────────────────────────────────────────────────

# 소스명 → job 함수 매핑. CLI/admin에서 타겟 이름으로 디스패치.
# "all" 실행 시 dict 삽입 순서대로 실행 → commercial 먼저, 자식 job 나중.
JOBS = {
    "seoul_commercial": ingest_seoul_commercial,
    "seoul_population": ingest_seoul_population,
    "seoul_business":   ingest_seoul_business,
    "seoul_foreign":    ingest_seoul_foreign,   # commercial_district.adstrd_code 선행 필요
    "seoul_rent":       ingest_seoul_rent,      # commercial_district.district_name 이름매칭 선행 필요
    "buzz":             ingest_buzz,
}


def run_targets(targets: list[str]) -> dict[str, str]:
    """타겟 리스트를 순차 실행. 결과 요약을 반환.

    한 소스의 실패가 다른 소스를 막지 않는다.
    단, "all"에서 순서를 보장하므로 seoul_commercial이 먼저 실행된다.
    """
    selected = list(JOBS) if targets == ["all"] else targets
    results: dict[str, str] = {}
    for name in selected:
        job = JOBS.get(name)
        if job is None:
            results[name] = "unknown_target"
            continue
        try:
            run = job()
            results[name] = f"{run.status}(upserted={run.upserted_count})"
        except Exception as exc:  # 한 소스 실패가 다른 소스를 막지 않게
            results[name] = f"failed({exc})"
    return results
