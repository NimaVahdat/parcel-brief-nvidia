"""Resolve the data directories the builder reads/writes.

`specs/` (bundled few-shot + demo specs) ships inside the package. Generated
textures and renders go to a writable data dir — `massing-generator/data/` by
default (gitignored), overridable via env, with a temp-dir fallback so the
engine still works from a read-only install.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_PKG = Path(__file__).resolve().parent  # .../massing_generator/builder

# committed, read-only: the few-shot example + demo specs
SPECS_DIR = _PKG / "specs"


def _data_root() -> Path:
    env = os.getenv("MASSING_DATA_DIR")
    if env:
        return Path(env)
    # _PKG.parents: [0]=massing_generator, [1]=src, [2]=massing-generator
    return _PKG.parents[2] / "data"


def _writable(p: Path) -> Path:
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".write_test"
        probe.write_text("ok")
        probe.unlink()
        return p
    except OSError:
        fallback = Path(tempfile.gettempdir()) / "massing_generator"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


DATA_DIR = _writable(_data_root())
TEXTURES_DIR = Path(os.getenv("MASSING_TEXTURES_DIR") or (DATA_DIR / "textures"))
OUTPUT_DIR = Path(os.getenv("MASSING_OUTPUT_DIR") or (DATA_DIR / "renders"))


def ensure_dirs() -> None:
    TEXTURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
