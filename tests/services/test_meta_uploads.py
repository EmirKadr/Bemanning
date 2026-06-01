import asyncio
import io
import re

import pytest
from fastapi import BackgroundTasks, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.datastructures import Headers, UploadFile

from app.backend.config import settings
from app.backend.database import Base
from app.backend.deps import get_current_user, get_db
from app.backend.main import app
from app.backend.models import AuditLog, MetaMediaUpload, MetaShipmentObservation, User
from app.backend import meta_analysis_service
from app.backend.routers import meta_uploads


@pytest.fixture(autouse=True)
def disable_meta_analysis_provider(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(meta_uploads, "_probe_video_duration_seconds", lambda data, filename: None)


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


def test_meta_analysis_uses_gemini_config_and_parses_json_response(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gemini-key")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-2.5-pro")

    assert meta_analysis_service.meta_analysis_configured()
    assert meta_analysis_service.gemini_model_name() == "gemini-2.5-pro"

    extracted = meta_analysis_service._extract_json_candidate(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    '{"order_number":"12345","username":"lots1","customer_name":"Kund AB",'
                                    '"pallet_id":"PALL-1","deviations":["Dåligt byggd pall"],'
                                    '"uncertainty_notes":"Kontrollera kundnamn","label_frame_time_seconds":2.5}'
                                )
                            }
                        ]
                    }
                }
            ]
        }
    )
    fields = meta_analysis_service.normalize_meta_analysis(extracted)

    assert fields["order_number"] == "12345"
    assert fields["username"] == "lots1"
    assert fields["customer_name"] == "Kund AB"
    assert fields["pallet_id"] == "PALL-1"
    assert fields["deviations"] == ["Dåligt byggd pall"]
    assert fields["uncertainty_notes"] == "Kontrollera kundnamn"
    assert fields["label_frame_time_seconds"] == "2.5"
    assert re.fullmatch(
        r"[0-9a-f]{64}",
        meta_analysis_service.calculate_record_hash(
            video_hash="b" * 64,
            order_number=fields["order_number"],
            username=fields["username"],
            customer_name=fields["customer_name"],
            pallet_id=fields["pallet_id"],
            deviations=fields["deviations"],
        ),
    )


def test_public_meta_upload_route_accepts_multiple_media_without_login(monkeypatch):
    monkeypatch.setattr(meta_uploads, "_probe_video_duration_seconds", lambda data, filename: 42.4)
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
        assert rows[0].duration_seconds is None
        assert rows[1].duration_seconds == 42.4
        assert len({row.batch_id for row in rows}) == 1
        assert payload["saved"][1]["duration_seconds"] == 42.4
        assert payload["saved"][1]["duration_label"] == "0:42"
        shipment = session.query(MetaShipmentObservation).one()
        assert shipment.media_upload_id == rows[1].id
        assert shipment.video_hash == rows[1].content_hash
        assert re.fullmatch(r"[0-9a-f]{64}", shipment.record_hash)
        assert shipment.analysis_status == "needs_configuration"
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
                    background_tasks=BackgroundTasks(),
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
        duration_seconds=65.1,
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
        assert item["duration_seconds"] == 65.1
        assert item["duration_label"] == "1:05"

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


def test_super_user_can_list_and_request_meta_shipment_analysis_without_configuration(monkeypatch):
    monkeypatch.setattr(meta_uploads, "meta_analysis_configured", lambda: False)
    engine, session = make_session()
    row = MetaMediaUpload(
        batch_id="batch",
        original_filename="etikettfilm.mov",
        stored_filename="20260531_120102_123456Z_01.mov",
        content_type="video/quicktime",
        media_type="video",
        size_bytes=11,
        duration_seconds=75.4,
        content_hash="b" * 64,
        data=b"hello-video",
        status="pending_analysis",
        source="public_upload",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    shipment = MetaShipmentObservation(
        media_upload_id=row.id,
        video_hash=row.content_hash,
        record_hash="c" * 64,
        order_number="12345",
        username="lots1",
        customer_name="Kund AB",
        pallet_id="PALL-1",
        deviations=["Dåligt byggd pall"],
        analysis_status="manual_review",
    )
    session.add(shipment)
    session.commit()

    def override_get_db():
        yield session

    def super_user():
        return User(id=99, username="root", role="super_user", roles=["super_user"], is_active=True)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = super_user
    try:
        client = TestClient(app)
        response = client.get("/api/meta/shipment-observations")
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["order_number"] == "12345"
        assert item["username"] == "lots1"
        assert item["customer_name"] == "Kund AB"
        assert item["pallet_id"] == "PALL-1"
        assert item["deviations"] == ["Dåligt byggd pall"]
        assert item["video_url"] == f"/api/meta/uploads/{row.id}/content"
        assert item["video_filename"] == "20260531_120102_123456Z_01.mov"
        assert item["video_duration_seconds"] == 75.4
        assert item["video_duration_label"] == "1:15"

        analysis = client.post(f"/api/meta/uploads/{row.id}/analyze")
        assert analysis.status_code == 200
        assert analysis.json()["status"] == "needs_configuration"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_super_user_can_delete_meta_uploads_and_audit_without_blob():
    engine, session = make_session()
    row = MetaMediaUpload(
        batch_id="batch-delete",
        original_filename="lagerbild.jpg",
        stored_filename="20260531_120102_123456Z_01.jpg",
        content_type="image/jpeg",
        media_type="image",
        size_bytes=10,
        content_hash="a" * 64,
        data=b"image-data",
        status="pending_analysis",
        source="public_upload",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    upload_id = row.id

    def override_get_db():
        yield session

    def super_user():
        return User(id=99, username="root", role="super_user", roles=["super_user"], is_active=True)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = super_user
    try:
        client = TestClient(app)
        response = client.delete(f"/api/meta/uploads/{upload_id}")

        assert response.status_code == 204
        assert session.get(MetaMediaUpload, upload_id) is None
        audit = session.query(AuditLog).filter_by(entity_type="meta_media_upload", action="delete").one()
        assert audit.entity_id == upload_id
        assert audit.old_value["filename"] == "20260531_120102_123456Z_01.jpg"
        assert audit.old_value["content_hash"] == "a" * 64
        assert "data" not in audit.old_value
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
        return User(id=100, username="regular-admin", role="admin", roles=["admin"], is_active=True)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = admin_user
    try:
        client = TestClient(app)
        response = client.get("/api/meta/uploads")
        assert response.status_code == 403
        delete_response = client.delete("/api/meta/uploads/1")
        assert delete_response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
