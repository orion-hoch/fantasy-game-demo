"""Helpers for importing legacy project modules from the strangler backend."""

from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def ensure_repo_on_path() -> Path:
    root = repo_root()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


REPO_ROOT = ensure_repo_on_path()
