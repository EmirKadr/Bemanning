"""QWebEngine setup for the desktop shell."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView

from core.app_info import APP_NAME


def create_web_view(parent=None) -> QWebEngineView:
    view = QWebEngineView(parent)

    app_data_dir = Path(
        QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
    )
    app_data_dir.mkdir(parents=True, exist_ok=True)

    profile = QWebEngineProfile(f"{APP_NAME.lower()}-profile", view)
    profile.setPersistentStoragePath(str(app_data_dir / "browser-profile"))
    profile.setCachePath(str(app_data_dir / "browser-cache"))
    profile.setPersistentCookiesPolicy(
        QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
    )

    page = QWebEnginePage(profile, view)
    view.setPage(page)

    settings = view.settings()
    settings.setAttribute(
        QWebEngineSettings.WebAttribute.JavascriptEnabled,
        True,
    )
    settings.setAttribute(
        QWebEngineSettings.WebAttribute.LocalStorageEnabled,
        True,
    )
    settings.setAttribute(
        QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls,
        True,
    )
    return view
