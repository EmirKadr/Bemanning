import subprocess
import sys
import threading
import time
import webbrowser

URL = "http://localhost:8000"


def open_browser():
    time.sleep(1.5)
    webbrowser.open(URL)


threading.Thread(target=open_browser, daemon=True).start()
subprocess.run([sys.executable, "-m", "uvicorn", "backend.main:app", "--reload"])
