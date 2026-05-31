"""add stored filename to meta media uploads

Revision ID: 0023_meta_upload_stored_filename
Revises: 0022_meta_media_uploads
Create Date: 2026-05-31
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "0023_meta_upload_stored_filename"
down_revision: Union[str, None] = "0022_meta_media_uploads"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    op.add_column(
        "meta_media_uploads",
        sa.Column("stored_filename", sa.String(length=255), nullable=False, server_default="meta_upload"),
    )
    op.alter_column("meta_media_uploads", "stored_filename", server_default=None)


def downgrade() -> None:
    op.drop_column("meta_media_uploads", "stored_filename")
