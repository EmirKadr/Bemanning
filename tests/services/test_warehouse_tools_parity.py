from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

from warehouse_tools import flows as new_flows


pd = pytest.importorskip("pandas")

PARITY_FLOW_IDS = (
    "allocate",
    "dispatch-check",
    "eftersok",
    "hib-koppling",
    "lyx",
    "observations-update",
    "ordersaldo",
    "overview-check",
    "pafyllnadsprio",
    "prognos-report",
    "split-values",
    "vecka27-check",
)

ROOT = Path(__file__).resolve().parents[2]
PROJECTS_ROOT = ROOT.parent
ALLOKERING_ROOT = PROJECTS_ROOT / "allokering"
ALLOKERING_BACKEND = ALLOKERING_ROOT / "web" / "backend"
ALLOKERING_TESTDATA = ALLOKERING_ROOT / "testdata"


def _require_legacy_allokering() -> None:
    if not (ALLOKERING_BACKEND / "flows.py").is_file():
        pytest.skip(f"Saknar gammal Allokering-backend: {ALLOKERING_BACKEND}")
    if not ALLOKERING_TESTDATA.is_dir():
        pytest.skip(f"Saknar Allokering-testdata: {ALLOKERING_TESTDATA}")


def _load_legacy_flows() -> ModuleType:
    _require_legacy_allokering()
    module_names = (
        "flows",
        "engine",
        "allokering_engine",
        "app_info",
        "analytics_store",
        "update_service",
        "wms_sok79_module",
    )
    saved_modules = {name: sys.modules.get(name) for name in module_names}
    saved_path = list(sys.path)

    for name in module_names:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(ALLOKERING_BACKEND))
    sys.path.insert(0, str(ALLOKERING_ROOT))
    try:
        legacy_flows = importlib.import_module("flows")
    finally:
        sys.path[:] = saved_path
        for name in module_names:
            if saved_modules[name] is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = saved_modules[name]
    return legacy_flows


def _testdata() -> dict[str, Path]:
    _require_legacy_allokering()
    return {
        "orders": ALLOKERING_TESTDATA / "v_ask_customer_order_details_all-20260317145125.csv",
        "buffer": ALLOKERING_TESTDATA / "v_ask_article_buffertpallet-20260317145136.csv",
        "saldo": ALLOKERING_TESTDATA / "v_ask_item_summary_stock_automation-20260317145351.csv",
        "items": ALLOKERING_TESTDATA / "item_option-20260317145203.csv",
        "overview": ALLOKERING_TESTDATA / "v_ask_order_overview-20260317145114.csv",
        "dispatch": ALLOKERING_TESTDATA / "v_ask_dispatch_pallet-20260316130458.csv",
        "prognos": next(ALLOKERING_TESTDATA.glob("Prognos idag_*.xlsx")),
        "campaign": next(ALLOKERING_TESTDATA.glob("Granng*prognos*.xlsx")),
        "wms_receive": ALLOKERING_TESTDATA / "v_ask_receive_log-20260317145157.csv",
        "wms_booking": ALLOKERING_TESTDATA / "v_ask_booking_putaway-20260317145232.csv",
        "wms_buffert": ALLOKERING_TESTDATA / "v_ask_article_buffertpallet-20260317145136.csv",
        "wms_trans": ALLOKERING_TESTDATA / "v_ask_trans_log-20260317170854.csv",
        "wms_pick": ALLOKERING_TESTDATA / "v_ask_pick_log_full-20260317170910.csv",
        "wms_correct": ALLOKERING_TESTDATA / "v_ask_correct_log-20260317145302.csv",
    }


def _scenario_payloads() -> dict[str, tuple[dict[str, Path], dict[str, str]]]:
    files = _testdata()
    return {
        "allocate": (
            {
                "orders": files["orders"],
                "buffer": files["buffer"],
                "saldo": files["saldo"],
                "items": files["items"],
            },
            {},
        ),
        "ordersaldo": ({"orders": files["orders"], "saldo": files["saldo"]}, {}),
        "lyx": ({"saldo": files["saldo"]}, {}),
        "pafyllnadsprio": (
            {"orders": files["orders"], "saldo": files["saldo"], "overview": files["overview"]},
            {},
        ),
        "hib-koppling": ({"details": files["orders"], "overview": files["overview"]}, {}),
        "overview-check": ({"overview": files["overview"], "details": files["orders"]}, {}),
        "dispatch-check": (
            {"overview": files["overview"], "dispatch": files["dispatch"], "details": files["orders"]},
            {},
        ),
        "vecka27-check": ({"orders": files["orders"]}, {}),
        "eftersok": (
            {
                "wms_receive": files["wms_receive"],
                "wms_booking": files["wms_booking"],
                "wms_buffert": files["wms_buffert"],
                "wms_trans": files["wms_trans"],
                "wms_pick": files["wms_pick"],
                "wms_correct": files["wms_correct"],
            },
            {"purchase": "999109415", "article": "200847340"},
        ),
        "prognos-report": (
            {
                "prognos": files["prognos"],
                "campaign": files["campaign"],
                "saldo": files["saldo"],
                "buffer": files["buffer"],
            },
            {},
        ),
        "observations-update": ({"buffer": files["buffer"]}, {}),
        "split-values": ({}, {"values": "A\nB\nC\nD\nE", "chunk_size": "2"}),
    }


def _assert_results_equal(flow_id: str, old_result: dict, new_result: dict) -> None:
    assert new_result.get("summary") == old_result.get("summary"), flow_id
    assert new_result.get("text") == old_result.get("text"), flow_id

    old_tables = old_result.get("tables", [])
    new_tables = new_result.get("tables", [])
    assert [(key, label) for key, label, _df in new_tables] == [
        (key, label) for key, label, _df in old_tables
    ], flow_id

    for (old_key, _old_label, old_df), (new_key, _new_label, new_df) in zip(old_tables, new_tables):
        assert new_key == old_key
        pd.testing.assert_frame_equal(new_df, old_df, check_dtype=False)


def test_vendored_warehouse_registry_matches_old_allokering_app():
    legacy_flows = _load_legacy_flows()

    assert new_flows.public_pool() == legacy_flows.public_pool()
    assert new_flows.public_registry() == legacy_flows.public_registry()
    assert set(new_flows.FLOW_BY_ID) == set(legacy_flows.FLOW_BY_ID)


@pytest.mark.parametrize("flow_id", PARITY_FLOW_IDS)
def test_vendored_warehouse_flows_match_old_allokering_app(flow_id: str):
    legacy_flows = _load_legacy_flows()
    files, params = _scenario_payloads()[flow_id]

    old_result = legacy_flows.FLOW_BY_ID[flow_id]["handler"](dict(files), dict(params))
    new_result = new_flows.FLOW_BY_ID[flow_id]["handler"](dict(files), dict(params))

    _assert_results_equal(flow_id, old_result, new_result)
