"""Offline and startup error view for the desktop client."""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ErrorView(QWidget):
    retry_requested = pyqtSignal()
    open_browser_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self._title = QLabel("Kunde inte ansluta till flow")
        self._title.setStyleSheet("font-size: 22px; font-weight: 700;")

        self._message = QLabel(
            "Kontrollera internetanslutningen eller att den centrala servern är igång."
        )
        self._message.setWordWrap(True)
        self._message.setStyleSheet("font-size: 14px; color: #4b5563;")

        retry_button = QPushButton("Försök igen")
        retry_button.clicked.connect(self.retry_requested.emit)

        browser_button = QPushButton("Öppna i webbläsare")
        browser_button.clicked.connect(self.open_browser_requested.emit)
        browser_button.setStyleSheet(
            "QPushButton { background: #e5e7eb; color: #111827; }"
        )

        button_row = QHBoxLayout()
        button_row.addWidget(retry_button)
        button_row.addWidget(browser_button)
        button_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(14)
        layout.addWidget(self._title)
        layout.addWidget(self._message)
        layout.addLayout(button_row)
        layout.addStretch(1)

    @property
    def message_text(self) -> str:
        return self._message.text()

    def set_message(self, message: str) -> None:
        self._message.setText(message)
