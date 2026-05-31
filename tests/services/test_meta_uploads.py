import asyncio
import io
import re

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers, UploadFile

from app.backend.database import Base
from app.backend.deps import get_current_user, get_db
from app.backend.main import app
from app.backend.models import MetaMediaUpload, User
from app.backend.routers import meta_uploads


def make_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    return engine, session


def make_upload(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def test_public_meta_upload_route_accepts_multiple_media_without_login():
    engine, session = make_session()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/meta/uploads",
            files=[
                ("files", ("bild.jpg", b"image-bytes", "image/jpeg")),
                ("files", ("film.mov", b"video-bytes", "video/quicktime")),
            ],
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["saved_count"] == 2
        assert payload["status"] == "pending_analysis"

        rows = session.query(MetaMediaUpload).order_by(MetaMediaUpload.id).all()
        assert [row.original_filename for row in rows] == ["bild.jpg", "film.mov"]
        assert re.fullmatch(r"\d{8}_\d{6}_\d{6}Z_01\.jpg", rows[0].stored_filename)
        assert re.fullmatch(r"\d{8}_\d{6}_\d{6}Z_02\.mov", rows[1].stored_filename)
        assert [item["filename"] for item in payload["saved"]] == [row.stored_filename for row in rows]
        assert all(re.fullmatch(r"[0-9a-f]{64}", row.content_hash or "") for row in rows)
        assert len({row.content_hash for row in rows}) == 2
        assert [row.media_type for row in rows] == ["image", "video"]
        assert rows[0].data == b"image-bytes"
        assert rows[1].data == b"video-bytes"
        assert len({row.batch_id for row in rows}) == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_meta_upload_skips_duplicate_media_bytes():
    engine, session = make_session()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        first = client.post(
            "/api/meta/uploads",
            files=[
                ("files", ("film-a.mov", b"same-video", "video/quicktime")),
                ("files", ("film-b.mov", b"same-video", "video/quicktime")),
            ],
        )

        assert first.status_code == 201
        first_payload = first.json()
        assert first_payload["saved_count"] == 1
        assert first_payload["skipped_count"] == 1
        assert first_payload["skipped"][0]["reason"] == "duplicate"
        assert first_payload["skipped"][0]["duplicate_of_filename"] == first_payload["saved"][0]["filename"]
        assert session.query(MetaMediaUpload).count() == 1

        second = client.post(
            "/api/meta/uploads",
            files=[("files", ("film-c.mov", b"same-video", "video/quicktime"))],
        )
        assert second.status_code == 201
        second_payload = second.json()
        assert second_payload["saved_count"] == 0
        assert second_payload["skipped_count"] == 1
        assert second_payload["skipped"][0]["duplicate_of_id"] is not None
        assert session.query(MetaMediaUpload).count() == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_meta_upload_rejects_non_media_files():
    engine, session = make_session()
    try:
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                meta_uploads.upload_meta_media(
                    files=[make_upload("anteckning.txt", b"text", "text/plain")],
                    db=session,
                )
            )

        assert exc_info.value.status_code == 400
        assert session.query(MetaMediaUpload).count() == 0
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_super_user_can_list_meta_uploads_and_stream_content():
    engine, session = make_session()
    row = MetaMediaUpload(
        batch_id="batch",
        original_filename="semesterfilm.mov",
        stored_filename="20260531_120102_123456Z_01.mov",
        content_type="video/quicktime",
        media_type="video",
        size_bytes=11,
        data=b"hello-video",
        status="pending_analysis",
        source="public_upload",
    )
    session.add(row)
    session.commit()
    session.refresh(row)

    def override_get_db():
        yield session

    def super_user():
        return User(id=99, username="root", role="super_user", roles=["super_user"], is_active=True)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = super_user
    try:
        client = TestClient(app)
        response = client.get("/api/meta/uploads")
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["filename"] == "20260531_120102_123456Z_01.mov"
        assert item["original_filename"] == "semesterfilm.mov"
        assert item["media_type"] == "video"

        content = client.get(f"/api/meta/uploads/{row.id}/content", headers={"Range": "bytes=0-4"})
        assert content.status_code == 206
        assert content.content == b"hello"
        assert content.headers["content-range"] == "bytes 0-4/11"
        assert "20260531_120102_123456Z_01.mov" in content.headers["content-disposition"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_non_super_user_cannot_list_meta_uploads():
    engine, session = make_session()

    def override_get_db():
        yield session

    def admin_user():
        return User(id=100, username="admin", role="admin", roles=["admin"], is_active=True)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = admin_user
    try:
        client = TestClient(app)
        response = client.get("/api/meta/uploads")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
