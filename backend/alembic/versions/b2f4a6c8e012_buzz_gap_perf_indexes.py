"""buzz-gap 성능: 분기 필터 인덱스 추가 (business_category, population_timeseries)

buzz-gap은 최신 분기의 전체 상권 매출 합·유동인구를 조회해 백분위를 계산한다.
기존 유니크 인덱스는 year_quarter/dimension이 leftmost가 아니라 WHERE 분기 필터에
쓰이지 못해 각각 풀스캔(business_category ~150만행)이 발생, p95를 끌어올렸다.
분기 필터 전용 인덱스를 추가해 집계를 인덱스 스캔으로 전환한다.

Revision ID: b2f4a6c8e012
Revises: 77f166a7d804
Create Date: 2026-07-14
"""

from alembic import op

revision = "b2f4a6c8e012"
down_revision = "77f166a7d804"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 분기별 상권 매출 합 (GROUP BY commercial_district_id) 집계용
    op.create_index(
        "ix_biz_cat_yq_cd",
        "business_category",
        ["year_quarter", "commercial_district_id"],
    )
    # dimension='total' + year_quarter 필터 조회용
    op.create_index(
        "ix_pop_ts_dim_yq",
        "population_timeseries",
        ["dimension", "year_quarter"],
    )


def downgrade() -> None:
    op.drop_index("ix_pop_ts_dim_yq", table_name="population_timeseries")
    op.drop_index("ix_biz_cat_yq_cd", table_name="business_category")
