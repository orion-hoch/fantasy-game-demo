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
    else:
        print("WARNING: No NBA season stat files found.")

    # ── NBA draft stats ───────────────────────────────────────────────────────
    draft_dir = os.path.join(base_dir, "NBA_stats", "Draft_NBA_stats")
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
