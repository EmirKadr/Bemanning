"""add meta shipment observations

Revision ID: 0025_meta_shipment_observations
Revises: 0024_meta_upload_content_hash
Create Date: 2026-05-31
"""
from __future__ import annotations

import hashlib
import json
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "0025_meta_shipment_observations"
down_revision: Union[str, None] = "0024_meta_upload_content_hash"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def _record_hash(video_hash: str) -> str:
    payload = {
        "version": "v1",
        "video_hash": str(video_hash or "").strip().lower(),
        "label_image_hash": "",
        "order_number": "",
        "username": "",
        "customer_name": "",
        "pallet_id": "",
        "deviations": [],
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def upgrade() -> None:
    op.create_table(
        "meta_shipment_observations",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("media_upload_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("label_image_upload_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("video_hash", sa.String(length=64), nullable=False),
        sa.Column("label_image_hash", sa.String(length=64), nullable=True),
        sa.Column("record_hash", sa.String(length=64), nullable=False),
        sa.Column("order_number", sa.String(length=80), nullable=True),
        sa.Column("username", sa.String(length=120), nullable=True),
        sa.Column("customer_name", sa.String(length=200), nullable=True),
        sa.Column("pallet_id", sa.String(length=120), nullable=True),
        sa.Column("deviations", sa.JSON(), nullable=True),
        sa.Column("uncertainty_notes", sa.Text(), nullable=True),
        sa.Column("label_frame_time_seconds", sa.String(length=40), nullable=True),
        sa.Column("analysis_status", sa.String(length=40), server_default="pending_analysis", nullable=False),
        sa.Column("analysis_error", sa.Text(), nullable=True),
        sa.Column("llm_model", sa.String(length=120), nullable=True),
        sa.Column("llm_raw_response", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["media_upload_id"], ["meta_media_uploads.id"]),
        sa.ForeignKeyConstraint(["label_image_upload_id"], ["meta_media_uploads.id"]),
        sa.UniqueConstraint("media_upload_id", name="uq_meta_shipment_observations_media_upload"),
    )
    op.create_index("ix_meta_shipment_observations_status", "meta_shipment_observations", ["analysis_status"])
    op.create_index("ix_meta_shipment_observations_video_hash", "meta_shipment_observations", ["video_hash"])
    op.create_index(
        "ux_meta_shipment_observations_record_hash",
        "meta_shipment_observations",
        ["record_hash"],
        unique=True,
    )

    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, content_hash
            FROM meta_media_uploads
            WHERE media_type = 'video' AND content_hash IS NOT NULL
            ORDER BY created_at ASC, id ASC
            """
        )
    )
    for row in rows:
        video_hash = str(row.content_hash or "")
        connection.execute(
            sa.text(
                """
                INSERT INTO meta_shipment_observations
                    (media_upload_id, video_hash, record_hash, analysis_status)
                VALUES
                    (:media_upload_id, :video_hash, :record_hash, 'needs_configuration')
                """
            ),
            {
                "media_upload_id": row.id,
                "video_hash": video_hash,
                "record_hash": _record_hash(video_hash),
            },
        )


def downgrade() -> None:
    op.drop_index("ux_meta_shipment_observations_record_hash", table_name="meta_shipment_observations")
    op.drop_index("ix_meta_shipment_observations_video_hash", table_name="meta_shipment_observations")
    op.drop_index("ix_meta_shipment_observations_status", table_name="meta_shipment_observations")
    op.drop_table("meta_shipment_observations")
