"""add unique constraint on ml_predictions for idempotent upsert

Revision ID: c8f1a2b34d90
Revises: b7e4d9f21a83
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c8f1a2b34d90'
down_revision: Union[str, None] = 'b7e4d9f21a83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_ml_pred_cd_type_quarter',
        'ml_predictions',
        ['commercial_district_id', 'prediction_type', 'target_quarter'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_ml_pred_cd_type_quarter', 'ml_predictions', type_='unique')
