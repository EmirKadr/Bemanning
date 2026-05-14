"""support imported users without initial password

Revision ID: 0009_user_import_first_login
Revises: 0008_schedule_lookup_index
Create Date: 2026-05-14
"""

from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "0009_user_import_first_login"
down_revision: Union[str, None] = "0008_schedule_lookup_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(255),
        nullable=True,
    )


def downgrade() -> None:
    op.execute("UPDATE users SET password_hash = '' WHERE password_hash IS NULL")
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(255),
        nullable=False,
    )
    op.drop_column("users", "must_change_password")
