import pandas as pd
import sqlite3
import glob
import os

COLUMN_MAP = {
    "Unnamed: 0_level_0 Rk": "rk",
    "Unnamed: 1_level_0 Player": "player",
    "Unnamed: 2_level_0 PPR": "ppr",
    "Unnamed: 3_level_0 Season": "season",
    "Unnamed: 4_level_0 Age": "age",
    "Unnamed: 5_level_0 Team": "team",
    "Unnamed: 6_level_0 G": "games",
    "Unnamed: 7_level_0 GS": "games_started",
    "Fantasy FantPt": "fantasy_pts",
    "Fantasy PPR": "fantasy_ppr",
    "Fantasy per Game FantPt": "fantasy_pts_per_game",
    "Fantasy per Game PPR/G": "ppr_per_game",
    "Unnamed: 12_level_0 Pos": "pos",
}

POS_NORM = {
    "QB": "QB",
    "RB": "RB", "FB": "RB", "HB": "RB", "LH": "RB", "RH": "RB",
    "BB": "RB", "WB": "RB", "RHB": "RB", "LHB": "RB",
    "WR": "WR", "FL": "WR", "SE": "WR", "LE": "WR", "RE": "WR",
    "TE": "TE",
}


def normalize_pos(pos):
    if not isinstance(pos, str):
        return pos
    primary = pos.split("/")[0].strip()
    return POS_NORM.get(primary, pos)


# Franchise relocations — old code → current code
TEAM_MAP = {
    "CRD": "ARI", "CHR": "ARI", "PHO": "ARI",   # Cardinals
    "RAM": "LAR", "STL": "LAR",                   # Rams
    "RAI": "LVR", "OAK": "LVR",                   # Raiders
    "SDG": "LAC",                                  # Chargers
    # HOU→TEN handled below (season-dependent; Oilers ≤1996, Texans 2002+)
    # BAL stays BAL (Colts + Ravens share the city/abbreviation)
}

# Teams with no current NFL franchise — excluded entirely
DEFUNCT_TEAMS = {"BCL", "BDA", "BKN", "BOS", "NYB", "NYT", "NYY", "DTX"}


def normalize_team(team, season):
    if not isinstance(team, str):
        return team
    # Houston Oilers (through 1996) → Tennessee Titans
    if team == "HOU" and pd.notna(season) and season <= 1996:
        return "TEN"
    return TEAM_MAP.get(team, team)


def load_folder(folder):
    combined_path = os.path.join(folder, "combined.xlsx")

    if os.path.exists(combined_path):
        df = pd.read_excel(combined_path, engine="openpyxl")
    else:
        files = [
            f for f in
            glob.glob(os.path.join(folder, "*.xlsx")) + glob.glob(os.path.join(folder, "*.xls"))
            if os.path.abspath(f) != os.path.abspath(combined_path)
        ]
        if not files:
            return pd.DataFrame()
        dfs = []
        for f in files:
            try:
                engine = "xlrd" if f.endswith(".xls") else "openpyxl"
                df = pd.read_excel(f, engine=engine)
            except Exception:
                df = pd.read_html(f)[0]
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [" ".join(str(c) for c in col).strip() for col in df.columns]
            dfs.append(df)
        df = pd.concat(dfs, ignore_index=True)

    df.rename(columns=COLUMN_MAP, inplace=True)
    if "player" in df.columns:
        df = df[df["player"] != "Player"]
    print(f"  {folder}: {len(df)} rows")
    return df


def build_db(folders, db_path="fantasy.db"):
    conn = sqlite3.connect(db_path)
    all_dfs = []
    for folder in folders:
        df = load_folder(folder)
        if not df.empty:
            all_dfs.append(df)
    if not all_dfs:
        print("No data loaded.")
        return conn

    combined = pd.concat(all_dfs, ignore_index=True)

    numeric_cols = ["ppr", "season", "age", "games", "games_started",
                    "fantasy_pts", "fantasy_ppr", "fantasy_pts_per_game", "ppr_per_game"]
    for col in numeric_cols:
        if col in combined.columns:
            combined[col] = pd.to_numeric(combined[col], errors="coerce")

    # Drop multi-team rows (traded mid-season, e.g. "CIN,HOU")
    combined = combined[~combined["team"].astype(str).str.contains(",", na=False)]

    # Normalize franchise relocations
    combined["team"] = combined.apply(
        lambda r: normalize_team(r["team"], r.get("season")), axis=1
    )

    # Drop defunct/pre-merger teams
    combined = combined[~combined["team"].isin(DEFUNCT_TEAMS)]

    # Normalize archaic position codes to modern equivalents
    if "pos" in combined.columns:
        combined["pos"] = combined["pos"].apply(normalize_pos)
    combined = combined[combined["pos"].isin(["QB", "RB", "WR", "TE"])]

    combined.drop_duplicates(subset=["player", "season", "team"], inplace=True)
    combined.to_sql("stats", conn, if_exists="replace", index=False)
    print(f"Total: {len(combined)} rows loaded into SQLite.")
    return conn
