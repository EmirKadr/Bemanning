"""Health checks for the central Bemanning backend."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

import requests

from core.app_info import SERVER_BASE_URL


@dataclass(frozen=True)
class HealthInfo:
    status: str
    environment: str = ""


class HealthCheckError(RuntimeError):
    """Raised when the central backend cannot be reached or is unhealthy."""


def build_health_url(base_url: str = SERVER_BASE_URL) -> str:
    return urljoin(base_url.rstrip("/") + "/", "api/health")


def check_server_health(
    base_url: str = SERVER_BASE_URL,
    timeout: int = 8,
    session=None,
) -> HealthInfo:
    http = session or requests
    url = build_health_url(base_url)
    try:
        response = http.get(
            url,
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise HealthCheckError(str(exc)) from exc

    try:
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise HealthCheckError(str(exc)) from exc

    status = str(data.get("status") or "").lower()
    if status != "ok":
        raise HealthCheckError("Servern svarade, men health endpoint returnerade inte ok.")

    return HealthInfo(
        status=str(data.get("status") or "ok"),
        environment=str(data.get("environment") or ""),
    )
