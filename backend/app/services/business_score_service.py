from sqlalchemy import text
from sqlalchemy.orm import Session

# 규칙 기반 district_score 계산 (ML 학습 없이, 이미 적재된 지표로 산정):
#   score = 0.4 * survival_rate + 0.2 * open_rate + 0.4 * sales_percentile
# - survival_rate/open_rate: 이미 0~100 스케일의 비율이라 그대로 사용
# - sales_percentile: total_sales는 업종마다 절대값 편차가 커서 그대로 비교 불가.
#   같은 (상권, 분기) 안에서의 백분위(0~100)로 정규화해 상대적 매출 성과로 반영
_COMPUTE_SCORES_SQL = text(
    """
    WITH scored AS (
        SELECT
            id,
            0.4 * survival_rate
            + 0.2 * open_rate
            + 0.4 * (COALESCE(PERCENT_RANK() OVER (
                PARTITION BY commercial_district_id, year_quarter
                ORDER BY total_sales
            ), 0) * 100) AS score
        FROM business_category
        WHERE is_deleted = false
          AND survival_rate IS NOT NULL
          AND open_rate IS NOT NULL
          AND (:district_id IS NULL OR commercial_district_id = :district_id)
    )
    UPDATE business_category bc
    SET district_score = scored.score, updated_at = now()
    FROM scored
    WHERE bc.id = scored.id
    """
)


class BusinessScoreService:
    @staticmethod
    def compute_scores(db: Session, district_id: int | None = None) -> int:
        result = db.execute(_COMPUTE_SCORES_SQL, {"district_id": district_id})
        db.commit()
        return result.rowcount
