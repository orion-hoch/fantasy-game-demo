#!/usr/bin/env python3
"""
assign_player_ids.py

Assigns Basketball-Reference IDs to NBA players and Pro-Football-Reference
IDs to NFL players using the formula, without HTTP probing (both sites block
server-side requests, but browser <img> tags load them fine).

Formula:
  NBA (BBRef): [first5_last][first2_first][2-digit 1-indexed]
    e.g. Stephen Curry → curryst01
  NFL (PFR):   [Cap-first4_last][Cap-first2_first][2-digit 0-indexed]
    e.g. Nick Chubb → ChubNi00

Disambiguation strategy:
  - For NBA: 4142 verified IDs already exist in nba_player_ids.
    For a new player, start at 01 and increment until the candidate
    does not already exist in the table.
  - For NFL: same — start at 00, increment past any collisions.
  - Name mismatches (accents, suffixes) are resolved by normalizing both
    sides and doing a fuzzy match before generating a new ID.

Run:
  python assign_player_ids.py [--nba-only | --nfl-only]
"""

import argparse
import re
import sqlite3
import unicodedata

DB = "data/fantasy.db"


# ─── Name utilities ────────────────────────────────────────────────────────

def strip_accents(text: str) -> str:
    """'Dončić' → 'Doncic'"""
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def normalize_for_match(name: str) -> str:
    """Lowercase, strip accents, drop non-alpha + common suffixes.
    Used for fuzzy matching names across data sources."""
    name = strip_accents(name).lower()
    name = re.sub(r"\b(jr\.?|sr\.?|ii+|iv|v)\b", "", name)
    name = re.sub(r"[^a-z\s]", "", name)
    return re.sub(r"\s+", " ", name).strip()


def alpha_only(text: str) -> str:
    """Lowercase alpha only. Used for BBRef (all-lowercase IDs)."""
    return re.sub(r"[^a-z]", "", strip_accents(text).lower())


def alpha_keep_case(text: str) -> str:
    """Strip non-alpha but preserve original capitalization.
    Used for PFR IDs which mirror the name's natural casing.
    'LaPorta' → 'LaPorta',  'O\\'Brien' → 'OBrien',  'McDonald' → 'McDonald'"""
    return re.sub(r"[^a-zA-Z]", "", strip_accents(text))


def split_name(player: str):
    """Split 'Nick Chubb' → ('Nick', 'Chubb').
    Multi-word last names stay joined: 'Karl-Anthony Towns' → ('Karl-Anthony','Towns')"""
    parts = player.strip().split()
    if len(parts) == 1:
        return "", parts[0]
    return parts[0], " ".join(parts[1:])


# ─── ID generators ─────────────────────────────────────────────────────────

def bbref_base(player: str) -> str:
    """'Stephen Curry' → 'curryst'"""
    first, last = split_name(player)
    return alpha_only(last)[:5] + alpha_only(first)[:2]


def pfr_base(player: str) -> str:
    """PFR preserves the name's original internal capitalization.
    'Nick Chubb'  → 'ChubNi'
    'Sam LaPorta' → 'LaPoSa'  (capital P preserved from LaPorta)
    'Trey McBride'→ 'McBrTr'  (capital B preserved from McBride)
    'Ken O\\'Brien'→ 'OBriKe'  (capital B preserved after stripping apostrophe)
    """
    first, last = split_name(player)
    lp = alpha_keep_case(last)[:4]   # preserve internal caps in last name
    fp = alpha_keep_case(first)[:2]  # first 2 of first name (only 2 chars, caps usually irrelevant)
    # Ensure the first character of each segment is uppercase
    lp = (lp[0].upper() + lp[1:]) if lp else ""
    fp = (fp[0].upper() + fp[1:]) if fp else ""
    return lp + fp


def next_bbref_id(player: str, taken: set) -> str:
    """Return lowest bbref_id not already in `taken`."""
    base = bbref_base(player)
    n = 1
    while True:
        cand = f"{base}{n:02d}"
        if cand not in taken:
            return cand
        n += 1


def next_pfr_id(player: str, taken: set) -> str:
    """Return lowest pfr_id not already in `taken`."""
    base = pfr_base(player)
    n = 0
    while True:
        cand = f"{base}{n:02d}"
        if cand not in taken:
            return cand
        n += 1


# ─── NBA ───────────────────────────────────────────────────────────────────

def assign_nba_ids(conn: sqlite3.Connection):
    print("\n── NBA ──────────────────────────────────────────────────────")

    # All existing ID rows
    existing = conn.execute(
        "SELECT bbref_name, nba_id, bbref_id FROM nba_player_ids"
    ).fetchall()

    # Set of all currently-assigned bbref_ids (for collision avoidance)
    taken_ids: set = {row[2] for row in existing if row[2]}

    # Normalized lookup: norm_key → (bbref_name, nba_id, bbref_id)
    norm_lookup: dict = {}
    for bbref_name, nba_id, bbref_id in existing:
        key = normalize_for_match(bbref_name)
        if key not in norm_lookup:
            norm_lookup[key] = (bbref_name, nba_id, bbref_id)

    # Players already mapped with a real ID (exact name + non-null bbref_id)
    mapped_with_id: set = {row[0] for row in existing if row[2]}
    # Players in table but missing bbref_id
    null_id_rows: set = {row[0] for row in existing if not row[2]}

    # All nba_stats players
    all_stats = [
        row[0] for row in conn.execute("SELECT DISTINCT player FROM nba_stats")
    ]

    # Unresolved = not in table at all, OR in table but bbref_id is NULL
    unresolved = [p for p in all_stats if p not in mapped_with_id]
    print(f"Total players in nba_stats: {len(all_stats)}")
    print(f"Already have exact ID match: {len(mapped_with_id)}")
    print(f"Need resolution: {len(unresolved)} ({len(null_id_rows)} have NULL id in table)")

    norm_matched = 0
    generated = 0
    new_rows = []

    for player in unresolved:
        key = normalize_for_match(player)

        if key in norm_lookup and norm_lookup[key][2]:
            # Fuzzy name match with a verified ID — reuse it
            _, nba_id, bbref_id = norm_lookup[key]
            new_rows.append((player, nba_id, bbref_id))
            norm_matched += 1
        else:
            # No match or matched entry also has NULL — generate formula ID
            new_id = next_bbref_id(player, taken_ids)
            taken_ids.add(new_id)
            new_rows.append((player, None, new_id))
            generated += 1

    for bbref_name, nba_id, bbref_id in new_rows:
        if bbref_name in null_id_rows:
            # Row exists but bbref_id is NULL — UPDATE it
            conn.execute(
                "UPDATE nba_player_ids SET nba_id=?, bbref_id=? WHERE bbref_name=?",
                (nba_id, bbref_id, bbref_name),
            )
        else:
            conn.execute(
                "INSERT OR IGNORE INTO nba_player_ids (bbref_name, nba_id, bbref_id) "
                "VALUES (?, ?, ?)",
                (bbref_name, nba_id, bbref_id),
            )
    conn.commit()

    print(f"Resolved by normalized name match: {norm_matched}")
    print(f"Generated new formula IDs:         {generated}")
    print(f"Total new rows inserted:           {len(new_rows)}")

    # Show a sample of generated IDs
    print("\nSample generated IDs:")
    for player, _, bbref_id in [r for r in new_rows if r[1] is None][:15]:
        print(f"  {player:30s} → {bbref_id}")


# ─── NFL ───────────────────────────────────────────────────────────────────

def assign_nfl_ids(conn: sqlite3.Connection, recalculate: bool = False):
    print("\n── NFL ──────────────────────────────────────────────────────")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS nfl_player_ids (
            pfr_name TEXT PRIMARY KEY,
            pfr_id   TEXT
        )
    """)
    conn.commit()

    if recalculate:
        print("Recalculating all NFL IDs (--recalculate-nfl)...")
        conn.execute("DELETE FROM nfl_player_ids")
        conn.commit()

    # Already done
    already: set = {
        row[0] for row in conn.execute("SELECT pfr_name FROM nfl_player_ids")
    }
    taken_ids: set = {
        row[0] for row in conn.execute(
            "SELECT pfr_id FROM nfl_player_ids WHERE pfr_id IS NOT NULL"
        )
    }

    all_players = [
        row[0] for row in conn.execute("SELECT DISTINCT player FROM stats")
    ]
    todo = [p for p in all_players if p not in already]

    print(f"Total NFL players: {len(all_players)}")
    print(f"Already assigned:  {len(already)}")
    print(f"Need assignment:   {len(todo)}")

    new_rows = []
    for player in todo:
        pfr_id = next_pfr_id(player, taken_ids)
        taken_ids.add(pfr_id)
        new_rows.append((player, pfr_id))

    conn.executemany(
        "INSERT OR IGNORE INTO nfl_player_ids (pfr_name, pfr_id) VALUES (?, ?)",
        new_rows,
    )
    conn.commit()

    print(f"Assigned {len(new_rows)} new PFR IDs")

    print("\nSample generated IDs:")
    for player, pfr_id in new_rows[:15]:
        print(f"  {player:30s} → {pfr_id}")


# ─── Entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nba-only", action="store_true")
    parser.add_argument("--nfl-only", action="store_true")
    parser.add_argument("--recalculate-nfl", action="store_true",
                        help="Wipe and regenerate all NFL PFR IDs (use after formula fixes)")
    args = parser.parse_args()

    conn = sqlite3.connect(DB)
    try:
        if not args.nfl_only:
            assign_nba_ids(conn)
        if not args.nba_only:
            assign_nfl_ids(conn, recalculate=args.recalculate_nfl)
    finally:
        conn.close()

    print("\nDone. Re-run safely — already-resolved players are skipped.")


if __name__ == "__main__":
    main()
