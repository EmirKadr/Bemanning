from datetime import date

import pytest
from fastapi import HTTPException

from app.backend.routers import public


def test_resolve_day_from_date():
    assert public._resolve_day_params(date(2026, 5, 13), None, None, None) == (2026, 20, 3)


def test_resolve_day_from_legacy_params():
    assert public._resolve_day_params(None, 2026, 20, 3) == (2026, 20, 3)


def test_resolve_day_defaults_to_today(monkeypatch):
    monkeypatch.setattr(public, "_today_local", lambda: date(2026, 5, 14))

    assert public._resolve_day_params(None, None, None, None) == (2026, 20, 4)


def test_resolve_day_rejects_mixed_date_and_legacy_params():
    with pytest.raises(HTTPException) as exc_info:
        public._resolve_day_params(date(2026, 5, 13), 2026, 20, 3)

    assert exc_info.value.status_code == 400


def test_resolve_day_rejects_partial_legacy_params():
    with pytest.raises(HTTPException) as exc_info:
        public._resolve_day_params(None, 2026, 20, None)

    assert exc_info.value.status_code == 400


def test_resolve_week_from_date():
    assert public._resolve_week_params(date(2026, 5, 13), None, None) == (2026, 20)


def test_resolve_week_defaults_to_current_week(monkeypatch):
    monkeypatch.setattr(public, "_today_local", lambda: date(2026, 5, 14))

    assert public._resolve_week_params(None, None, None) == (2026, 20)


def test_verify_token_strips_incoming_value(monkeypatch):
    monkeypatch.setattr(public.settings, "EXCEL_API_TOKEN", "abc123")

    public._verify_token(" abc123 ")

