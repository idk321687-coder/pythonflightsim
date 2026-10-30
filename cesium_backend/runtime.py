"""Runtime configuration kept out of browser-served source files."""

from __future__ import annotations

import os
from pathlib import Path


def read_dotenv_value(path: Path, variable: str) -> str:
    """Read one simple dotenv assignment without importing third-party code."""
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() != variable:
            continue
        return value.strip().strip('"').strip("'")
    return ""


def cesium_ion_token(project_root: Path) -> str:
    """Prefer deployment environment over the local developer dotenv file."""
    return os.getenv("CESIUM_ION_TOKEN", "").strip() or read_dotenv_value(project_root / ".env", "CESIUM_ION_TOKEN")
