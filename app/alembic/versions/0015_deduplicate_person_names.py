"""deduplicate person names

Revision ID: 0015_deduplicate_person_names
Revises: 0014_keep_activities_active
Create Date: 2026-05-20
"""
from typing import Union

from alembic import op


revision: str = "0015_deduplicate_person_names"
down_revision: Union[str, None] = "0014_keep_activities_active"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    duplicate_ids = """
        SELECT id
        FROM (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY lower(trim(name))
                    ORDER BY id
                ) AS duplicate_number
            FROM persons
        ) ranked_persons
        WHERE duplicate_number > 1
    """
    op.execute(f"DELETE FROM schedule_cells WHERE person_id IN ({duplicate_ids})")
    op.execute(f"DELETE FROM person_schedule_templates WHERE person_id IN ({duplicate_ids})")
    op.execute(f"DELETE FROM persons WHERE id IN ({duplicate_ids})")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_persons_name_normalized ON persons (lower(trim(name)))")


def downgrade() -> None:
    op.drop_index("uq_persons_name_normalized", table_name="persons")
