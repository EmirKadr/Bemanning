from unittest.mock import patch

from PyQt6.QtWidgets import QWidget

from core.app_info import SERVER_BASE_URL, UPDATE_DISABLED_ENV
from desktop.app import MainWindow
from services.health_service import HealthInfo


class FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class FakeBrowser(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loadFinished = FakeSignal()
        self.loaded_urls = []

    def load(self, url):
        self.loaded_urls.append(url.toString())


class FakeHealthWorker:
    def __init__(self):
        self.healthy = FakeSignal()
        self.error = FakeSignal()
        self.finished = FakeSignal()
        self.start_called = 0
        self.running = False
        self.deleted = False

    def start(self):
        self.start_called += 1
        self.running = True

    def isRunning(self):
        return self.running

    def wait(self, *_args):
        self.running = False
        return True

    def deleteLater(self):
        self.deleted = True


class FakeUpdateCheckWorker(FakeHealthWorker):
    def __init__(self):
        super().__init__()
        self.update_available = FakeSignal()
        self.no_update = FakeSignal()


def test_startup_health_check_loads_server(qapp, monkeypatch):
    monkeypatch.setenv(UPDATE_DISABLED_ENV, "1")
    browser = FakeBrowser()
    worker = FakeHealthWorker()
    window = MainWindow(
        browser_factory=lambda parent=None: browser,
        health_worker_factory=lambda: worker,
    )

    qapp.processEvents()
    assert worker.start_called == 1

    worker.healthy.emit(HealthInfo(status="ok", environment="production"))

    assert window._stack.currentWidget() is browser
    assert browser.loaded_urls == [SERVER_BASE_URL]


def test_startup_health_error_shows_error_view(qapp, monkeypatch):
    monkeypatch.setenv(UPDATE_DISABLED_ENV, "1")
    worker = FakeHealthWorker()
    window = MainWindow(
        browser_factory=lambda parent=None: FakeBrowser(),
        health_worker_factory=lambda: worker,
    )

    qapp.processEvents()
    worker.error.emit("timeout")

    assert window._stack.currentWidget() is window._error_view
    assert "timeout" in window._error_view.message_text


def test_manual_update_check_starts_worker(qapp, monkeypatch):
    monkeypatch.setenv(UPDATE_DISABLED_ENV, "1")
    health_worker = FakeHealthWorker()
    update_worker = FakeUpdateCheckWorker()
    window = MainWindow(
        browser_factory=lambda parent=None: FakeBrowser(),
        health_worker_factory=lambda: health_worker,
        update_check_worker_factory=lambda: update_worker,
    )

    qapp.processEvents()
    window._check_for_updates(manual=True)

    assert update_worker.start_called == 1


def test_update_downloaded_runs_installer_silently(qapp, monkeypatch):
    monkeypatch.setenv(UPDATE_DISABLED_ENV, "1")
    window = MainWindow(
        browser_factory=lambda parent=None: FakeBrowser(),
        health_worker_factory=lambda: FakeHealthWorker(),
    )

    with patch("desktop.app.QProcess.startDetached", return_value=True) as start, patch(
        "desktop.app.QApplication.quit"
    ) as quit_app:
        window._on_update_downloaded(r"C:\Temp\Bemanning-Setup.exe")

    start.assert_called_once()
    installer_path, args = start.call_args.args
    assert installer_path == r"C:\Temp\Bemanning-Setup.exe"
    assert "/VERYSILENT" in args
    assert "/SUPPRESSMSGBOXES" in args
    assert "/CLOSEAPPLICATIONS" in args
    assert "/FORCECLOSEAPPLICATIONS" in args
    quit_app.assert_called_once()
