import asyncio
import json
from types import SimpleNamespace

from fastapi import HTTPException
from openpyxl import load_workbook
import pytest
import requests

from app.backend import data_fetch_service as service
from app.backend.config import settings
from app.backend.external_data_client import ExternalDataClient, ExternalDataClientError
from app.backend.models import AuditLog
from app.backend.routers import data_fetch


SAMPLE_CATALOG = {
    "version": 1,
    "views": [
        {
            "id": "dblog_count_log",
            "label_en": "Activity Log",
            "label_sv": "Aktivitetslogg",
            "columns": [
                {"id": "type", "order": 1, "label_en": "Type", "label_sv": "Typ"},
                {"id": "item_num", "order": 2, "label_en": "Item Num", "label_sv": "Artikel"},
                {"id": "created_at", "order": 3, "label_en": "Created At", "label_sv": "Skapad"},
            ],
        }
    ],
}


def fake_user():
    return SimpleNamespace(id=1, username="emikad", display_name="Emir")


class FakeAuditDb:
    def __init__(self):
        self.items = []
        self.committed = False
        self.rolled_back = False

    def add(self, item):
        self.items.append(item)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_minimax_payload_never_contains_external_connection_details(monkeypatch):
    monkeypatch.setattr(settings, "DATA_SOURCE_API_BASE_URL", "https://secret.example/api/")
    monkeypatch.setattr(settings, "DATA_SOURCE_API_KEY", "very-secret-key")
    monkeypatch.setattr(settings, "DATA_SOURCE_API_CLIENT", "secret-client")
    monkeypatch.setattr(settings, "DATA_SOURCE_API_KEY_HEADER", "secret-key-header")
    monkeypatch.setattr(settings, "DATA_SOURCE_API_CLIENT_HEADER", "secret-client-header")
    monkeypatch.setattr(settings, "DATA_SOURCE_VIEW_DATA_PATH_TEMPLATE", "secret/path/{view}/data")
    catalog = service.catalog_from_payload(SAMPLE_CATALOG)

    context = service.build_catalog_context("Aktivitetslogg typ korrigering", catalog)
    payload = service.build_data_fetch_minimax_payload("Hämta aktivitetslogg", context)
    text = json.dumps(payload, ensure_ascii=False)

    assert "dblog_count_log" in text
    assert "Aktivitetslogg" in text
    assert "https://secret.example" not in text
    assert "very-secret-key" not in text
    assert "secret-client" not in text
    assert "secret-key-header" not in text
    assert "secret/path" not in text


def test_validate_plan_normalizes_columns_and_filters():
    catalog = service.catalog_from_payload(SAMPLE_CATALOG)
    plan = service.validate_plan_payload(
        {
            "status": "ok",
            "view": "dblog_count_log",
            "output_columns": ["type", "item_num"],
            "filters": [{"field": "type", "operator": "eq", "value": "korrigering"}],
        },
        catalog,
    )

    assert plan["view_label"] == "Aktivitetslogg"
    assert plan["output_column_labels"]["type"] == "Typ"
    assert plan["filters"] == [{"id": "type", "operator": "EQ", "value": "korrigering"}]


def test_validate_plan_rejects_unknown_column():
    catalog = service.catalog_from_payload(SAMPLE_CATALOG)

    with pytest.raises(service.DataFetchPlanError):
        service.validate_plan_payload(
            {
                "status": "ok",
                "view": "dblog_count_log",
                "output_columns": ["does_not_exist"],
            },
            catalog,
        )


def test_run_data_fetch_uses_validated_llm_plan_and_projects_rows(monkeypatch):
    captured = {}
    db = FakeAuditDb()

    class FakeExternalDataClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        def fetch_data(self, view, filters=None, identifiers=None):
            captured["view"] = view
            captured["filters"] = filters
            captured["identifiers"] = identifiers
            return [
                {"type": "korrigering", "item_num": "A1", "created_at": "2026-05-21", "extra": "x"},
                {"type": "korrigering", "item_num": "A2", "created_at": "2026-05-21", "extra": "y"},
            ]

    monkeypatch.setattr(settings, "DATA_SOURCE_CATALOG_JSON", json.dumps(SAMPLE_CATALOG))
    monkeypatch.setattr(settings, "DATA_SOURCE_API_BASE_URL", "https://secret.example/api/")
    monkeypatch.setattr(settings, "DATA_SOURCE_API_KEY", "secret-key")
    monkeypatch.setattr(settings, "DATA_SOURCE_API_CLIENT", "secret-client")
    monkeypatch.setattr(settings, "DATA_SOURCE_API_KEY_HEADER", "secret-key-header")
    monkeypatch.setattr(settings, "DATA_SOURCE_API_CLIENT_HEADER", "secret-client-header")
    monkeypatch.setattr(settings, "DATA_SOURCE_VIEW_DATA_PATH_TEMPLATE", "secret/path/{view}/data")
    monkeypatch.setattr(settings, "MINIMAX_API_KEY", "minimax-key")
    service.clear_catalog_cache()
    monkeypatch.setattr(
        data_fetch,
        "_call_minimax",
        lambda _payload: json.dumps(
            {
                "status": "ok",
                "view": "dblog_count_log",
                "output_columns": ["type", "item_num"],
                "filters": [{"field": "type", "operator": "EQ", "value": "korrigering"}],
            }
        ),
    )
    monkeypatch.setattr(data_fetch, "ExternalDataClient", FakeExternalDataClient)

    result = asyncio.run(
        data_fetch.run_data_fetch(
            data_fetch.DataFetchRunRequest(prompt="Hämta Aktivitetslogg där typ är korrigering"),
            current_user=fake_user(),
            db=db,
        )
    )

    assert captured["view"] == "dblog_count_log"
    assert captured["filters"] == [{"id": "type", "operator": "EQ", "value": "korrigering"}]
    assert captured["client_kwargs"]["base_url"] == "https://secret.example/api/"
    assert result["columns"] == [
        {"id": "type", "label": "Typ"},
        {"id": "item_num", "label": "Artikel"},
    ]
    assert result["rows"] == [
        {"type": "korrigering", "item_num": "A1"},
        {"type": "korrigering", "item_num": "A2"},
    ]
    assert result["session_id"]
    assert data_fetch.DATA_FETCH_SESSIONS[result["session_id"]]["user_key"] == "1"
    assert db.committed is True
    assert len(db.items) == 1
    assert isinstance(db.items[0], AuditLog)
    assert db.items[0].entity_type == "data_fetch"
    assert db.items[0].action == "fetch_success"
    assert db.items[0].new_value["view"] == "dblog_count_log"
    assert db.items[0].new_value["total_rows"] == 2


def test_excel_export_session_is_bound_to_user():
    session_id = "session-for-user-1"
    data_fetch.DATA_FETCH_SESSIONS[session_id] = {
        "user_key": "1",
        "plan": {"view": "dblog_count_log", "view_label": "Aktivitetslogg"},
        "columns": [{"id": "type", "label": "Typ"}],
        "rows": [{"type": "korrigering"}],
        "total_rows": 1,
    }

    try:
        with pytest.raises(HTTPException) as exc_info:
            data_fetch.export_data_fetch_excel(session_id, current_user=SimpleNamespace(id=2))
        assert getattr(exc_info.value, "status_code", None) == 404
    finally:
        data_fetch.DATA_FETCH_SESSIONS.pop(session_id, None)


def test_excel_export_writes_data_and_metadata(tmp_path):
    session = {
        "plan": {"view": "dblog_count_log", "view_label": "Aktivitetslogg"},
        "columns": [{"id": "type", "label": "Typ"}, {"id": "item_num", "label": "Artikel"}],
        "rows": [{"type": "korrigering", "item_num": "A1"}],
        "total_rows": 1,
    }

    path = data_fetch._write_excel(session)
    workbook = load_workbook(path)

    assert workbook["Data"]["A1"].value == "Typ"
    assert workbook["Data"]["B2"].value == "A1"
    assert workbook["Fråga"]["B2"].value == "dblog_count_log"


def test_health_reports_missing_catalog_without_spending_ai(monkeypatch):
    monkeypatch.setattr(data_fetch, "load_catalog", lambda: (_ for _ in ()).throw(service.DataFetchConfigError("saknas")))
    for setting_name in data_fetch.REQUIRED_API_SETTINGS:
        monkeypatch.setattr(settings, setting_name, "")
    monkeypatch.setattr(settings, "MINIMAX_API_KEY", "minimax-key")

    result = data_fetch.data_fetch_health(fake_user())

    assert result["ok"] is False
    assert result["catalog_configured"] is False
    assert result["api_configured"] is False
    assert result["api_missing"] == list(data_fetch.REQUIRED_API_SETTINGS)
    assert result["minimax_configured"] is True
    assert result["catalog"] == {"views": 0, "columns": 0}


def test_api_client_reports_exact_missing_settings(monkeypatch):
    for setting_name in data_fetch.REQUIRED_API_SETTINGS:
        monkeypatch.setattr(settings, setting_name, "")
    monkeypatch.setattr(settings, "DATA_SOURCE_API_BASE_URL", "https://secret.example/api/")
    monkeypatch.setattr(settings, "DATA_SOURCE_VIEW_DATA_PATH_TEMPLATE", "secret/path/{view}/data")

    with pytest.raises(HTTPException) as exc_info:
        data_fetch._api_client_or_503()

    assert exc_info.value.status_code == 503
    detail = exc_info.value.detail
    assert "DATA_SOURCE_API_KEY" in detail
    assert "DATA_SOURCE_API_CLIENT" in detail
    assert "DATA_SOURCE_API_KEY_HEADER" in detail
    assert "DATA_SOURCE_API_CLIENT_HEADER" in detail
    assert "DATA_SOURCE_API_BASE_URL" not in detail
    assert "DATA_SOURCE_VIEW_DATA_PATH_TEMPLATE" not in detail


def test_external_data_client_wraps_connection_errors():
    class BrokenSession:
        headers = {}

        def post(self, *_args, **_kwargs):
            raise requests.ConnectionError("connection reset")

    client = ExternalDataClient(
        base_url="https://secret.example/api/",
        view_data_path_template="views/{view}/data",
        session=BrokenSession(),
    )

    with pytest.raises(ExternalDataClientError) as exc_info:
        client.fetch_data("dblog_count_log")

    assert "Extern datakälla kunde inte nås" in str(exc_info.value)


def test_run_data_fetch_returns_logged_external_error(monkeypatch):
    db = FakeAuditDb()

    class FailingExternalDataClient:
        def __init__(self, **_kwargs):
            pass

        def fetch_data(self, *_args, **_kwargs):
            raise ExternalDataClientError("Extern datakälla kunde inte nås.")

    monkeypatch.setattr(settings, "DATA_SOURCE_CATALOG_JSON", json.dumps(SAMPLE_CATALOG))
    monkeypatch.setattr(settings, "DATA_SOURCE_API_BASE_URL", "https://secret.example/api/")
    monkeypatch.setattr(settings, "DATA_SOURCE_API_KEY", "secret-key")
    monkeypatch.setattr(settings, "DATA_SOURCE_API_CLIENT", "secret-client")
    monkeypatch.setattr(settings, "DATA_SOURCE_API_KEY_HEADER", "secret-key-header")
    monkeypatch.setattr(settings, "DATA_SOURCE_API_CLIENT_HEADER", "secret-client-header")
    monkeypatch.setattr(settings, "DATA_SOURCE_VIEW_DATA_PATH_TEMPLATE", "secret/path/{view}/data")
    service.clear_catalog_cache()
    monkeypatch.setattr(data_fetch, "ExternalDataClient", FailingExternalDataClient)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            data_fetch.run_data_fetch(
                data_fetch.DataFetchRunRequest(
                    plan={
                        "status": "ok",
                        "view": "dblog_count_log",
                        "output_columns": ["type", "item_num"],
                        "filters": [{"field": "type", "operator": "EQ", "value": "korrigering"}],
                    }
                ),
                current_user=fake_user(),
                db=db,
            )
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail["message"] == "Extern datakälla kunde inte nås."
    assert exc_info.value.detail["view"] == "dblog_count_log"
    assert exc_info.value.detail["error_id"]
    assert db.committed is True
    assert len(db.items) == 1
    assert db.items[0].entity_type == "data_fetch"
    assert db.items[0].action == "fetch_failed"
    assert db.items[0].new_value["status_code"] == 502
    assert db.items[0].new_value["error_id"] == exc_info.value.detail["error_id"]
