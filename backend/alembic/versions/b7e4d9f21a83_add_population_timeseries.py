"""add population_timeseries for ML population forecast

Revision ID: b7e4d9f21a83
Revises: 79332016126d
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e4d9f21a83'
down_revision: Union[str, None] = '79332016126d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'population_timeseries',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('commercial_district_id', sa.BigInteger(), nullable=False),
        sa.Column('year_quarter', sa.String(length=7), nullable=False),
        sa.Column(
            'dimension',
            sa.Enum('total', 'gender', 'age', name='pop_ts_dimension_enum'),
            nullable=False,
        ),
        sa.Column('slot', sa.String(length=10), nullable=False),
        sa.Column('avg_population', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['commercial_district_id'], ['commercial_district.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'commercial_district_id', 'year_quarter', 'dimension', 'slot',
            name='uq_pop_ts_cd_yq_dim_slot',
        ),
    )


def downgrade() -> None:
    op.drop_table('population_timeseries')
    sa.Enum(name='pop_ts_dimension_enum').drop(op.get_bind())
