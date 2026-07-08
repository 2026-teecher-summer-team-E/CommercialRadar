"""add category_name to ml_predictions and widen unique key

Revision ID: d4a9c1e07b52
Revises: c8f1a2b34d90
Create Date: 2026-07-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd4a9c1e07b52'
down_revision: Union[str, None] = 'c8f1a2b34d90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_UQ = 'uq_ml_pred_cd_type_quarter'
NEW_UQ = 'uq_ml_pred_cd_type_quarter_category'


def upgrade() -> None:
    op.add_column(
        'ml_predictions',
        sa.Column('category_name', sa.String(length=50), nullable=False,
                  server_default='__ALL__'),
    )
    op.drop_constraint(OLD_UQ, 'ml_predictions', type_='unique')
    op.create_unique_constraint(
        NEW_UQ, 'ml_predictions',
        ['commercial_district_id', 'prediction_type', 'target_quarter', 'category_name'],
    )


def downgrade() -> None:
    # 주의: 업종별(category_name) 행이 이미 적재된 뒤에는 downgrade가 실패한다.
    # 같은 (상권, type, 분기)에 여러 업종 행이 있으면 3-컬럼 유니크 재생성이
    # 중복으로 막힌다. 롤백하려면 먼저 업종별 행을 합쳐(또는 삭제)야 한다.
    op.drop_constraint(NEW_UQ, 'ml_predictions', type_='unique')
    op.create_unique_constraint(
        OLD_UQ, 'ml_predictions',
        ['commercial_district_id', 'prediction_type', 'target_quarter'],
    )
    op.drop_column('ml_predictions', 'category_name')
