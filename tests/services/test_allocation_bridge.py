import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.backend import allocation_bridge as bridge
from app.backend.routers import allocation as allocation_router


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def clear_allocation_sessions():
    bridge.SESSIONS.clear()
    yield
    bridge.SESSIONS.clear()


def fake_available(monkeypatch, *, flows_module=None, engine_module=None):
    engine = engine_module or SimpleNamespace(APP_VERSION="test", APP_TITLE="Allokering")
    flows = flows_module or SimpleNamespace(
        FLOW_BY_ID={},
        public_registry=lambda: [],
        public_pool=lambda: [],
    )
    monkeypatch.setattr(bridge, "require_available", lambda: (engine, flows))
    return engine, flows


def route_user(role: str):
    return SimpleNamespace(id=1, username=f"{role}-user", role=role, roles=[role], is_active=True)


def test_df_to_table_serializes_preview_without_nan_values():
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame(
        {
            "Artikel": ["A100", None],
            "Antal": [1.0, float("nan")],
        }
    )

    table = bridge.df_to_table(df, preview_limit=1)

    assert table == {
        "columns": ["Artikel", "Antal"],
        "rows": [["A100", "1"]],
        "row_count": 2,
        "truncated": True,
    }


def test_allocation_bridge_uses_vendored_warehouse_tools_by_default():
    assert bridge.warehouse_tools_dir().name == "warehouse_tools"
    assert bridge.allokering_backend_dir() == bridge.warehouse_tools_dir()
    assert (bridge.warehouse_tools_dir() / "vendor" / "allokering12.1.py").is_file()


def test_allocation_bridge_imports_warehouse_tools_when_started_from_app_root():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from backend import allocation_bridge as bridge; "
                "engine, flows = bridge.require_available(); "
                "print(engine.APP_VERSION, len(flows.FLOW_BY_ID))"
            ),
        ],
        cwd=ROOT / "app",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "12.1.5" in result.stdout


def test_allocation_catalog_loads_without_pandas_when_started_from_app_root():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import builtins\n"
                "real_import = builtins.__import__\n"
                "def guard(name, *args, **kwargs):\n"
                "    if name == 'pandas' or name.startswith('pandas.'):\n"
                "        raise ModuleNotFoundError(\"No module named 'pandas'\")\n"
                "    return real_import(name, *args, **kwargs)\n"
                "builtins.__import__ = guard\n"
                "from backend import allocation_bridge as bridge\n"
                "print(len(bridge.public_registry()), len(bridge.public_pool()))\n"
            ),
        ],
        cwd=ROOT / "app",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().split() == ["14", "10"]


def test_native_detector_recognizes_wms_csv_without_pandas(tmp_path):
    pick_log = tmp_path / "v_ask_pick_log_full-test.csv"
    pick_log.write_text("Pallid;Artikelnr;Plockat;Ordernr;Datum\nP1;A1;1;O1;2026-05-18\n", encoding="utf-8")

    assert bridge.detect_file_type(pick_log) == "wms_pick"


def test_native_detector_uses_ask_filename_hints_without_reading_headers(tmp_path):
    orders = tmp_path / "v_ask_customer_order_details_all-20260518075529.csv"
    orders.write_text("helt;okand;header\n1;2;3\n", encoding="utf-8")

    assert bridge.detect_file_type(orders) == "orders"


def test_allocation_bridge_imports_without_tkinter_on_headless_server():
    env = dict(**os.environ, WAREHOUSE_TOOLS_FORCE_HEADLESS_TK="1")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from backend import allocation_bridge as bridge; "
                "engine, flows = bridge.require_available(); "
                "print(engine.APP_VERSION, len(flows.FLOW_BY_ID))"
            ),
        ],
        cwd=ROOT / "app",
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "12.1.5" in result.stdout


def test_run_flow_handler_serializes_tables_and_keeps_session(monkeypatch):
    pd = pytest.importorskip("pandas")
    df = pd.DataFrame({"Artikel": ["A100", ""], "Antal": [1, 2]})
    flows = SimpleNamespace(
        FLOW_BY_ID={
            "demo": {
                "handler": lambda files, params: {
                    "summary": {"files": sorted(files), "limit": params["limit"]},
                    "tables": [("main", "Demoresultat", df)],
                    "text": "klart",
                    "log": ["rad 1"],
                }
            }
        }
    )
    fake_available(monkeypatch, flows_module=flows)
    monkeypatch.setattr(bridge, "_catalog", lambda: SimpleNamespace(FLOW_BY_ID={"demo": {}}))

    result = bridge.run_flow_handler("demo", {"orders": object()}, {"limit": "10"})

    assert result["flow_id"] == "demo"
    assert result["summary"] == {"files": ["orders"], "limit": "10"}
    assert result["text"] == "klart"
    assert result["log"] == ["rad 1"]
    assert result["tables"][0]["key"] == "main"
    assert result["tables"][0]["label"] == "Demoresultat"
    assert result["tables"][0]["table"]["row_count"] == 2
    assert result["session_id"] in bridge.SESSIONS
    assert bridge.table_column_text(result["session_id"], "main", 0) == {"text": "A100"}


def test_run_split_values_uses_native_flow_without_legacy_runtime(monkeypatch):
    def fail_available():
        raise AssertionError("legacy allocation runtime should not load for split-values")

    monkeypatch.setattr(bridge, "require_available", fail_available)

    result = bridge.run_flow_handler("split-values", {}, {"values": "A\nB\nC\nD\nE", "chunk_size": "2"})

    assert result["summary"] == {"Antal värden": 5, "Antal kolumner": 3, "Per kolumn": 2}
    assert result["tables"][0]["table"] == {
        "columns": ["Kolumn 1", "Kolumn 2", "Kolumn 3"],
        "rows": [["A", "C", "E"], ["B", "D", ""]],
        "row_count": 2,
        "truncated": False,
    }
    assert bridge.table_column_text(result["session_id"], "report", 1) == {"text": "C\nD"}


def test_run_flow_handler_returns_404_for_unknown_flow(monkeypatch):
    fake_available(monkeypatch)

    with pytest.raises(HTTPException) as exc_info:
        bridge.run_flow_handler("saknas", {}, {})

    assert exc_info.value.status_code == 404


def test_allocation_router_exposes_flow_registry_and_pool(monkeypatch):
    monkeypatch.setattr(bridge, "public_registry", lambda: [{"id": "allocering", "label": "Allokering"}])
    monkeypatch.setattr(bridge, "public_pool", lambda: [{"key": "orders", "label": "Bestallningslinjer"}])

    assert allocation_router.list_flows(user=route_user("super_user")) == {"flows": [{"id": "allocering", "label": "Allokering"}]}
    assert allocation_router.list_pool(user=route_user("super_user")) == {"pool": [{"key": "orders", "label": "Bestallningslinjer"}]}


def test_allocation_router_limits_lager_and_artikelplacering_to_self_service_flows(monkeypatch):
    monkeypatch.setattr(
        bridge,
        "public_registry",
        lambda: [
            {"id": "allocate", "label": "Allokering"},
            {"id": "eftersok", "label": "Eftersok"},
            {"id": "split-values", "label": "Dela varden"},
        ],
    )
    monkeypatch.setattr(bridge, "public_pool", lambda: [{"key": "orders", "label": "Bestallningslinjer"}])

    for role in ("warehouse_clerk", "article_placer"):
        user = route_user(role)
        assert allocation_router.list_flows(user=user) == {
            "flows": [
                {"id": "eftersok", "label": "Eftersok"},
                {"id": "split-values", "label": "Dela varden"},
            ]
        }
        assert allocation_router.list_pool(user=user) == {"pool": []}


def test_allocation_health_reports_unavailable_without_crashing(monkeypatch):
    def fail():
        raise RuntimeError("saknas")

    monkeypatch.setattr(bridge, "public_registry", fail)
    monkeypatch.setattr(
        bridge,
        "unavailable_detail",
        lambda: {"available": False, "message": "Allokering saknas", "backend_dir": "x"},
    )

    assert allocation_router.health() == {
        "available": False,
        "message": "Allokering saknas",
        "backend_dir": "x",
    }
