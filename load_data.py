import pandas as pd
import sqlite3
import glob
import os

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
    df = _clean_text_columns(df, ["player", "team", "pos"])
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

    # Disambiguate players with colliding names
    for (name, team), new_name in PLAYER_RENAMES_BY_TEAM.items():
        mask = (combined["player"] == name) & (combined["team"] == team)
        combined.loc[mask, "player"] = new_name

    combined = _clean_text_columns(combined, ["player", "team", "pos"])
    combined.to_sql("stats", conn, if_exists="replace", index=False)
    print(f"Total: {len(combined)} rows loaded into SQLite.")
    return conn
