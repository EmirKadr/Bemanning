"""add minute ranges to schedule cells

Revision ID: 0005_half_hour_schedule_cells
Revises: 0004_person_home_activity
Create Date: 2026-05-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_half_hour_schedule_cells"
down_revision: Union[str, None] = "0004_person_home_activity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "schedule_cells",
        sa.Column("minute_start", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "schedule_cells",
        sa.Column("minute_end", sa.SmallInteger(), nullable=False, server_default="60"),
    )
    op.alter_column("schedule_cells", "minute_start", server_default=None)
    op.alter_column("schedule_cells", "minute_end", server_default=None)
    op.drop_constraint("uq_schedule_cell", "schedule_cells", type_="unique")
    op.create_unique_constraint(
        "uq_schedule_cell",
        "schedule_cells",
        ["year", "week", "weekday", "hour", "person_id", "minute_start"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_schedule_cell", "schedule_cells", type_="unique")
    op.create_unique_constraint(
        "uq_schedule_cell",
        "schedule_cells",
        ["year", "week", "weekday", "hour", "person_id"],
    )
    op.drop_column("schedule_cells", "minute_end")
    op.drop_column("schedule_cells", "minute_start")
