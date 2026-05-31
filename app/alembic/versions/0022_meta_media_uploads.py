"""add public meta media uploads

Revision ID: 0022_meta_media_uploads
Revises: 0021_user_wait_metrics
Create Date: 2026-05-31
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "0022_meta_media_uploads"
down_revision: Union[str, None] = "0021_user_wait_metrics"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    op.create_table(
        "meta_media_uploads",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("media_type", sa.String(length=20), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending_analysis"),
        sa.Column("analysis", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="public_upload"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
    )
    op.create_index("ix_meta_media_uploads_batch_id", "meta_media_uploads", ["batch_id"])
    op.create_index("ix_meta_media_uploads_created_at", "meta_media_uploads", ["created_at"])
    op.create_index("ix_meta_media_uploads_status", "meta_media_uploads", ["status"])


def downgrade() -> None:
    op.drop_index("ix_meta_media_uploads_status", table_name="meta_media_uploads")
    op.drop_index("ix_meta_media_uploads_created_at", table_name="meta_media_uploads")
    op.drop_index("ix_meta_media_uploads_batch_id", table_name="meta_media_uploads")
    op.drop_table("meta_media_uploads")
