import sqlite3
import glob
import os

# Pandas is only needed for offline data-loading / ETL functions.  It takes
# ~1.3s to import, so we defer it to avoid penalizing runtime cold-starts
# (the running web app only imports `repair_db_text`, which does its own
# local import).  Offline entry-points like `build_db`, `load_folder`, etc.
# call `_ensure_pd()` at the top so `pd` is available for the rest of the
# module once any ETL function runs.
pd = None  # type: ignore[assignment]


def _ensure_pd():
    global pd
    if pd is None:
        import pandas as _pd
        pd = _pd

SUSPECT_TEXT_MARKERS = ("Ã", "Â", "â", "Ä", "Å")

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


def _repair_mojibake_text(value):
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text or not any(marker in text for marker in SUSPECT_TEXT_MARKERS):
        return text
    try:
        repaired = text.encode("latin-1").decode("utf-8")
    except Exception:
        return text
    return repaired.strip() if repaired else text


def _clean_text_columns(df, columns):
    for column in columns:
        if column in df.columns:
            df[column] = df[column].apply(_repair_mojibake_text)
    return df


def repair_db_text(db_path="fantasy.db"):
    import pandas as pd  # heavy import — only needed for this offline repair step

    conn = sqlite3.connect(db_path)
    targets = {
        "stats": ["player", "team", "pos"],
        "season_stats": ["player", "team", "pos"],
        "draft": ["player", "draft_team", "pos", "college"],
        "def_stats": ["player", "team", "pos"],
        "nba_stats": ["player", "team", "pos"],
        "nba_draft": ["player", "draft_team", "college"],
    }
    for table, columns in targets.items():
        try:
            frame = pd.read_sql_query(f"SELECT rowid, * FROM {table}", conn)
        except Exception:
            continue
        original = frame.copy()
        _clean_text_columns(frame, columns)
        if frame.equals(original):
            continue
        cleaned = frame.drop(columns=["rowid"])
        cleaned.to_sql(table, conn, if_exists="replace", index=False)
    conn.close()


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

# Players whose names collide with another player of the same name+pos.
# Maps (name, primary_team) → disambiguated display name.
PLAYER_RENAMES_BY_TEAM = {
    ("Adrian Peterson", "CHI"): "Adrian Peterson (CHI)",
    ("Kellen Winslow", "LAC"): "Kellen Winslow (LAC)",    # Sr. — entire career with SD/LAC
    ("Clay Matthews", "CLE"):  "Clay Matthews (CLE)",     # Sr. — Browns LB 1978-1993
    ("Anthony Miller", "LAC"): "Anthony Miller (LAC)",    # older WR — drafted by SD 1988
    ("Mark Clayton", "BAL"):   "Mark Clayton (BAL)",      # newer WR — drafted by BAL 2005
    ("Robert Woods", "KAN"):   "Robert Woods (KAN)",      # older WR — drafted by KC 1978
    ("Charles Johnson", "GNB"): "Charles Johnson (GNB)",  # newer WR — drafted by GB 2013
    ("Scott Miller", "MIA"):   "Scott Miller (MIA)",      # older WR — drafted by MIA 1991
    ("Mickey Shuler", "MIN"):  "Mickey Shuler (MIN)",     # Jr. — drafted by MIN 2010
    ("Golden Tate", "IND"):    "Golden Tate (IND)",       # older player — drafted by IND 1984
}

# Same for draft table — keyed by (name, draft_year).
PLAYER_RENAMES_BY_DRAFT_YEAR = {
    ("Adrian Peterson", 2002):   "Adrian Peterson (CHI)",
    ("Kellen Winslow", 1979):    "Kellen Winslow (LAC)",
    ("Clay Matthews", 1978):     "Clay Matthews (CLE)",
    ("Anthony Miller", 1988):    "Anthony Miller (LAC)",
    ("Mark Clayton", 2005):      "Mark Clayton (BAL)",
    ("Robert Woods", 1978):      "Robert Woods (KAN)",
    ("Charles Johnson", 2013):   "Charles Johnson (GNB)",
    ("Scott Miller", 1991):      "Scott Miller (MIA)",
    ("Mickey Shuler", 2010):     "Mickey Shuler (MIN)",
    ("Golden Tate", 1984):       "Golden Tate (IND)",
}


def normalize_team(team, season):
    if not isinstance(team, str):
        return team
    # Houston Oilers (through 1996) → Tennessee Titans
    if team == "HOU" and season is not None and season == season and season <= 1996:
        return "TEN"
    return TEAM_MAP.get(team, team)


def load_folder(folder):
    _ensure_pd()
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
    df = _clean_text_columns(df, ["player", "team", "pos"])
    print(f"  {folder}: {len(df)} rows")
    return df


def load_total_stats(base_dir, db_path="fantasy.db"):
    """Load season_stats.xlsx and Draft_stats/combined.xlsx into the database."""
    _ensure_pd()
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

        for (name, team), new_name in PLAYER_RENAMES_BY_TEAM.items():
            mask = (ss["player"] == name) & (ss["team"] == team)
            ss.loc[mask, "player"] = new_name

        ss = _clean_text_columns(ss, ["player", "team", "pos"])
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

        for (name, yr), new_name in PLAYER_RENAMES_BY_DRAFT_YEAR.items():
            mask = (draft["player"] == name) & (draft["draft_year"] == yr)
            draft.loc[mask, "player"] = new_name

        draft = _clean_text_columns(draft, ["player", "draft_team", "pos", "college"])
        draft.to_sql("draft", conn, if_exists="replace", index=False)
        print(f"draft: {len(draft)} rows loaded.")
    else:
        print(f"WARNING: {draft_path} not found, skipping draft.")

    conn.close()


DEF_POS_NORM = {
    "CB": "CB", "LCB": "CB", "RCB": "CB", "RDH": "CB", "LDH": "CB",
    "S": "S", "SS": "S", "FS": "S", "SAF": "S", "DB": "S", "SF": "S", "RS": "S",
    "LB": "LB", "OLB": "LB", "ILB": "LB", "MLB": "LB",
    "RILB": "LB", "LILB": "LB", "ROLB": "LB", "LOLB": "LB",
    "SLB": "LB", "WLB": "LB", "MIKE": "LB", "WILL": "LB", "SAM": "LB",
    "LLB": "LB", "RLB": "LB",
    "DE": "DE", "LDE": "DE", "RDE": "DE", "EDGE": "DE", "LE": "DE", "RE": "DE", "DL": "DE",
    "DT": "DT", "NT": "DT", "MG": "DT", "DG": "DT", "NG": "DT", "LDT": "DT", "RDT": "DT",
}

_DEF_POSITIONS_VALID = {"CB", "S", "LB", "DE", "DT"}

_INT_COL_MAP = {
    "Unnamed: 1_level_0 Player": "player",
    "Unnamed: 3_level_0 Season": "season",
    "Unnamed: 4_level_0 Age": "age",
    "Unnamed: 5_level_0 Team": "team",
    "Unnamed: 6_level_0 G": "games",
    "Unnamed: 7_level_0 GS": "games_started",
    "Def Interceptions Int": "interceptions",
    "Def Interceptions Yds": "int_yards",
    "Def Interceptions IntTD": "int_td",
    "Def Interceptions PD": "passes_defended",
    "Unnamed: 12_level_0 Pos": "pos",
}

_SACK_TACKLE_COL_MAP = {
    "Unnamed: 1_level_0 Player": "player",
    "Unnamed: 3_level_0 Season": "season",
    "Unnamed: 4_level_0 Age": "age",
    "Unnamed: 5_level_0 Team": "team",
    "Unnamed: 6_level_0 G": "games",
    "Unnamed: 7_level_0 GS": "games_started",
    "Unnamed: 8_level_0 Sk": "sacks",
    "Tackles Solo": "solo_tackles",
    "Tackles Ast": "ast_tackles",
    "Tackles Comb": "comb_tackles",
    "Tackles TFL": "tfl",
    "Tackles QBHits": "qb_hits",
    "Unnamed: 14_level_0 Pos": "pos",
}


def _load_def_folder(folder, col_map):
    """Load all XLS files from a defensive stats folder, return cleaned DataFrame."""
    _ensure_pd()
    files = glob.glob(os.path.join(folder, "*.xls"))
    if not files:
        return pd.DataFrame()
    dfs = []
    for f in files:
        try:
            df = pd.read_html(f, header=[0, 1])[0]
        except Exception:
            continue
        df.columns = [" ".join(str(c) for c in col).strip() for col in df.columns]
        df.rename(columns=col_map, inplace=True)
        if "player" in df.columns:
            df = df[df["player"] != "Player"]
            df = df[df["player"].notna()]
        dfs.append(df)
    if not dfs:
        return pd.DataFrame()
    combined = pd.concat(dfs, ignore_index=True)
    keep = [c for c in col_map.values() if c in combined.columns]
    return combined[keep].copy()


def load_defensive_stats(base_dir, db_path="fantasy.db"):
    """Load INTs, Sacks, and Tackles into the def_stats table."""
    _ensure_pd()
    conn = sqlite3.connect(db_path)
    def_base = os.path.join(base_dir, "Total_stats", "Defensive_stats")

    # ── Load each stat type ───────────────────────────────────────────────────
    ints_df = _load_def_folder(os.path.join(def_base, "Ints_stats"), _INT_COL_MAP)
    sacks_df = _load_def_folder(os.path.join(def_base, "Sacks_stats"), _SACK_TACKLE_COL_MAP)
    tackles_df = _load_def_folder(os.path.join(def_base, "Tackles_stats"), _SACK_TACKLE_COL_MAP)

    # ── Combine sacks + tackles (same columns; dedupe) ────────────────────────
    sack_tackle = pd.concat([sacks_df, tackles_df], ignore_index=True)
    num_st = ["season", "age", "games", "games_started", "sacks",
              "solo_tackles", "ast_tackles", "comb_tackles", "tfl", "qb_hits"]
    for col in num_st:
        if col in sack_tackle.columns:
            sack_tackle[col] = pd.to_numeric(sack_tackle[col], errors="coerce")
    sack_tackle.drop_duplicates(subset=["player", "season", "team"], inplace=True)

    # ── Clean INTs ────────────────────────────────────────────────────────────
    num_i = ["season", "age", "games", "games_started",
             "interceptions", "int_yards", "int_td", "passes_defended"]
    for col in num_i:
        if col in ints_df.columns:
            ints_df[col] = pd.to_numeric(ints_df[col], errors="coerce")
    ints_df.drop_duplicates(subset=["player", "season", "team"], inplace=True)

    # ── Outer merge on player/season/team ─────────────────────────────────────
    if not sack_tackle.empty and not ints_df.empty:
        merged = pd.merge(
            sack_tackle, ints_df,
            on=["player", "season", "team"],
            how="outer",
            suffixes=("", "_i"),
        )
        # Coalesce shared columns (pos, games, games_started, age)
        for col in ["pos", "games", "games_started", "age"]:
            if f"{col}_i" in merged.columns:
                merged[col] = merged[col].combine_first(merged[f"{col}_i"])
                merged.drop(columns=[f"{col}_i"], inplace=True)
    elif not sack_tackle.empty:
        merged = sack_tackle
    elif not ints_df.empty:
        merged = ints_df
    else:
        print("WARNING: No defensive stat files found.")
        conn.close()
        return

    # ── Apply team normalization ──────────────────────────────────────────────
    merged = merged[~merged["team"].astype(str).str.contains(",", na=False)]
    merged["team"] = merged.apply(
        lambda r: normalize_team(r["team"], r.get("season")), axis=1
    )
    merged = merged[~merged["team"].isin(DEFUNCT_TEAMS)]

    # ── Normalize defensive positions ─────────────────────────────────────────
    def norm_def_pos(pos):
        if not isinstance(pos, str):
            return pos
        primary = pos.split("/")[0].strip()
        return DEF_POS_NORM.get(primary, primary)

    if "pos" in merged.columns:
        merged["pos"] = merged["pos"].apply(norm_def_pos)

    merged.drop_duplicates(subset=["player", "season", "team"], inplace=True)
    merged = merged[merged["player"].notna()]
    merged = _clean_text_columns(merged, ["player", "team", "pos"])

    # Keep only actual defensive positions
    if "pos" in merged.columns:
        merged = merged[merged["pos"].isin(_DEF_POSITIONS_VALID)]

    merged.to_sql("def_stats", conn, if_exists="replace", index=False)
    print(f"def_stats: {len(merged)} rows loaded.")
    conn.close()


NBA_TEAM_MAP = {
    "NJN": "BRK", "SEA": "OKC", "NOH": "NOP", "NOK": "NOP",
    "CHH": "CHA", "CHO": "CHA", "VAN": "MEM", "WSB": "WAS",
    "NOJ": "UTA", "KCK": "SAC", "KCO": "SAC", "FTW": "DET",
    "SDC": "LAC", "SDR": "HOU", "PHW": "GSW", "SFW": "GSW",
    "MLH": "ATL", "STL": "ATL", "CAP": "WAS", "INO": "IND",
    "WSC": "WAS",
    # Historical franchises with direct modern successors
    "MNL": "LAL",  # Minneapolis Lakers → Los Angeles Lakers
    "ROC": "SAC",  # Rochester Royals → Sacramento Kings
    "CIN": "SAC",  # Cincinnati Royals → Sacramento Kings
    "TRI": "ATL",  # Tri-Cities Blackhawks → Atlanta Hawks
    "SYR": "PHI",  # Syracuse Nationals → Philadelphia 76ers
    "BUF": "LAC",  # Buffalo Braves → Los Angeles Clippers
    "BAL": "WAS",  # Baltimore Bullets → Washington Wizards
    "CHP": "WAS",  # Chicago Packers → Washington Wizards
    "CHZ": "WAS",  # Chicago Zephyrs → Washington Wizards
}

NBA_DEFUNCT_TEAMS = {
    # Truly defunct — no modern franchise successor
    "BLB", "CHS", "DNN",
    "AND", "NYN", "PIT", "PRO", "SHE", "STB", "WAT",
}

NBA_POS_NORM = {
    "C": "C", "G": "G", "F": "F",
    "G-F": "G", "F-G": "F", "F-C": "F", "C-F": "C",
}


def load_nba_stats(base_dir, db_path="fantasy.db"):
    """Load NBA single-season stats and draft stats into the database."""
    _ensure_pd()
    import glob as _glob
    conn = sqlite3.connect(db_path)

    # ── NBA season stats ──────────────────────────────────────────────────────
    season_dir = os.path.join(base_dir, "NBA_stats", "NBA_single_season_stats")
    season_files = _glob.glob(os.path.join(season_dir, "*.xls")) + \
                   _glob.glob(os.path.join(season_dir, "*.xlsx"))

    nba_dfs = []
    for f in season_files:
        try:
            df = pd.read_html(f, header=0)[0]
            nba_dfs.append(df)
        except Exception as e:
            print(f"  WARNING: could not read {f}: {e}")

    if nba_dfs:
        nba = pd.concat(nba_dfs, ignore_index=True)

        # Filter garbage rows
        nba = nba[nba["Player"].notna()]
        nba = nba[nba["Player"] != "Player"]

        # Drop rows where team contains ',' (traded mid-season)
        nba = nba[~nba["Team"].astype(str).str.contains(",", na=False)]

        # Convert numerics
        stat_cols = ["Age", "G", "PTS", "3P", "FG", "FGA", "FT", "FTA", "TRB", "AST", "STL", "BLK", "TOV"]
        for col in stat_cols:
            if col in nba.columns:
                nba[col] = pd.to_numeric(nba[col], errors="coerce").fillna(0)

        # Drop rows where games == 0
        nba = nba[nba["G"].notna() & (nba["G"] > 0)]

        # Parse season year (first 4 chars of "2008-09")
        nba["season_int"] = nba["Season"].astype(str).str[:4]
        nba["season_int"] = pd.to_numeric(nba["season_int"], errors="coerce")

        # Normalize position
        nba["pos_norm"] = nba["Pos"].apply(
            lambda p: NBA_POS_NORM.get(str(p).strip(), None) if isinstance(p, str) else None
        )
        nba = nba[nba["pos_norm"].isin(["C", "G", "F"])]

        # Map team codes
        nba["team_mapped"] = nba["Team"].apply(
            lambda t: NBA_TEAM_MAP.get(str(t).strip(), str(t).strip()) if isinstance(t, str) else t
        )

        # Drop defunct teams
        nba = nba[~nba["team_mapped"].isin(NBA_DEFUNCT_TEAMS)]

        # Compute per-game stats (kept for chain categories / hints)
        nba["pts_pg"] = (nba["PTS"] / nba["G"]).round(2)
        nba["trb_pg"] = (nba["TRB"] / nba["G"]).round(2)
        nba["ast_pg"] = (nba["AST"] / nba["G"]).round(2)

        # Fantasy score = season totals formula:
        # PTS×1 + 3PM×1 + FGM×2 + FGA×(-1) + FTM×1 + FTA×(-1) +
        # REB×1 + AST×2 + STL×4 + BLK×4 + TOV×(-2)
        nba["fantasy_score"] = (
            nba["PTS"] * 1
            + nba["3P"] * 1
            + nba["FG"] * 2
            + nba["FGA"] * -1
            + nba["FT"] * 1
            + nba["FTA"] * -1
            + nba["TRB"] * 1
            + nba["AST"] * 2
            + nba["STL"] * 4
            + nba["BLK"] * 4
            + nba["TOV"] * -2
        ).round(0).astype(int)

        # Build output dataframe
        out = pd.DataFrame({
            "player": nba["Player"],
            "season": nba["season_int"].astype("Int64"),
            "age": pd.to_numeric(nba["Age"], errors="coerce").astype("Int64"),
            "team": nba["team_mapped"],
            "games": nba["G"].astype("Int64"),
            "pts": nba["PTS"],
            "trb": nba["TRB"],
            "ast": nba["AST"],
            "threepm": nba["3P"],
            "fgm": nba["FG"],
            "fga": nba["FGA"],
            "ftm": nba["FT"],
            "fta": nba["FTA"],
            "stl": nba["STL"],
            "blk": nba["BLK"],
            "tov": nba["TOV"],
            "pos": nba["pos_norm"],
            "pts_pg": nba["pts_pg"],
            "trb_pg": nba["trb_pg"],
            "ast_pg": nba["ast_pg"],
            "fantasy_score": nba["fantasy_score"],
        })

        out.drop_duplicates(subset=["player", "season", "team"], inplace=True)
        out = out[out["player"].notna()]
        out = _clean_text_columns(out, ["player", "team", "pos"])

        out.to_sql("nba_stats", conn, if_exists="replace", index=False)
        print(f"nba_stats: {len(out)} rows loaded.")
        _seed_missing_nba_players(conn)
    else:
        print("WARNING: No NBA season stat files found.")

    # ── NBA draft stats ───────────────────────────────────────────────────────
    draft_dir = os.path.join(base_dir, "NBA_stats", "Draft_NBA_stats")


def _seed_missing_nba_players(conn):
    _ensure_pd()
    """Insert Cincinnati Royals players whose data is absent from source files.

    The source Excel files never included CIN data. CIN → SAC per NBA_TEAM_MAP.
    Stats from Basketball-Reference; STL/BLK/TOV/3PM = 0 (not tracked pre-1973).
    Fantasy score = PTS + FGM*2 - FGA + FTM - FTA + TRB + AST*2
    """
    # fmt: off
    rows = [
        # (player, season, age, team, games, pts, trb, ast, threepm, fgm, fga, ftm, fta,
        #  stl, blk, tov, pos, pts_pg, trb_pg, ast_pg, fantasy_score)

        # Oscar Robertson — Cincinnati Royals 1960-1969
        ('Oscar Robertson', 1960, 22, 'SAC', 71, 2165,  716, 690, 0,  756, 1600, 653,  794, 0, 0, 0, 'G', 30.49, 10.08,  9.72, 4032),
        ('Oscar Robertson', 1961, 23, 'SAC', 79, 2432,  985, 899, 0,  866, 1810, 700,  872, 0, 0, 0, 'G', 30.78, 12.47, 11.38, 4965),
        ('Oscar Robertson', 1962, 24, 'SAC', 80, 2264,  835, 758, 0,  825, 1593, 614,  758, 0, 0, 0, 'G', 28.30, 10.44,  9.48, 4528),
        ('Oscar Robertson', 1963, 25, 'SAC', 79, 2480,  783, 868, 0,  840, 1740, 800,  938, 0, 0, 0, 'G', 31.39,  9.91, 10.99, 4801),
        ('Oscar Robertson', 1964, 26, 'SAC', 75, 2279,  674, 861, 0,  807, 1681, 665,  793, 0, 0, 0, 'G', 30.39,  8.99, 11.48, 4480),
        ('Oscar Robertson', 1965, 27, 'SAC', 76, 2378,  586, 847, 0,  818, 1723, 742,  881, 0, 0, 0, 'G', 31.29,  7.71, 11.14, 4432),
        ('Oscar Robertson', 1966, 28, 'SAC', 79, 2412,  486, 845, 0,  838, 1699, 736,  843, 0, 0, 0, 'G', 30.53,  6.15, 10.70, 4458),
        ('Oscar Robertson', 1967, 29, 'SAC', 65, 1896,  391, 633, 0,  660, 1381, 576,  694, 0, 0, 0, 'G', 29.17,  6.02,  9.74, 3374),
        ('Oscar Robertson', 1968, 30, 'SAC', 79, 1955,  502, 772, 0,  656, 1351, 643,  767, 0, 0, 0, 'G', 24.75,  6.35,  9.77, 3838),
        ('Oscar Robertson', 1969, 31, 'SAC', 69, 1748,  422, 558, 0,  647, 1267, 454,  560, 0, 0, 0, 'G', 25.33,  6.12,  8.09, 3207),

        # Jerry Lucas — Cincinnati Royals 1963-1969
        ('Jerry Lucas', 1963, 23, 'SAC', 79, 1400, 1375, 204, 0,  545, 1035, 310,  398, 0, 0, 0, 'F', 17.72, 17.41, 2.58, 3150),
        ('Jerry Lucas', 1964, 24, 'SAC', 66, 1414, 1321, 157, 0,  558, 1121, 298,  366, 0, 0, 0, 'F', 21.42, 20.02, 2.38, 2976),
        ('Jerry Lucas', 1965, 25, 'SAC', 79, 1697, 1668, 213, 0,  690, 1523, 317,  403, 0, 0, 0, 'F', 21.48, 21.11, 2.70, 3562),
        ('Jerry Lucas', 1966, 26, 'SAC', 81, 1443, 1547, 267, 0,  576, 1256, 287,  363, 0, 0, 0, 'F', 17.81, 19.09, 3.30, 3344),
        ('Jerry Lucas', 1967, 27, 'SAC', 82, 1763, 1558, 254, 0,  705, 1358, 346,  445, 0, 0, 0, 'F', 21.50, 19.00, 3.10, 3782),
        ('Jerry Lucas', 1968, 28, 'SAC', 74, 1354, 1361, 304, 0,  555, 1007, 244,  323, 0, 0, 0, 'F', 18.30, 18.39, 4.11, 3347),
        ('Jerry Lucas', 1969, 29, 'SAC',  4,   41,   45,   9, 0,   18,   35,   5,    7, 0, 0, 0, 'F', 10.25, 11.25, 2.25,  103),

        # Jack Twyman — Cincinnati Royals 1957-1965
        ('Jack Twyman', 1957, 23, 'SAC', 72, 1237,  464, 110, 0,  465, 1028, 307,  396, 0, 0, 0, 'F', 17.18,  6.44, 1.53, 1734),
        ('Jack Twyman', 1958, 24, 'SAC', 72, 1857,  653, 209, 0,  710, 1691, 437,  558, 0, 0, 0, 'F', 25.79,  9.07, 2.90, 2536),
        ('Jack Twyman', 1959, 25, 'SAC', 75, 2338,  664, 260, 0,  870, 2063, 598,  762, 0, 0, 0, 'F', 31.17,  8.85, 3.47, 3035),
        ('Jack Twyman', 1960, 26, 'SAC', 79, 1997,  672, 225, 0,  796, 1632, 405,  554, 0, 0, 0, 'F', 25.28,  8.51, 2.85, 2930),
        ('Jack Twyman', 1961, 27, 'SAC', 80, 1831,  638, 215, 0,  739, 1542, 353,  435, 0, 0, 0, 'F', 22.89,  7.98, 2.69, 2753),
        ('Jack Twyman', 1962, 28, 'SAC', 80, 1586,  598, 214, 0,  641, 1335, 304,  375, 0, 0, 0, 'F', 19.83,  7.48, 2.68, 2488),
        ('Jack Twyman', 1963, 29, 'SAC', 68, 1083,  364, 137, 0,  447,  993, 189,  228, 0, 0, 0, 'F', 15.93,  5.35, 2.01, 1583),
        ('Jack Twyman', 1964, 30, 'SAC', 80, 1156,  383, 137, 0,  479, 1081, 198,  239, 0, 0, 0, 'F', 14.45,  4.79, 1.71, 1649),
        ('Jack Twyman', 1965, 31, 'SAC', 73,  543,  168,  60, 0,  224,  498,  95,  117, 0, 0, 0, 'F',  7.44,  2.30, 0.82,  759),

        # Wayne Embry — Cincinnati Royals 1958-1965
        ('Wayne Embry', 1958, 21, 'SAC', 66,  750,  597,  96, 0,  272,  702, 206,  314, 0, 0, 0, 'C', 11.36,  9.05, 1.45, 1273),
        ('Wayne Embry', 1959, 22, 'SAC', 73,  773,  692,  83, 0,  303,  690, 167,  325, 0, 0, 0, 'C', 10.59,  9.48, 1.14, 1389),
        ('Wayne Embry', 1960, 23, 'SAC', 79, 1137,  864, 127, 0,  458, 1015, 221,  331, 0, 0, 0, 'C', 14.39, 10.94, 1.61, 2046),
        ('Wayne Embry', 1961, 24, 'SAC', 75, 1484,  977, 182, 0,  564, 1210, 356,  516, 0, 0, 0, 'C', 19.79, 13.03, 2.43, 2583),
        ('Wayne Embry', 1962, 25, 'SAC', 76, 1411,  936, 177, 0,  534, 1165, 343,  514, 0, 0, 0, 'C', 18.57, 12.32, 2.33, 2433),
        ('Wayne Embry', 1963, 26, 'SAC', 80, 1383,  925, 113, 0,  556, 1213, 271,  417, 0, 0, 0, 'C', 17.29, 11.56, 1.41, 2287),
        ('Wayne Embry', 1964, 27, 'SAC', 74,  943,  741,  92, 0,  352,  772, 239,  371, 0, 0, 0, 'C', 12.74, 10.01, 1.24, 1668),
        ('Wayne Embry', 1965, 28, 'SAC', 80,  605,  525,  81, 0,  232,  564, 141,  234, 0, 0, 0, 'C',  7.56,  6.56, 1.01, 1099),

        # Happy Hairston — Cincinnati Royals 1964-1967
        ('Happy Hairston', 1964, 22, 'SAC', 61,  372,  295,  48, 0,  131,  351, 110,  165, 0, 0, 0, 'F',  6.10,  4.84, 0.79,  619),
        ('Happy Hairston', 1965, 23, 'SAC', 72, 1016,  516,  98, 0,  398,  814, 220,  321, 0, 0, 0, 'F', 14.11,  7.17, 1.36, 1609),
        ('Happy Hairston', 1966, 24, 'SAC', 79, 1174,  613, 105, 0,  461,  962, 252,  382, 0, 0, 0, 'F', 14.86,  7.76, 1.33, 1827),
        ('Happy Hairston', 1967, 25, 'SAC', 48,  837,  358,  72, 0,  317,  630, 203,  296, 0, 0, 0, 'F', 17.44,  7.46, 1.50, 1250),

        # Bob Boozer — Cincinnati Royals 1960-1963
        ('Bob Boozer', 1960, 23, 'SAC', 79,  666,  488, 109, 0,  250,  603, 166,  247, 0, 0, 0, 'F',  8.43,  6.18, 1.38, 1188),
        ('Bob Boozer', 1961, 24, 'SAC', 79, 1083,  804, 130, 0,  410,  936, 263,  372, 0, 0, 0, 'F', 13.71, 10.18, 1.65, 1922),
        ('Bob Boozer', 1962, 25, 'SAC', 79, 1132,  878, 102, 0,  440,  992, 252,  353, 0, 0, 0, 'F', 14.33, 11.11, 1.29, 2001),
        ('Bob Boozer', 1963, 26, 'SAC', 32,  352,  178,  33, 0,  139,  334,  74,  119, 0, 0, 0, 'F', 11.00,  5.56, 1.03,  495),
    ]
    # fmt: on
    conn.executemany(
        """INSERT OR IGNORE INTO nba_stats
           (player, season, age, team, games, pts, trb, ast, threepm, fgm, fga, ftm, fta,
            stl, blk, tov, pos, pts_pg, trb_pg, ast_pg, fantasy_score)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    print(f"Seeded {len(rows)} Cincinnati Royals player rows (→ SAC).")
    draft_files = _glob.glob(os.path.join(draft_dir, "*.xls")) + \
                  _glob.glob(os.path.join(draft_dir, "*.xlsx"))

    draft_dfs = []
    for f in draft_files:
        try:
            df = pd.read_html(f, header=[0, 1])[0]
            df.columns = [" ".join(str(c) for c in col).strip() for col in df.columns]
            draft_dfs.append(df)
        except Exception as e:
            print(f"  WARNING: could not read draft file {f}: {e}")

    if draft_dfs:
        draft = pd.concat(draft_dfs, ignore_index=True)

        # Filter garbage rows
        player_col = "Round 1 Player"
        pick_col = "Unnamed: 1_level_0 Pk"
        team_col = "Unnamed: 2_level_0 Tm"
        college_col = "Round 1 College"

        draft = draft[draft[player_col].notna()]
        draft = draft[draft[player_col] != "Player"]
        draft = draft[draft[pick_col].notna()]

        # Convert numerics
        for col in [pick_col, "Per Game PTS", "Per Game TRB", "Per Game AST", "Advanced WS"]:
            if col in draft.columns:
                draft[col] = pd.to_numeric(draft[col], errors="coerce")

        out_draft = pd.DataFrame({
            "player": draft[player_col],
            "draft_pick": pd.to_numeric(draft[pick_col], errors="coerce").astype("Int64"),
            "draft_team": draft[team_col] if team_col in draft.columns else None,
            "college": draft[college_col] if college_col in draft.columns else None,
            "pts_pg": draft["Per Game PTS"] if "Per Game PTS" in draft.columns else None,
            "trb_pg": draft["Per Game TRB"] if "Per Game TRB" in draft.columns else None,
            "ast_pg": draft["Per Game AST"] if "Per Game AST" in draft.columns else None,
            "win_shares": draft["Advanced WS"] if "Advanced WS" in draft.columns else None,
        })

        out_draft.drop_duplicates(subset=["player"], inplace=True)
        out_draft = out_draft[out_draft["player"].notna()]
        out_draft = _clean_text_columns(out_draft, ["player", "draft_team", "college"])

        out_draft.to_sql("nba_draft", conn, if_exists="replace", index=False)
        print(f"nba_draft: {len(out_draft)} rows loaded.")
    else:
        print("WARNING: No NBA draft files found.")

    conn.close()


def load_nba_allstars(db_path="fantasy.db", csv_path="NBA_AllStars.csv"):
    """Parse NBA_AllStars.csv and load into the nba_allstars table."""
    _ensure_pd()
    import re
    import unicodedata

    # Known nickname / CSV-vs-DB name mismatches
    _NAME_FIXES = {
        "Penny Hardaway":         "Anfernee Hardaway",
        "Nate Archibald":         "Tiny Archibald",
        "Micheal Ray Richardson": "Michael Ray Richardson",
        "Žydrūnas Ilgauskas":     "Zydrunas Ilgauskas",
    }

    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_csv(csv_path, encoding="utf-8")
    except Exception as e:
        print(f"WARNING: Could not read {csv_path}: {e}")
        conn.close()
        return

    # Get all player names actually in nba_stats for validation
    stats_names = set(
        r[0] for r in conn.execute("SELECT DISTINCT player FROM nba_stats").fetchall()
    )

    def clean_name(name):
        if not isinstance(name, str):
            return name
        # Strip footnote markers, HOF/active/deceased/banned symbols
        name = re.sub(r'\[[a-z]\]', '', name)
        name = name.replace('*', '').replace('^', '').replace('†', '').replace('§', '')
        name = name.strip()
        # Apply known fixes first
        if name in _NAME_FIXES:
            return _NAME_FIXES[name]
        # If still not in stats, try stripping accents
        if name not in stats_names:
            stripped = ''.join(
                c for c in unicodedata.normalize('NFD', name)
                if unicodedata.category(c) != 'Mn'
            )
            if stripped in stats_names:
                return stripped
        return name

    df['player'] = df['Player'].apply(clean_name)
    df['selections'] = pd.to_numeric(df['#'], errors='coerce').astype('Int64')
    df = df[df['player'].notna() & df['selections'].notna()]
    df = df[['player', 'selections']].drop_duplicates(subset=['player'])

    df.to_sql("nba_allstars", conn, if_exists="replace", index=False)

    # Report how many matched stats
    matched = conn.execute(
        "SELECT COUNT(DISTINCT na.player) FROM nba_allstars na "
        "JOIN nba_stats ns ON na.player = ns.player"
    ).fetchone()[0]
    print(f"nba_allstars: {len(df)} rows loaded, {matched} matched to nba_stats.")
    conn.close()


LOCKOUT_GAMES = {
    "1998-99": 50,
    "2011-12": 66,
    "2019-20": 72,
}

# Maps sportsref download file number → award name
_AWARD_FILE_MAP = {
    1: "MVP",
    2: "ABA_MVP",
    3: "ROY",
    4: "ABA_ROY",
    5: "DPOY",
    6: "6MOY",
    7: "MIP",
    8: "SMOTY",   # Twyman-Stokes Teammate of the Year
    9: "FMVP",    # Finals MVP
}


def _read_sportsref_xls(path):
    """Read a Sports Reference XLS (HTML table) and flatten MultiIndex columns."""
    _ensure_pd()
    try:
        df = pd.read_html(path)[0]
    except Exception:
        df = pd.read_excel(path, engine="xlrd")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [" ".join(str(c) for c in col).strip() for col in df.columns]
    return df


def _strip_pos_suffix(name):
    """Strip trailing position tag from All-NBA player names, e.g. 'Nikola Jokić C' → 'Nikola Jokić'."""
    import re
    if not isinstance(name, str):
        return name
    return re.sub(r"\s+[CFG]$", "", name.strip())


def load_new_nba_data(new_data_dir="new_data", db_path="fantasy.db"):
    _ensure_pd()
    """Load all supplemental NBA data from new_data/ into the database.

    Tables created/replaced:
      nba_awards          – MVP/ROY/DPOY/6MOY/MIP/FMVP/SMOTY voting results
      nba_allnba          – All-NBA 1st/2nd/3rd team selections
      nba_allrookie       – All-Rookie 1st/2nd team selections
      nba_alldefensive    – All-Defensive 1st/2nd team selections
      nba_allstar_games   – All-Star game totals per player per season
      nba_contracts       – Current player contracts (2025-26 season)
      nba_team_wins       – Team win totals per season (long format)
      nba_team_index      – Franchise all-time records
      nba_recruiting      – RSCI recruiting rankings (top-100 per draft class)
      nba_ncaa_poty       – NCAA Player of the Year award
      nba_olympic_teams   – USA Olympic basketball rosters and stats
    """
    conn = sqlite3.connect(db_path)

    # ── 1. Award voting (files 1–9) ──────────────────────────────────────────
    award_rows = []
    for fnum, award in _AWARD_FILE_MAP.items():
        path = os.path.join(new_data_dir, f"sportsref_download ({fnum}).xls")
        if not os.path.exists(path):
            continue
        df = _read_sportsref_xls(path)
        season_col = next((c for c in df.columns if "Season" in c), None)
        player_col = next((c for c in df.columns if "Player" in c), None)
        voting_col = next((c for c in df.columns if "Voting" in c), None)
        if not season_col or not player_col:
            continue

        df = df[df[player_col].notna()]
        df = df[df[player_col] != "Player"]
        df = _clean_text_columns(df, [player_col])

        for season_val, grp in df.groupby(season_col, sort=False):
            season_str = str(season_val)[:4]
            if not season_str.isdigit():
                continue
            season = int(season_str)
            # Check if any row in this group has "(V)" — if not, fall back to rank==1
            group_has_voting = voting_col and any(
                str(r).strip() == "(V)" for r in grp[voting_col]
            )
            for rank, (_, row) in enumerate(grp.iterrows(), 1):
                player = row[player_col]
                if not isinstance(player, str) or not player.strip():
                    continue
                if voting_col and group_has_voting:
                    is_winner = str(row[voting_col]).strip() == "(V)"
                else:
                    is_winner = rank == 1
                award_rows.append({
                    "player": player.strip(),
                    "season": season,
                    "award": award,
                    "vote_rank": rank,
                    "is_winner": 1 if is_winner else 0,
                })

    if award_rows:
        awards_df = pd.DataFrame(award_rows)
        awards_df.to_sql("nba_awards", conn, if_exists="replace", index=False)
        winners = awards_df["is_winner"].sum()
        print(f"nba_awards: {len(awards_df)} rows ({winners} winners) loaded.")

    # ── 2. All-NBA / All-Rookie / All-Defensive teams ────────────────────────
    team_tables = {
        12: "nba_allnba",
        13: "nba_allrookie",
        14: "nba_alldefensive",
    }
    for fnum, table_name in team_tables.items():
        path = os.path.join(new_data_dir, f"sportsref_download ({fnum}).xls")
        if not os.path.exists(path):
            continue
        df = _read_sportsref_xls(path)
        season_col = next((c for c in df.columns if "Season" in c), None)
        tm_col = next((c for c in df.columns if df.columns.tolist().index(c) > 0
                       and ("Tm" in c or c == "Tm") and "Season" not in c), None)
        # Player name columns are the 5 unnamed trailing columns
        skip = {season_col, tm_col,
                next((c for c in df.columns if "Lg" in c), ""),
                next((c for c in df.columns if "Voting" in c), "")}
        player_cols = [c for c in df.columns if c not in skip and c]

        rows = []
        for _, row in df.iterrows():
            season_str = str(row[season_col])[:4] if season_col else ""
            if not season_str.isdigit():
                continue
            season = int(season_str)
            team_num = {"1st": 1, "2nd": 2, "3rd": 3}.get(str(row[tm_col]), None)
            if team_num is None:
                continue
            for pc in player_cols:
                val = row[pc]
                if not isinstance(val, str) or not val.strip():
                    continue
                player = _strip_pos_suffix(val)
                if player:
                    rows.append({"player": player, "season": season, "team_num": team_num})

        if rows:
            result = pd.DataFrame(rows)
            result = _clean_text_columns(result, ["player"])
            result.to_sql(table_name, conn, if_exists="replace", index=False)
            print(f"{table_name}: {len(result)} rows loaded.")

    # ── 3. All-Star game totals per player per season (file 11) ──────────────
    path = os.path.join(new_data_dir, "sportsref_download (11).xls")
    if os.path.exists(path):
        df = _read_sportsref_xls(path)
        season_col = next((c for c in df.columns if "Season" in c), None)
        player_col = next((c for c in df.columns if "Player" in c), None)
        pts_col = next((c for c in df.columns if "PTS" in c), None)
        trb_col = next((c for c in df.columns if "TRB" in c), None)
        ast_col = next((c for c in df.columns if "AST" in c), None)
        stl_col = next((c for c in df.columns if "STL" in c), None)
        blk_col = next((c for c in df.columns if "BLK" in c), None)
        fg_col = next((c for c in df.columns if "FG%" in c), None)
        threep_col = next((c for c in df.columns if "3P%" in c), None)
        ft_col = next((c for c in df.columns if "FT%" in c), None)

        df = df[df[player_col].notna()]
        df = df[df[player_col] != "Player"]
        df = _clean_text_columns(df, [player_col])
        df["season"] = pd.to_numeric(df[season_col].astype(str).str[:4], errors="coerce")

        for col in [pts_col, trb_col, ast_col, stl_col, blk_col, fg_col, threep_col, ft_col]:
            if col:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        agg = df.groupby([player_col, "season"]).agg(
            appearances=(season_col, "count"),
            pts=(pts_col, "sum"),
            trb=(trb_col, "sum"),
            ast=(ast_col, "sum"),
            stl=(stl_col, "sum"),
            blk=(blk_col, "sum"),
            fg_pct=(fg_col, "mean"),
            threep_pct=(threep_col, "mean"),
            ft_pct=(ft_col, "mean"),
        ).reset_index().rename(columns={player_col: "player"})

        agg.to_sql("nba_allstar_games", conn, if_exists="replace", index=False)
        print(f"nba_allstar_games: {len(agg)} rows loaded.")

    # ── 4. Contracts ─────────────────────────────────────────────────────────
    path = os.path.join(new_data_dir, "Contracts.xls")
    if os.path.exists(path):
        df = _read_sportsref_xls(path)
        player_col = next((c for c in df.columns if "Player" in c), None)
        team_col = next((c for c in df.columns if "Tm" in c and "Player" not in c), None)

        def _parse_salary(val):
            if not isinstance(val, str):
                return None
            cleaned = val.replace("$", "").replace(",", "").strip()
            return pd.to_numeric(cleaned, errors="coerce")

        out = pd.DataFrame({
            "player": df[player_col],
            "team": df[team_col] if team_col else None,
        })
        for col in df.columns:
            if "Salary" in col:
                year_tag = col.replace("Salary ", "").replace("-", "_")
                out[f"salary_{year_tag}"] = df[col].apply(_parse_salary)
        guar_col = next((c for c in df.columns if "Guaranteed" in c), None)
        if guar_col:
            out["guaranteed"] = df[guar_col].apply(_parse_salary)

        out = out[out["player"].notna() & (out["player"] != "Player")]
        out = _clean_text_columns(out, ["player"])
        out.to_sql("nba_contracts", conn, if_exists="replace", index=False)
        print(f"nba_contracts: {len(out)} rows loaded.")

    # ── 5. Team wins per season ───────────────────────────────────────────────
    path = os.path.join(new_data_dir, "Team_wins.xls")
    if os.path.exists(path):
        df = _read_sportsref_xls(path)
        season_col = next((c for c in df.columns if "Season" in c), None)
        skip = {season_col, "Rk", "Lg", "rk", "lg"}
        team_cols = [c for c in df.columns if c not in skip]

        rows = []
        for _, row in df.iterrows():
            season = str(row[season_col]) if season_col else None
            if not isinstance(season, str) or not season:
                continue
            gp = LOCKOUT_GAMES.get(season, 82)
            for team in team_cols:
                wins = row[team]
                if pd.notna(wins):
                    rows.append({"season": season, "team": team,
                                 "wins": int(wins), "games_played": gp})

        if rows:
            result = pd.DataFrame(rows)
            result.to_sql("nba_team_wins", conn, if_exists="replace", index=False)
            print(f"nba_team_wins: {len(result)} rows loaded.")

    # ── 6. Team franchise index ───────────────────────────────────────────────
    path = os.path.join(new_data_dir, "Team_index.xls")
    if os.path.exists(path):
        df = _read_sportsref_xls(path)
        df.columns = [
            c.lower().replace("/", "_").replace("%", "pct").replace(" ", "_").replace(".", "")
            for c in df.columns
        ]
        df = _clean_text_columns(df, ["franchise"])
        df.to_sql("nba_team_index", conn, if_exists="replace", index=False)
        print(f"nba_team_index: {len(df)} rows loaded.")

    # ── 7. RSCI recruiting rankings (files 16–42) ─────────────────────────────
    rsci_dfs = []
    for fnum in range(16, 43):
        path = os.path.join(new_data_dir, f"sportsref_download ({fnum}).xls")
        if not os.path.exists(path):
            continue
        df = _read_sportsref_xls(path)
        rsci_col = next((c for c in df.columns if "RSCI" in c), None)
        player_col = next((c for c in df.columns if "Player" in c), None)
        draft_col = next((c for c in df.columns if "Draft" in c), None)
        rd_col = next((c for c in df.columns if c.endswith(" Rd") or c == "Rd"), None)
        pk_col = next((c for c in df.columns if c.endswith(" Pk") or c == "Pk"), None)
        college_col = next((c for c in df.columns if "College" in c), None)
        team_col = next((c for c in df.columns if c.endswith(" Tm") or c == "Tm"), None)
        from_col = next((c for c in df.columns if "From" in c), None)
        to_col = next((c for c in df.columns if c.endswith(" To") or c == "To"), None)
        ws_col = next((c for c in df.columns if c.endswith(" WS") or c == "WS"), None)
        if not player_col:
            continue

        df = df[df[player_col].notna()]
        df = df[df[player_col] != "Player"]
        df = _clean_text_columns(df, [player_col])
        # Strip "(college)" suffix added by Sports Reference
        df[player_col] = df[player_col].str.replace(r"\s*\(college\)\s*$", "", regex=True).str.strip()

        row_df = pd.DataFrame({
            "rsci_rank": pd.to_numeric(df[rsci_col], errors="coerce") if rsci_col else None,
            "player": df[player_col],
            "draft_year": pd.to_numeric(df[draft_col], errors="coerce") if draft_col else None,
            "round": pd.to_numeric(df[rd_col], errors="coerce") if rd_col else None,
            "pick": pd.to_numeric(df[pk_col], errors="coerce") if pk_col else None,
            "college": df[college_col] if college_col else None,
            "nba_team": df[team_col] if team_col else None,
            "from_year": pd.to_numeric(df[from_col], errors="coerce") if from_col else None,
            "to_year": pd.to_numeric(df[to_col], errors="coerce") if to_col else None,
            "win_shares": pd.to_numeric(df[ws_col], errors="coerce") if ws_col else None,
        })
        rsci_dfs.append(row_df)

    if rsci_dfs:
        rsci = pd.concat(rsci_dfs, ignore_index=True)
        rsci.drop_duplicates(subset=["player", "draft_year"], inplace=True)
        rsci.to_sql("nba_recruiting", conn, if_exists="replace", index=False)
        print(f"nba_recruiting: {len(rsci)} rows loaded.")

    # ── 8. NCAA Player of the Year ────────────────────────────────────────────
    # Layout: row 0 = section labels (Totals/Shooting/Per Game), row 1 = field names.
    # Per Game fields (last 4 cols) duplicate earlier names, so we use iloc by position.
    path = os.path.join(new_data_dir, "NCAA_POTY.xlsx")
    if os.path.exists(path):
        raw = pd.read_excel(path, engine="openpyxl", header=None)
        # Assign unique positional names
        # Known layout: Year, Player, College, G, MP, FG, FGA, 3P, 3PA, FT, FTA,
        #   ORB, TRB, AST, STL, BLK, TOV, PF, PTS, FG%, 3P%, FT%, MP_pg, PTS_pg, TRB_pg, AST_pg
        raw = raw.iloc[2:].reset_index(drop=True)
        raw.columns = range(len(raw.columns))

        out = pd.DataFrame({
            "year":        pd.to_numeric(raw[0], errors="coerce"),
            "player":      raw[1].astype(str),
            "college":     raw[2].astype(str),
            "g":           pd.to_numeric(raw[3], errors="coerce"),
            "pts_pg":      pd.to_numeric(raw[23], errors="coerce"),
            "trb_pg":      pd.to_numeric(raw[24], errors="coerce"),
            "ast_pg":      pd.to_numeric(raw[25], errors="coerce"),
            "fg_pct":      pd.to_numeric(raw[19], errors="coerce"),
            "threep_pct":  pd.to_numeric(raw[20], errors="coerce"),
            "ft_pct":      pd.to_numeric(raw[21], errors="coerce"),
        })
        out = out[out["player"].notna() & (out["player"] != "nan")]
        out = _clean_text_columns(out, ["player", "college"])
        out.to_sql("nba_ncaa_poty", conn, if_exists="replace", index=False)
        print(f"nba_ncaa_poty: {len(out)} rows loaded.")

    # ── 9a. NBA Hall of Fame ──────────────────────────────────────────────────
    path = os.path.join(new_data_dir, "HallofFameNBA.xlsx")
    if os.path.exists(path):
        raw = pd.read_excel(path, engine="openpyxl", header=None)
        # Row 0 = section groupings, row 1 = column names, data starts row 2
        raw = raw.iloc[2:].reset_index(drop=True)
        raw.columns = range(len(raw.columns))
        out = pd.DataFrame({
            "induction_year": pd.to_numeric(raw[0], errors="coerce"),
            "player":         raw[1].astype(str),
            "category":       raw[2].astype(str) if len(raw.columns) > 2 else None,
            "g":              pd.to_numeric(raw[3], errors="coerce") if len(raw.columns) > 3 else None,
            "pts_pg":         pd.to_numeric(raw[4], errors="coerce") if len(raw.columns) > 4 else None,
            "trb_pg":         pd.to_numeric(raw[5], errors="coerce") if len(raw.columns) > 5 else None,
            "ast_pg":         pd.to_numeric(raw[6], errors="coerce") if len(raw.columns) > 6 else None,
            "ws":             pd.to_numeric(raw[12], errors="coerce") if len(raw.columns) > 12 else None,
        })
        # Only keep Player inductees (not coaches/contributors/teams)
        out = out[out["player"].notna() & (out["player"] != "nan")]
        out = out[out["category"].str.contains("Player", na=False, case=False)]
        # Clean player names (may contain role suffixes like "Player / Int'l / CBB player")
        out["player"] = out["player"].str.replace(r"\s+Player.*$", "", regex=True).str.strip()
        out["player"] = out["player"].str.replace(r"\s+WNBA.*$", "", regex=True).str.strip()
        out = _clean_text_columns(out, ["player"])
        out = out[out["player"].str.len() > 1]
        out.to_sql("nba_hof", conn, if_exists="replace", index=False)
        print(f"nba_hof: {len(out)} rows loaded.")

    # ── 9. USA Olympic Teams ──────────────────────────────────────────────────
    # Layout: row 0 = section labels (Totals/Per Game), row 1 = field names.
    # Known layout: Year, Player, G, PTS, TRB, AST, STL, BLK, TOV,
    #               PTS_pg, TRB_pg, AST_pg, STL_pg, BLK_pg, TOV_pg
    path = os.path.join(new_data_dir, "USA_Olympic_Teams.xlsx")
    if os.path.exists(path):
        raw = pd.read_excel(path, engine="openpyxl", header=None)
        raw = raw.iloc[2:].reset_index(drop=True)
        raw.columns = range(len(raw.columns))

        out = pd.DataFrame({
            "year":    pd.to_numeric(raw[0], errors="coerce"),
            "player":  raw[1].astype(str),
            "g":       pd.to_numeric(raw[2], errors="coerce"),
            "pts":     pd.to_numeric(raw[3], errors="coerce"),
            "trb":     pd.to_numeric(raw[4], errors="coerce"),
            "ast":     pd.to_numeric(raw[5], errors="coerce"),
            "stl":     pd.to_numeric(raw[6], errors="coerce"),
            "blk":     pd.to_numeric(raw[7], errors="coerce") if len(raw.columns) > 7 else None,
            "pts_pg":  pd.to_numeric(raw[9], errors="coerce") if len(raw.columns) > 9 else None,
            "trb_pg":  pd.to_numeric(raw[10], errors="coerce") if len(raw.columns) > 10 else None,
            "ast_pg":  pd.to_numeric(raw[11], errors="coerce") if len(raw.columns) > 11 else None,
        })
        out = out[out["player"].notna() & (out["player"] != "nan")]
        out = _clean_text_columns(out, ["player"])
        out.to_sql("nba_olympic_teams", conn, if_exists="replace", index=False)
        print(f"nba_olympic_teams: {len(out)} rows loaded.")

    conn.close()


_NFL_AWARD_FILE_MAP = {
    2: "NFL_MVP",
    3: "AP_OPOY",    # AP Offensive Player of the Year
    4: "AP_DPOY",    # AP Defensive Player of the Year
    5: "AP_OROY",    # AP Offensive Rookie of the Year
    6: "AP_DROY",    # AP Defensive Rookie of the Year
    7: "Comeback",   # Comeback Player of the Year
    8: "SB_MVP",     # Super Bowl MVP
}

# All-Rookie team: file N covers season year = 2034 - N  (file 9 → 2025, file 60 → 1974)
# Kicking stats: 2 files per season, season = 2025 - (N - 2) // 2
_SB_RESULT_RE = (
    r"Super Bowl [\w]+:\s+"          # handles Roman numerals AND "50"
    r"(.+?)\s+\((\w+),([\d-]+)\)\s+defeated\s+"
    r"(.+?)\s+\((\w+),([\d-]+)\),\s+Score:\s+(\d+)-(\d+)"
)
# Pre-Super Bowl era: "Winner (League,record), Loser (League,record)" or just "Winner (League,record)"
_CHAMP_BOTH_RE = r"^(.+?)\s+\((\w+),[\d-]+\),\s+(.+?)\s+\((\w+),[\d-]+\)$"
_CHAMP_ONE_RE  = r"^(.+?)\s+\((\w+),[\d-]+\)$"


def load_new_nfl_data(new_data_dir="new_data_nfl", db_path="fantasy.db"):
    _ensure_pd()
    """Load supplemental NFL data from new_data_nfl/ into the database.

    Tables created/replaced:
      nfl_superbowl   – Super Bowl results (year, teams, score)
      nfl_awards      – Individual awards: MVP/OPOY/DPOY/OROY/DROY/Comeback/SB MVP
      nfl_hof         – Hall of Fame inductees with career stats (2017–2026 classes)
      nfl_allrookie   – All-Rookie team per season with full rookie stats (1974–2025)
      nfl_kicking     – Kicker season stats by distance range (1977–2025)
    """
    import re as _re
    conn = sqlite3.connect(db_path)

    # ── 1. Super Bowl results ─────────────────────────────────────────────────
    path = os.path.join(new_data_dir, "sportsref_download (1).xls")
    if os.path.exists(path):
        df = _read_sportsref_xls(path)
        rows = []
        for _, row in df.iterrows():
            year = row.get("Year") or row.iloc[0]
            desc = row.iloc[2] if len(row) > 2 else ""
            if not isinstance(desc, str) or not isinstance(year, (int, float)):
                continue
            # Modern Super Bowl with score
            m = _re.search(_SB_RESULT_RE, desc)
            if m:
                winner, winner_conf, winner_rec, loser, loser_conf, loser_rec, wscore, lscore = m.groups()
                rows.append({
                    "year": int(year), "game_type": "Super Bowl",
                    "winner": winner.strip(), "winner_conf": winner_conf,
                    "loser": loser.strip(), "loser_conf": loser_conf,
                    "winner_score": int(wscore), "loser_score": int(lscore),
                })
                continue
            # Pre-SB era: two-team championship game
            m2 = _re.match(_CHAMP_BOTH_RE, desc.strip())
            if m2:
                winner, w_lg, loser, l_lg = m2.groups()
                rows.append({
                    "year": int(year), "game_type": "Championship",
                    "winner": winner.strip(), "winner_conf": w_lg,
                    "loser": loser.strip(), "loser_conf": l_lg,
                    "winner_score": None, "loser_score": None,
                })
                continue
            # Pre-SB era: single champion listed
            m3 = _re.match(_CHAMP_ONE_RE, desc.strip())
            if m3:
                winner, w_lg = m3.groups()
                rows.append({
                    "year": int(year), "game_type": "Championship",
                    "winner": winner.strip(), "winner_conf": w_lg,
                    "loser": None, "loser_conf": None,
                    "winner_score": None, "loser_score": None,
                })
        if rows:
            pd.DataFrame(rows).to_sql("nfl_superbowl", conn, if_exists="replace", index=False)
            print(f"nfl_superbowl: {len(rows)} rows loaded.")

    # ── 2. Individual awards ──────────────────────────────────────────────────
    award_rows = []
    for fnum, award in _NFL_AWARD_FILE_MAP.items():
        path = os.path.join(new_data_dir, f"sportsref_download ({fnum}).xls")
        if not os.path.exists(path):
            continue
        df = _read_sportsref_xls(path)
        player_col = next((c for c in df.columns if c == "Player"), None)
        year_col = next((c for c in df.columns if c == "Year"), None)
        pos_col = next((c for c in df.columns if c == "Pos"), None)
        team_col = next((c for c in df.columns if c == "Tm"), None)
        if not player_col or not year_col:
            continue
        df = df[df[player_col].notna() & (df[player_col] != "Player")]
        df = _clean_text_columns(df, [player_col])
        for _, row in df.iterrows():
            year = row[year_col]
            player = row[player_col]
            if not isinstance(player, str) or not str(year).isdigit() if not isinstance(year, (int, float)) else False:
                pass
            try:
                yr = int(year)
            except (ValueError, TypeError):
                continue
            award_rows.append({
                "player": str(player).strip(),
                "year": yr,
                "award": award,
                "pos": str(row[pos_col]).strip() if pos_col else None,
                "team": str(row[team_col]).strip() if team_col else None,
            })
    if award_rows:
        awards_df = pd.DataFrame(award_rows)
        awards_df.to_sql("nfl_awards", conn, if_exists="replace", index=False)
        print(f"nfl_awards: {len(awards_df)} rows ({awards_df['award'].nunique()} award types) loaded.")

    # ── 3. Hall of Fame ───────────────────────────────────────────────────────
    path = os.path.join(new_data_dir, "HallofFameNFL.xls")
    if os.path.exists(path):
        df = _read_sportsref_xls(path)
        col_map = {
            "Unnamed: 1_level_0 Player": "player",
            "Unnamed: 2_level_0 Pos":    "pos",
            "Unnamed: 3_level_0 Indct":  "induction_year",
            "Unnamed: 4_level_0 From":   "from_year",
            "Unnamed: 5_level_0 To":     "to_year",
            "Unnamed: 6_level_0 AP1":    "all_pro1",
            "Unnamed: 7_level_0 PB":     "pro_bowls",
            "Unnamed: 9_level_0 wAV":    "wav",
            "Unnamed: 10_level_0 G":     "games",
            "Passing Yds":               "pass_yds",
            "Passing TD":                "pass_td",
            "Rushing Yds":               "rush_yds",
            "Rushing TD":                "rush_td",
            "Receiving Yds":             "rec_yds",
            "Receiving TD":              "rec_td",
            "Defense Comb":              "def_tackles",
            "Defense Sk":                "def_sacks",
            "Defense Int":               "def_int",
        }
        df.rename(columns=col_map, inplace=True)
        keep = [c for c in col_map.values() if c in df.columns]
        df = df[keep].copy()
        df = df[df["player"].notna() & (df["player"] != "Player")]
        df = _clean_text_columns(df, ["player", "pos"])
        for col in ["induction_year", "from_year", "to_year", "all_pro1",
                    "pro_bowls", "wav", "games"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df.to_sql("nfl_hof", conn, if_exists="replace", index=False)
        print(f"nfl_hof: {len(df)} rows loaded.")

    # ── 4. All-Rookie team per season (files 9–60) ────────────────────────────
    rookie_dfs = []
    for fnum in range(9, 61):
        path = os.path.join(new_data_dir, f"sportsref_download ({fnum}).xls")
        if not os.path.exists(path):
            continue
        season_year = 2034 - fnum
        df = _read_sportsref_xls(path)
        pos_col    = next((c for c in df.columns if "Pos" in c), None)
        player_col = next((c for c in df.columns if "Player" in c), None)
        team_col   = next((c for c in df.columns if c.endswith(" Tm") or c == "Tm"), None)
        g_col      = next((c for c in df.columns if c.endswith(" G") and "GS" not in c), None)
        gs_col     = next((c for c in df.columns if "GS" in c), None)
        # Offensive stat columns
        pass_yds = next((c for c in df.columns if "Passing Yds" in c), None)
        pass_td  = next((c for c in df.columns if "Passing TD" in c), None)
        pass_int = next((c for c in df.columns if "Passing Int" in c), None)
        rush_yds = next((c for c in df.columns if "Rushing Yds" in c), None)
        rush_td  = next((c for c in df.columns if "Rushing TD" in c), None)
        rec_rec  = next((c for c in df.columns if "Receiving Rec" in c), None)
        rec_yds  = next((c for c in df.columns if "Receiving Yds" in c), None)
        rec_td   = next((c for c in df.columns if "Receiving TD" in c), None)
        def_solo = next((c for c in df.columns if "Solo" in c), None)
        def_sk   = next((c for c in df.columns if "Sk" in c and "Passing" not in c), None)
        def_int  = next((c for c in df.columns if df.columns.tolist().index(c) > (df.columns.tolist().index(def_sk) if def_sk else 0)
                         and "Int" in c), None) if def_sk else next((c for c in df.columns if "Int" in c), None)
        if not player_col:
            continue
        df = df[df[player_col].notna() & (df[player_col] != "Player")]
        df = _clean_text_columns(df, [player_col])

        rdf = pd.DataFrame({"player": df[player_col], "season": season_year})
        for src, dst in [(pos_col,"pos"), (team_col,"team"), (g_col,"games"), (gs_col,"games_started"),
                         (pass_yds,"pass_yds"), (pass_td,"pass_td"), (pass_int,"pass_int"),
                         (rush_yds,"rush_yds"), (rush_td,"rush_td"),
                         (rec_rec,"rec_rec"), (rec_yds,"rec_yds"), (rec_td,"rec_td"),
                         (def_solo,"def_solo"), (def_sk,"def_sacks"), (def_int,"def_int")]:
            if src:
                rdf[dst] = pd.to_numeric(df[src], errors="coerce") if dst != "pos" and dst != "team" else df[src].astype(str)
        rookie_dfs.append(rdf)

    if rookie_dfs:
        allrookie = pd.concat(rookie_dfs, ignore_index=True)
        allrookie = allrookie[allrookie["player"].notna()]
        allrookie.drop_duplicates(subset=["player", "season"], inplace=True)
        allrookie.to_sql("nfl_allrookie", conn, if_exists="replace", index=False)
        print(f"nfl_allrookie: {len(allrookie)} rows loaded ({allrookie['season'].nunique()} seasons).")

    # ── 5. Kicker season stats (Kicking folder, files 2–99, 2 per season) ─────
    kicking_dir = os.path.join(new_data_dir, "Kicking")
    kick_dfs = []
    for fnum in range(2, 100):
        path = os.path.join(kicking_dir, f"sportsref_download ({fnum}).xls")
        if not os.path.exists(path):
            continue
        season_year = 2025 - (fnum - 2) // 2
        df = _read_sportsref_xls(path)
        player_col = next((c for c in df.columns if "Player" in c), None)
        team_col   = next((c for c in df.columns if "Team" in c), None)
        age_col    = next((c for c in df.columns if "Age" in c), None)
        g_col      = next((c for c in df.columns if c.endswith(" G") and "GS" not in c), None)
        if not player_col:
            continue
        df = df[df[player_col].notna() & (df[player_col] != "Player")]
        df = _clean_text_columns(df, [player_col])

        kdf = pd.DataFrame({"player": df[player_col], "season": season_year})
        col_map_k = {
            team_col:               "team",
            age_col:                "age",
            g_col:                  "games",
            "Scoring FGA":         "fga",
            "Scoring FGM":         "fgm",
            "Scoring Lng":         "fg_long",
            "Scoring FG%":         "fg_pct",
            "Scoring XPA":         "xpa",
            "Scoring XPM":         "xpm",
            "Scoring XP%":         "xp_pct",
            "0-19 FGM":            "fg_0_19",
            "20-29 FGM":           "fg_20_29",
            "30-39 FGM":           "fg_30_39",
            "40-49 FGM":           "fg_40_49",
            "50+ FGM":             "fg_50plus",
            "0-19 FGA":            "fga_0_19",
            "20-29 FGA":           "fga_20_29",
            "30-39 FGA":           "fga_30_39",
            "40-49 FGA":           "fga_40_49",
            "50+ FGA":             "fga_50plus",
        }
        for src, dst in col_map_k.items():
            if src and src in df.columns:
                if dst in ("team",):
                    kdf[dst] = df[src].astype(str)
                else:
                    kdf[dst] = pd.to_numeric(df[src], errors="coerce")
        kick_dfs.append(kdf)

    if kick_dfs:
        kicking = pd.concat(kick_dfs, ignore_index=True)
        kicking = kicking[kicking["player"].notna()]
        kicking.drop_duplicates(subset=["player", "season", "team"], inplace=True)
        kicking.to_sql("nfl_kicking", conn, if_exists="replace", index=False)
        seasons = kicking["season"].nunique()
        print(f"nfl_kicking: {len(kicking)} rows loaded ({seasons} seasons).")

    conn.close()


def build_db(folders, db_path="fantasy.db"):
    _ensure_pd()
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

    # Disambiguate players with colliding names
    for (name, team), new_name in PLAYER_RENAMES_BY_TEAM.items():
        mask = (combined["player"] == name) & (combined["team"] == team)
        combined.loc[mask, "player"] = new_name

    combined = _clean_text_columns(combined, ["player", "team", "pos"])
    combined.to_sql("stats", conn, if_exists="replace", index=False)
    print(f"Total: {len(combined)} rows loaded into SQLite.")
    return conn
