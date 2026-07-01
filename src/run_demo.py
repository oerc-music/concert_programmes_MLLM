"""
run_demo.py
============
Single entry point for the GUI demo: starts the
local FastAPI server and opens it in your default browser.

Run from this repo's root:
    python src/run_demo.py

Everything stays on your machine except image data sent to Google Gemini
when you press Run inside the app -- see README.md's "Privacy and data
handling" section.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Make sibling modules (server.py, annotate.py, ...) importable as plain
# top-level modules regardless of the current working directory this is
# launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent))

HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def _find_open_port(host: str, start_port: int, attempts: int = 20) -> int:
    for port in range(start_port, start_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"Could not find an open port near {start_port} on {host}.")


def _open_browser_when_ready(url: str, host: str, port: int) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.2)
    webbrowser.open(url)


def main() -> None:
    try:
        import uvicorn
    except ImportError:
        sys.exit(
            "Dependencies are not installed yet.\n"
            "Install them with:  pip install -r requirements.txt\n"
            "Then run:           python src/run_demo.py"
        )

    import server  # imported after sys.path is set up above

    port = _find_open_port(HOST, DEFAULT_PORT)
    url = f"http://{HOST}:{port}"

    print("=" * 60)
    print(" GUI Demo — MLLM-Assisted Concert Programme Metadata Extraction (DLfM 2026)")
    print("=" * 60)
    print(f"\n  Opening {url} in your browser...")
    print("  Press Ctrl+C here to stop the server.\n")

    threading.Thread(target=_open_browser_when_ready, args=(url, HOST, port), daemon=True).start()

    uvicorn.run(server.app, host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
