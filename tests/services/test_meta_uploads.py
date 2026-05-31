import asyncio
import io

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers, UploadFile

from app.backend.database import Base
from app.backend.deps import get_db
from app.backend.main import app
from app.backend.models import MetaMediaUpload
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
        assert [row.media_type for row in rows] == ["image", "video"]
        assert rows[0].data == b"image-bytes"
        assert rows[1].data == b"video-bytes"
        assert len({row.batch_id for row in rows}) == 1
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
