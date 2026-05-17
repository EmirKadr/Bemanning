"""add fixed schedule flag to persons

Revision ID: 0012_person_fixed_schedule_flag
Revises: 0011_user_area
Create Date: 2026-05-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0012_person_fixed_schedule_flag"
down_revision: Union[str, None] = "0011_user_area"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "persons",
        sa.Column("has_fixed_schedule", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column("persons", "has_fixed_schedule", server_default=None)


def downgrade() -> None:
    op.drop_column("persons", "has_fixed_schedule")
