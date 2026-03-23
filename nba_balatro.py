import sqlite3
import random
import uuid
import time
from collections import Counter

from session_store import GameStore

_TTL = 3600 * 4
_GAMES = GameStore("nba_balatro", ttl_seconds=_TTL)

POS_MULT = {"G": 1.0, "F": 1.5, "C": 2.5}
POS_ORDER = ["G", "F", "C"]

# ── NBA Conferences ────────────────────────────────────────────────────────────

NBA_CONFERENCES = {
    "East": ["ATL", "BOS", "BRK", "CHA", "CHI", "CLE", "DET", "IND",
             "MIA", "MIL", "NYK", "ORL", "PHI", "TOR", "WAS"],
    "West": ["DAL", "DEN", "GSW", "HOU", "LAC", "LAL", "MEM", "MIN",
             "NOP", "OKC", "PHO", "POR", "SAC", "SAS", "UTA"],
}

_TEAM_TO_CONF = {}
for _conf, _teams in NBA_CONFERENCES.items():
    for _t in _teams:
        _TEAM_TO_CONF[_t] = _conf


def get_nba_conference(team):
    if not team:
        return None
    return _TEAM_TO_CONF.get(team.upper().strip())

NBA_DIVISIONS = {
    # Atlantic
    "BOS": "Atlantic", "BRK": "Atlantic", "BKN": "Atlantic", "NYK": "Atlantic",
    "PHI": "Atlantic", "TOR": "Atlantic", "NJN": "Atlantic",
    # Central
    "CHI": "Central", "CLE": "Central", "DET": "Central", "IND": "Central", "MIL": "Central",
    # Southeast
    "ATL": "Southeast", "CHA": "Southeast", "CHH": "Southeast", "MIA": "Southeast",
    "ORL": "Southeast", "WAS": "Southeast",
    # Northwest
    "DEN": "Northwest", "MIN": "Northwest", "OKC": "Northwest", "POR": "Northwest",
    "UTA": "Northwest", "SEA": "Northwest",
    # Pacific
    "GSW": "Pacific", "LAC": "Pacific", "LAL": "Pacific", "PHX": "Pacific",
    "PHO": "Pacific", "SAC": "Pacific",
    # Southwest
    "DAL": "Southwest", "HOU": "Southwest", "MEM": "Southwest", "NOP": "Southwest",
    "SAS": "Southwest", "NOH": "Southwest", "VAN": "Southwest", "NOK": "Southwest",
}

_TEAM_TO_DIV = {t: d for d, teams in [
    ("Atlantic",  ["BOS","BRK","BKN","NYK","PHI","TOR","NJN"]),
    ("Central",   ["CHI","CLE","DET","IND","MIL"]),
    ("Southeast", ["ATL","CHA","CHH","MIA","ORL","WAS"]),
    ("Northwest", ["DEN","MIN","OKC","POR","UTA","SEA"]),
    ("Pacific",   ["GSW","LAC","LAL","PHX","PHO","SAC"]),
    ("Southwest", ["DAL","HOU","MEM","NOP","SAS","NOH","VAN","NOK"]),
] for t in teams}

def get_nba_division(team):
    if not team:
        return None
    return _TEAM_TO_DIV.get(team.upper().strip())

HAND_TYPES = {
    "division_lineup":  {"name": "Division Starting Lineup", "mult": 25.0, "desc": "G + F + C all present (5+ cards) all from same division"},
    "royal_flush":      {"name": "Royal Flush",       "mult": 20.0, "desc": "5+ cards same position & same division"},
    "division_six":     {"name": "Division Court",    "mult": 6.0,  "desc": "5+ cards all from same division"},
    "six_man_rotation": {"name": "Zone Press",        "mult": 5.5,  "desc": "5 of the same position"},
    "twin_towers":      {"name": "Twin Towers",        "mult": 4.0,  "desc": "3 of one position + 2 of another"},
    "starting_lineup":  {"name": "Starting Lineup",   "mult": 3.5,  "desc": "G + F + C all present (5+ cards)"},
    "starting_four":    {"name": "Starting Four",      "mult": 3.0,  "desc": "4 of same position"},
    "pick_roll":        {"name": "Pick & Roll",        "mult": 2.0,  "desc": "3 of same position"},
    "catch_shoot":      {"name": "Catch & Shoot",      "mult": 1.5,  "desc": "2 of same position"},
    "isolation":        {"name": "Isolation",          "mult": 1.0,  "desc": "Best single card"},
}

ROUND_BASE_TARGETS = [1800, 5000, 13000, 32000, 80000, 200000, 500000, 1300000]
ROUND_NAMES = ["Preseason", "Regular Season", "Play-In", "First Round",
               "Conference Semis", "Conference Finals", "NBA Finals", "Championship"]
FIGHT_SCALE = [1.0, 1.3, 1.7]

BOSS_EFFECTS = [
    {"id": "goaltending",    "name": "Goaltending",     "desc": "C players are removed from your hand this fight"},
    {"id": "zone_defense",   "name": "Zone Defense",    "desc": "Pick & Roll mult is halved"},
    {"id": "double_team",    "name": "Double Team",     "desc": "G position multiplier x0.5 this fight"},
    {"id": "shot_clock",     "name": "Shot Clock",      "desc": "Max 4 cards playable per hand"},
    {"id": "technical_foul", "name": "Technical Foul",  "desc": "All scores reduced by 20%"},
    {"id": "blocking_foul",  "name": "Blocking Foul",   "desc": "F position multiplier x0.5 this fight"},
    {"id": "flagrant_foul",  "name": "Flagrant Foul",   "desc": "Players from seasons 2010+ removed from hand"},
    {"id": "salary_cap",     "name": "Salary Cap",      "desc": "Base pts per card capped at 200 this fight"},
]
BOSS_EFFECT_MAP = {b["id"]: b for b in BOSS_EFFECTS}

JOKERS = [
    # ── Common ──────────────────────────────────────────────────────────────────
    {"id": "rim_protector",    "name": "Rim Protector",        "desc": "+2 mult per C card in scoring hand",                                    "rarity": "common"},
    {"id": "floor_general",    "name": "Floor General",        "desc": "+2 mult per G card in scoring hand",                                    "rarity": "common"},
    {"id": "power_forward",    "name": "Power Forward",        "desc": "+2 mult per F card in scoring hand",                                    "rarity": "common"},
    {"id": "fast_break",       "name": "Fast Break",           "desc": "+300 pts per card played",                                              "rarity": "common"},
    {"id": "depth_chart",      "name": "Depth Chart",          "desc": "+2 mult per unique position in scoring hand",                           "rarity": "common"},
    {"id": "lottery_pick",     "name": "Lottery Pick",         "desc": "+3 mult per top-10 draft pick in scoring hand",                         "rarity": "common"},
    {"id": "volume_scorer",    "name": "Volume Scorer",        "desc": "+1.5 mult per card played beyond 3",                                    "rarity": "common"},
    # ── Uncommon ────────────────────────────────────────────────────────────────
    {"id": "undrafted_hero",   "name": "Undrafted Hero",       "desc": "+5 mult per undrafted player in scoring hand",                          "rarity": "uncommon"},
    {"id": "sixth_man",        "name": "Sixth Man",            "desc": "+50 pts for the highest-scoring card played",                           "rarity": "uncommon"},
    {"id": "bench_mob",        "name": "Bench Mob",            "desc": "+300 pts per card played beyond 3",                                     "rarity": "uncommon"},
    {"id": "triple_double",    "name": "Triple Double",        "desc": "+5 mult when playing Pick & Roll or better",                            "rarity": "uncommon"},
    {"id": "old_school",       "name": "Old School",           "desc": "+5 mult if all played cards from seasons before 1990",                  "rarity": "uncommon"},
    {"id": "modern_era",       "name": "Modern Era",           "desc": "+5 mult if all played cards from seasons 2010+",                        "rarity": "uncommon"},
    {"id": "home_court",       "name": "Home Court",           "desc": "Earn $1 per card in scoring hand",                                      "rarity": "uncommon"},
    {"id": "double_agent",     "name": "Double Agent",         "desc": "+2 mult per other joker you own",                                       "rarity": "uncommon"},
    {"id": "east_pride",       "name": "East Coast Pride",     "desc": "+6 mult if all scoring cards from Eastern Conference teams",             "rarity": "uncommon"},
    {"id": "showtime",         "name": "Showtime",             "desc": "+3 mult per G beyond the first in scoring hand",                        "rarity": "uncommon"},
    {"id": "pick_and_pop",     "name": "Pick & Pop",           "desc": "+6 mult when playing Twin Towers",                                      "rarity": "uncommon"},
    # ── Rare ─────────────────────────────────────────────────────────────────────
    {"id": "championship_run", "name": "Championship Run",     "desc": "+6 mult when playing Starting Lineup",                                  "rarity": "rare"},
    {"id": "franchise_corner", "name": "Franchise Cornerstone","desc": "Best card in scoring hand adds double its fantasy pts as bonus pts",    "rarity": "rare"},
    {"id": "smart_money",      "name": "Smart Money",          "desc": "Earn $1 per $5 held at end of each round (max $5)",                     "rarity": "rare"},
    {"id": "ring_chaser",      "name": "Ring Chaser",          "desc": "+1 mult per joker you own",                                             "rarity": "rare"},
    {"id": "hot_streak",       "name": "Hot Streak",           "desc": "+3 mult per consecutive hand scored above 2000 pts (resets if below)",  "rarity": "rare"},
    {"id": "big_man_premium",  "name": "Big Man Premium",      "desc": "C position multiplier +0.5 (stacks with skill levels)",                 "rarity": "rare"},
    {"id": "stretch_forward",  "name": "Stretch Forward",      "desc": "F position multiplier +0.3 (stacks with skill levels)",                 "rarity": "rare"},
    {"id": "point_guard_plus", "name": "Point Guard Plus",     "desc": "G position multiplier +0.3 (stacks with skill levels)",                 "rarity": "rare"},
    {"id": "clutch_gene",      "name": "Clutch Gene",          "desc": "+10 mult when playing Isolation (1 card)",                              "rarity": "rare"},
    {"id": "the_duo_joker",    "name": "The Duo",              "desc": "+5 mult when playing Catch & Shoot",                                    "rarity": "rare"},
    {"id": "the_trio_joker",   "name": "The Trio",             "desc": "+7 mult when playing Pick & Roll",                                      "rarity": "rare"},
    # ── Multiplicative Rare ──────────────────────────────────────────────────────
    {"id": "west_dynasty",     "name": "West Dynasty",         "desc": "×1.35 MULT per Western Conf. player in scoring hand (multiplicative)",  "rarity": "rare"},
    {"id": "dynasty_team",     "name": "Dynasty Team",         "desc": "×2 MULT if all scoring cards from same NBA team (multiplicative)",      "rarity": "rare"},
    {"id": "scoring_machine",  "name": "Scoring Machine",      "desc": "×1.3 MULT if best scoring card has 35+ fantasy pts (multiplicative)",   "rarity": "rare"},
    {"id": "snowball",         "name": "Snowball",             "desc": "×1.12 MULT per consecutive high-scoring hand, stacks up to ×1.72 (multiplicative)", "rarity": "rare"},
    # ── Legendary ────────────────────────────────────────────────────────────────
    {"id": "goat_status",      "name": "GOAT Status",          "desc": "×2 MULT; gains +15% each time you win a boss fight",                   "rarity": "legendary"},
    {"id": "dynasty_mode",     "name": "Dynasty Mode",         "desc": "×1.2 MULT per other joker owned (multiplicative)",                     "rarity": "legendary"},
    {"id": "blueprint",        "name": "Blueprint",            "desc": "Copies the mult bonus of the next joker to the right",                  "rarity": "legendary"},
    {"id": "smash_factor",     "name": "Smash Factor",         "desc": "×1.5 final score (multiplicative, applied after all other mult)",       "rarity": "legendary"},
    # New jokers
    {"id": "flat_mult",       "name": "Lineup Anchor",          "desc": "+4 Mult. Every great team needs a foundation.",                                 "rarity": "common"},
    {"id": "pair_bonus",      "name": "Paint Attack",           "desc": "+8 Mult if played hand is Catch & Shoot.",                                      "rarity": "common"},
    {"id": "trips_bonus",     "name": "Break Away",             "desc": "+12 Mult if played hand is Pick & Roll.",                                       "rarity": "common"},
    {"id": "pair_chips",      "name": "Hustle Points",          "desc": "+300 base pts if played hand is Catch & Shoot.",                                "rarity": "common"},
    {"id": "no_disc_mult",    "name": "Overtime",               "desc": "+15 Mult if you have 0 discards remaining when this hand is played.",           "rarity": "common"},
    {"id": "small_hand_mult", "name": "Veteran Presence",       "desc": "+20 Mult if scoring hand has 3 or fewer cards.",                               "rarity": "common"},
    {"id": "clockwork",       "name": "Pace Setter",            "desc": "Gains +1 Mult per hand played this fight, loses -1 per discard (min 0).",      "rarity": "common"},
    {"id": "deck_pts",        "name": "Arena Advantage",        "desc": "+2 base pts per card remaining in deck.",                                       "rarity": "common"},
    {"id": "loyalty_xmult",   "name": "Max Contract",           "desc": "×4 Mult every 6 hands played this run (multiplicative).",                      "rarity": "uncommon"},
    {"id": "clutch_xmult",    "name": "Buzzer Winner",          "desc": "×3 Mult on the final hand of the fight (multiplicative).",                     "rarity": "uncommon"},
    {"id": "padder_stacker",  "name": "Rebounder's Edge",       "desc": "Gains +2 Mult when you play Twin Towers. Stacks permanently.",                 "rarity": "uncommon"},
    {"id": "restock_stacker", "name": "Player Option",          "desc": "Gains +2 Mult each time the shop is restocked. Stacks permanently.",           "rarity": "uncommon"},
    {"id": "uncommon_xmult",  "name": "All-NBA Selection",      "desc": "×1.5 Mult per Uncommon Joker owned (multiplicative).",                         "rarity": "uncommon"},
    {"id": "cavendish_mult",  "name": "Immortal Status",        "desc": "×3 Mult. 1 in 1000 chance destroyed at end of each hand.",                     "rarity": "common"},
    {"id": "flush_xmult",     "name": "Finals MVP",             "desc": "×3 Mult if played hand is Zone Press (multiplicative).",                       "rarity": "rare"},
    {"id": "four_xmult",      "name": "Hall of Fame",           "desc": "×4 Mult if played hand is Starting Four (multiplicative).",                    "rarity": "rare"},
    {"id": "delayed_coins",   "name": "Injury Report",          "desc": "Earn $2 at end of fight if no discards were used that fight.",                  "rarity": "common"},
    # ── On-scored per-card attribute jokers ──────────────────────────────────────
    {"id": "high_scorer_chip", "name": "Big Game Player",       "desc": "Each scored card with 40+ fantasy pts adds +300 base pts.",                     "rarity": "common"},
    {"id": "big_man_chip",     "name": "Post Presence",         "desc": "Each scored C card adds +300 base pts.",                                         "rarity": "common"},
    {"id": "veteran_chip",     "name": "Veteran IQ",            "desc": "Each scored card from seasons before 2000 adds +300 base pts.",                  "rarity": "common"},
    {"id": "youth_chip",       "name": "Young Gun",             "desc": "Each scored card from seasons 2015+ adds +300 base pts.",                        "rarity": "common"},
    {"id": "late_pick_chip",   "name": "Undrafted Upside",      "desc": "Each scored undrafted player or pick 31+ adds +300 base pts.",                   "rarity": "common"},
    {"id": "top_pick_chip",    "name": "Lottery Selection",     "desc": "Each scored top-5 draft pick adds +300 base pts.",                              "rarity": "uncommon"},
    {"id": "teammate_chip",    "name": "Team Chemistry",        "desc": "Each scored card sharing a team with another scored card adds +300 base pts.",   "rarity": "uncommon"},
    {"id": "west_chip",        "name": "West Coast Game",       "desc": "Each scored Western Conference card adds +300 base pts.",                        "rarity": "uncommon"},
    # Division jokers
    {"id": "div_scout",     "name": "Conference Scout",     "desc": "4 same-division cards score as Division Straight (5×).",          "rarity": "uncommon"},
    {"id": "div_dynasty",   "name": "Conference Dynasty",   "desc": "5 same-division cards score as Division Six (6×).",               "rarity": "rare"},
    {"id": "div_dominance", "name": "Conference Dominance", "desc": "4 cards same position & division score as Royal Flush (20×).",    "rarity": "rare"},
    {"id": "homefield",     "name": "Home Court Advantage", "desc": "Division hands (Straight/Six/Royal Flush) get +4 mult.",          "rarity": "uncommon"},
    {"id": "div_stacker",   "name": "Conference Stacker",   "desc": "Each scored card in a division hand adds +300 base pts.",         "rarity": "common"},
    {"id": "div_escalator", "name": "Conference Escalator", "desc": "Each division hand played this run permanently adds +0.5 mult.",  "rarity": "rare"},
    # All-Star jokers
    {"id": "all_star_chips",  "name": "All-Star Weekend",   "desc": "Each scored card with any All-Star selection adds +300 base pts.",          "rarity": "common"},
    {"id": "star_power",      "name": "Star Power",          "desc": "+5 Mult per All-Star in the scored hand.",                                    "rarity": "uncommon"},
    {"id": "legend_status",   "name": "Legend Status",       "desc": "Each scored card with 10+ All-Star selections adds +300 base pts.",           "rarity": "rare"},
    {"id": "franchise_icon",  "name": "Franchise Icon",      "desc": "×2 Mult if every scored card has at least 1 All-Star selection (multiplicative).", "rarity": "rare"},
]
JOKER_MAP = {j["id"]: j for j in JOKERS}

SHOP_SKILL_CARDS = [
    {"id": "skill_g", "type": "skill_card", "pos": "G", "name": "G Training",  "desc": "Level up G skill",  "cost": 4},
    {"id": "skill_f", "type": "skill_card", "pos": "F", "name": "F Academy",   "desc": "Level up F skill",  "cost": 4},
    {"id": "skill_c", "type": "skill_card", "pos": "C", "name": "C Clinic",    "desc": "Level up C skill",  "cost": 4},
]

SHOP_COMBO_CARDS = [
    {"id": "combo_starting_lineup",  "type": "combo_card", "hand_type": "starting_lineup",  "boost": 0.5, "name": "Full Rotation",      "desc": "+0.5 Starting Lineup mult",   "cost": 5},
    {"id": "combo_zone_press",       "type": "combo_card", "hand_type": "zone_press",       "boost": 0.5, "name": "Full Court Press",   "desc": "+0.5 Zone Press mult",        "cost": 5},
    {"id": "combo_twin_towers",      "type": "combo_card", "hand_type": "twin_towers",      "boost": 0.5, "name": "Big Man Duo",        "desc": "+0.5 Twin Towers mult",       "cost": 5},
    {"id": "combo_pick_roll",        "type": "combo_card", "hand_type": "pick_roll",        "boost": 0.5, "name": "Pick & Pop",         "desc": "+0.5 Pick & Roll mult",       "cost": 5},
    {"id": "combo_catch_shoot",      "type": "combo_card", "hand_type": "catch_shoot",      "boost": 0.5, "name": "Catch & Shoot",      "desc": "+0.5 Catch & Shoot mult",     "cost": 5},
    {"id": "combo_isolation",        "type": "combo_card", "hand_type": "isolation",        "boost": 1.0, "name": "One on One",         "desc": "+1.0 Isolation mult",         "cost": 5},
]

SHOP_EFFECT_CARDS = [
    {"id": "effect_gold", "type": "effect_card", "effect": "gold", "needs_target": True,
     "name": "Gold Sneakers", "desc": "Target card earns $2 when played", "cost": 3},
    {"id": "effect_glass", "type": "effect_card", "effect": "glass", "needs_target": True,
     "name": "Glass Headband", "desc": "Target card gets +4 mult but 33% chance to break when played", "cost": 3},
    {"id": "effect_foil", "type": "effect_card", "effect": "foil", "needs_target": True,
     "name": "Foil Jersey", "desc": "Target card gets +50 base pts when played", "cost": 3},
]

SHOP_YEAR_CARD = {"id": "year_peak", "type": "year_card", "needs_target": True,
                  "name": "Time Machine", "desc": "Target card: choose any season for that player from the DB", "cost": 4}

SHOP_CUT_CARD = {"id": "cut_card", "type": "cut_card", "needs_target": True,
                 "name": "Trade Clause", "desc": "Permanently remove a player from your deck", "cost": 3}

SHOP_UPGRADES = [
    {"id": "hand_size_up", "type": "upgrade", "stat": "max_hand_size", "amount": 1,
     "name": "Extra Roster Spot", "desc": "+1 max hand size (draw 1 extra card)", "cost": 6},
    {"id": "discard_up", "type": "upgrade", "stat": "base_discards", "amount": 1,
     "name": "Coach's Challenge", "desc": "+1 discard per level", "cost": 5},
    {"id": "joker_slot_up", "type": "upgrade", "stat": "max_jokers", "amount": 1,
     "name": "Scout Report", "desc": "+1 Joker slot (hold more Jokers)", "cost": 7},
]

SHOP_MOD_CARDS = [
    {"id": "carbon_copy", "type": "mod_card", "effect": "duplicate", "needs_target": True,
     "name": "Carbon Copy", "desc": "Add a duplicate of a target card to your deck", "cost": 5},
    {"id": "training_camp", "type": "mod_card", "effect": "trained", "needs_target": True,
     "name": "Training Camp", "desc": "Target card permanently gains +20% Fantasy Pts", "cost": 5},
    {"id": "position_switch", "type": "mod_card", "effect": "pos_switch", "needs_target": True,
     "name": "Position Switch", "desc": "Transform a G to F or F to C (keeps card, changes mult)", "cost": 6},
]

JOKER_ENHANCEMENT_ITEMS = [
    {"id": "boost_sticker",      "name": "Boost Sticker",     "type": "joker_enhancement", "enhancement_id": "boost_sticker",
     "desc": "+2 to this joker's mult contribution", "cost": 4, "needs_joker_target": True},
    {"id": "multiplier_sticker", "name": "Multiplier Sticker","type": "joker_enhancement", "enhancement_id": "multiplier_sticker",
     "desc": "x1.5 to this joker's contribution",     "cost": 6, "needs_joker_target": True},
    {"id": "echo_sticker",       "name": "Echo Sticker",      "type": "joker_enhancement", "enhancement_id": "echo_sticker",
     "desc": "This joker fires twice (x2 effect)",    "cost": 7, "needs_joker_target": True},
    {"id": "gold_wire",          "name": "Gold Wire",         "type": "joker_enhancement", "enhancement_id": "gold_wire",
     "desc": "Earn $1 each time this joker activates", "cost": 5, "needs_joker_target": True},
]

PACKS = [
    {"id": "starter_pack",   "name": "Starter Draft",        "desc": "5 random players, pick 2",                           "cost": 6,  "count": 5, "tier": "common"},
    {"id": "elite_pack",     "name": "Star Pack",             "desc": "5 high-FP players, pick 2",                          "cost": 10, "count": 5, "tier": "uncommon"},
    {"id": "position_pack",  "name": "Position Draft",        "desc": "5 players of 1 random position, pick 2",             "cost": 8,  "count": 5, "tier": "common"},
    {"id": "gold_pack",      "name": "Gold Pack",             "desc": "3 players — all receive Gold effect, pick 1",        "cost": 12, "count": 2, "tier": "uncommon"},
    {"id": "all_star_pack",  "name": "All-Star Pack",         "desc": "5 elite players (1500+ FP season), pick 2",          "cost": 15, "count": 5, "tier": "rare"},
    {"id": "legend_pack",    "name": "Legend Pack",           "desc": "3 all-time great seasons, pick 1 — possible Glass",  "cost": 20, "count": 2, "tier": "legendary"},
    {"id": "dynasty_pack",   "name": "Dynasty Pack",          "desc": "5 players from 1 NBA team, pick 2",                  "cost": 10, "count": 5, "tier": "uncommon"},
    {"id": "big_man_pack",   "name": "Big Man Pack",          "desc": "5 Centers, pick 2",                                  "cost": 9,  "count": 5, "tier": "common"},
    {"id": "joker_pack",     "name": "Joker Pack",            "desc": "Choose 1 of 3 jokers",                               "cost": 10, "count": 3, "tier": "uncommon", "is_joker_pack": True},
    {"id": "big_joker_pack",      "name": "All-Star Joker Pack",  "desc": "Choose 2 of 5 jokers",                               "cost": 18, "count": 5, "tier": "rare",     "is_joker_pack": True},
    {"id": "allstar_draft_pack",  "name": "All-Star Draft",        "desc": "5 NBA All-Stars, pick 2 — ranked by career selections", "cost": 14, "count": 5, "tier": "uncommon"},
]
PACK_MAP = {p["id"]: p for p in PACKS}


def cleanup_old_games():
    _GAMES.cleanup_expired()


def _get_effective_pos_mult(pos, joker_ids, skill_levels, card_effects_for_card=None):
    base = POS_MULT.get(pos, 1.0)
    for jid in joker_ids:
        if jid == "big_man_premium" and pos == "C":
            base += 0.5
        elif jid == "stretch_forward" and pos == "F":
            base += 0.3
        elif jid == "point_guard_plus" and pos == "G":
            base += 0.3
    base += skill_levels.get(pos, 0) * 0.12
    return base


def _get_effective_pts(card, skill_levels, card_effects):
    pts = card["fantasy_pts"]
    level = skill_levels.get(card["pos"], 0)
    pts *= (1 + level * 0.08)
    effects = card_effects.get(card["id"], [])
    if "foil" in effects:
        pts += 50
    if "trained" in effects:
        pts *= 1.2
    return round(pts, 1)


def _build_deck_pool(conn):
    """Fetch cards with exact position counts: G=12, F=12, C=10 = 34 total."""
    exact_counts = {"G": 12, "F": 12, "C": 10}
    pool_rows = []
    used = set()

    for pos, count in exact_counts.items():
        rows = conn.execute("""
            SELECT ns.player, ns.season, ns.pos, ns.team, ns.fantasy_score,
                   nd.draft_pick, nd.college, na.selections
            FROM nba_stats ns
            LEFT JOIN nba_draft nd ON ns.player = nd.player
            LEFT JOIN nba_allstars na ON ns.player = na.player
            WHERE ns.pos = ? AND ns.fantasy_score >= 600
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
        draft_pick = r[5]
        college = r[6] if r[6] else ("No college" if draft_pick is not None else None)
        cards.append({
            "id": card_id,
            "player": r[0],
            "season": r[1],
            "pos": r[2],
            "team": r[3],
            "fantasy_pts": round(r[4] / 10, 1),
            "draft_pick": draft_pick,
            "college": college,
            "undrafted": draft_pick is None,
            "allstar_count": int(r[7]) if r[7] is not None else 0,
            "conference": get_nba_conference(r[3]),
            "division": get_nba_division(r[3]),
        })
    return cards


def _deal_for_level(state):
    pool = list(state["deck_pool"])
    random.shuffle(pool)
    hand_size = state.get("max_hand_size", 6)
    state["hand"] = pool[:hand_size]
    state["deck"] = pool[hand_size:]
    state["fight_discards"] = []
    state["fight_played"] = []


def evaluate_hand(cards):
    n = len(cards)
    if n == 0:
        return None, []

    pos_counts = Counter(c["pos"] for c in cards)
    max_count = max(pos_counts.values()) if pos_counts else 0

    # Division Starting Lineup: G + F + C all present (5+ cards) all same division (25x)
    if n >= 5 and all(p in pos_counts for p in ["G", "F", "C"]):
        divs = [c.get("division") or get_nba_division(c.get("team", "")) for c in cards]
        if divs[0] and all(d == divs[0] for d in divs):
            return "division_lineup", cards

    # Royal Flush: 5-6 cards all same position AND all same division (20x)
    if n >= 5:
        divs = [c.get("division") or get_nba_division(c.get("team", "")) for c in cards]
        if divs[0] and all(d == divs[0] for d in divs) and len(pos_counts) == 1:
            return "royal_flush", cards

    # Division Court: 5+ cards all from same division (6x)
    if n >= 5:
        divs = [c.get("division") or get_nba_division(c.get("team", "")) for c in cards]
        if divs[0] and all(d == divs[0] for d in divs):
            return "division_six", cards

    # Zone Press (six_man_rotation key): 5 of same position (5.5x)
    if max_count >= 5:
        best_pos = max(pos_counts, key=lambda p: (pos_counts[p], sum(c["fantasy_pts"] * POS_MULT.get(c["pos"], 1) for c in cards if c["pos"] == p)))
        five_cards = sorted([c for c in cards if c["pos"] == best_pos], key=lambda c: c["fantasy_pts"] * POS_MULT.get(c["pos"], 1), reverse=True)[:5]
        return "six_man_rotation", five_cards

    # starting_lineup: all 3 positions present AND n >= 5
    if n >= 5 and len(pos_counts) == 3 and all(p in pos_counts for p in ["G", "F", "C"]):
        return "starting_lineup", cards

    # twin_towers: one position with 3+, another with 2+ (3+2 = 5 cards)
    trio_positions = [p for p, cnt in pos_counts.items() if cnt >= 3]
    pair_positions = [p for p, cnt in pos_counts.items() if cnt >= 2]
    if trio_positions and len(pair_positions) >= 2:
        best_trio = max(trio_positions, key=lambda p: sum(c["fantasy_pts"] * POS_MULT.get(c["pos"], 1) for c in cards if c["pos"] == p))
        remaining_pairs = [p for p in pair_positions if p != best_trio]
        if remaining_pairs:
            best_pair = max(remaining_pairs, key=lambda p: sum(c["fantasy_pts"] * POS_MULT.get(c["pos"], 1) for c in cards if c["pos"] == p))
            twin_cards = sorted([c for c in cards if c["pos"] == best_trio], key=lambda c: c["fantasy_pts"] * POS_MULT.get(c["pos"], 1), reverse=True)[:3]
            twin_cards += sorted([c for c in cards if c["pos"] == best_pair], key=lambda c: c["fantasy_pts"] * POS_MULT.get(c["pos"], 1), reverse=True)[:2]
            return "twin_towers", twin_cards

    # starting_four: 4 of same position
    if max_count >= 4:
        best_pos = max(pos_counts, key=lambda p: (pos_counts[p], sum(c["fantasy_pts"] * POS_MULT.get(c["pos"], 1) for c in cards if c["pos"] == p)))
        four_cards = sorted([c for c in cards if c["pos"] == best_pos], key=lambda c: c["fantasy_pts"] * POS_MULT.get(c["pos"], 1), reverse=True)[:4]
        return "starting_four", four_cards

    # pick_roll: 3 of same position
    if max_count >= 3:
        best_pos = max(pos_counts, key=lambda p: (pos_counts[p], sum(c["fantasy_pts"] * POS_MULT.get(c["pos"], 1) for c in cards if c["pos"] == p)))
        three_cards = sorted([c for c in cards if c["pos"] == best_pos], key=lambda c: c["fantasy_pts"] * POS_MULT.get(c["pos"], 1), reverse=True)[:3]
        return "pick_roll", three_cards

    # catch_shoot: 2 of same position
    pairs = [pos for pos, cnt in pos_counts.items() if cnt >= 2]
    if pairs:
        best_pos = max(pairs, key=lambda p: sum(c["fantasy_pts"] * POS_MULT.get(c["pos"], 1) for c in cards if c["pos"] == p))
        pair_cards = sorted([c for c in cards if c["pos"] == best_pos], key=lambda c: c["fantasy_pts"] * POS_MULT.get(c["pos"], 1), reverse=True)[:2]
        return "catch_shoot", pair_cards

    # isolation: best single card
    best = max(cards, key=lambda c: c["fantasy_pts"] * POS_MULT.get(c["pos"], 1))
    return "isolation", [best]


def _calc_joker_mult(joker_ids, cards_played, hand_type, skill_levels, card_effects,
                     joker_state=None, joker_enhancements=None, is_blueprint_call=False,
                     deck_size=0, is_last_hand=False):
    if joker_state is None:
        joker_state = {}
    if joker_enhancements is None:
        joker_enhancements = {}

    bonus = 0.0
    pts_bonus = 0.0
    state_updates = {}
    contributing_ids = []

    for jid in joker_ids:
        jbonus = 0.0
        jpts = 0.0

        if jid == "rim_protector":
            jbonus = 2 * sum(1 for c in cards_played if c["pos"] == "C")
        elif jid == "floor_general":
            jbonus = 2 * sum(1 for c in cards_played if c["pos"] == "G")
        elif jid == "power_forward":
            jbonus = 2 * sum(1 for c in cards_played if c["pos"] == "F")
        elif jid == "fast_break":
            jpts = 300 * len(cards_played)
        elif jid == "depth_chart":
            jbonus = 2 * len(set(c["pos"] for c in cards_played))
        elif jid == "lottery_pick":
            jbonus = 3 * sum(1 for c in cards_played if c.get("draft_pick") is not None and c["draft_pick"] <= 10)
        elif jid == "undrafted_hero":
            jbonus = 5 * sum(1 for c in cards_played if c.get("undrafted"))
        elif jid == "sixth_man":
            if cards_played:
                jpts = max(c["fantasy_pts"] for c in cards_played)
        elif jid == "bench_mob":
            extra = len(cards_played) - 3
            if extra > 0:
                jpts = 300 * extra
        elif jid == "triple_double":
            if hand_type in ("pick_roll", "catch_shoot", "zone_press", "twin_towers", "starting_four", "six_man_rotation", "starting_lineup"):
                jbonus = 5
        elif jid == "old_school":
            if all((c.get("season") or 9999) < 1990 for c in cards_played):
                jbonus = 5
        elif jid == "modern_era":
            if all((c.get("season") or 0) >= 2010 for c in cards_played):
                jbonus = 5
        elif jid == "volume_scorer":
            extra = len(cards_played) - 3
            if extra > 0:
                jbonus = 1.5 * extra
        elif jid == "double_agent":
            jbonus = 2 * (len(joker_ids) - 1)
        elif jid == "east_pride":
            confs = [get_nba_conference(c.get("team")) for c in cards_played]
            confs = [c for c in confs if c]
            if confs and all(c == "East" for c in confs):
                jbonus = 6
        elif jid == "showtime":
            g_cards = [c for c in cards_played if c["pos"] == "G"]
            if len(g_cards) > 1:
                jbonus = 3 * (len(g_cards) - 1)
        elif jid == "pick_and_pop":
            if hand_type == "twin_towers":
                jbonus = 6
        elif jid == "championship_run":
            if hand_type == "starting_lineup":
                jbonus = 6
        elif jid == "franchise_corner":
            if cards_played:
                jpts = max(c["fantasy_pts"] for c in cards_played)
        elif jid == "ring_chaser":
            jbonus = len(joker_ids)
        elif jid == "hot_streak":
            jbonus = joker_state.get("hot_streak_count", 0) * 3
        elif jid == "clutch_gene":
            if hand_type == "isolation":
                jbonus = 10
        elif jid == "the_duo_joker":
            if hand_type == "catch_shoot":
                jbonus = 5
        elif jid == "the_trio_joker":
            if hand_type == "pick_roll":
                jbonus = 7
        elif jid == "blueprint" and not is_blueprint_call:
            try:
                idx = list(joker_ids).index("blueprint")
                next_idx = idx + 1
                if next_idx < len(joker_ids):
                    next_jid = list(joker_ids)[next_idx]
                    bp_bonus, _, bp_pts, _ = _calc_joker_mult(
                        [next_jid], cards_played, hand_type, skill_levels, card_effects,
                        joker_state=joker_state, joker_enhancements=joker_enhancements,
                        is_blueprint_call=True, deck_size=deck_size, is_last_hand=is_last_hand,
                    )
                    jbonus = bp_bonus
                    jpts = bp_pts
            except ValueError:
                pass

        elif jid == "flat_mult":
            jbonus = 4
        elif jid == "pair_bonus":
            if hand_type == "catch_shoot":
                jbonus = 8
        elif jid == "trips_bonus":
            if hand_type == "pick_roll":
                jbonus = 12
        elif jid == "pair_chips":
            if hand_type == "catch_shoot":
                jpts = 300
        elif jid == "no_disc_mult":
            jbonus = 15 if joker_state.get("_discards_remaining", 0) == 0 else 0
        elif jid == "small_hand_mult":
            if len(cards_played) <= 3:
                jbonus = 20
        elif jid == "clockwork":
            jbonus = joker_state.get("clockwork_stacks", 0)
        elif jid == "deck_pts":
            jpts = 2 * deck_size
        elif jid == "padder_stacker":
            jbonus = joker_state.get("padder_stacks", 0)
        elif jid == "restock_stacker":
            jbonus = joker_state.get("restock_stacks", 0)
        # ── On-scored per-card attribute jokers ──────────────────────────────
        elif jid == "high_scorer_chip":
            jpts = sum(300 for c in cards_played if c.get("fantasy_pts", 0) >= 40)
        elif jid == "big_man_chip":
            jpts = sum(300 for c in cards_played if c.get("pos") == "C")
        elif jid == "veteran_chip":
            jpts = sum(300 for c in cards_played if (c.get("season") or 9999) < 2000)
        elif jid == "youth_chip":
            jpts = sum(300 for c in cards_played if (c.get("season") or 0) >= 2015)
        elif jid == "late_pick_chip":
            jpts = sum(300 for c in cards_played if c.get("undrafted") or (c.get("draft_pick") or 0) > 30)
        elif jid == "top_pick_chip":
            jpts = sum(300 for c in cards_played if c.get("draft_pick") is not None and c["draft_pick"] <= 5)
        elif jid == "teammate_chip":
            _team_counts = Counter(c.get("team") for c in cards_played if c.get("team"))
            jpts = sum(300 for c in cards_played if _team_counts.get(c.get("team"), 0) >= 2)
        elif jid == "west_chip":
            jpts = sum(300 for c in cards_played if get_nba_conference(c.get("team")) == "West")
        elif jid == "homefield":
            if hand_type in ("division_five", "division_six", "royal_flush"):
                jbonus = 4
        elif jid == "div_stacker":
            if hand_type in ("division_five", "division_six", "royal_flush"):
                jpts = sum(300 for _ in cards_played)
        elif jid == "div_escalator":
            jbonus = joker_state.get("div_escalator_stacks", 0) * 0.5
        # ── All-Star jokers ──────────────────────────────────────────────────
        elif jid == "all_star_chips":
            jpts = sum(300 for c in cards_played if (c.get("allstar_count") or 0) >= 1)
        elif jid == "star_power":
            jbonus = 5 * sum(1 for c in cards_played if (c.get("allstar_count") or 0) >= 1)
        elif jid == "legend_status":
            jpts = sum(300 for c in cards_played if (c.get("allstar_count") or 0) >= 10)
        elif jid == "franchise_icon":
            pass  # handled in _calc_xmult_factor

        # Apply joker enhancements
        if jbonus != 0:
            enhs = joker_enhancements.get(jid, [])
            if "boost_sticker" in enhs:
                jbonus += 2
            if "multiplier_sticker" in enhs:
                jbonus *= 1.5
            if "echo_sticker" in enhs:
                jbonus *= 2

        if jbonus != 0:
            contributing_ids.append(jid)
        bonus += jbonus
        pts_bonus += jpts

    return bonus, contributing_ids, pts_bonus, state_updates


def _calc_joker_mult_factor(cards_played, joker_ids, joker_state=None, hand_type=None, is_last_hand=False):
    joker_state = joker_state or {}
    factor = 1.0
    xmult_ids = []

    if "goat_status" in joker_ids:
        base = 2.0 + joker_state.get("goat_bonus", 0.0)
        factor *= base
        xmult_ids.append("goat_status")

    if "dynasty_mode" in joker_ids:
        other_count = len(joker_ids) - 1
        if other_count > 0:
            factor *= (1.2 ** other_count)
            xmult_ids.append("dynasty_mode")

    if "west_dynasty" in joker_ids:
        west_count = sum(1 for c in cards_played if get_nba_conference(c.get("team")) == "West")
        if west_count > 0:
            factor *= (1.35 ** west_count)
            xmult_ids.append("west_dynasty")

    if "dynasty_team" in joker_ids:
        teams = [c.get("team") for c in cards_played if c.get("team")]
        if teams and len(set(teams)) == 1:
            factor *= 2.0
            xmult_ids.append("dynasty_team")

    if "scoring_machine" in joker_ids:
        if cards_played and max(c["fantasy_pts"] for c in cards_played) >= 35:
            factor *= 1.3
            xmult_ids.append("scoring_machine")

    if "snowball" in joker_ids:
        streak = joker_state.get("hot_streak_count", 0)
        if streak > 0:
            stacks = min(streak, 5)
            factor *= (1.12 ** stacks)
            xmult_ids.append("snowball")

    if "smash_factor" in joker_ids:
        factor *= 1.5
        xmult_ids.append("smash_factor")

    if "loyalty_xmult" in joker_ids:
        if joker_state.get("hands_played_run", 0) > 0 and joker_state.get("hands_played_run", 0) % 6 == 0:
            factor *= 4.0
            xmult_ids.append("loyalty_xmult")

    if "clutch_xmult" in joker_ids:
        if is_last_hand:
            factor *= 3.0
            xmult_ids.append("clutch_xmult")

    if "uncommon_xmult" in joker_ids:
        uncommon_count = sum(1 for jid in joker_ids if JOKER_MAP.get(jid, {}).get("rarity") == "uncommon")
        if uncommon_count > 0:
            factor *= (1.5 ** uncommon_count)
            xmult_ids.append("uncommon_xmult")

    if "cavendish_mult" in joker_ids:
        factor *= 3.0
        xmult_ids.append("cavendish_mult")

    if "flush_xmult" in joker_ids:
        if hand_type == "zone_press":
            factor *= 3.0
            xmult_ids.append("flush_xmult")

    if "four_xmult" in joker_ids:
        if hand_type == "starting_four":
            factor *= 4.0
            xmult_ids.append("four_xmult")

    if "franchise_icon" in joker_ids:
        if cards_played and all((c.get("allstar_count") or 0) >= 1 for c in cards_played):
            factor *= 2.0
            xmult_ids.append("franchise_icon")

    return round(factor, 4), xmult_ids


def _calc_coins_earned(hand_type, scoring_cards, all_played, joker_ids, coins, joker_enhancements=None):
    joker_enhancements = joker_enhancements or {}
    earned = 0
    if "home_court" in joker_ids:
        earned += len(all_played)
    gold_wire_count = sum(1 for jid in joker_ids if "gold_wire" in joker_enhancements.get(jid, []))
    earned += gold_wire_count
    return earned


def _maybe_upgrade_hand_for_jokers(hand_type, scoring_cards, cards_played, joker_ids, joker_state):
    """Upgrade hand type if division-reducing jokers are owned."""
    if not joker_ids:
        return hand_type, scoring_cards
    n = len(cards_played)
    if n < 4:
        return hand_type, scoring_cards

    def _get_div(c):
        return c.get("division") or get_nba_division(c.get("team", ""))

    divs = [_get_div(c) for c in cards_played]
    same_div = bool(divs[0]) and all(d == divs[0] for d in divs)
    pos_counts = Counter(c["pos"] for c in cards_played)
    same_pos = len(pos_counts) == 1

    if "div_dominance" in joker_ids and n >= 4 and same_div and same_pos:
        return "royal_flush", cards_played
    if "div_dynasty" in joker_ids and n >= 5 and same_div and hand_type not in ("royal_flush", "division_six"):
        return "division_six", cards_played
    if "div_scout" in joker_ids and n >= 4 and same_div and hand_type not in ("royal_flush", "division_six", "division_five"):
        return "division_five", cards_played
    return hand_type, scoring_cards


def score_hand(cards_played, joker_ids, skill_levels=None, combo_boosts=None, card_effects=None, joker_state=None, floor=1, joker_enhancements=None, deck_size=0, is_last_hand=False):
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
    hand_type, scoring_cards = _maybe_upgrade_hand_for_jokers(hand_type, scoring_cards, cards_played, joker_ids, joker_state)

    base_pts = 0.0
    for c in scoring_cards:
        eff_pts = _get_effective_pts(c, skill_levels, card_effects)
        eff_pos_mult = _get_effective_pos_mult(c["pos"], joker_ids, skill_levels)
        base_pts += eff_pts * eff_pos_mult

    card_contributions = [
        {
            "id": c["id"],
            "player": c["player"],
            "pos": c["pos"],
            "effective_pts": round(_get_effective_pts(c, skill_levels, card_effects), 1),
            "pos_mult": round(_get_effective_pos_mult(c["pos"], joker_ids, skill_levels), 2),
            "contribution": round(_get_effective_pts(c, skill_levels, card_effects) * _get_effective_pos_mult(c["pos"], joker_ids, skill_levels), 1),
        }
        for c in scoring_cards
    ]

    glass_in_scoring = any("glass" in card_effects.get(c["id"], []) for c in scoring_cards)
    glass_mult = 2.0 if glass_in_scoring else 1.0

    hand_mult = HAND_TYPES[hand_type]["mult"] + combo_boosts.get(hand_type, 0)
    joker_add, joker_add_ids, joker_pts_bonus, _state_updates = _calc_joker_mult(
        joker_ids, cards_played, hand_type, skill_levels, card_effects,
        joker_state=joker_state, joker_enhancements=joker_enhancements,
        deck_size=deck_size, is_last_hand=is_last_hand
    )
    total_mult = hand_mult + joker_add

    mult_factor, xmult_joker_ids = _calc_joker_mult_factor(cards_played, joker_ids, joker_state=joker_state, hand_type=hand_type, is_last_hand=is_last_hand)

    base_pts_total = base_pts + joker_pts_bonus
    score = round(base_pts_total * total_mult * mult_factor * glass_mult)

    return {
        "score": score,
        "hand_type": hand_type,
        "hand_name": HAND_TYPES[hand_type]["name"],
        "hand_desc": HAND_TYPES[hand_type]["desc"],
        "base_pts": round(base_pts_total, 1),
        "hand_mult": hand_mult,
        "joker_mult": round(joker_add, 1),
        "joker_add_ids": joker_add_ids,
        "total_mult": round(total_mult, 1),
        "mult_factor": mult_factor,
        "xmult_joker_ids": xmult_joker_ids,
        "glass_mult": glass_mult,
        "scoring_cards": scoring_cards,
        "card_contributions": card_contributions,
        "scoring_card_ids": [c["id"] for c in scoring_cards],
    }


def _get_joker_options(current_jokers, n=3):
    owned = set(current_jokers)
    available = [j for j in JOKERS if j["id"] not in owned]
    random.shuffle(available)
    return available[:n]


def _weighted_joker_sample(pool, weights_by_rarity, n):
    """Sample n unique jokers from pool using per-rarity weights."""
    if not pool:
        return []
    remaining = list(pool)
    remaining_w = [weights_by_rarity.get(j["rarity"], 1) for j in remaining]
    selected = []
    for _ in range(min(n, len(remaining))):
        chosen = random.choices(remaining, weights=remaining_w, k=1)[0]
        idx = remaining.index(chosen)
        selected.append(chosen)
        remaining.pop(idx)
        remaining_w.pop(idx)
    return selected


def _generate_shop(conn, state):
    floor = state.get("floor", 1)
    if floor <= 3:
        tier_name = "Common"
        tier_mult = 1.0
        shop_weights = {"common": 60, "uncommon": 28, "rare": 10, "legendary": 2}
    elif floor <= 6:
        tier_name = "Veteran"
        tier_mult = 1.5
        shop_weights = {"common": 40, "uncommon": 35, "rare": 20, "legendary": 5}
    else:
        tier_name = "Elite"
        tier_mult = 2.0
        shop_weights = {"common": 20, "uncommon": 35, "rare": 35, "legendary": 10}

    def scale_cost(base):
        return max(1, round(base * tier_mult))

    owned_joker_ids = set(state["jokers"])
    available_jokers = [j for j in JOKERS if j["id"] not in owned_joker_ids]
    available_jokers = _weighted_joker_sample(available_jokers, shop_weights, 4)

    items = []
    slot_idx = 0

    for j in available_jokers:
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

    # Player cards — always 3
    roster_player_count = 3
    try:
        fp_min = 80 if floor <= 3 else (120 if floor <= 6 else 180)
        # Scale to raw fantasy_score (multiply by 10)
        score_min = fp_min * 10
        buy_rows = conn.execute("""
            SELECT ns.player, ns.season, ns.pos, ns.team, ns.fantasy_score,
                   nd.draft_pick, nd.college, na.selections
            FROM nba_stats ns
            LEFT JOIN nba_draft nd ON ns.player = nd.player
            LEFT JOIN nba_allstars na ON ns.player = na.player
            WHERE ns.fantasy_score >= ?
              AND ns.pos IN ('G','F','C')
            ORDER BY RANDOM()
            LIMIT 20
        """, (score_min,)).fetchall()
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
                "fantasy_pts": round(row[4] / 10, 1),
                "draft_pick": row[5],
                "college": college,
                "undrafted": row[5] is None,
                "allstar_count": int(row[7]) if row[7] is not None else 0,
            }
            base_card_cost = random.randint(4, 8)
            items.append({
                "shop_id": str(uuid.uuid4())[:8],
                "slot": slot_idx,
                "section": "roster",
                "type": "buy_card",
                "name": f"{row[0]} '{str(row[1])[-2:]}",
                "desc": f"{row[2]} · {row[3]} · {round(row[4] / 10, 1)} FP",
                "cost": scale_cost(base_card_cost),
                "tier_name": tier_name,
                "sold": False,
                "card_data": card_data,
            })
            slot_idx += 1
    except Exception:
        pass

    training_pool = []

    # 2 skill cards (different positions)
    skill_options = list(SHOP_SKILL_CARDS)
    random.shuffle(skill_options)
    for sk in skill_options[:2]:
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

    # 2 effect/mod cards
    effect_pool = list(SHOP_EFFECT_CARDS) + [SHOP_YEAR_CARD, SHOP_CUT_CARD] + list(SHOP_MOD_CARDS)
    random.shuffle(effect_pool)
    for ey in effect_pool[:2]:
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

    # 2 upgrades
    upgrade_options = list(SHOP_UPGRADES)
    random.shuffle(upgrade_options)
    for ug in upgrade_options[:2]:
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

    # Division sticker (always available floor 2+)
    if floor >= 2:
        items.append({
            "shop_id": str(uuid.uuid4())[:8],
            "slot": slot_idx,
            "section": "training",
            "type": "division_sticker",
            "name": "Division Sticker",
            "desc": "Reassign any card to a new NBA division. Slap it on!",
            "cost": scale_cost(7),
            "sold": False,
        })
        slot_idx += 1

    for tp in training_pool:
        tp["slot"] = slot_idx
        items.append(tp)
        slot_idx += 1

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
    boss = state.get("boss_effect")
    if not boss:
        return
    if boss == "goaltending":
        state["hand"] = [c for c in state["hand"] if c.get("pos") != "C"]
        state["deck_pool"] = [c for c in state["deck_pool"] if c.get("pos") != "C"]
    elif boss == "flagrant_foul":
        state["hand"] = [c for c in state["hand"] if not ((c.get("season") or 0) >= 2010)]
        state["deck_pool"] = [c for c in state["deck_pool"] if not ((c.get("season") or 0) >= 2010)]


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
        "skill_levels": {"G": 0, "F": 0, "C": 0},
        "combo_boosts": {ht: 0 for ht in HAND_TYPES},
        "card_effects": {},
        "shop_items": [],
        "max_hand_size": 6,
        "base_discards": 3,
        "restock_count": 0,
        "max_jokers": 5,
        "joker_state": {},
        "joker_enhancements": {},
        "shop_packs": [],
        "held_items": [],  # each entry: {"kind": "card"|"consumable", ...fields}
        "fight_discards": [],
    }
    _deal_for_level(state)
    _GAMES[gid] = state
    return gid, state


def get_state(gid):
    return _GAMES.get(gid)


def play_hand(gid, card_ids):
    g = _GAMES.get(gid)
    if not g or g["status"] != "playing":
        return None, "Invalid game state"
    if g["hands_remaining"] <= 0:
        return None, "No hands remaining"
    if not card_ids or len(card_ids) > 6:
        return None, "Must play 1-6 cards"

    boss_effect = g.get("boss_effect")
    if boss_effect == "shot_clock" and len(card_ids) > 4:
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

    # Pre-scoring state updates
    is_last_hand = (g["hands_remaining"] == 1)
    deck_size = len(g["deck"])
    joker_state["_discards_remaining"] = g.get("discards_remaining", 0)
    joker_state["hands_played_run"] = joker_state.get("hands_played_run", 0) + 1
    joker_state["hands_played_fight"] = joker_state.get("hands_played_fight", 0) + 1
    joker_state["clockwork_stacks"] = joker_state.get("clockwork_stacks", 0) + 1

    result = score_hand(played, g["jokers"], skill_levels, combo_boosts, card_effects,
                        joker_state=joker_state, floor=g.get("floor", 1),
                        joker_enhancements=joker_enhancements, deck_size=deck_size, is_last_hand=is_last_hand)

    if result.get("hand_type") in ("division_five", "division_six", "royal_flush"):
        joker_state["div_escalator_stacks"] = joker_state.get("div_escalator_stacks", 0) + 1

    # Boss score factors
    boss_factor = 1.0
    if boss_effect == "zone_defense" and result["hand_type"] == "pick_roll":
        boss_factor = 0.5
    elif boss_effect == "double_team" and any(c["pos"] == "G" for c in result["scoring_cards"]):
        boss_factor = 0.6
    elif boss_effect == "technical_foul":
        boss_factor = 0.8
    elif boss_effect == "blocking_foul" and any(c["pos"] == "F" for c in result["scoring_cards"]):
        boss_factor = 0.6
    elif boss_effect == "salary_cap":
        # Cap base pts per card at 200 — apply retroactively as a factor estimate
        boss_factor = 0.7
    if boss_factor != 1.0:
        result["score"] = int(result["score"] * boss_factor)
    result["boss_factor"] = boss_factor

    g["current_score"] += result["score"]
    g["hands_remaining"] -= 1
    g.setdefault("fight_played", []).extend(played)

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
                g["deck_pool"] = [c for c in g["deck_pool"] if c["id"] != cid]
                g["hand"] = [c for c in g["hand"] if c["id"] != cid]
                g["deck"] = [c for c in g["deck"] if c["id"] != cid]

    # Update hot_streak joker state
    if "hot_streak" in g["jokers"]:
        threshold = 2000
        if result["score"] >= threshold:
            g["joker_state"]["hot_streak_count"] = g["joker_state"].get("hot_streak_count", 0) + 1
        else:
            g["joker_state"]["hot_streak_count"] = 0

    # padder_stacker: gains +2 when twin_towers is played
    if "padder_stacker" in g["jokers"] and result["hand_type"] == "twin_towers":
        g["joker_state"]["padder_stacks"] = g["joker_state"].get("padder_stacks", 0) + 2

    # cavendish_mult: 1 in 1000 chance destroyed
    if "cavendish_mult" in g["jokers"] and random.random() < 0.001:
        g["jokers"].remove("cavendish_mult")

    result["joker_state"] = g["joker_state"]
    result["cumulative_score"] = g["current_score"]
    result["target_score"] = g["target_score"]
    result["hands_remaining"] = g["hands_remaining"]
    result["discards_remaining"] = g["discards_remaining"]
    result["coins_earned"] = coins_earned
    result["coins"] = g["coins"]
    result["broken_cards"] = broken_cards
    result["hand"] = g["hand"]
    result["deck_cards"] = g["deck"]
    result["fight_played"] = g.get("fight_played", [])

    if g["current_score"] >= g["target_score"]:
        fight = g.get("fight", 1)
        round_num = g.get("round", 1)
        if fight == 3 and round_num >= 8:
            g["status"] = "won_game"
            result["status"] = "won_game"
        else:
            g["status"] = "won_fight"
            result["status"] = "won_fight"
            result["fight"] = fight
            result["round"] = round_num
    elif g["hands_remaining"] <= 0:
        g["status"] = "lost"
        result["status"] = "lost"
    else:
        result["status"] = "playing"

    # delayed_coins: earn $2 at end of fight if no discards used
    if result.get("status") in ("won_fight", "won_game", "lost"):
        if "delayed_coins" in g["jokers"] and g["joker_state"].get("discards_used_fight", 0) == 0:
            g["coins"] += 2
            result["coins"] = g["coins"]
            coins_earned += 2
            result["coins_earned"] = coins_earned

    g["history"].append(result)
    _GAMES[gid] = g
    return result, None


def advance_fight(gid, conn=None):
    g = _GAMES.get(gid)
    if not g or g["status"] != "won_fight":
        return None, "Not in won_fight state"

    fight = g.get("fight", 1)
    round_num = g.get("round", 1)

    if fight == 3:
        next_round = round_num + 1
        next_fight = 1
        boss_effect = None
    else:
        next_round = round_num
        next_fight = fight + 1
        boss_effect = random.choice(BOSS_EFFECTS)["id"] if next_fight == 3 else None

    g["pending_fight_advance"] = True
    g["next_round"] = next_round
    g["next_fight"] = next_fight
    g["pending_boss_effect"] = boss_effect

    # goat_status: gain +0.15 bonus each round won (boss fight win)
    if fight == 3 and "goat_status" in g["jokers"]:
        g["joker_state"]["goat_bonus"] = g["joker_state"].get("goat_bonus", 0.0) + 0.15

    # Generate reward options — player chooses between coins or a free joker
    reward_coins = 3 + round_num * 2
    owned = set(g.get("jokers", []))
    available = [j for j in JOKERS if j["id"] not in owned]
    reward_weights = {"common": 35, "uncommon": 35, "rare": 25, "legendary": 5}
    reward_jokers = _weighted_joker_sample(available, reward_weights, 3)

    g["reward_coins_amount"] = reward_coins
    g["reward_joker_options"] = [j["id"] for j in reward_jokers]
    g["status"] = "choosing_reward"

    _GAMES[gid] = g
    return {
        "status": "choosing_reward",
        "coins": g["coins"],
        "reward_coins_amount": reward_coins,
        "reward_joker_options": reward_jokers,
        "next_fight": next_fight,
        "next_boss_effect": BOSS_EFFECT_MAP.get(boss_effect) if boss_effect else None,
    }, None


def claim_fight_reward(gid, choice, joker_id=None, conn=None):
    g = _GAMES.get(gid)
    if not g or g["status"] != "choosing_reward":
        return None, "Not in choosing_reward state"

    if choice == "coins":
        reward_coins = g.get("reward_coins_amount", 5)
        g["coins"] = g.get("coins", 0) + reward_coins
    elif choice == "joker":
        if joker_id not in g.get("reward_joker_options", []):
            return None, "Invalid joker choice"
        if len(g.get("jokers", [])) >= g.get("max_jokers", 5):
            return None, "Joker slots full"
        g["jokers"].append(joker_id)
        g["coins"] = g.get("coins", 0) + 2  # small base coins
    else:
        return None, "Invalid choice"

    g["status"] = "shopping"
    g["restock_count"] = 0

    shop_packs = list(PACKS)
    random.shuffle(shop_packs)
    g["shop_packs"] = shop_packs[:4]

    if conn:
        g["shop_items"] = _generate_shop(conn, g)
    else:
        g["shop_items"] = []
        g["pending_shop_generation"] = True

    _GAMES[gid] = g
    return {
        "status": "shopping",
        "coins": g["coins"],
        "jokers": [JOKER_MAP[jid] for jid in g["jokers"]],
        "max_jokers": g.get("max_jokers", 5),
        "shop_items": g["shop_items"],
        "shop_packs": g["shop_packs"],
        "joker_enhancements": g.get("joker_enhancements", {}),
        "held_items": g.get("held_items", []),
        "next_fight": g.get("next_fight", 1),
        "next_boss_effect": BOSS_EFFECT_MAP.get(g.get("pending_boss_effect")) if g.get("pending_boss_effect") else None,
    }, None


def discard_cards(gid, card_ids):
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
    g["joker_state"]["discards_used_fight"] = g["joker_state"].get("discards_used_fight", 0) + 1
    g["joker_state"]["clockwork_stacks"] = max(0, g["joker_state"].get("clockwork_stacks", 0) - 1)
    g["hand"] = [c for c in g["hand"] if c["id"] not in id_set]
    draw_count = min(len(discarded), len(g["deck"]))
    g["hand"].extend(g["deck"][:draw_count])
    g["deck"] = g["deck"][draw_count:]
    g.setdefault("fight_discards", []).extend(discarded)

    _GAMES[gid] = g
    return {
        "discards_remaining": g["discards_remaining"],
        "hand": g["hand"],
        "status": "playing",
        "deck_cards": g["deck"],
        "fight_discards": g["fight_discards"],
    }, None


def select_joker(gid, joker_id):
    g = _GAMES.get(gid)
    if not g or g["status"] != "won_level":
        return None, "Not in reward selection state"

    floor_coins = max(3, g["floor"] * 2)
    g["coins"] = g.get("coins", 0) + floor_coins

    held = g["coins"]
    interest = min(5, held // 5)
    g["coins"] += interest

    g["status"] = "shopping"
    g["reward_options"] = []
    g["restock_count"] = 0

    shop_packs = list(PACKS)
    random.shuffle(shop_packs)
    g["shop_packs"] = shop_packs[:4]

    g["pending_shop_generation"] = True

    _GAMES[gid] = g
    return {
        "status": "shopping",
        "coins": g["coins"],
        "floor_coins_earned": floor_coins,
        "interest_earned": interest,
        "jokers": [JOKER_MAP[jid] for jid in g["jokers"]],
        "max_jokers": g.get("max_jokers", 5),
        "shop_packs": g["shop_packs"],
        "joker_enhancements": g.get("joker_enhancements", {}),
        "held_items": g.get("held_items", []),
    }, None


def generate_shop_for_game(gid, conn):
    g = _GAMES.get(gid)
    if not g:
        return None
    g["shop_items"] = _generate_shop(conn, g)
    g.pop("pending_shop_generation", None)
    _GAMES[gid] = g
    return g["shop_items"]


def buy_shop_item(gid, item_type, shop_id, target_card_id=None, target_year=None, conn=None):
    g = _GAMES.get(gid)
    if not g or g["status"] != "shopping":
        return None, "Not in shopping state"

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

    elif item["type"] in ("skill_card", "combo_card", "effect_card", "year_card",
                          "cut_card", "upgrade", "mod_card"):
        # These go into held_items as consumables instead of applying immediately
        if "held_items" not in g:
            g["held_items"] = []
        if len(g["held_items"]) >= 3:
            return None, "Held item limit reached (max 3)"
        held_entry = {
            "kind": "consumable",
            "held_id": str(uuid.uuid4())[:8],
            "item_type": item["type"],
            "name": item.get("name", ""),
            "desc": item.get("desc", ""),
            "needs_target": item.get("needs_target", False),
            "stat": item.get("stat"),
            "amount": item.get("amount"),
            "effect": item.get("effect"),
            "pos": item.get("pos"),
            "hand_type": item.get("hand_type"),
            "boost": item.get("boost"),
        }
        g["held_items"].append(held_entry)

    elif item["type"] == "buy_card":
        card_data = item.get("card_data")
        if not card_data:
            return None, "No card data in item"
        import copy as _copy
        new_card = _copy.deepcopy(card_data)
        g.setdefault("deck_pool", []).append(new_card)
        g.setdefault("deck", []).append(new_card)

    elif item["type"] == "joker_enhancement":
        target_joker_id = target_card_id
        if not target_joker_id or target_joker_id not in g["jokers"]:
            return None, "Joker not in collection"
        enhancement_id = item.get("enhancement_id")
        if not enhancement_id:
            return None, "No enhancement_id on item"
        enhs = g["joker_enhancements"].setdefault(target_joker_id, [])
        enhs.append(enhancement_id)

    g["coins"] -= cost
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
        "max_hand_size": g.get("max_hand_size", 6),
        "base_discards": g.get("base_discards", 3),
        "max_jokers": g.get("max_jokers", 5),
        "joker_enhancements": g.get("joker_enhancements", {}),
        "held_items": g.get("held_items", []),
    }
    if updated_card:
        result["updated_card"] = updated_card

    _GAMES[gid] = g
    return result, None


def restock_shop(gid, conn):
    g = _GAMES.get(gid)
    if not g or g["status"] != "shopping":
        return None, "Not in shopping state"
    cost = 2 + g.get("restock_count", 0) * 2
    if g["coins"] < cost:
        return None, f"Not enough coins (need {cost})"
    g["coins"] -= cost
    g["restock_count"] = g.get("restock_count", 0) + 1
    if "restock_stacker" in g["jokers"]:
        g["joker_state"]["restock_stacks"] = g["joker_state"].get("restock_stacks", 0) + 2
    g["shop_items"] = _generate_shop(conn, g)
    shop_packs = list(PACKS)
    random.shuffle(shop_packs)
    g["shop_packs"] = shop_packs[:4]
    _GAMES[gid] = g
    return {
        "coins": g["coins"],
        "shop_items": g["shop_items"],
        "shop_packs": g["shop_packs"],
        "next_restock_cost": 2 + g["restock_count"] * 2,
    }, None


def sell_joker(gid, joker_id):
    g = _GAMES.get(gid)
    if not g:
        return None, "Game not found"
    if joker_id not in g["jokers"]:
        return None, "Joker not owned"
    joker = JOKER_MAP.get(joker_id, {})
    sell_price = {"common": 2, "uncommon": 3, "rare": 4}.get(joker.get("rarity", "common"), 2)
    g["jokers"].remove(joker_id)
    g["coins"] += sell_price
    _GAMES[gid] = g
    return {
        "coins": g["coins"],
        "jokers": [JOKER_MAP[j] for j in g["jokers"]],
        "sold": joker.get("name", joker_id),
        "earned": sell_price,
    }, None


def use_held_item(gid, held_id, target_card_id=None, target_year=None, conn=None, discard_only=False):
    g = _GAMES.get(gid)
    if not g:
        return None, "Game not found"
    if "held_items" not in g:
        g["held_items"] = []
    item = next((i for i in g["held_items"] if i.get("held_id") == held_id), None)
    if not item:
        return None, "Held item not found"

    if not discard_only:
        kind = item.get("kind", "consumable")
        itype = item.get("item_type", kind)

        if kind == "card":
            if len(g["hand"]) >= g.get("max_hand_size", 6):
                return None, "Hand is full"
            import copy as _copy
            card = _copy.deepcopy(item)
            card.pop("kind", None)
            card.pop("held_id", None)
            g["hand"].append(card)

        elif itype == "upgrade":
            stat = item["stat"]
            amount = item["amount"]
            if stat == "max_jokers":
                g["max_jokers"] = g.get("max_jokers", 5) + amount
            else:
                g[stat] = g.get(stat, 7 if stat == "max_hand_size" else 3) + amount
            if stat == "max_hand_size" and g.get("deck"):
                g["hand"].append(g["deck"][0])
                g["deck"] = g["deck"][1:]

        elif itype == "skill_card":
            pos = item.get("pos")
            if pos:
                g["skill_levels"][pos] = g["skill_levels"].get(pos, 0) + 1

        elif itype == "combo_card":
            ht = item["hand_type"]
            g["combo_boosts"][ht] = round(g["combo_boosts"].get(ht, 0) + item["boost"], 2)

        elif itype == "effect_card":
            if not target_card_id:
                return None, "Target card required"
            effect = item["effect"]
            g["card_effects"].setdefault(target_card_id, [])
            if effect not in g["card_effects"][target_card_id]:
                g["card_effects"][target_card_id].append(effect)

        elif itype == "year_card":
            if not target_card_id or not target_year or not conn:
                return None, "Target and year required"
            target_card = next((c for c in g["deck_pool"] if c["id"] == target_card_id), None)
            if not target_card:
                return None, "Target card not found"
            rows = conn.execute(
                "SELECT season, team, fantasy_score FROM nba_stats WHERE player = ? AND season = ? AND pos = ? LIMIT 1",
                (target_card["player"], int(target_year), target_card["pos"])
            ).fetchall()
            if rows:
                r = rows[0]
                target_card["season"] = r[0]
                target_card["team"] = r[1]
                target_card["fantasy_pts"] = round(r[2] / 10, 1)
                for hc in g["hand"]:
                    if hc["id"] == target_card_id:
                        hc["season"] = r[0]
                        hc["team"] = r[1]
                        hc["fantasy_pts"] = round(r[2] / 10, 1)

        elif itype == "cut_card":
            if not target_card_id:
                return None, "Target card required"
            g["deck_pool"] = [c for c in g["deck_pool"] if c["id"] != target_card_id]
            g["hand"] = [c for c in g["hand"] if c["id"] != target_card_id]
            g["deck"] = [c for c in g["deck"] if c["id"] != target_card_id]
            g["card_effects"].pop(target_card_id, None)

        elif itype == "mod_card":
            if not target_card_id:
                return None, "Target card required"
            effect = item.get("effect", "")
            if effect == "duplicate":
                import copy as _copy
                target = next((c for c in g["deck_pool"] if c["id"] == target_card_id), None)
                if target:
                    dup = _copy.deepcopy(target)
                    dup["id"] = target["id"] + "_dup" + str(len(g["deck_pool"]))
                    g["deck_pool"].append(dup)
            elif effect == "trained":
                g["card_effects"].setdefault(target_card_id, [])
                if "trained" not in g["card_effects"][target_card_id]:
                    g["card_effects"][target_card_id].append("trained")
            elif effect == "pos_switch":
                switch_map = {"G": "F", "F": "C", "C": "F"}
                target = next((c for c in g["deck_pool"] if c["id"] == target_card_id), None)
                if target:
                    new_pos = switch_map.get(target["pos"], target["pos"])
                    target["pos"] = new_pos
                    for hc in g["hand"]:
                        if hc["id"] == target_card_id:
                            hc["pos"] = new_pos

    # Remove from held_items
    g["held_items"] = [i for i in g["held_items"] if i.get("held_id") != held_id]

    _GAMES[gid] = g
    return {
        "held_items": g["held_items"],
        "hand": g["hand"],
        "skill_levels": g["skill_levels"],
        "combo_boosts": g["combo_boosts"],
        "card_effects": g["card_effects"],
        "max_hand_size": g.get("max_hand_size", 6),
        "base_discards": g.get("base_discards", 3),
        "max_jokers": g.get("max_jokers", 5),
        "deck_pool": g["deck_pool"],
    }, None


def leave_shop(gid):
    g = _GAMES.get(gid)
    if not g or g["status"] != "shopping":
        return None, "Not in shopping state"

    if g.get("pending_fight_advance"):
        new_fight = g.pop("next_fight")
        new_round = g.pop("next_round", g.get("round", 1))
        boss_effect = g.pop("pending_boss_effect", None)
        g.pop("pending_fight_advance")
        old_round = g.get("round", 1)

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

        if new_round != old_round:
            if "joker_state" not in g:
                g["joker_state"] = {}
            g["joker_state"]["hot_streak_count"] = 0

        # Reset per-fight joker state
        if "joker_state" not in g:
            g["joker_state"] = {}
        g["joker_state"]["hands_played_fight"] = 0
        g["joker_state"]["discards_used_fight"] = 0
        g["joker_state"]["clockwork_stacks"] = 0

        _deal_for_level(g)
        if boss_effect:
            _apply_boss_hand_effect(g)
        _GAMES[gid] = g
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
            "max_hand_size": g.get("max_hand_size", 6),
            "base_discards": g.get("base_discards", 3),
            "max_jokers": g.get("max_jokers", 5),
            "joker_state": g.get("joker_state", {}),
            "joker_enhancements": g.get("joker_enhancements", {}),
            "held_items": g.get("held_items", []),
            "deck_cards": g["deck"],
            "fight_discards": g.get("fight_discards", []),
            "fight_played": g.get("fight_played", []),
        }, None

    # Legacy fallback
    if "smart_money" in g["jokers"]:
        held = g["coins"]
        bonus = min(5, held // 5)
        g["coins"] += bonus

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

    if "joker_state" not in g:
        g["joker_state"] = {}
    g["joker_state"]["hot_streak_count"] = 0
    g["joker_state"]["hands_played_fight"] = 0
    g["joker_state"]["discards_used_fight"] = 0
    g["joker_state"]["clockwork_stacks"] = 0

    _deal_for_level(g)

    _GAMES[gid] = g
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
        "max_hand_size": g.get("max_hand_size", 6),
        "base_discards": g.get("base_discards", 3),
        "max_jokers": g.get("max_jokers", 5),
        "joker_state": g.get("joker_state", {}),
        "joker_enhancements": g.get("joker_enhancements", {}),
        "held_items": g.get("held_items", []),
        "deck_cards": g["deck"],
        "fight_discards": g.get("fight_discards", []),
        "fight_played": g.get("fight_played", []),
    }, None


def get_pool(gid):
    g = _GAMES.get(gid)
    if not g:
        return None, "Game not found"
    return {
        "deck_pool": g["deck_pool"],
        "card_effects": g["card_effects"],
    }, None


def get_player_seasons(conn, player_name):
    rows = conn.execute(
        "SELECT season, fantasy_score, team FROM nba_stats WHERE player = ? AND fantasy_score IS NOT NULL ORDER BY season DESC",
        (player_name,)
    ).fetchall()
    return [{"season": r[0], "fantasy_pts": round(r[1] / 10, 1), "team": r[2]} for r in rows]


def get_card_stats(conn, player, season):
    row = conn.execute(
        "SELECT player, season, pos, team, pts_pg, trb_pg, ast_pg FROM nba_stats WHERE player = ? AND season = ?",
        (player, int(season))
    ).fetchone()
    if not row:
        return None
    return {
        "pts_pg": row[4],
        "trb_pg": row[5],
        "ast_pg": row[6],
        "team": row[3],
        "pos": row[2],
    }


def get_score_preview(cards_played, joker_ids, skill_levels=None, combo_boosts=None, card_effects=None, joker_state=None, floor=1, joker_enhancements=None):
    return score_hand(cards_played, joker_ids, skill_levels, combo_boosts, card_effects,
                      joker_state=joker_state, floor=floor, joker_enhancements=joker_enhancements)


def _generate_pack_cards(conn, pack_id, state, candidate_count=5):
    pack = PACK_MAP.get(pack_id)
    if not pack:
        return [], {}

    base_q = """
        SELECT ns.player, ns.season, ns.pos, ns.team, ns.fantasy_score,
               nd.draft_pick, nd.college, na.selections
        FROM nba_stats ns
        LEFT JOIN nba_draft nd ON ns.player = nd.player
        LEFT JOIN nba_allstars na ON ns.player = na.player
        WHERE ns.pos IN ('G','F','C')
    """

    existing_ids = {(c["player"], c["season"]) for c in state["deck_pool"]}
    fetch_limit = candidate_count * 4

    dynasty_team = None
    if pack_id == "starter_pack":
        rows = conn.execute(base_q + f" AND ns.fantasy_score >= 800 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    elif pack_id == "elite_pack":
        rows = conn.execute(base_q + f" AND ns.fantasy_score >= 2000 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    elif pack_id == "position_pack":
        pos = random.choice(["G", "F", "C"])
        rows = conn.execute(base_q + f" AND ns.pos = '{pos}' AND ns.fantasy_score >= 800 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    elif pack_id == "gold_pack":
        rows = conn.execute(base_q + f" AND ns.fantasy_score >= 1200 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    elif pack_id == "all_star_pack":
        rows = conn.execute(base_q + f" AND ns.fantasy_score >= 1500 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    elif pack_id == "allstar_draft_pack":
        rows = conn.execute(base_q + f" AND na.selections >= 1 AND ns.fantasy_score >= 800 ORDER BY na.selections DESC, RANDOM() LIMIT {fetch_limit}").fetchall()
    elif pack_id == "legend_pack":
        rows = conn.execute(base_q + f" AND ns.fantasy_score >= 3500 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    elif pack_id == "dynasty_pack":
        # Pick a random team that has enough players in DB
        team_rows = conn.execute(
            "SELECT team, COUNT(*) as cnt FROM nba_stats WHERE fantasy_score >= 800 AND pos IN ('G','F','C') GROUP BY team ORDER BY RANDOM()"
        ).fetchall()
        dynasty_team = next((r[0] for r in team_rows if r[1] >= 3), None)
        if dynasty_team:
            rows = conn.execute(
                base_q + f" AND ns.team = ? AND ns.fantasy_score >= 800 ORDER BY RANDOM() LIMIT {fetch_limit}",
                (dynasty_team,)
            ).fetchall()
        else:
            rows = conn.execute(base_q + f" AND ns.fantasy_score >= 800 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    elif pack_id == "big_man_pack":
        rows = conn.execute(base_q + f" AND ns.pos = 'C' AND ns.fantasy_score >= 800 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()
    else:
        rows = conn.execute(base_q + f" AND ns.fantasy_score >= 800 ORDER BY RANDOM() LIMIT {fetch_limit}").fetchall()

    cards = []
    idx_start = len(state["deck_pool"]) + 1000
    for i, r in enumerate(rows):
        if (r[0], r[1]) in existing_ids:
            continue
        college = r[6]
        card = {
            "id": f"{r[0]}_{r[1]}_{r[2]}_pack{idx_start + i}",
            "player": r[0], "season": r[1], "pos": r[2], "team": r[3],
            "fantasy_pts": round(r[4] / 10, 1),
            "draft_pick": r[5],
            "college": college,
            "undrafted": r[5] is None,
            "allstar_count": int(r[7]) if r[7] is not None else 0,
            "conference": get_nba_conference(r[3]),
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
    g = _GAMES.get(gid)
    if not g or g["status"] != "shopping":
        return None, "Not in shopping state"

    pack = PACK_MAP.get(pack_id)
    if not pack:
        return None, "Pack not found"

    if g["coins"] < pack["cost"]:
        return None, f"Need {pack['cost']} coins (have {g['coins']})"

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
        _GAMES[gid] = g
        return {
            "pack_name": pack["name"],
            "candidates": candidates,
            "picks_allowed": picks_allowed,
            "is_joker_pack": True,
            "coins": g["coins"],
        }, None

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

    _GAMES[gid] = g
    return {
        "coins": g["coins"],
        "pack_name": pack["name"],
        "pack_tier": pack["tier"],
        "candidates": candidates,
        "picks_allowed": picks_allowed,
        "card_effects": effects,
    }, None


def confirm_pack_picks(gid, selected_ids):
    g = _GAMES.get(gid)
    if not g or "pending_pack" not in g:
        return None, "No pending pack"

    pending = g["pending_pack"]

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
        _GAMES[gid] = g
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

    _GAMES[gid] = g
    return {
        "coins": g["coins"],
        "deck_pool_size": len(g["deck_pool"]),
        "added_cards": selected,
        "card_effects": g["card_effects"],
    }, None


def apply_division_sticker(game_id, card_id, new_division):
    """Update a card's division in the game's deck pool."""
    state = _GAMES.get(game_id)
    if not state:
        return {"error": "Game not found"}
    for card in state["deck_pool"]:
        if card["id"] == card_id:
            card["division"] = new_division
            _GAMES[game_id] = state
            return {"ok": True, "card_id": card_id, "division": new_division}
    return {"error": "Card not found"}
