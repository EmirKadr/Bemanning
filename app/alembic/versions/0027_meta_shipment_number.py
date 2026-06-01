"""add meta shipment number

Revision ID: 0027_meta_shipment_number
Revises: 0026_meta_media_duration
Create Date: 2026-06-01
"""
from __future__ import annotations

import hashlib
import json
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "0027_meta_shipment_number"
down_revision: Union[str, None] = "0026_meta_media_duration"
branch_labels: Union[str, tuple[str, ...], None] = None
depends_on: Union[str, tuple[str, ...], None] = None


def _deviations(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value
        return _deviations(parsed) if parsed is not value else ([value.strip()] if value.strip() else [])
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = item.get("description") or item.get("text") or item.get("avvikelse") or item.get("deviation")
            else:
                text = item
            cleaned = str(text or "").strip()
            if cleaned:
                result.append(cleaned[:500])
        return result
    return [str(value).strip()[:500]] if str(value).strip() else []


def _record_hash(row) -> str:
    payload = {
        "version": "v1",
        "video_hash": str(row.video_hash or "").strip().lower(),
        "label_image_hash": str(row.label_image_hash or "").strip().lower(),
        "order_number": str(row.order_number or "").strip().casefold(),
        "shipment_number": str(row.shipment_number or "").strip().casefold(),
        "username": str(row.username or "").strip().casefold(),
        "customer_name": str(row.customer_name or "").strip().casefold(),
        "pallet_id": str(row.pallet_id or "").strip().casefold(),
        "deviations": sorted(item.casefold() for item in _deviations(row.deviations)),
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def upgrade() -> None:
    op.add_column("meta_shipment_observations", sa.Column("shipment_number", sa.String(length=120), nullable=True))
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, video_hash, label_image_hash, order_number, shipment_number,
                   username, customer_name, pallet_id, deviations
            FROM meta_shipment_observations
            ORDER BY id ASC
            """
        )
    )
    for row in rows:
        connection.execute(
            sa.text("UPDATE meta_shipment_observations SET record_hash = :record_hash WHERE id = :id"),
            {"id": row.id, "record_hash": _record_hash(row)},
        )


def downgrade() -> None:
    op.drop_column("meta_shipment_observations", "shipment_number")
