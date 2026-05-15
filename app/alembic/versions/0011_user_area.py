"""add user area

Revision ID: 0011_user_area
Revises: 0010_app_settings
Create Date: 2026-05-15
"""

from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "0011_user_area"
down_revision: Union[str, None] = "0010_app_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("area_id", sa.Integer(), sa.ForeignKey("areas.id"), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "area_id")
