"""Helpers for importing legacy project modules from the strangler backend."""

from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def ensure_repo_on_path() -> Path:
    """Put the repo root and the legacy engine dir on sys.path.

    Legacy game engines live in ``<repo>/legacy`` and import each other with
    bare module names (e.g. ``import session_store``), so that directory must be
    importable. The repo root stays on the path for data/quiz lookups.
    """
    root = repo_root()
    legacy_dir = root / "legacy"
    for path in (str(legacy_dir), str(root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    return root


REPO_ROOT = ensure_repo_on_path()
