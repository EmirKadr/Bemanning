"""add app settings

Revision ID: 0010_app_settings
Revises: 0009_user_import_first_login
Create Date: 2026-05-14
"""

from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "0010_app_settings"
down_revision: Union[str, None] = "0009_user_import_first_login"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id")),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
