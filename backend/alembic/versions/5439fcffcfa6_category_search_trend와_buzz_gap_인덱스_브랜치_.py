"""category_search_trend와 buzz-gap 인덱스 브랜치 병합

Revision ID: 5439fcffcfa6
Revises: 068a54953a4b, b2f4a6c8e012
Create Date: 2026-07-14 15:50:52.404814

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = '5439fcffcfa6'
down_revision: Union[str, None] = ('068a54953a4b', 'b2f4a6c8e012')
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
