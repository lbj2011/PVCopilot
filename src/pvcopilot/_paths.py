"""Locations of packaged data and the per-user cache."""
from __future__ import annotations

import os
import sys
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
DATA_DIR = PKG_DIR / "data"
EXAMPLES_DIR = DATA_DIR / "examples"
ASSETS_DIR = PKG_DIR / "app" / "assets"


def data_path(name: str) -> Path:
    return DATA_DIR / name


def example_path(name: str) -> Path:
    return EXAMPLES_DIR / name


def user_cache_dir() -> str:
    """Writable per-user directory (the install dir may be read-only)."""
    d = os.environ.get("PVCOPILOT_CACHE_DIR")
    if not d:
        if sys.platform == "darwin":
            d = Path.home() / "Library" / "Caches" / "pvcopilot"
        elif os.name == "nt":
            d = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "pvcopilot" / "cache"
        else:
            d = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "pvcopilot"
    os.makedirs(d, exist_ok=True)
    return str(d)
