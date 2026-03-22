import sqlite3
import random
import uuid
import time
from collections import Counter

_GAMES = {}
_TTL = 3600 * 4

POS_MULT = {"QB": 1.0, "RB": 1.4, "WR": 1.5, "TE": 2.5}
POS_COLOR = {"QB": "qb", "RB": "rb", "WR": "wr", "TE": "te"}
POS_ORDER = ["QB", "RB", "WR", "TE"]

HAND_TYPES = {
    "balanced_offense": {"name": "Balanced Offense", "mult": 6.0,  "desc": "QB + 2 WRs + 2 RBs + TE"},
    "six_of_a_kind":    {"name": "Six of a Kind",    "mult": 5.5,  "desc": "6 of the same position"},
    "flush":            {"name": "Position Flush",   "mult": 5.0,  "desc": "5 of same position"},
    "position_split":   {"name": "Position Split",   "mult": 4.0,  "desc": "3 of one position + 3 of another"},
    "quad":             {"name": "Quad Set",          "mult": 3.0,  "desc": "4 of same position"},
    "trips":            {"name": "Triple Threat",     "mult": 2.0,  "desc": "3 of same position"},
    "double":           {"name": "Dynamic Duo",       "mult": 1.5,  "desc": "2 of same position"},
    "single":           {"name": "Highlight Reel",    "mult": 1.0,  "desc": "Best single card"},
}

LEVEL_TARGETS = [2000, 6000, 15000, 40000, 100000, 250000, 600000, 1500000]
LEVEL_NAMES = ["Preseason", "Wild Card", "Divisional Round", "Conference Championship", "Super Bowl LIX", "Super Bowl LX", "Super Bowl LXI", "Super Bowl LXII"]

ROUND_BASE_TARGETS = [1800, 5000, 13000, 32000, 80000, 200000, 500000, 1300000]
ROUND_NAMES = ["Preseason", "Wild Card", "Divisional Round", "Conference Championship",
               "Super Bowl LIX", "Super Bowl LX", "Super Bowl LXI", "Super Bowl LXII"]
FIGHT_SCALE = [1.0, 1.3, 1.7]  # within-round scaling (fight 1, 2, 3=boss)

BOSS_EFFECTS = [
    {"id": "sec_lockout",    "name": "SEC Lockout",    "desc": "SEC players are removed from your hand this fight"},
    {"id": "zone_coverage",  "name": "Zone Coverage",  "desc": "Quad Set mult is halved"},
    {"id": "receiver_foul",  "name": "Receiver Foul",  "desc": "WR position multiplier x0.5 this fight"},
    {"id": "false_start",    "name": "False Start",    "desc": "Max 4 cards playable per hand"},
    {"id": "penalty_flag",   "name": "Penalty Flag",   "desc": "All scores reduced by 20%"},
    {"id": "rb_stuffed",     "name": "Run Stuffed",    "desc": "RB position multiplier x0.5 this fight"},
    {"id": "rookie_ban",     "name": "Rookie Ban",     "desc": "Players drafted 2020+ removed from your hand"},
    {"id": "scoreboard_cap", "name": "Scoreboard Cap", "desc": "Base pts per card capped at 150 this fight"},
]
BOSS_EFFECT_MAP = {b["id"]: b for b in BOSS_EFFECTS}

# ── College Conferences ────────────────────────────────────────────────────────

COLLEGE_CONFERENCES = {
    "SEC": ["Alabama", "LSU", "Georgia", "Florida", "Tennessee", "Auburn", "Ole Miss",
            "Mississippi St.", "Arkansas", "South Carolina", "Kentucky", "Missouri",
            "Texas A&M", "Vanderbilt", "Texas", "Oklahoma"],
    "Big Ten": ["Ohio St.", "Michigan", "Penn St.", "Wisconsin", "Iowa", "Michigan St.",
                "Minnesota", "Purdue", "Illinois", "Indiana", "Nebraska", "Northwestern",
                "Maryland", "Rutgers", "Oregon", "USC", "UCLA", "Washington"],
    "ACC": ["Clemson", "Florida St.", "Miami (FL)", "North Carolina", "North Carolina St.",
            "NC State", "Virginia Tech", "Georgia Tech", "Pittsburgh", "Wake Forest",
            "Duke", "Virginia", "Boston College", "Syracuse", "Louisville"],
    "Big 12": ["TCU", "Baylor", "Kansas St.", "Iowa St.", "West Virginia", "Kansas",
               "Texas Tech", "Oklahoma St.", "BYU", "Cincinnati", "Houston", "UCF"],
    "Pac-12": ["Arizona St.", "Arizona", "Cal", "Stanford", "Utah", "Colorado",
               "Washington St.", "Oregon St."],
    "AAC": ["Memphis", "SMU", "Tulane", "Navy", "Temple", "East Carolina",
            "Tulsa", "South Florida", "UTSA"],
    "Mountain West": ["Boise St.", "Fresno St.", "Nevada", "San Diego St.",
                      "Wyoming", "Air Force", "Colorado St.", "New Mexico", "UNLV"],
    "MAC": ["Toledo", "Western Michigan", "Bowling Green", "Ohio", "Akron",
            "Ball St.", "Buffalo", "Kent St.", "Miami (OH)", "Northern Illinois"],
}

_COLLEGE_TO_CONF = {}
for _conf, _colleges in COLLEGE_CONFERENCES.items():
    for _c in _colleges:
        _COLLEGE_TO_CONF[_c.lower()] = _conf


def get_conference(college):
    if not college:
        return None
    return _COLLEGE_TO_CONF.get(college.lower().strip())


JOKERS = [
    {"id": "te_monster", "name": "TE Monster", "desc": "+2 mult per TE card played", "rarity": "common"},
    {"id": "air_raid", "name": "Air Raid", "desc": "+1.5 mult per WR card played", "rarity": "common"},
    {"id": "ground_pound", "name": "Ground & Pound", "desc": "+2 mult per RB card played", "rarity": "common"},
    {"id": "field_general", "name": "Field General", "desc": "+4 mult per QB card played", "rarity": "uncommon"},
    {"id": "pro_bowl_pedigree", "name": "Pro Bowl Pedigree", "desc": "+1 mult per Pro Bowl appearance in scoring hand", "rarity": "uncommon"},
    {"id": "star_power", "name": "Star Power", "desc": "+3 mult per player with 3+ Pro Bowls in scoring hand", "rarity": "rare"},
    {"id": "first_rounder", "name": "First Round Value", "desc": "+2 mult per 1st round pick in scoring hand", "rarity": "common"},
    {"id": "west_coast_offense", "name": "West Coast Offense", "desc": "+6 mult when playing Balanced Offense", "rarity": "uncommon"},
    {"id": "position_coach", "name": "Position Coach", "desc": "+5 mult when playing a Position Flush", "rarity": "uncommon"},
    {"id": "team_chemistry", "name": "Team Chemistry", "desc": "+7 mult if all played cards from same NFL team", "rarity": "rare"},
    {"id": "college_dynasty", "name": "College Dynasty", "desc": "+4 mult if 3+ played cards from same college", "rarity": "uncommon"},
    {"id": "new_wave", "name": "New Wave", "desc": "+7 mult if all played cards drafted 2020+", "rarity": "rare"},
    {"id": "old_school", "name": "Old School", "desc": "+5 mult if all played cards drafted before 2016", "rarity": "uncommon"},
    {"id": "volume_scorer", "name": "Volume Scorer", "desc": "+1.5 mult per card played beyond 3", "rarity": "common"},
    {"id": "red_zone_weapon", "name": "Red Zone Weapon", "desc": "TE position multiplier +0.5 (stacks)", "rarity": "rare"},
    {"id": "workhorse_back", "name": "Workhorse Back", "desc": "RB position multiplier +0.3 (stacks)", "rarity": "uncommon"},
    {"id": "slot_receiver", "name": "Slot Receiver", "desc": "WR position multiplier +0.3 (stacks)", "rarity": "uncommon"},
    {"id": "franchise_qb", "name": "Franchise QB", "desc": "QB position multiplier +0.5 (stacks)", "rarity": "rare"},
    # Money-earning jokers
    {"id": "accountant", "name": "Accountant", "desc": "Earn $2 every time you play a hand", "rarity": "rare"},
    {"id": "sports_agent", "name": "Sports Agent", "desc": "Earn $1 per Pro Bowl in scoring hand", "rarity": "uncommon"},
    {"id": "endorsement_deal", "name": "Endorsement Deal", "desc": "Earn $1 per WR in played hand", "rarity": "common"},
    {"id": "cap_space", "name": "Cap Space", "desc": "Earn $1 per unique position in played hand", "rarity": "uncommon"},
    {"id": "bonus_clause", "name": "Bonus Clause", "desc": "Earn $5 when playing Balanced Offense", "rarity": "rare"},
    {"id": "smart_money", "name": "Smart Money", "desc": "Earn $1 interest per $5 held at end of each level (max $5)", "rarity": "rare"},
    # Conference joker
    {"id": "conference_pride", "name": "Conference Pride", "desc": "+6 mult if all scoring cards from same college conference (SEC, Big Ten, ACC, etc.)", "rarity": "rare"},
    # Scaling jokers
    {"id": "film_study", "name": "Film Study", "desc": "Gains +0.5 mult each hand played this run", "rarity": "rare"},
    {"id": "hot_streak", "name": "Hot Streak", "desc": "+3 mult per consecutive hand scored above 2000 pts (resets if below)", "rarity": "rare"},
    # Stack/copy jokers
    {"id": "blueprint", "name": "Blueprint", "desc": "Copies the mult bonus of the next joker to the right", "rarity": "legendary"},
    {"id": "double_agent", "name": "Double Agent", "desc": "+2 mult for each other joker you own", "rarity": "uncommon"},
    {"id": "smash_factor", "name": "Smash Factor", "desc": "x1.5 final score (multiplicative, applied after all other mult)", "rarity": "legendary"},
    # Situational
    {"id": "depth_chart", "name": "Depth Chart", "desc": "+2 mult per unique position in scoring hand", "rarity": "common"},
    {"id": "hail_mary", "name": "Hail Mary", "desc": "+15 mult when scoring hand has only 1 card (Highlight Reel)", "rarity": "rare"},
    {"id": "the_duo_joker", "name": "The Duo", "desc": "+5 mult when playing Dynamic Duo", "rarity": "uncommon"},
    {"id": "the_trio_joker", "name": "The Trio", "desc": "+6 mult when playing Triple Threat", "rarity": "uncommon"},
    {"id": "the_squad", "name": "The Squad", "desc": "+8 mult when playing Quad Set", "rarity": "rare"},
    {"id": "championship_run", "name": "Championship Run", "desc": "+1 mult for every level completed (floor-1)", "rarity": "rare"},
    # Undrafted
    {"id": "undrafted_diamond", "name": "Undrafted Diamond", "desc": "+5 mult per undrafted player in scoring hand", "rarity": "rare"},
    # Multiplicative mult jokers
    {"id": "sec_speed", "name": "SEC Speed", "desc": "×1.35 MULT per SEC player in scoring hand (multiplicative)", "rarity": "rare"},
    {"id": "power5_premium", "name": "Power 5 Premium", "desc": "×1.4 MULT if all scoring cards from Power 5 conferences (multiplicative)", "rarity": "uncommon"},
    {"id": "snowball", "name": "Snowball", "desc": "×1.12 MULT per consecutive high-scoring hand this level, stacks up to ×1.72 (multiplicative)", "rarity": "rare"},
    {"id": "dynasty_builder", "name": "Dynasty Builder", "desc": "×2 MULT if 3+ scoring cards from same college (multiplicative)", "rarity": "legendary"},
    {"id": "chain_reaction", "name": "Chain Reaction", "desc": "×1.2 MULT per other joker owned beyond the first (multiplicative)", "rarity": "rare"},
]
JOKER_MAP = {j["id"]: j for j in JOKERS}

SHOP_SKILL_CARDS = [
    {"id": "skill_qb", "type": "skill_card", "pos": "QB", "name": "QB Training", "desc": "Level up QB skill", "cost": 4},
    {"id": "skill_rb", "type": "skill_card", "pos": "RB", "name": "RB Academy", "desc": "Level up RB skill", "cost": 4},
    {"id": "skill_wr", "type": "skill_card", "pos": "WR", "name": "WR Workshop", "desc": "Level up WR skill", "cost": 4},
    {"id": "skill_te", "type": "skill_card", "pos": "TE", "name": "TE Clinic", "desc": "Level up TE skill", "cost": 4},
]

SHOP_COMBO_CARDS = [
    {"id": "combo_balanced", "type": "combo_card", "hand_type": "balanced_offense", "boost": 0.5,
     "name": "Balanced Formation", "desc": "+0.5 Balanced Offense mult", "cost": 5},
    {"id": "combo_flush", "type": "combo_card", "hand_type": "flush", "boost": 0.5,
     "name": "Zone Flood", "desc": "+0.5 Position Flush mult", "cost": 5},
    {"id": "combo_trips", "type": "combo_card", "hand_type": "trips", "boost": 0.5,
     "name": "Triple Option", "desc": "+0.5 Triple Threat mult", "cost": 5},
    {"id": "combo_quad", "type": "combo_card", "hand_type": "quad", "boost": 0.5,
     "name": "Power Sweep", "desc": "+0.5 Quad Set mult", "cost": 5},
    {"id": "combo_double", "type": "combo_card", "hand_type": "double", "boost": 0.5,
     "name": "Shotgun Short", "desc": "+0.5 Dynamic Duo mult", "cost": 5},
    {"id": "combo_single", "type": "combo_card", "hand_type": "single", "boost": 1.0,
     "name": "Audible", "desc": "+1.0 Highlight Reel mult", "cost": 5},
]

SHOP_EFFECT_CARDS = [
    {"id": "effect_gold", "type": "effect_card", "effect": "gold", "needs_target": True,
     "name": "Gold Tape", "desc": "Target card earns $2 when played", "cost": 3},
    {"id": "effect_glass", "type": "effect_card", "effect": "glass", "needs_target": True,
     "name": "Glass Film", "desc": "Target card gets +4 mult but 33% chance to break when played", "cost": 3},
    {"id": "effect_foil", "type": "effect_card", "effect": "foil", "needs_target": True,
     "name": "Foil Wrap", "desc": "Target card gets +50 base pts when played", "cost": 3},
]

SHOP_YEAR_CARD = {"id": "year_peak", "type": "year_card", "needs_target": True,
                  "name": "Time Machine", "desc": "Target card: choose any season for that player from the DB", "cost": 4}

SHOP_CUT_CARD = {"id": "cut_card", "type": "cut_card", "needs_target": True,
                 "name": "Release Clause", "desc": "Permanently remove a player from your deck", "cost": 3}

SHOP_UPGRADES = [
    {"id": "hand_size_up", "type": "upgrade", "stat": "max_hand_size", "amount": 1,
     "name": "Extra Playbook", "desc": "+1 max hand size (draw 1 extra card)", "cost": 6},
    {"id": "discard_up", "type": "upgrade", "stat": "base_discards", "amount": 1,
     "name": "Challenge Flag", "desc": "+1 discard per level", "cost": 5},
    {"id": "joker_slot_up", "type": "upgrade", "stat": "max_jokers", "amount": 1,
     "name": "Scout Report", "desc": "+1 Joker slot (hold more Jokers)", "cost": 7},
]

SHOP_MOD_CARDS = [
    {"id": "carbon_copy", "type": "mod_card", "effect": "duplicate", "needs_target": True,
     "name": "Carbon Copy", "desc": "Add a duplicate of a target card to your deck", "cost": 5},
    {"id": "training_camp", "type": "mod_card", "effect": "trained", "needs_target": True,
     "name": "Training Camp", "desc": "Target card permanently gains +20% PPR", "cost": 5},
    {"id": "position_switch", "type": "mod_card", "effect": "pos_switch", "needs_target": True,
     "name": "Position Switch", "desc": "Transform a RB to TE or WR to QB (keeps card, changes mult)", "cost": 6},
]

JOKER_ENHANCEMENT_ITEMS = [
    {"id": "boost_sticker",      "name": "Boost Sticker",     "type": "joker_enhancement", "enhancement_id": "boost_sticker",
     "desc": "+2 to this joker's mult contribution", "cost": 4, "needs_joker_target": True},
    {"id": "multiplier_sticker", "name": "Multiplier Sticker", "type": "joker_enhancement", "enhancement_id": "multiplier_sticker",
     "desc": "x1.5 to this joker's contribution",     "cost": 6, "needs_joker_target": True},
    {"id": "echo_sticker",       "name": "Echo Sticker",       "type": "joker_enhancement", "enhancement_id": "echo_sticker",
     "desc": "This joker fires twice (x2 effect)",    "cost": 7, "needs_joker_target": True},
    {"id": "gold_wire",          "name": "Gold Wire",          "type": "joker_enhancement", "enhancement_id": "gold_wire",
     "desc": "Earn $1 each time this joker activates", "cost": 5, "needs_joker_target": True},
]

PACKS = [
    {"id": "starter_pack",  "name": "Starter Pack",  "desc": "3 random players",                      "cost": 6,  "count": 3, "tier": "common"},
    {"id": "elite_pack",    "name": "Elite Pack",     "desc": "3 players (200+ PPR seasons)",          "cost": 10, "count": 3, "tier": "uncommon"},
    {"id": "position_pack", "name": "Position Pack",  "desc": "3 players of 1 random position",        "cost": 8,  "count": 3, "tier": "common"},
    {"id": "gold_pack",     "name": "Gold Pack",      "desc": "2 players — both receive Gold effect",  "cost": 12, "count": 2, "tier": "uncommon"},
    {"id": "all_pro_pack",  "name": "All-Pro Pack",   "desc": "2 players with 2+ Pro Bowls",           "cost": 15, "count": 2, "tier": "rare"},
    {"id": "legend_pack",   "name": "Legend Pack",    "desc": "1-2 elite players (350+ PPR), possible Glass effect", "cost": 20, "count": 2, "tier": "legendary"},
    {"id": "joker_pack",     "name": "Joker Pack",     "desc": "Choose 1 of 3 jokers",    "cost": 10, "count": 3, "tier": "uncommon", "is_joker_pack": True},
    {"id": "big_joker_pack", "name": "All-Star Joker Pack", "desc": "Choose 2 of 5 jokers", "cost": 18, "count": 5, "tier": "rare",     "is_joker_pack": True},
]
PACK_MAP = {p["id"]: p for p in PACKS}


def cleanup_old_games():
    now = time.time()
    stale = [gid for gid, g in _GAMES.items() if now - g.get("created_at", 0) > _TTL]
    for gid in stale:
        del _GAMES[gid]


def _get_effective_pos_mult(pos, joker_ids, skill_levels, card_effects_for_card=None):
    base = POS_MULT.get(pos, 1.0)
    for jid in joker_ids:
        if jid == "red_zone_weapon" and pos == "TE":
            base += 0.5
        elif jid == "workhorse_back" and pos == "RB":
            base += 0.3
        elif jid == "slot_receiver" and pos == "WR":
            base += 0.3
        elif jid == "franchise_qb" and pos == "QB":
            base += 0.5
    base += skill_levels.get(pos, 0) * 0.12
    return base


def _get_effective_ppr(card, skill_levels, card_effects):
    ppr = card["fantasy_ppr"]
    level = skill_levels.get(card["pos"], 0)
    ppr *= (1 + level * 0.08)
    effects = card_effects.get(card["id"], [])
    if "foil" in effects:
        ppr += 50
    if "trained" in effects:
        ppr *= 1.2
    return round(ppr, 1)


def _build_deck_pool(conn):
    """Fetch cards with exact position counts: 6 QB, 12 RB, 12 WR, 10 TE = 40 total."""
    exact_counts = {"QB": 6, "RB": 12, "WR": 12, "TE": 10}
    pool_rows = []
    used = set()

    for pos, count in exact_counts.items():
        rows = conn.execute("""
            SELECT s.player, s.season, s.pos, s.team, s.fantasy_ppr,
                   d.pro_bowls, d.college, d.draft_year, d.draft_round, d.draft_pick
            FROM stats s
            LEFT JOIN draft d ON s.player = d.player
            WHERE (d.draft_year >= 2010 OR d.draft_year IS NULL)
              AND s.pos = ?
              AND s.fantasy_ppr >= 50
            ORDER BY RANDOM()
        """, (pos,)).fetchall()
        added = 0
        for row in rows:
            key = (row[0], row[1], row[2])
            if key not in used:
                pool_rows.append(row)
                used.add(key)
                added += 1
                if added >= count:
                    break

    random.shuffle(pool_rows)

    cards = []
    for i, r in enumerate(pool_rows):
        card_id = f"{r[0]}_{r[1]}_{r[2]}_{i}"
        college = r[6]
        cards.append({
            "id": card_id,
            "player": r[0],
            "season": r[1],
            "pos": r[2],
            "team": r[3],
            "fantasy_ppr": round(r[4], 1),
            "pro_bowls": int(r[5]) if r[5] else 0,
            "college": college,
            "draft_year": r[7],
            "draft_round": r[8],
            "draft_pick": r[9],
            "undrafted": not college or college == "Unknown",
            "conference": get_conference(college),
        })
    return cards


def _build_deck(conn):
    """Fetch all qualifying player-season cards from DB."""
    rows = conn.execute("""
        SELECT s.player, s.season, s.pos, s.team, s.fantasy_ppr,
               d.pro_bowls, d.college, d.draft_year, d.draft_round, d.draft_pick
        FROM stats s
        LEFT JOIN draft d ON s.player = d.player
        WHERE (d.draft_year >= 2010 OR d.draft_year IS NULL)
          AND s.pos IN ('QB','RB','WR','TE')
          AND s.fantasy_ppr >= 50
        ORDER BY RANDOM()
    """).fetchall()

    cards = []
    seen_ids = set()
    for r in rows:
        card_id = f"{r[0]}_{r[1]}"
        if card_id in seen_ids:
            card_id = f"{r[0]}_{r[1]}_{r[2]}"
        seen_ids.add(card_id)
        college = r[6]
        cards.append({
            "id": card_id,
            "player": r[0],
            "season": r[1],
            "pos": r[2],
            "team": r[3],
            "fantasy_ppr": round(r[4], 1),
            "pro_bowls": int(r[5]) if r[5] else 0,
            "college": college,
            "draft_year": r[7],
            "draft_round": r[8],
            "draft_pick": r[9],
            "conference": get_conference(college),
        })
    return cards


def _deal_for_level(state):
    """Shuffle deck_pool, deal hand_size for hand, rest into deck."""
    pool = list(state["deck_pool"])
    random.shuffle(pool)
    hand_size = state.get("max_hand_size", 9)
    state["hand"] = pool[:hand_size]
    state["deck"] = pool[hand_size:]


def evaluate_hand(cards):
    """Evaluate hand type. Returns (type_key, scoring_cards)."""
    n = len(cards)
    if n == 0:
        return None, []

    pos_counts = Counter(c["pos"] for c in cards)

    # Balanced Offense: exactly QB=1, WR=2, RB=2, TE=1 (needs 6 cards)
    if n == 6 and pos_counts.get("QB") == 1 and pos_counts.get("WR") == 2 and pos_counts.get("RB") == 2 and pos_counts.get("TE") == 1:
        return "balanced_offense", cards

    # Six of a Kind: 6 of same position
    if n == 6 and len(pos_counts) == 1:
        return "six_of_a_kind", cards

    # Flush: 5 of same position
    if n == 5 and len(pos_counts) == 1:
        return "flush", cards

    # Position Split: exactly 3 of one position + 3 of another (6 cards, 2 positions)
    if n == 6 and len(pos_counts) == 2:
        counts = sorted(pos_counts.values())
        if counts == [3, 3]:
            return "position_split", cards

    # Quad: 4 of same position (use highest 4 by score)
    for pos, cnt in sorted(pos_counts.items(), key=lambda x: -x[1]):
        if cnt >= 4:
            quad_cards = sorted([c for c in cards if c["pos"] == pos], key=lambda c: c["fantasy_ppr"] * POS_MULT.get(c["pos"], 1), reverse=True)[:4]
            return "quad", quad_cards

    # Trips: 3 of same position
    for pos, cnt in sorted(pos_counts.items(), key=lambda x: -x[1]):
        if cnt >= 3:
            trip_cards = sorted([c for c in cards if c["pos"] == pos], key=lambda c: c["fantasy_ppr"] * POS_MULT.get(c["pos"], 1), reverse=True)[:3]
            return "trips", trip_cards

    # Double: best pair by total score
    pairs = [pos for pos, cnt in pos_counts.items() if cnt >= 2]
    if pairs:
        best_pos = max(pairs, key=lambda p: sum(c["fantasy_ppr"] * POS_MULT.get(c["pos"], 1) for c in cards if c["pos"] == p))
        pair_cards = sorted([c for c in cards if c["pos"] == best_pos], key=lambda c: c["fantasy_ppr"] * POS_MULT.get(c["pos"], 1), reverse=True)[:2]
        return "double", pair_cards

    # Single: highest scoring card
    best = max(cards, key=lambda c: c["fantasy_ppr"] * POS_MULT.get(c["pos"], 1))
    return "single", [best]


def _calc_joker_mult(hand_type, scoring_cards, all_played, joker_ids, joker_state=None, floor=1, is_blueprint_call=False, joker_enhancements=None):
    if joker_state is None:
        joker_state = {}
    if joker_enhancements is None:
        joker_enhancements = {}
    bonus = 0.0
    for jid in joker_ids:
        jbonus = 0.0
        if jid == "te_monster":
            jbonus = 2 * sum(1 for c in scoring_cards if c["pos"] == "TE")
        elif jid == "air_raid":
            jbonus = 1.5 * sum(1 for c in scoring_cards if c["pos"] == "WR")
        elif jid == "ground_pound":
            jbonus = 2 * sum(1 for c in scoring_cards if c["pos"] == "RB")
        elif jid == "field_general":
            jbonus = 4 * sum(1 for c in scoring_cards if c["pos"] == "QB")
        elif jid == "pro_bowl_pedigree":
            jbonus = sum(c.get("pro_bowls", 0) or 0 for c in scoring_cards)
        elif jid == "star_power":
            jbonus = 3 * sum(1 for c in scoring_cards if (c.get("pro_bowls", 0) or 0) >= 3)
        elif jid == "first_rounder":
            jbonus = 2 * sum(1 for c in scoring_cards if c.get("draft_round") == 1)
        elif jid == "west_coast_offense" and hand_type == "balanced_offense":
            jbonus = 6
        elif jid == "position_coach" and hand_type == "flush":
            jbonus = 5
        elif jid == "team_chemistry":
            if len(set(c["team"] for c in all_played)) == 1:
                jbonus = 7
        elif jid == "college_dynasty":
            colleges = Counter(c.get("college") for c in scoring_cards if c.get("college"))
            if any(v >= 3 for v in colleges.values()):
                jbonus = 4
        elif jid == "new_wave":
            if all((c.get("draft_year") or 0) >= 2020 for c in all_played):
                jbonus = 7
        elif jid == "old_school":
            if all(0 < (c.get("draft_year") or 9999) < 2016 for c in all_played):
                jbonus = 5
        elif jid == "volume_scorer":
            extra = len(all_played) - 3
            if extra > 0:
                jbonus = 1.5 * extra
        elif jid == "conference_pride":
            confs = [get_conference(c.get("college")) for c in scoring_cards]
            confs = [c for c in confs if c]  # remove None
            if confs and len(set(confs)) == 1 and len(confs) >= 2:
                jbonus = 6
        # New jokers
        elif jid == "film_study":
            jbonus = joker_state.get("film_study_stacks", 0) * 0.5
        elif jid == "hot_streak":
            jbonus = joker_state.get("hot_streak_count", 0) * 3
        elif jid == "blueprint" and not is_blueprint_call:
            # Find next joker to the right
            try:
                idx = list(joker_ids).index("blueprint")
                next_idx = idx + 1
                if next_idx < len(joker_ids):
                    next_jid = list(joker_ids)[next_idx]
                    # Calculate that joker's individual bonus (one-joker list, blueprint call)
                    jbonus = _calc_joker_mult(
                        hand_type, scoring_cards, all_played, [next_jid],
                        joker_state=joker_state, floor=floor, is_blueprint_call=True,
                        joker_enhancements=joker_enhancements
                    )
            except ValueError:
                pass
        elif jid == "double_agent":
            jbonus = 2 * (len(joker_ids) - 1)
        elif jid == "depth_chart":
            jbonus = 2 * len(set(c["pos"] for c in scoring_cards))
        elif jid == "hail_mary" and hand_type == "single":
            jbonus = 15
        elif jid == "the_duo_joker" and hand_type == "double":
            jbonus = 5
        elif jid == "the_trio_joker" and hand_type == "trips":
            jbonus = 6
        elif jid == "the_squad" and hand_type == "quad":
            jbonus = 8
        elif jid == "championship_run":
            jbonus = (floor - 1)
        elif jid == "undrafted_diamond":
            jbonus = 5 * sum(1 for c in scoring_cards if c.get("undrafted") or not c.get("college") or c.get("college") == "Unknown")
        # Apply joker enhancements to per-joker contribution
        if jbonus != 0:
            enhs = joker_enhancements.get(jid, [])
            if "boost_sticker" in enhs:
                jbonus += 2
            if "multiplier_sticker" in enhs:
                jbonus *= 1.5
            if "echo_sticker" in enhs:
                jbonus *= 2
        bonus += jbonus
    return bonus


def _calc_joker_mult_factor(hand_type, scoring_cards, all_played, joker_ids, joker_state=None, floor=1):
    """Returns a multiplicative factor (default 1.0) applied to total mult."""
    joker_state = joker_state or {}
    factor = 1.0
    p5 = {"SEC", "Big Ten", "ACC", "Big 12", "Pac-12"}
    for jid in joker_ids:
        if jid == "sec_speed":
            sec_count = sum(1 for c in scoring_cards if get_conference(c.get("college", "")) == "SEC")
            if sec_count > 0:
                factor *= (1 + 0.35 * sec_count)
        elif jid == "power5_premium":
            if scoring_cards and all(get_conference(c.get("college", "")) in p5 for c in scoring_cards):
                factor *= 1.4
        elif jid == "snowball":
            stacks = min(joker_state.get("hot_streak_count", 0), 6)
            factor *= (1 + 0.12 * stacks)
        elif jid == "dynasty_builder":
            colleges = Counter(c.get("college") for c in scoring_cards if c.get("college") and c.get("college") != "Unknown")
            if any(v >= 3 for v in colleges.values()):
                factor *= 2.0
        elif jid == "chain_reaction":
            factor *= max(1.0, 1.0 + 0.2 * (len(joker_ids) - 1))
    return round(factor, 3)


def _calc_coins_earned(hand_type, scoring_cards, all_played, joker_ids, coins, joker_enhancements=None):
    """Calculate coins earned from money jokers this play."""
    joker_enhancements = joker_enhancements or {}
    earned = 0
    for jid in joker_ids:
        if jid == "accountant":
            earned += 2
        elif jid == "sports_agent":
            earned += sum(c.get("pro_bowls", 0) or 0 for c in scoring_cards)
        elif jid == "endorsement_deal":
            earned += sum(1 for c in all_played if c["pos"] == "WR")
        elif jid == "cap_space":
            earned += len(set(c["pos"] for c in all_played))
        elif jid == "bonus_clause" and hand_type == "balanced_offense":
            earned += 5
    # gold_wire: earn $1 per joker with gold_wire enhancement
    gold_wire_count = sum(1 for jid in joker_ids if "gold_wire" in joker_enhancements.get(jid, []))
    earned += gold_wire_count
    return earned


def score_hand(cards_played, joker_ids, skill_levels=None, combo_boosts=None, card_effects=None, joker_state=None, floor=1, joker_enhancements=None):
    """Score a played hand with skill levels, combo boosts, and card effects."""
    if skill_levels is None:
        skill_levels = {}
    if combo_boosts is None:
        combo_boosts = {}
    if card_effects is None:
        card_effects = {}
    if joker_state is None:
        joker_state = {}
    if joker_enhancements is None:
        joker_enhancements = {}

    if not cards_played:
        return {"score": 0, "hand_type": None}

    hand_type, scoring_cards = evaluate_hand(cards_played)

    # Calculate base pts with effective PPR and position multipliers
    base_pts = 0.0
    for c in scoring_cards:
        eff_ppr = _get_effective_ppr(c, skill_levels, card_effects)
        eff_pos_mult = _get_effective_pos_mult(c["pos"], joker_ids, skill_levels)
        base_pts += eff_ppr * eff_pos_mult

    # Card-by-card contributions (before smash_factor)
    card_contributions = [
        {
            "id": c["id"],
            "player": c["player"],
            "pos": c["pos"],
            "effective_ppr": round(_get_effective_ppr(c, skill_levels, card_effects), 1),
            "pos_mult": round(_get_effective_pos_mult(c["pos"], joker_ids, skill_levels), 2),
            "contribution": round(_get_effective_ppr(c, skill_levels, card_effects) * _get_effective_pos_mult(c["pos"], joker_ids, skill_levels), 1),
        }
        for c in scoring_cards
    ]

    # Glass cards: x2 score if in scoring cards
    glass_in_scoring = any("glass" in card_effects.get(c["id"], []) for c in scoring_cards)
    glass_mult = 2.0 if glass_in_scoring else 1.0

    # Also add glass mult bonus to joker mult display
    hand_mult = HAND_TYPES[hand_type]["mult"] + combo_boosts.get(hand_type, 0)
    joker_mult = _calc_joker_mult(hand_type, scoring_cards, cards_played, joker_ids, joker_state=joker_state, floor=floor, joker_enhancements=joker_enhancements)
    total_mult = hand_mult + joker_mult
    # Multiplicative factor from special jokers
    mult_factor = _calc_joker_mult_factor(hand_type, scoring_cards, cards_played, joker_ids, joker_state=joker_state, floor=floor)
    score = round(base_pts * total_mult * mult_factor * glass_mult)

    # smash_factor: x1.5 multiplicative after all other scoring
    if "smash_factor" in joker_ids:
        score = round(score * 1.5)

    return {
        "score": score,
        "hand_type": hand_type,
        "hand_name": HAND_TYPES[hand_type]["name"],
        "hand_desc": HAND_TYPES[hand_type]["desc"],
        "base_pts": round(base_pts, 1),
        "hand_mult": hand_mult,
        "joker_mult": round(joker_mult, 1),
        "total_mult": round(total_mult, 1),
        "mult_factor": mult_factor,
        "glass_mult": glass_mult,
        "scoring_cards": scoring_cards,
        "card_contributions": card_contributions,
        "scoring_card_ids": [c["id"] for c in scoring_cards],
    }


def _get_joker_options(current_jokers, n=3):
    """Return n random joker options not already owned."""
    owned = set(current_jokers)
    available = [j for j in JOKERS if j["id"] not in owned]
    random.shuffle(available)
    return available[:n]


def _generate_shop(conn, state):
    """Generate shop items grouped into sections."""
    floor = state.get("floor", 1)
    # Tier based on floor
    if floor <= 3:
        tier_name = "Common"
        tier_mult = 1.0
        allowed_rarities = ("common",)
    elif floor <= 6:
        tier_name = "Veteran"
        tier_mult = 1.5
        allowed_rarities = ("common", "uncommon")
    else:
        tier_name = "Elite"
        tier_mult = 2.0
        allowed_rarities = ("common", "uncommon", "rare", "legendary")

    def scale_cost(base):
        return max(1, round(base * tier_mult))

    owned_joker_ids = set(state["jokers"])
    available_jokers = [j for j in JOKERS if j["id"] not in owned_joker_ids and j["rarity"] in allowed_rarities]
    random.shuffle(available_jokers)

    items = []
    slot_idx = 0

    # ── Section "roster": up to 2 jokers + player cards, total 3 ──────
    joker_count = min(2, len(available_jokers))
    for j in available_jokers[:joker_count]:
        base_cost = {"common": 5, "uncommon": 6, "rare": 8, "legendary": 10}.get(j["rarity"], 5)
        cost = scale_cost(base_cost)
        items.append({
            "shop_id": str(uuid.uuid4())[:8],
            "slot": slot_idx,
            "section": "roster",
            "type": "joker",
            "joker_id": j["id"],
            "name": j["name"],
            "desc": j["desc"],
            "rarity": j["rarity"],
            "cost": cost,
            "tier_name": tier_name,
            "sold": False,
        })
        slot_idx += 1

    # Player card(s) to fill roster section to 3 total
    roster_player_count = 3 - joker_count
    try:
        ppr_min = 80 if floor <= 3 else (120 if floor <= 6 else 180)
        buy_rows = conn.execute("""
            SELECT s.player, s.season, s.pos, s.team, s.fantasy_ppr,
                   d.pro_bowls, d.college, d.draft_year, d.draft_round, d.draft_pick
            FROM stats s
            LEFT JOIN draft d ON s.player = d.player
            WHERE s.fantasy_ppr >= ?
              AND s.pos IN ('QB','RB','WR','TE')
            ORDER BY RANDOM()
            LIMIT 10
        """, (ppr_min,)).fetchall()
        existing_ids = {(c["player"], c["season"]) for c in state.get("deck_pool", [])}
        buy_candidates = [r for r in buy_rows if (r[0], r[1]) not in existing_ids]
        for i, row in enumerate(buy_candidates[:roster_player_count]):
            college = row[6]
            card_data = {
                "id": f"{row[0]}_{row[1]}_{row[2]}_buycard{i}",
                "player": row[0],
                "season": row[1],
                "pos": row[2],
                "team": row[3],
                "fantasy_ppr": round(row[4], 1),
                "pro_bowls": int(row[5]) if row[5] else 0,
                "college": college,
                "draft_year": row[7],
                "draft_round": row[8],
                "draft_pick": row[9],
                "undrafted": not college or college == "Unknown",
                "conference": get_conference(college),
            }
            base_card_cost = random.randint(4, 8)
            items.append({
                "shop_id": str(uuid.uuid4())[:8],
                "slot": slot_idx,
                "section": "roster",
                "type": "buy_card",
                "name": f"{row[0]} '{str(row[1])[-2:]}",
                "desc": f"{row[2]} · {row[3]} · {round(row[4], 1)} PPR",
                "cost": scale_cost(base_card_cost),
                "tier_name": tier_name,
                "sold": False,
                "card_data": card_data,
            })
            slot_idx += 1
    except Exception:
        pass

    # ── Section "training": pick 3 from pool of (skill, effect/mod, upgrade, enhancement) ─
    training_pool = []

    # Option A: skill card
    skill_options = list(SHOP_SKILL_CARDS)
    random.shuffle(skill_options)
    sk = skill_options[0]
    level = state["skill_levels"].get(sk["pos"], 0)
    training_pool.append({
        "shop_id": str(uuid.uuid4())[:8],
        "section": "training",
        "type": "skill_card",
        "pos": sk["pos"],
        "name": sk["name"],
        "desc": f"{sk['desc']} (Level {level} → {level + 1})",
        "cost": scale_cost(sk["cost"]),
        "tier_name": tier_name,
        "sold": False,
    })

    # Option B: effect/mod card
    effect_year_cut_mod = list(SHOP_EFFECT_CARDS) + [SHOP_YEAR_CARD, SHOP_CUT_CARD] + list(SHOP_MOD_CARDS)
    random.shuffle(effect_year_cut_mod)
    ey = effect_year_cut_mod[0]
    eitem = {
        "shop_id": str(uuid.uuid4())[:8],
        "section": "training",
        "needs_target": ey.get("needs_target", False),
        "cost": scale_cost(ey["cost"]),
        "tier_name": tier_name,
        "sold": False,
    }
    eitem.update({k: v for k, v in ey.items() if k != "id"})
    if "effect" in ey:
        eitem["effect"] = ey["effect"]
    training_pool.append(eitem)

    # Option C: upgrade
    # Option C: upgrade — only available ~33% of the time (rare permanent stat boosts)
    if random.random() < 0.33:
        upgrade_options = list(SHOP_UPGRADES)
        random.shuffle(upgrade_options)
        ug = upgrade_options[0]
        training_pool.append({
            "shop_id": str(uuid.uuid4())[:8],
            "section": "training",
            "type": "upgrade",
            "stat": ug["stat"],
            "amount": ug["amount"],
            "name": ug["name"],
            "desc": ug["desc"],
            "cost": scale_cost(ug["cost"]),
            "tier_name": tier_name,
            "sold": False,
        })

    # Option D: joker enhancement
    enh_options = list(JOKER_ENHANCEMENT_ITEMS)
    random.shuffle(enh_options)
    eh = enh_options[0]
    training_pool.append({
        "shop_id": str(uuid.uuid4())[:8],
        "section": "training",
        "type": "joker_enhancement",
        "enhancement_id": eh["enhancement_id"],
        "name": eh["name"],
        "desc": eh["desc"],
        "cost": scale_cost(eh["cost"]),
        "tier_name": tier_name,
        "needs_joker_target": True,
        "sold": False,
    })

    # Option E: second effect/mod card for variety
    effect_year_cut_mod2 = list(SHOP_EFFECT_CARDS) + [SHOP_YEAR_CARD, SHOP_CUT_CARD] + list(SHOP_MOD_CARDS)
    random.shuffle(effect_year_cut_mod2)
    ey2 = effect_year_cut_mod2[0]
    eitem2 = {
        "shop_id": str(uuid.uuid4())[:8],
        "section": "training",
        "needs_target": ey2.get("needs_target", False),
        "cost": scale_cost(ey2["cost"]),
        "tier_name": tier_name,
        "sold": False,
    }
    eitem2.update({k: v for k, v in ey2.items() if k != "id"})
    if "effect" in ey2:
        eitem2["effect"] = ey2["effect"]
    training_pool.append(eitem2)

    # Pick 3 (skill always included; randomly pick 2 of the remaining options)
    random.shuffle(training_pool[1:])
    for tp in training_pool[:3]:
        tp["slot"] = slot_idx
        items.append(tp)
        slot_idx += 1

    # Sort by slot
    items.sort(key=lambda x: x["slot"])
    return items


def _get_fight_target(round_num, fight_num):
    base = ROUND_BASE_TARGETS[min(round_num - 1, len(ROUND_BASE_TARGETS) - 1)]
    scale = FIGHT_SCALE[min(fight_num - 1, len(FIGHT_SCALE) - 1)]
    return int(base * scale)


def _get_level_name(round_num, fight_num, boss_effect=None):
    round_name = ROUND_NAMES[min(round_num - 1, len(ROUND_NAMES) - 1)]
    if fight_num == 3:
        boss_name = BOSS_EFFECT_MAP.get(boss_effect, {}).get("name", "Boss") if boss_effect else "Boss"
        return f"{round_name} · BOSS: {boss_name}"
    return f"{round_name} · Fight {fight_num}"


def _apply_boss_hand_effect(state):
    """Remove cards from hand affected by boss effect."""
    boss = state.get("boss_effect")
    if not boss:
        return
    if boss == "sec_lockout":
        state["hand"] = [c for c in state["hand"] if c.get("conference") != "SEC"]
        state["deck_pool"] = [c for c in state["deck_pool"] if c.get("conference") != "SEC"]
    elif boss == "rookie_ban":
        state["hand"] = [c for c in state["hand"] if not ((c.get("draft_year") or 0) >= 2020)]
        state["deck_pool"] = [c for c in state["deck_pool"] if not ((c.get("draft_year") or 0) >= 2020)]


def start_game(conn):
    cleanup_old_games()
    deck_pool = _build_deck_pool(conn)

    gid = str(uuid.uuid4())[:8]
    state = {
        "created_at": time.time(),
        "floor": 1,
        "round": 1,
        "fight": 1,
        "boss_effect": None,
        "target_score": _get_fight_target(1, 1),
        "level_name": _get_level_name(1, 1),
        "current_score": 0,
        "hands_remaining": 4,
        "discards_remaining": 3,
        "hand": [],
        "deck": [],
        "deck_pool": deck_pool,
        "jokers": [],
        "status": "playing",
        "history": [],
        "reward_options": [],
        "coins": 4,
        "skill_levels": {"QB": 0, "RB": 0, "WR": 0, "TE": 0},
        "combo_boosts": {"balanced_offense": 0, "six_of_a_kind": 0, "flush": 0, "position_split": 0, "quad": 0, "trips": 0, "double": 0, "single": 0},
        "card_effects": {},  # card_id -> list of effects
        "shop_items": [],
        "max_hand_size": 7,
        "base_discards": 3,
        "restock_count": 0,
        "max_jokers": 5,
        "joker_state": {},
        "joker_enhancements": {},
        "shop_packs": [],
        "held_cards": [],
    }
    _deal_for_level(state)
    _GAMES[gid] = state
    return gid, state


def get_state(gid):
    return _GAMES.get(gid)


def play_hand(gid, card_ids):
    """Play a set of cards. card_ids are the card 'id' strings."""
    g = _GAMES.get(gid)
    if not g or g["status"] != "playing":
        return None, "Invalid game state"
    if g["hands_remaining"] <= 0:
        return None, "No hands remaining"
    if not card_ids or len(card_ids) > 6:
        return None, "Must play 1-6 cards"

    boss_effect = g.get("boss_effect")
    if boss_effect == "false_start" and len(card_ids) > 4:
        return None, "Boss effect: max 4 cards"

    id_set = set(card_ids)
    played = [c for c in g["hand"] if c["id"] in id_set]
    if len(played) != len(card_ids):
        return None, "Some cards not found in hand"

    skill_levels = g.get("skill_levels", {})
    combo_boosts = g.get("combo_boosts", {})
    card_effects = g.get("card_effects", {})
    joker_state = g.get("joker_state", {})
    joker_enhancements = g.get("joker_enhancements", {})

    result = score_hand(played, g["jokers"], skill_levels, combo_boosts, card_effects, joker_state=joker_state, floor=g.get("floor", 1), joker_enhancements=joker_enhancements)

    # Apply boss score factors
    boss_factor = 1.0
    if boss_effect == "zone_coverage" and result["hand_type"] == "quad":
        boss_factor = 0.5
    elif boss_effect == "receiver_foul" and any(c["pos"] == "WR" for c in result["scoring_cards"]):
        boss_factor = 0.6
    elif boss_effect == "penalty_flag":
        boss_factor = 0.8
    elif boss_effect == "rb_stuffed" and any(c["pos"] == "RB" for c in result["scoring_cards"]):
        boss_factor = 0.6
    elif boss_effect == "scoreboard_cap":
        boss_factor = 0.7
    if boss_factor != 1.0:
        result["score"] = int(result["score"] * boss_factor)
    result["boss_factor"] = boss_factor

    g["current_score"] += result["score"]
    g["hands_remaining"] -= 1

    # Calculate coins earned from money jokers
    coins_earned = _calc_coins_earned(
        result["hand_type"], result["scoring_cards"], played, g["jokers"], g["coins"],
        joker_enhancements=joker_enhancements
    )

    # Gold card coins
    for c in result["scoring_cards"]:
        if "gold" in card_effects.get(c["id"], []):
            coins_earned += 2

    g["coins"] = g.get("coins", 0) + coins_earned

    # Remove played cards from hand and draw replacements
    g["hand"] = [c for c in g["hand"] if c["id"] not in id_set]
    draw_count = min(len(card_ids), len(g["deck"]))
    g["hand"].extend(g["deck"][:draw_count])
    g["deck"] = g["deck"][draw_count:]

    # Handle glass breaking
    broken_cards = []
    scoring_card_ids = {c["id"] for c in result["scoring_cards"]}
    for cid in list(scoring_card_ids):
        effects = card_effects.get(cid, [])
        if "glass" in effects:
            if random.random() < 0.33:
                broken_cards.append(cid)
                new_effects = [e for e in effects if e != "glass"]
                if new_effects:
                    card_effects[cid] = new_effects
                else:
                    card_effects.pop(cid, None)
                # Also remove card from deck_pool if broken
                g["deck_pool"] = [c for c in g["deck_pool"] if c["id"] != cid]
                g["hand"] = [c for c in g["hand"] if c["id"] != cid]
                g["deck"] = [c for c in g["deck"] if c["id"] != cid]

    # Update scaling joker states
    if "film_study" in g["jokers"]:
        g["joker_state"]["film_study_stacks"] = g["joker_state"].get("film_study_stacks", 0) + 1

    if "hot_streak" in g["jokers"]:
        threshold = 2000
        if result["score"] >= threshold:
            g["joker_state"]["hot_streak_count"] = g["joker_state"].get("hot_streak_count", 0) + 1
        else:
            g["joker_state"]["hot_streak_count"] = 0

    result["joker_state"] = g["joker_state"]
    result["cumulative_score"] = g["current_score"]
    result["target_score"] = g["target_score"]
    result["hands_remaining"] = g["hands_remaining"]
    result["discards_remaining"] = g["discards_remaining"]
    result["coins_earned"] = coins_earned
    result["coins"] = g["coins"]
    result["broken_cards"] = broken_cards

    if g["current_score"] >= g["target_score"]:
        fight = g.get("fight", 1)
        round_num = g.get("round", 1)
        if fight == 3 and round_num >= 8:
            # Final boss of final round — game won
            g["status"] = "won_game"
            result["status"] = "won_game"
        else:
            # Every fight win (including boss) goes to shop
            g["status"] = "won_fight"
            result["status"] = "won_fight"
            result["fight"] = fight
            result["round"] = round_num
    elif g["hands_remaining"] <= 0:
        g["status"] = "lost"
        result["status"] = "lost"
    else:
        result["status"] = "playing"

    g["history"].append(result)
    return result, None


def advance_fight(gid, conn=None):
    """Called when won_fight. Award coins, open shop, then advance to next fight when leaving shop."""
    g = _GAMES.get(gid)
    if not g or g["status"] != "won_fight":
        return None, "Not in won_fight state"

    fight = g.get("fight", 1)
    round_num = g.get("round", 1)

    # Award coins for completing fight
    fight_coins = 2 + round_num
    g["coins"] = g.get("coins", 0) + fight_coins

    # Determine next state: within round or new round
    if fight == 3:
        # Boss defeated — advance to next round
        next_round = round_num + 1
        next_fight = 1
        boss_effect = None  # No boss for fight 1 of new round
    else:
        next_round = round_num
        next_fight = fight + 1
        boss_effect = random.choice(BOSS_EFFECTS)["id"] if next_fight == 3 else None

    # Store pending advance — resolved when player leaves shop
    g["pending_fight_advance"] = True
    g["next_round"] = next_round
    g["next_fight"] = next_fight
    g["pending_boss_effect"] = boss_effect

    # Transition to shopping
    g["status"] = "shopping"
    g["restock_count"] = 0

    # Generate shop
    shop_packs = list(PACKS)
    random.shuffle(shop_packs)
    g["shop_packs"] = shop_packs[:2]
    if conn:
        g["shop_items"] = _generate_shop(conn, g)
    else:
        g["shop_items"] = []
        g["pending_shop_generation"] = True

    return {
        "status": "shopping",
        "coins": g["coins"],
        "fight_coins_earned": fight_coins,
        "jokers": [JOKER_MAP[jid] for jid in g["jokers"]],
        "max_jokers": g.get("max_jokers", 5),
        "shop_items": g["shop_items"],
        "shop_packs": g["shop_packs"],
        "joker_enhancements": g.get("joker_enhancements", {}),
        "held_cards": g.get("held_cards", []),
        "next_fight": next_fight,
        "next_boss_effect": BOSS_EFFECT_MAP.get(boss_effect) if boss_effect else None,
    }, None


def discard_cards(gid, card_ids):
    """Discard cards and draw replacements."""
    g = _GAMES.get(gid)
    if not g or g["status"] != "playing":
        return None, "Invalid game state"
    if g["discards_remaining"] <= 0:
        return None, "No discards remaining"
    if not card_ids or len(card_ids) > 5:
        return None, "Must discard 1-5 cards"

    id_set = set(card_ids)
    discarded = [c for c in g["hand"] if c["id"] in id_set]
    if not discarded:
        return None, "No valid cards to discard"

    g["discards_remaining"] -= 1
    g["hand"] = [c for c in g["hand"] if c["id"] not in id_set]
    draw_count = min(len(discarded), len(g["deck"]))
    g["hand"].extend(g["deck"][:draw_count])
    g["deck"] = g["deck"][draw_count:]

    return {
        "discards_remaining": g["discards_remaining"],
        "hand": g["hand"],
        "status": "playing",
    }, None


def select_joker(gid, joker_id):
    """Advance from won_level to shopping, giving coins."""
    g = _GAMES.get(gid)
    if not g or g["status"] != "won_level":
        return None, "Not in reward selection state"

    # Earn floor coins
    floor_coins = max(3, g["floor"] * 2)
    g["coins"] = g.get("coins", 0) + floor_coins

    # Interest: 1 coin per 5 held, capped at 5
    held = g["coins"]
    interest = min(5, held // 5)
    g["coins"] += interest

    g["status"] = "shopping"
    g["reward_options"] = []
    g["restock_count"] = 0  # reset restock count each shop visit

    # Generate shop packs
    shop_packs = list(PACKS)
    random.shuffle(shop_packs)
    g["shop_packs"] = shop_packs[:2]

    # Generate shop using conn - store shop items directly
    # We'll generate shop without DB for jokers already in pool
    # For full shop we need conn; we'll return a flag and generate in route
    g["pending_shop_generation"] = True

    return {
        "status": "shopping",
        "coins": g["coins"],
        "floor_coins_earned": floor_coins,
        "interest_earned": interest,
        "jokers": [JOKER_MAP[jid] for jid in g["jokers"]],
        "max_jokers": g.get("max_jokers", 5),
        "shop_packs": g["shop_packs"],
        "joker_enhancements": g.get("joker_enhancements", {}),
        "held_cards": g.get("held_cards", []),
    }, None


def generate_shop_for_game(gid, conn):
    """Generate shop items for a game (called from route with db connection)."""
    g = _GAMES.get(gid)
    if not g:
        return None
    g["shop_items"] = _generate_shop(conn, g)
    g.pop("pending_shop_generation", None)
    return g["shop_items"]


def buy_shop_item(gid, item_type, shop_id, target_card_id=None, target_year=None, conn=None):
    """Buy an item from the shop."""
    g = _GAMES.get(gid)
    if not g or g["status"] != "shopping":
        return None, "Not in shopping state"

    # Find item in shop
    item = next((i for i in g["shop_items"] if i["shop_id"] == shop_id), None)
    if not item:
        return None, "Item not found in shop"

    cost = item["cost"]
    if g["coins"] < cost:
        return None, "Not enough coins"

    updated_card = None

    if item["type"] == "joker":
        if len(g["jokers"]) >= g.get("max_jokers", 5):
            return None, "Joker slots full"
        g["jokers"].append(item["joker_id"])

    elif item["type"] == "skill_card":
        pos = item["pos"]
        g["skill_levels"][pos] = g["skill_levels"].get(pos, 0) + 1

    elif item["type"] == "combo_card":
        ht = item["hand_type"]
        g["combo_boosts"][ht] = round(g["combo_boosts"].get(ht, 0) + item["boost"], 2)

    elif item["type"] == "effect_card":
        if not target_card_id:
            return None, "Target card required"
        effect = item["effect"]
        if target_card_id not in g["card_effects"]:
            g["card_effects"][target_card_id] = []
        if effect not in g["card_effects"][target_card_id]:
            g["card_effects"][target_card_id].append(effect)

    elif item["type"] == "year_card":
        if not target_card_id:
            return None, "Target card required"
        if not target_year:
            return None, "Year not specified"
        if not conn:
            return None, "DB connection required"
        # Find card in deck_pool
        target_card = next((c for c in g["deck_pool"] if c["id"] == target_card_id), None)
        if not target_card:
            return None, "Target card not found in pool"
        # Fetch stats for target_year
        rows = conn.execute("""
            SELECT s.season, s.team, s.fantasy_ppr
            FROM stats s
            WHERE s.player = ? AND s.season = ? AND s.pos = ?
            LIMIT 1
        """, (target_card["player"], int(target_year), target_card["pos"])).fetchall()
        if rows:
            r = rows[0]
            target_card["season"] = r[0]
            target_card["team"] = r[1]
            target_card["fantasy_ppr"] = round(r[2], 1)
            # Also update in hand if present
            for hcard in g["hand"]:
                if hcard["id"] == target_card_id:
                    hcard["season"] = r[0]
                    hcard["team"] = r[1]
                    hcard["fantasy_ppr"] = round(r[2], 1)
            updated_card = target_card

    elif item["type"] == "cut_card":
        if not target_card_id:
            return None, "Target card required"
        g["deck_pool"] = [c for c in g["deck_pool"] if c["id"] != target_card_id]
        g["hand"] = [c for c in g["hand"] if c["id"] != target_card_id]
        g["deck"] = [c for c in g["deck"] if c["id"] != target_card_id]
        g["card_effects"].pop(target_card_id, None)

    elif item["type"] == "upgrade":
        stat = item["stat"]
        amount = item["amount"]
        if stat == "max_jokers":
            g["max_jokers"] = g.get("max_jokers", 5) + amount
        else:
            g[stat] = g.get(stat, 7 if stat == "max_hand_size" else 3) + amount
        # For hand size upgrade: draw 1 more card from deck into hand
        if stat == "max_hand_size" and g["deck"]:
            g["hand"].append(g["deck"][0])
            g["deck"] = g["deck"][1:]

    elif item["type"] == "mod_card":
        if not target_card_id:
            return None, "Target card required"
        effect = item.get("effect", "")
        if effect == "duplicate":
            import copy as _copy
            target = next((c for c in g["deck_pool"] if c["id"] == target_card_id), None)
            if not target:
                return None, "Card not found"
            dup = _copy.deepcopy(target)
            dup["id"] = target["id"] + "_dup" + str(len(g["deck_pool"]))
            g["deck_pool"].append(dup)
        elif effect == "trained":
            effs = g["card_effects"].setdefault(target_card_id, [])
            if "trained" not in effs:
                effs.append("trained")
            # Apply trained effect visually (add to card class)
            for c in g["deck_pool"]:
                if c["id"] == target_card_id:
                    break
        elif effect == "pos_switch":
            switch_map = {"RB": "TE", "WR": "QB", "TE": "RB", "QB": "WR"}
            target = next((c for c in g["deck_pool"] if c["id"] == target_card_id), None)
            if not target:
                return None, "Card not found"
            new_pos = switch_map.get(target["pos"], target["pos"])
            target["pos"] = new_pos
            for hc in g["hand"]:
                if hc["id"] == target_card_id:
                    hc["pos"] = new_pos

    elif item["type"] == "buy_card":
        card_data = item.get("card_data")
        if not card_data:
            return None, "No card data in item"
        if "held_cards" not in g:
            g["held_cards"] = []
        if len(g["held_cards"]) >= 3:
            return None, "Held card limit reached (max 3)"
        g["held_cards"].append(card_data)

    elif item["type"] == "joker_enhancement":
        target_joker_id = target_card_id  # reuse target_card_id param as joker target
        if not target_joker_id or target_joker_id not in g["jokers"]:
            return None, "Joker not in collection"
        enhancement_id = item.get("enhancement_id")
        if not enhancement_id:
            return None, "No enhancement_id on item"
        enhs = g["joker_enhancements"].setdefault(target_joker_id, [])
        enhs.append(enhancement_id)

    g["coins"] -= cost
    # Mark item as sold instead of removing it
    for i in g["shop_items"]:
        if i["shop_id"] == shop_id:
            i["sold"] = True
            break

    result = {
        "coins": g["coins"],
        "shop_items": g["shop_items"],
        "jokers": [JOKER_MAP[jid] for jid in g["jokers"]],
        "skill_levels": g["skill_levels"],
        "combo_boosts": g["combo_boosts"],
        "card_effects": g["card_effects"],
        "hand": g["hand"],
        "max_hand_size": g.get("max_hand_size", 7),
        "base_discards": g.get("base_discards", 3),
        "max_jokers": g.get("max_jokers", 5),
        "joker_enhancements": g.get("joker_enhancements", {}),
        "held_cards": g.get("held_cards", []),
    }
    if updated_card:
        result["updated_card"] = updated_card

    return result, None


def reroll_shop(gid, conn):
    """Reroll shop items for 1 coin."""
    g = _GAMES.get(gid)
    if not g or g["status"] != "shopping":
        return None, "Not in shopping state"
    if g["coins"] < 1:
        return None, "Not enough coins"
    g["coins"] -= 1
    g["shop_items"] = _generate_shop(conn, g)
    return {
        "coins": g["coins"],
        "shop_items": g["shop_items"],
    }, None


def restock_shop(gid, conn):
    """Restock the shop (escalating cost)."""
    g = _GAMES.get(gid)
    if not g or g["status"] != "shopping":
        return None, "Not in shopping state"
    cost = 2 + g.get("restock_count", 0) * 2
    if g["coins"] < cost:
        return None, f"Not enough coins (need {cost})"
    g["coins"] -= cost
    g["restock_count"] = g.get("restock_count", 0) + 1
    g["shop_items"] = _generate_shop(conn, g)
    # Regenerate packs
    shop_packs = list(PACKS)
    random.shuffle(shop_packs)
    g["shop_packs"] = shop_packs[:2]
    return {
        "coins": g["coins"],
        "shop_items": g["shop_items"],
        "shop_packs": g["shop_packs"],
        "next_restock_cost": 2 + g["restock_count"] * 2,
    }, None


def sell_joker(gid, joker_id):
    """Sell a joker for coins."""
    g = _GAMES.get(gid)
    if not g:
        return None, "Game not found"
    if joker_id not in g["jokers"]:
        return None, "Joker not owned"
    joker = JOKER_MAP.get(joker_id, {})
    sell_price = {"common": 2, "uncommon": 3, "rare": 4}.get(joker.get("rarity", "common"), 2)
    g["jokers"].remove(joker_id)
    g["coins"] += sell_price
    return {
        "coins": g["coins"],
        "jokers": [JOKER_MAP[j] for j in g["jokers"]],
        "sold": joker.get("name", joker_id),
        "earned": sell_price,
    }, None


def leave_shop(gid):
    """Advance floor, deal new hand, resume playing."""
    g = _GAMES.get(gid)
    if not g or g["status"] != "shopping":
        return None, "Not in shopping state"

    # All shops go through pending_fight_advance
    if g.get("pending_fight_advance"):
        new_fight = g.pop("next_fight")
        new_round = g.pop("next_round", g.get("round", 1))
        boss_effect = g.pop("pending_boss_effect", None)
        g.pop("pending_fight_advance")
        old_round = g.get("round", 1)

        # Smart Money interest when advancing rounds
        if new_round != old_round and "smart_money" in g["jokers"]:
            held = g["coins"]
            bonus = min(5, held // 5)
            g["coins"] += bonus

        g["round"] = new_round
        g["fight"] = new_fight
        g["floor"] = (new_round - 1) * 3 + new_fight
        g["boss_effect"] = boss_effect
        g["target_score"] = _get_fight_target(new_round, new_fight)
        g["level_name"] = _get_level_name(new_round, new_fight, boss_effect)
        g["current_score"] = 0
        g["hands_remaining"] = 4
        g["discards_remaining"] = g.get("base_discards", 3)
        g["status"] = "playing"
        g["history"] = []
        g["shop_items"] = []

        # Reset hot streak on round advance
        if new_round != old_round:
            if "joker_state" not in g:
                g["joker_state"] = {}
            g["joker_state"]["hot_streak_count"] = 0

        _deal_for_level(g)
        if boss_effect:
            _apply_boss_hand_effect(g)
        return {
            "floor": g["floor"],
            "round": new_round,
            "fight": new_fight,
            "boss_effect": BOSS_EFFECT_MAP.get(boss_effect) if boss_effect else None,
            "target_score": g["target_score"],
            "level_name": g["level_name"],
            "hands_remaining": g["hands_remaining"],
            "discards_remaining": g["discards_remaining"],
            "hand": g["hand"],
            "jokers": [JOKER_MAP[jid] for jid in g["jokers"]],
            "coins": g["coins"],
            "skill_levels": g["skill_levels"],
            "combo_boosts": g["combo_boosts"],
            "card_effects": g["card_effects"],
            "status": "playing",
            "max_hand_size": g.get("max_hand_size", 7),
            "base_discards": g.get("base_discards", 3),
            "max_jokers": g.get("max_jokers", 5),
            "joker_state": g.get("joker_state", {}),
            "joker_enhancements": g.get("joker_enhancements", {}),
            "held_cards": g.get("held_cards", []),
        }, None

    # Legacy fallback: advance to next round (kept for safety)
    # Smart Money interest at end of level
    if "smart_money" in g["jokers"]:
        held = g["coins"]
        bonus = min(5, held // 5)
        g["coins"] += bonus

    # Advance to next round
    new_round = g.get("round", 1) + 1
    g["round"] = new_round
    g["fight"] = 1
    g["floor"] = (new_round - 1) * 3 + 1
    g["boss_effect"] = None
    g["target_score"] = _get_fight_target(new_round, 1)
    g["level_name"] = _get_level_name(new_round, 1)
    g["current_score"] = 0
    g["hands_remaining"] = 4
    g["discards_remaining"] = g.get("base_discards", 3)
    g["status"] = "playing"
    g["history"] = []
    g["shop_items"] = []

    # Reset hot streak on new level
    if "joker_state" not in g:
        g["joker_state"] = {}
    g["joker_state"]["hot_streak_count"] = 0

    _deal_for_level(g)

    return {
        "floor": g["floor"],
        "round": g["round"],
        "fight": g["fight"],
        "target_score": g["target_score"],
        "level_name": g["level_name"],
        "hands_remaining": g["hands_remaining"],
        "discards_remaining": g["discards_remaining"],
        "hand": g["hand"],
        "jokers": [JOKER_MAP[jid] for jid in g["jokers"]],
        "coins": g["coins"],
        "skill_levels": g["skill_levels"],
        "combo_boosts": g["combo_boosts"],
        "card_effects": g["card_effects"],
        "status": "playing",
        "max_hand_size": g.get("max_hand_size", 7),
        "base_discards": g.get("base_discards", 3),
        "max_jokers": g.get("max_jokers", 5),
        "joker_state": g.get("joker_state", {}),
        "joker_enhancements": g.get("joker_enhancements", {}),
        "held_cards": g.get("held_cards", []),
    }, None


def get_pool(gid):
    """Return deck_pool with applied effects for target selection."""
    g = _GAMES.get(gid)
    if not g:
        return None, "Game not found"
    return {
        "deck_pool": g["deck_pool"],
        "card_effects": g["card_effects"],
    }, None


def get_player_seasons(conn, player_name):
    """Get all seasons for a player from stats table."""
    rows = conn.execute(
        "SELECT season, fantasy_ppr, team FROM stats WHERE player = ? AND fantasy_ppr IS NOT NULL ORDER BY season DESC",
        (player_name,)
    ).fetchall()
    return [{"season": r[0], "fantasy_ppr": round(r[1], 1), "team": r[2]} for r in rows]


def get_card_stats(conn, player, season):
    """Get detailed season stats for a player from season_stats table."""
    row = conn.execute(
        "SELECT * FROM season_stats WHERE player = ? AND season = ?",
        (player, int(season))
    ).fetchone()
    if not row:
        return None
    cols = [d[1] for d in conn.execute("PRAGMA table_info(season_stats)").fetchall()]
    data = dict(zip(cols, row))
    return {
        "pass_yds": data.get("pass_yds"),
        "pass_td": data.get("pass_td"),
        "pass_int": data.get("pass_int"),
        "rush_yds": data.get("rush_yds"),
        "rush_td": data.get("rush_td"),
        "rec_rec": data.get("rec_rec"),
        "rec_yds": data.get("rec_yds"),
        "rec_td": data.get("rec_td"),
        "games": data.get("games"),
    }


def get_score_preview(cards_played, joker_ids, skill_levels=None, combo_boosts=None, card_effects=None, joker_state=None, floor=1, joker_enhancements=None):
    """Preview score without modifying state."""
    return score_hand(cards_played, joker_ids, skill_levels, combo_boosts, card_effects, joker_state=joker_state, floor=floor, joker_enhancements=joker_enhancements)


def _generate_pack_cards(conn, pack_id, state, candidate_count=5):
    """Generate candidate cards for a pack opening. Returns (list of card dicts, effects dict)."""
    pack = PACK_MAP.get(pack_id)
    if not pack:
        return [], {}

    base_q = """
        SELECT s.player, s.season, s.pos, s.team, s.fantasy_ppr,
               d.pro_bowls, d.college, d.draft_year, d.draft_round, d.draft_pick
        FROM stats s
        LEFT JOIN draft d ON s.player = d.player
        WHERE (d.draft_year >= 2010 OR d.draft_year IS NULL)
          AND s.pos IN ('QB','RB','WR','TE')
    """

    existing_ids = {(c["player"], c["season"]) for c in state["deck_pool"]}
    fetch_limit = candidate_count * 4  # fetch extra to filter duplicates

    if pack_id == "starter_pack":
        rows = conn.execute(base_q + f" AND s.fantasy_ppr >= 80 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    elif pack_id == "elite_pack":
        rows = conn.execute(base_q + f" AND s.fantasy_ppr >= 200 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    elif pack_id == "position_pack":
        pos = random.choice(["QB", "RB", "WR", "TE"])
        rows = conn.execute(base_q + f" AND s.pos = '{pos}' AND s.fantasy_ppr >= 80 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    elif pack_id == "gold_pack":
        rows = conn.execute(base_q + f" AND s.fantasy_ppr >= 120 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    elif pack_id == "all_pro_pack":
        rows = conn.execute(base_q + f" AND d.pro_bowls >= 2 AND s.fantasy_ppr >= 150 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    elif pack_id == "legend_pack":
        rows = conn.execute(base_q + f" AND s.fantasy_ppr >= 350 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    else:
        rows = conn.execute(base_q + f" AND s.fantasy_ppr >= 80 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()

    cards = []
    idx_start = len(state["deck_pool"]) + 1000
    for i, r in enumerate(rows):
        if (r[0], r[1]) in existing_ids:
            continue
        college = r[6]
        card = {
            "id": f"{r[0]}_{r[1]}_{r[2]}_pack{idx_start + i}",
            "player": r[0], "season": r[1], "pos": r[2], "team": r[3],
            "fantasy_ppr": round(r[4], 1),
            "pro_bowls": int(r[5]) if r[5] else 0,
            "college": college, "draft_year": r[7], "draft_round": r[8], "draft_pick": r[9],
            "undrafted": not college or college == "Unknown",
            "conference": get_conference(college),
        }
        cards.append(card)
        if len(cards) >= candidate_count:
            break

    effects = {}
    if pack_id == "gold_pack":
        for c in cards:
            effects[c["id"]] = ["gold"]
    elif pack_id == "legend_pack" and cards:
        if random.random() < 0.5:
            effects[cards[0]["id"]] = ["glass"]

    return cards, effects


def open_pack(gid, pack_id, conn):
    """Buy a pack and return candidate cards for player to choose from."""
    g = _GAMES.get(gid)
    if not g or g["status"] != "shopping":
        return None, "Not in shopping state"

    pack = PACK_MAP.get(pack_id)
    if not pack:
        return None, "Pack not found"

    if g["coins"] < pack["cost"]:
        return None, f"Need {pack['cost']} coins (have {g['coins']})"

    # Handle joker packs
    if pack.get("is_joker_pack"):
        owned_ids = set(j if isinstance(j, str) else j["id"] for j in g["jokers"])
        available_jokers = [j for j in JOKERS if j["id"] not in owned_ids]
        random.shuffle(available_jokers)
        pack_count = pack.get("count", 3)
        candidates = available_jokers[:pack_count]
        picks_allowed = 2 if pack_count >= 5 else 1
        g["coins"] -= pack["cost"]
        g["pending_pack"] = {
            "pack_id": pack_id,
            "candidates": [j["id"] for j in candidates],
            "picks_allowed": picks_allowed,
            "is_joker_pack": True,
        }
        return {
            "pack_name": pack["name"],
            "candidates": candidates,  # full joker objects
            "picks_allowed": picks_allowed,
            "is_joker_pack": True,
            "coins": g["coins"],
        }, None

    # Determine how many candidates to show and how many player can pick
    pack_count = pack.get("count", 3)
    if pack_count >= 3:
        candidate_count = 5
        picks_allowed = 2
    else:
        candidate_count = 3
        picks_allowed = 1

    candidates, effects = _generate_pack_cards(conn, pack_id, g, candidate_count=candidate_count)

    if not candidates:
        return None, "No unique cards available for this pack"

    g["coins"] -= pack["cost"]
    g["pending_pack"] = {"candidates": candidates, "effects": effects, "picks_allowed": picks_allowed}

    return {
        "coins": g["coins"],
        "pack_name": pack["name"],
        "pack_tier": pack["tier"],
        "candidates": candidates,
        "picks_allowed": picks_allowed,
        "card_effects": effects,
    }, None


def confirm_pack_picks(gid, selected_ids):
    """Confirm which cards the player chose from a pack."""
    g = _GAMES.get(gid)
    if not g or "pending_pack" not in g:
        return None, "No pending pack"

    pending = g["pending_pack"]

    # Handle joker packs
    if pending.get("is_joker_pack"):
        candidate_ids = pending["candidates"]
        picks_allowed = pending["picks_allowed"]
        selected_ids_set = set(selected_ids)
        valid_selected = [jid for jid in selected_ids_set if jid in candidate_ids]
        if len(valid_selected) == 0:
            return None, "Must pick at least 1 joker"
        if len(valid_selected) > picks_allowed:
            return None, f"Can only pick {picks_allowed} joker(s)"
        owned_ids = set(j if isinstance(j, str) else j["id"] for j in g["jokers"])
        for jid in valid_selected:
            if jid not in owned_ids and len(g["jokers"]) < g.get("max_jokers", 5):
                g["jokers"].append(jid)
        del g["pending_pack"]
        return {
            "added_jokers": valid_selected,
            "jokers": [JOKER_MAP[j if isinstance(j, str) else j["id"]] for j in g["jokers"]],
            "coins": g["coins"],
        }, None

    candidates = pending["candidates"]
    effects = pending["effects"]
    picks_allowed = pending["picks_allowed"]

    selected_ids_set = set(selected_ids)
    selected = [c for c in candidates if c["id"] in selected_ids_set]

    if len(selected) == 0:
        return None, "Must pick at least 1 card"
    if len(selected) > picks_allowed:
        return None, f"Can only pick {picks_allowed} card(s)"

    for c in selected:
        g["deck_pool"].append(c)
    for cid, effs in effects.items():
        if cid in selected_ids_set:
            g["card_effects"][cid] = effs

    del g["pending_pack"]

    return {
        "coins": g["coins"],
        "deck_pool_size": len(g["deck_pool"]),
        "added_cards": selected,
        "card_effects": g["card_effects"],
    }, None
