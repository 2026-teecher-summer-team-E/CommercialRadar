"""business_category age_sales/gender_sales 컬럼 추가

Revision ID: 5e78cadd972b
Revises: 5439fcffcfa6
Create Date: 2026-07-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5e78cadd972b'
down_revision: Union[str, None] = '5439fcffcfa6'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column('business_category', sa.Column('age_sales', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('business_category', sa.Column('gender_sales', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('business_category', 'gender_sales')
    op.drop_column('business_category', 'age_sales')
