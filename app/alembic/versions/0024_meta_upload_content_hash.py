"""deduplicate meta media uploads by content hash

Revision ID: 0024_meta_upload_content_hash
Revises: 0023_meta_upload_stored_filename
Create Date: 2026-05-31
"""
from __future__ import annotations

import hashlib
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "0024_meta_upload_content_hash"
down_revision: Union[str, None] = "0023_meta_upload_stored_filename"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def upgrade() -> None:
    op.add_column("meta_media_uploads", sa.Column("content_hash", sa.String(length=64), nullable=True))

    connection = op.get_bind()
    seen: set[str] = set()
    rows = connection.execute(
        sa.text("SELECT id, data FROM meta_media_uploads ORDER BY created_at ASC, id ASC")
    )
    for row in rows:
        data = bytes(row.data or b"")
        if not data:
            continue
        content_hash = hashlib.sha256(data).hexdigest()
        if content_hash in seen:
            connection.execute(sa.text("DELETE FROM meta_media_uploads WHERE id = :id"), {"id": row.id})
            continue
        seen.add(content_hash)
        connection.execute(
            sa.text("UPDATE meta_media_uploads SET content_hash = :content_hash WHERE id = :id"),
            {"content_hash": content_hash, "id": row.id},
        )

    op.create_index(
        "ux_meta_media_uploads_content_hash",
        "meta_media_uploads",
        ["content_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ux_meta_media_uploads_content_hash", table_name="meta_media_uploads")
    op.drop_column("meta_media_uploads", "content_hash")
