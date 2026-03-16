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


def load_total_stats(base_dir, db_path="fantasy.db"):
    """Load season_stats.xlsx and Draft_stats/combined.xlsx into the database."""
    conn = sqlite3.connect(db_path)

    # ── season_stats ──────────────────────────────────────────────────────────
    season_path = os.path.join(base_dir, "Total_stats", "season_stats.xlsx")
    if os.path.exists(season_path):
        ss = pd.read_excel(season_path, engine="openpyxl")
        # Keep only the expected columns (the file already has clean names)
        expected_ss = [
            "player", "season", "team", "pos", "age", "games", "games_started",
            "pass_cmp", "pass_att", "pass_yds", "pass_td", "pass_int",
            "pass_rate", "pass_ypa", "pass_ypg", "pass_cmp_pct",
            "pass_4qc", "pass_gwd", "rec_tgt", "rec_rec", "rec_yds",
            "rec_td", "rec_ypg", "rec_ypr", "rec_ctch_pct", "rec_first_downs",
            "rush_att", "rush_yds", "rush_td", "rush_ypg", "rush_ypa",
            "rush_first_downs",
        ]
        for col in expected_ss:
            if col not in ss.columns:
                ss[col] = None
        ss = ss[[c for c in expected_ss if c in ss.columns]]
        # Filter garbage header rows
        ss = ss[ss["player"] != "Player"]
        ss = ss[ss["player"].notna()]
        # Convert numerics
        num_cols = [c for c in ss.columns if c not in ("player", "team", "pos")]
        for col in num_cols:
            ss[col] = pd.to_numeric(ss[col], errors="coerce")
        ss.drop_duplicates(subset=["player", "season", "team"], inplace=True)
        ss.to_sql("season_stats", conn, if_exists="replace", index=False)
        print(f"season_stats: {len(ss)} rows loaded.")
    else:
        print(f"WARNING: {season_path} not found, skipping season_stats.")

    # ── draft ─────────────────────────────────────────────────────────────────
    draft_path = os.path.join(base_dir, "Total_stats", "Draft_stats", "combined.xlsx")
    if os.path.exists(draft_path):
        raw = pd.read_excel(draft_path, header=[0, 1], engine="openpyxl")
        # Flatten multi-index using only the first level
        raw.columns = [str(c[0]).strip() for c in raw.columns]

        # Map to clean names using positional column names from the first level
        col_map = {
            "Unnamed: 0_level_0 Rnd": "draft_round",
            "Unnamed: 1_level_0 Pick": "draft_pick",
            "Unnamed: 2_level_0 Tm": "draft_team",
            "Unnamed: 3_level_0 Player": "player",
            "Unnamed: 4_level_0 Pos": "pos",
            "Unnamed: 6_level_0 To": "to_year",
            "Misc AP1": "all_pro",
            "Misc PB": "pro_bowls",
            "Approx Val wAV": "career_wav",
            "Unnamed: 27_level_0 College/Univ": "college_a",
            "Unnamed: 26_level_0 College/Univ": "college_b",
            "draft_year": "draft_year",
        }
        raw.rename(columns=col_map, inplace=True)

        # Coalesce college from both possible columns
        if "college_a" in raw.columns and "college_b" in raw.columns:
            raw["college"] = raw["college_a"].combine_first(raw["college_b"])
        elif "college_a" in raw.columns:
            raw["college"] = raw["college_a"]
        elif "college_b" in raw.columns:
            raw["college"] = raw["college_b"]
        else:
            raw["college"] = None

        # Strip " HOF" suffix from player names
        if "player" in raw.columns:
            raw["player"] = raw["player"].astype(str).str.replace(r"\s+HOF$", "", regex=True).str.strip()

        # Remove header-repeat rows
        raw = raw[raw["player"] != "Player"]
        raw = raw[raw["player"].notna()]
        raw = raw[raw["player"] != "nan"]

        # Convert numerics
        for col in ["draft_round", "draft_pick", "all_pro", "pro_bowls", "career_wav", "draft_year"]:
            if col in raw.columns:
                raw[col] = pd.to_numeric(raw[col], errors="coerce")

        # Remove rows with null draft_round (not real draft picks)
        raw = raw[raw["draft_round"].notna()]

        # Keep only the desired columns
        keep_cols = ["player", "draft_round", "draft_pick", "draft_team", "pos",
                     "all_pro", "pro_bowls", "career_wav", "college", "draft_year"]
        keep_cols = [c for c in keep_cols if c in raw.columns]
        draft = raw[keep_cols].copy()
        draft.drop_duplicates(subset=["player", "draft_year"], inplace=True)
        draft.to_sql("draft", conn, if_exists="replace", index=False)
        print(f"draft: {len(draft)} rows loaded.")
    else:
        print(f"WARNING: {draft_path} not found, skipping draft.")

    conn.close()


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
