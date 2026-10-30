"""Start Skyline Vector in its own Windows game window.

This keeps the local FastAPI server private to the game and opens the Cesium
renderer inside Windows WebView2 instead of a normal browser tab.
"""

from __future__ import annotations

import sys
import threading
import time
import urllib.request

import uvicorn

from cesium_backend.app import create_app


HOST = "127.0.0.1"
# Keep this separate from `python run.py`, which uses port 8000 for the browser build.
PORT = 8001
GAME_URL = f"http://{HOST}:{PORT}"


def run_server(server: uvicorn.Server) -> None:
    """Run the local game API in the background."""
    server.run()


def server_is_ready() -> bool:
    """Return True after the game page is available."""
    try:
        with urllib.request.urlopen(GAME_URL, timeout=0.5) as response:
            return response.status == 200
    except OSError:
        return False


def wait_for_server() -> bool:
    """Give FastAPI a few seconds to start without freezing the window."""
    end_time = time.monotonic() + 10
    while time.monotonic() < end_time:
        if server_is_ready():
            return True
        time.sleep(0.1)
    return False


def main() -> int:
    try:
        import webview
    except ModuleNotFoundError:
        print("pywebview is missing. Run: python -m pip install -r requirements.txt")
        return 1

    config = uvicorn.Config(create_app(), host=HOST, port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=run_server, args=(server,), daemon=True)
    thread.start()

    if not wait_for_server():
        print("Skyline Vector could not start its local game server.")
        server.should_exit = True
        return 1

    webview.create_window(
        "Skyline Vector",
        GAME_URL,
        width=1600,
        height=950,
        min_size=(1100, 700),
        background_color="#061017",
    )

    try:
        # Edge WebView2 gives Cesium the modern GPU/WebGL renderer it needs.
        webview.start(gui="edgechromium", debug=False)
    finally:
        server.should_exit = True

    return 0


if __name__ == "__main__":
    sys.exit(main())
