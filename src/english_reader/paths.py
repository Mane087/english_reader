"""Locations for the files the app generates at runtime.

Audio used to be written next to the source modules, which breaks once the
package is installed (or frozen into a read-only bundle). These helpers put
it in the per-user data directory instead.
"""

import os
import sys
from pathlib import Path


APP_DIR_NAME = "english-reader"


def data_dir() -> Path:
    """Per-user directory for generated audio, created on first use."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"

    else:
        base = Path(
            os.environ.get("XDG_DATA_HOME")
            or Path.home() / ".local" / "share"
        )

    directory = base / APP_DIR_NAME
    directory.mkdir(parents=True, exist_ok=True)

    return directory


def data_file(name: str) -> Path:
    return data_dir() / name
