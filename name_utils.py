"""
name_utils.py — Shared player name normalization for search bars.

normalize_name() converts a player name (or search query) into a
canonical key used for fuzzy matching:
  - Unicode diacritics stripped  (Jokić → jokic)
  - Periods removed              (A.J. → aj)
  - Apostrophes removed          (De'Aaron → deaaron)
  - Hyphens kept as-is           (so "Al-Farouq" still matches)
  - Lowercased, whitespace collapsed
"""

import unicodedata


def normalize_name(text: str) -> str:
    if not text:
        return ""
    # Decompose Unicode (NFD) then drop combining characters (accents, etc.)
    nfd = unicodedata.normalize("NFD", text)
    ascii_only = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    # Remove periods and apostrophes, lowercase, collapse whitespace
    cleaned = ascii_only.replace(".", "").replace("'", "").replace("\u2019", "")
    return " ".join(cleaned.lower().split())
