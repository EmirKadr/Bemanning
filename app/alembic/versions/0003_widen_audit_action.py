"""widen audit_log.action to VARCHAR(50)

Revision ID: 0003_widen_audit_action
Revises: 0002_person_schedule_template
Create Date: 2026-05-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_widen_audit_action"
down_revision: Union[str, None] = "0002_person_schedule_template"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "audit_log", "action",
        existing_type=sa.String(10),
        type_=sa.String(50),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "audit_log", "action",
        existing_type=sa.String(50),
        type_=sa.String(10),
        existing_nullable=False,
    )
