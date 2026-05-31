from __future__ import annotations

from pathlib import Path
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models import MetaMediaUpload


router = APIRouter(prefix="/api/meta", tags=["meta"])

MAX_META_UPLOAD_FILES = 25
MAX_META_UPLOAD_FILE_BYTES = 256 * 1024 * 1024
MAX_META_UPLOAD_BATCH_BYTES = 1024 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 1024 * 1024

IMAGE_EXTENSIONS = {
    ".avif",
    ".bmp",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
VIDEO_EXTENSIONS = {
    ".3g2",
    ".3gp",
    ".avi",
    ".m4v",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".webm",
}


def _clean_filename(filename: str | None) -> str:
    name = Path(str(filename or "media").replace("\\", "/")).name
    name = re.sub(r"[\r\n\t]+", " ", name).strip()
    return (name or "media")[:255]


def _media_type(filename: str, content_type: str | None) -> str:
    normalized_type = str(content_type or "").split(";", 1)[0].strip().lower()
    if normalized_type.startswith("image/"):
        return "image"
    if normalized_type.startswith("video/"):
        return "video"
    suffix = Path(filename).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Bara bilder och videor kan laddas upp.")


def _format_size(bytes_count: int) -> str:
    if bytes_count >= 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.1f} MB"
    if bytes_count >= 1024:
        return f"{bytes_count / 1024:.1f} kB"
    return f"{bytes_count} B"


async def _read_upload_data(upload: UploadFile, *, batch_total: int) -> tuple[bytes, int]:
    chunks: list[bytes] = []
    size = 0
    try:
        while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
            size += len(chunk)
            if size > MAX_META_UPLOAD_FILE_BYTES:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"{_clean_filename(upload.filename)} är större än {_format_size(MAX_META_UPLOAD_FILE_BYTES)}.",
                )
            if batch_total + size > MAX_META_UPLOAD_BATCH_BYTES:
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Uppladdningen är större än {_format_size(MAX_META_UPLOAD_BATCH_BYTES)} totalt.",
                )
            chunks.append(chunk)
    finally:
        await upload.close()
    if size <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"{_clean_filename(upload.filename)} är tom.")
    return b"".join(chunks), size


@router.post("/uploads", status_code=status.HTTP_201_CREATED)
async def upload_meta_media(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> dict:
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Inga filer skickades.")
    if len(files) > MAX_META_UPLOAD_FILES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Du kan ladda upp max {MAX_META_UPLOAD_FILES} filer åt gången.",
        )

    batch_id = uuid4().hex
    batch_total = 0
    rows: list[MetaMediaUpload] = []
    saved: list[dict] = []

    for upload in files:
        filename = _clean_filename(upload.filename)
        content_type = str(upload.content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
        media_type = _media_type(filename, content_type)
        data, size = await _read_upload_data(upload, batch_total=batch_total)
        batch_total += size
        row = MetaMediaUpload(
            batch_id=batch_id,
            original_filename=filename,
            content_type=content_type or "application/octet-stream",
            media_type=media_type,
            size_bytes=size,
            data=data,
            status="pending_analysis",
            source="public_upload",
        )
        rows.append(row)
        saved.append(
            {
                "filename": filename,
                "content_type": row.content_type,
                "media_type": media_type,
                "size_bytes": size,
                "size_label": _format_size(size),
            }
        )

    try:
        db.add_all(rows)
        db.commit()
    except Exception:
        db.rollback()
        raise

    for row, item in zip(rows, saved):
        db.refresh(row)
        item["id"] = row.id

    return {
        "batch_id": batch_id,
        "saved_count": len(saved),
        "saved": saved,
        "status": "pending_analysis",
    }
