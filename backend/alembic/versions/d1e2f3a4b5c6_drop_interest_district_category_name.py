"""drop category_name from interest_district (unused, redundant with memo)

Revision ID: d1e2f3a4b5c6
Revises: c8f1a2b34d90
Create Date: 2026-07-08

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c8f1a2b34d90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('interest_district', 'category_name')


def downgrade() -> None:
    op.add_column(
        'interest_district',
        sa.Column('category_name', sa.String(length=100), nullable=True),
    )
