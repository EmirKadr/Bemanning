import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.json"

_cache: dict | None = None
_mtime: float = 0.0


def get_config() -> dict:
    global _cache, _mtime
    mt = CONFIG_PATH.stat().st_mtime
    if _cache is None or mt != _mtime:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            _cache = json.load(f)
        _mtime = mt
    return _cache


def invalidate():
    global _cache, _mtime
    _cache = None
    _mtime = 0.0
