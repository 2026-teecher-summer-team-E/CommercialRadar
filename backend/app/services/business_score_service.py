from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.database import SessionLocal
from app.models.ingestion_run import IngestionRun

# 규칙 기반 district_score 계산 (ML 학습 없이, 이미 적재된 지표로 산정):
#   score = 0.3 * survival_rate + 0.15 * open_rate
#         + 0.3 * sales_percentile + 0.25 * population_percentile
# - survival_rate/open_rate: 이미 0~100 스케일의 비율이라 그대로 사용
# - sales_percentile: total_sales는 업종마다 절대값 편차가 커서 그대로 비교 불가.
#   같은 (상권, 분기) 안에서의 백분위(0~100)로 정규화해 상대적 매출 성과로 반영
# - population_percentile: population_timeseries는 업종별이 아니라 상권+분기 단위라
#   같은 상권 내 업종 간 순위엔 영향이 없고, 같은 분기의 다른 상권들과 비교한
#   유동인구 순위(0~100)로 반영 — 유동인구가 많은 상권의 업종일수록 가점
_COMPUTE_SCORES_SQL = text(
    """
    WITH district_population AS (
        SELECT
            commercial_district_id,
            year_quarter,
            PERCENT_RANK() OVER (
                PARTITION BY year_quarter
                ORDER BY avg_population
            ) AS population_percentile
        FROM population_timeseries
        WHERE dimension = 'total' AND slot = 'total' AND is_deleted = false
    ),
    scored AS (
        SELECT
            bc.id,
            0.3 * bc.survival_rate
            + 0.15 * bc.open_rate
            + 0.3 * (COALESCE(PERCENT_RANK() OVER (
                PARTITION BY bc.commercial_district_id, bc.year_quarter
                ORDER BY bc.total_sales
            ), 0) * 100)
            + 0.25 * (COALESCE(dp.population_percentile, 0) * 100) AS score
        FROM business_category bc
        LEFT JOIN district_population dp
            ON dp.commercial_district_id = bc.commercial_district_id
           AND dp.year_quarter = bc.year_quarter
        WHERE bc.is_deleted = false
          AND bc.survival_rate IS NOT NULL
          AND bc.open_rate IS NOT NULL
          AND (:district_id IS NULL OR bc.commercial_district_id = :district_id)
    )
    UPDATE business_category bc
    SET district_score = scored.score, updated_at = now()
    FROM scored
    WHERE bc.id = scored.id
    """
)


class BusinessScoreService:
    SOURCE = "category_scores"

    @staticmethod
    def compute_scores(db: Session | None = None, district_id: int | None = None) -> IngestionRun:
        """district_score를 규칙 기반으로 재계산한다.

        db를 주입하지 않으면 자체 세션을 만든다 (BackgroundTasks에서 이렇게 호출).
        인제스천 잡과 동일하게 ingestion_run 테이블(source='category_scores')에
        실행 이력을 남겨, 오래 걸리는 전체 재계산의 진행 상태를 나중에 조회할 수 있게 한다.
        """
        owns_session = db is None
        db = db or SessionLocal()
        run = IngestionRun(source=BusinessScoreService.SOURCE, status="running")
        db.add(run)
        db.commit()
        db.refresh(run)

        try:
            result = db.execute(_COMPUTE_SCORES_SQL, {"district_id": district_id})
            run.status = "success"
            run.upserted_count = result.rowcount
            run.finished_at = func.now()
            db.commit()
            return run
        except Exception as exc:
            db.rollback()
            run.status = "failed"
            run.error_message = str(exc)[:2000]
            run.finished_at = func.now()
            db.commit()
            raise
        finally:
            if owns_session:
                db.close()
