"""Pytest path setup for tests that import the legacy game engines.

The legacy engines live in ``<repo>/legacy`` and are imported by bare module
name (e.g. ``import lobby_store``), mirroring how the FastAPI backend loads them
via ``backend/src/legacy/bridge.py``. Put that directory on sys.path so the
root-level tests can import them.
"""

import sys
from pathlib import Path

LEGACY_DIR = Path(__file__).resolve().parent / "legacy"
if str(LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(LEGACY_DIR))
