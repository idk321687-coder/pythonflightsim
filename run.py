"""Local development entry point for the Cesium flight simulator."""

from __future__ import annotations

import uvicorn


if __name__ == "__main__":
    uvicorn.run("cesium_backend.app:create_app", factory=True, host="127.0.0.1", port=8000, reload=True)
