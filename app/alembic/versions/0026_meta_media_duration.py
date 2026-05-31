"""add meta media duration

Revision ID: 0026_meta_media_duration
Revises: 0025_meta_shipment_observations
Create Date: 2026-05-31
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "0026_meta_media_duration"
down_revision: Union[str, None] = "0025_meta_shipment_observations"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    op.add_column("meta_media_uploads", sa.Column("duration_seconds", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("meta_media_uploads", "duration_seconds")
