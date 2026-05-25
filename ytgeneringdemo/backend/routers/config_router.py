import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.config_cache import CONFIG_PATH, get_config as _cached_config, invalidate as _invalidate_cache

router = APIRouter()


def write_config(data: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    _invalidate_cache()


class ConfigPatch(BaseModel):
    orderstop: Optional[str] = None
    agency_gap: Optional[int] = None


@router.get("/config")
def get_config():
    cfg = _cached_config()
    return {
        "orderstop": cfg.get("orderstop"),
        "agency_gap": cfg.get("agency_gap"),
    }


@router.patch("/config")
def patch_config(body: ConfigPatch):
    try:
        cfg = _cached_config()
        updated = {**cfg}
        if body.orderstop is not None:
            updated["orderstop"] = body.orderstop
        if body.agency_gap is not None:
            updated["agency_gap"] = body.agency_gap
        write_config(updated)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
