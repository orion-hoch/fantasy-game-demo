"""Shared player-name search across all game surfaces."""

from __future__ import annotations

import sqlite3

from name_utils import normalize_name


_PLAYER_TABLES_CACHE: dict[str, tuple[str, ...]] = {}


def _table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]


def _table_has_player_column(conn: sqlite3.Connection, table_name: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(str(row[1]).lower() == "player" for row in rows)


def _tables_for_sport(conn: sqlite3.Connection, sport: str) -> tuple[str, ...]:
    key = "nba" if sport == "nba" else "nfl"
    cached = _PLAYER_TABLES_CACHE.get(key)
    if cached is not None:
        return cached

    tables: list[str] = []
    for table_name in _table_names(conn):
        is_nba_table = table_name.startswith("nba_")
        if key == "nba" and not is_nba_table:
            continue
        if key == "nfl" and is_nba_table:
            continue
        if _table_has_player_column(conn, table_name):
            tables.append(table_name)

    result = tuple(tables)
    _PLAYER_TABLES_CACHE[key] = result
    return result


def all_players(conn: sqlite3.Connection, sport: str) -> list[str]:
    """Return all distinct player names for the selected sport."""
    players: set[str] = set()
    for table_name in _tables_for_sport(conn, sport):
        rows = conn.execute(
            f"SELECT DISTINCT player FROM {table_name} WHERE player IS NOT NULL AND TRIM(player) != ''"
        ).fetchall()
        for row in rows:
            name = row[0]
            if isinstance(name, str) and name.strip():
                players.add(name.strip())
    return sorted(players)


def search_players(conn: sqlite3.Connection, sport: str, query: str) -> list[str]:
    """Search the full sport database player pool (no gameplay filtering)."""
    key = normalize_name(query)
    players = all_players(conn, sport)
    if not key:
        return players

    starts: list[str] = []
    contains: list[str] = []
    for player in players:
        nk = normalize_name(player)
        if nk.startswith(key):
            starts.append(player)
        elif key in nk:
            contains.append(player)
    return starts + contains
