"""business_category (year_quarter, commercial_district_id) 인덱스 추가

Revision ID: e2a7c5f18b3d
Revises: 77f166a7d804
Create Date: 2026-07-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e2a7c5f18b3d'
down_revision: Union[str, None] = '77f166a7d804'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # 기존 UNIQUE(commercial_district_id, category_name, year_quarter)는
    # district_id가 있는 조회는 커버하지만, year_quarter만으로 거는 조회
    # (예: /buzz-gap의 분기별 전체 상권 매출 집계)는 인덱스를 못 타고
    # 풀 스캔이 발생한다(EXPLAIN ANALYZE로 확인, 1528872행 기준 ~225ms).
    # year_quarter를 선두 컬럼으로 둬서 이 패턴을 인덱스 스캔으로 바꾼다.
    op.create_index(
        "ix_business_category_yq_cd",
        "business_category",
        ["year_quarter", "commercial_district_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_business_category_yq_cd", table_name="business_category")
