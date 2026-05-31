from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import log as audit_log
from ..deps import get_db, require_super_user
from ..models import MetaMediaUpload, User


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


def _stored_filename(uploaded_at: datetime, index: int, original_filename: str, media_type: str) -> str:
    suffix = Path(original_filename).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS and suffix not in VIDEO_EXTENSIONS:
        suffix = ".mp4" if media_type == "video" else ".jpg"
    timestamp = uploaded_at.astimezone(timezone.utc).strftime("%Y%m%d_%H%M%S_%fZ")
    return f"{timestamp}_{index:02d}{suffix}"[:255]


def _media_upload_out(row: MetaMediaUpload) -> dict:
    return {
        "id": row.id,
        "batch_id": row.batch_id,
        "filename": row.stored_filename or row.original_filename,
        "stored_filename": row.stored_filename or row.original_filename,
        "original_filename": row.original_filename,
        "content_type": row.content_type,
        "media_type": row.media_type,
        "size_bytes": row.size_bytes,
        "size_label": _format_size(row.size_bytes),
        "status": row.status,
        "source": row.source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _media_upload_audit_snapshot(row: MetaMediaUpload) -> dict:
    return {
        "batch_id": row.batch_id,
        "filename": row.stored_filename or row.original_filename,
        "original_filename": row.original_filename,
        "content_type": row.content_type,
        "media_type": row.media_type,
        "size_bytes": row.size_bytes,
        "content_hash": row.content_hash,
        "status": row.status,
        "source": row.source,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


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
    skipped: list[dict] = []
    pending_hashes: dict[str, str] = {}

    for index, upload in enumerate(files, start=1):
        filename = _clean_filename(upload.filename)
        content_type = str(upload.content_type or "application/octet-stream").split(";", 1)[0].strip().lower()
        media_type = _media_type(filename, content_type)
        data, size = await _read_upload_data(upload, batch_total=batch_total)
        batch_total += size
        content_hash = hashlib.sha256(data).hexdigest()
        pending_duplicate = pending_hashes.get(content_hash)
        if pending_duplicate:
            skipped.append(
                _duplicate_item(
                    filename=filename,
                    content_type=content_type or "application/octet-stream",
                    media_type=media_type,
                    size=size,
                    duplicate_of_id=None,
                    duplicate_of_filename=pending_duplicate,
                )
            )
            continue
        existing = db.query(MetaMediaUpload).filter(MetaMediaUpload.content_hash == content_hash).first()
        if existing is not None:
            skipped.append(
                _duplicate_item(
                    filename=filename,
                    content_type=content_type or "application/octet-stream",
                    media_type=media_type,
                    size=size,
                    duplicate_of_id=existing.id,
                    duplicate_of_filename=existing.stored_filename or existing.original_filename,
                )
            )
            continue
        uploaded_at = datetime.now(timezone.utc)
        stored_filename = _stored_filename(uploaded_at, index, filename, media_type)
        pending_hashes[content_hash] = stored_filename
        row = MetaMediaUpload(
            batch_id=batch_id,
            original_filename=filename,
            stored_filename=stored_filename,
            content_type=content_type or "application/octet-stream",
            media_type=media_type,
            size_bytes=size,
            content_hash=content_hash,
            data=data,
            status="pending_analysis",
            source="public_upload",
            created_at=uploaded_at,
        )
        rows.append(row)
        saved.append(
            {
                "filename": stored_filename,
                "stored_filename": stored_filename,
                "original_filename": filename,
                "content_type": row.content_type,
                "media_type": media_type,
                "size_bytes": size,
                "size_label": _format_size(size),
            }
        )

    if rows:
        try:
            db.add_all(rows)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="En eller flera filer fanns redan och sparades inte dubbelt. Försök ladda upp igen om andra filer saknas.",
            )
        except Exception:
            db.rollback()
            raise

        for row, item in zip(rows, saved):
            db.refresh(row)
            item["id"] = row.id

    return {
        "batch_id": batch_id,
        "saved_count": len(saved),
        "skipped_count": len(skipped),
        "saved": saved,
        "skipped": skipped,
        "status": "pending_analysis",
    }


@router.get("/uploads")
def list_meta_media_uploads(
    limit: int = Query(200, ge=1, le=500),
    media_type: str | None = Query(None, pattern="^(image|video)$"),
    db: Session = Depends(get_db),
    _: User = Depends(require_super_user),
) -> dict:
    query = db.query(MetaMediaUpload)
    if media_type:
        query = query.filter(MetaMediaUpload.media_type == media_type)
    rows = (
        query.order_by(MetaMediaUpload.created_at.desc(), MetaMediaUpload.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "count": len(rows),
        "items": [_media_upload_out(row) for row in rows],
    }


@router.delete("/uploads/{upload_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_meta_media_upload(
    upload_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_super_user),
) -> None:
    row = db.get(MetaMediaUpload, upload_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Uppladdningen hittades inte.")
    before = _media_upload_audit_snapshot(row)
    db.delete(row)
    audit_log(
        db,
        entity_type="meta_media_upload",
        entity_id=row.id,
        action="delete",
        old_value=before,
        new_value=None,
        user_id=user.id,
        business_id=None,
    )
    db.commit()


def _content_disposition(filename: str) -> str:
    safe_filename = _clean_filename(filename)
    return f"inline; filename*=UTF-8''{quote(safe_filename)}"


def _duplicate_item(
    *,
    filename: str,
    content_type: str,
    media_type: str,
    size: int,
    duplicate_of_id: int | None,
    duplicate_of_filename: str,
) -> dict:
    return {
        "filename": filename,
        "original_filename": filename,
        "content_type": content_type,
        "media_type": media_type,
        "size_bytes": size,
        "size_label": _format_size(size),
        "reason": "duplicate",
        "duplicate_of_id": duplicate_of_id,
        "duplicate_of_filename": duplicate_of_filename,
    }


def _media_response(row: MetaMediaUpload, request: Request) -> Response:
    data = row.data or b""
    total = len(data)
    filename = row.stored_filename or row.original_filename
    base_headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": _content_disposition(filename),
    }
    range_header = request.headers.get("range") or request.headers.get("Range") or ""
    match = re.match(r"bytes=(\d*)-(\d*)$", range_header.strip())
    if match and total:
        start_text, end_text = match.groups()
        if not start_text and end_text:
            length = min(int(end_text), total)
            start = total - length
            end = total - 1
        else:
            start = int(start_text or 0)
            end = int(end_text) if end_text else total - 1
            end = min(end, total - 1)
        if start > end or start >= total:
            return Response(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                headers={**base_headers, "Content-Range": f"bytes */{total}"},
            )
        chunk = data[start : end + 1]
        headers = {
            **base_headers,
            "Content-Range": f"bytes {start}-{end}/{total}",
            "Content-Length": str(len(chunk)),
        }
        return Response(content=chunk, status_code=status.HTTP_206_PARTIAL_CONTENT, media_type=row.content_type, headers=headers)

    return Response(
        content=data,
        media_type=row.content_type,
        headers={**base_headers, "Content-Length": str(total)},
    )


@router.get("/uploads/{upload_id}/content")
def get_meta_media_content(
    upload_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_user),
) -> Response:
    row = db.get(MetaMediaUpload, upload_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Uppladdningen hittades inte.")
    return _media_response(row, request)
