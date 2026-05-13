"""add schedule lookup index for person/hour reads

Revision ID: 0008_schedule_lookup_index
Revises: 0007_schedule_empty_override
Create Date: 2026-05-13
"""

from typing import Union

from alembic import op


revision: str = "0008_schedule_lookup_index"
down_revision: Union[str, None] = "0007_schedule_empty_override"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_schedule_cells_ywd_person_hour",
        "schedule_cells",
        ["year", "week", "weekday", "person_id", "hour"],
    )


def downgrade() -> None:
    op.drop_index("ix_schedule_cells_ywd_person_hour", table_name="schedule_cells")
