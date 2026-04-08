import sqlite3
import random
import uuid
import time
from collections import Counter

from session_store import GameStore

_TTL = 3600 * 4
_GAMES = GameStore("nfl_balatro", ttl_seconds=_TTL)

POS_MULT = {"QB": 1.0, "RB": 1.4, "WR": 1.5, "TE": 2.5}
POS_COLOR = {"QB": "qb", "RB": "rb", "WR": "wr", "TE": "te"}
POS_ORDER = ["QB", "RB", "WR", "TE"]

NFL_DIVISIONS = {
    # AFC East
    "BUF": "AFC East", "MIA": "AFC East", "NE": "AFC East", "NWE": "AFC East", "NYJ": "AFC East",
    # AFC North
    "BAL": "AFC North", "CIN": "AFC North", "CLE": "AFC North", "PIT": "AFC North",
    # AFC South
    "HOU": "AFC South", "IND": "AFC South", "JAX": "AFC South", "JAC": "AFC South", "TEN": "AFC South",
    # AFC West
    "DEN": "AFC West", "KC": "AFC West", "KAN": "AFC West", "LV": "AFC West",
    "OAK": "AFC West", "LAC": "AFC West", "SD": "AFC West", "SDG": "AFC West",
    # NFC East
    "DAL": "NFC East", "NYG": "NFC East", "PHI": "NFC East", "WAS": "NFC East", "WSH": "NFC East",
    # NFC North
    "CHI": "NFC North", "DET": "NFC North", "GB": "NFC North", "GNB": "NFC North", "MIN": "NFC North",
    # NFC South
    "ATL": "NFC South", "CAR": "NFC South", "NO": "NFC South", "NOR": "NFC South",
    "TB": "NFC South", "TAM": "NFC South",
    # NFC West
    "ARI": "NFC West", "PHO": "NFC West", "LAR": "NFC West", "STL": "NFC West",
    "SEA": "NFC West", "SF": "NFC West", "SFO": "NFC West",
}

def get_nfl_division(team):
    if not team:
        return None
    return NFL_DIVISIONS.get(team.upper().strip())

HAND_TYPES = {
    "division_balanced": {"name": "Division Balanced Offense", "mult": 25.0, "desc": "QB + 2 WRs + 2 RBs + TE all from same division"},
    "royal_flush":      {"name": "Royal Flush",       "mult": 20.0, "desc": "5-6 cards all same position & same division"},
    "division_six":     {"name": "Division Six",      "mult": 6.0,  "desc": "6 cards all from same division"},
    "six_of_a_kind":    {"name": "Six of a Kind",     "mult": 5.5,  "desc": "6 of the same position"},
    "flush":            {"name": "Position Flush",    "mult": 5.0,  "desc": "5 of same position"},
    "division_five":    {"name": "Division Straight", "mult": 5.0,  "desc": "5 cards all from same division"},
    "position_split":   {"name": "Position Split",    "mult": 4.0,  "desc": "3 of one position + 3 of another"},
    "balanced_offense": {"name": "Balanced Offense",  "mult": 3.5,  "desc": "QB + 2 WRs + 2 RBs + TE"},
    "quad":             {"name": "Quad Set",           "mult": 3.0,  "desc": "4 of same position"},
    "trips":            {"name": "Triple Threat",      "mult": 2.0,  "desc": "3 of same position"},
    "double":           {"name": "Dynamic Duo",        "mult": 1.5,  "desc": "2 of same position"},
    "single":           {"name": "Highlight Reel",     "mult": 1.0,  "desc": "Best single card"},
}

LEVEL_TARGETS = [2000, 6000, 15000, 40000, 100000, 250000, 600000, 1500000]
LEVEL_NAMES = ["Preseason", "Wild Card", "Divisional Round", "Conference Championship", "Super Bowl LIX", "Super Bowl LX", "Super Bowl LXI", "Super Bowl LXII"]

ROUND_BASE_TARGETS = [1800, 5000, 13000, 32000, 80000, 200000, 500000, 1300000]
ROUND_NAMES = ["Preseason", "Wild Card", "Divisional Round", "Conference Championship",
               "Super Bowl LIX", "Super Bowl LX", "Super Bowl LXI", "Super Bowl LXII"]
FIGHT_SCALE = [1.0, 1.3, 1.7]  # within-round scaling (fight 1, 2, 3=boss)
MAX_HAND_SIZE = 8
MAX_DISCARDS = 8

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
    {"id": "te_monster", "name": "TE Monster", "desc": "×1.3 Mult per scored TE (multiplicative, per card)", "rarity": "common"},
    {"id": "air_raid", "name": "Air Raid", "desc": "×1.5 Mult per scored WR (multiplicative, per card)", "rarity": "common"},
    {"id": "ground_pound", "name": "Ground & Pound", "desc": "×1.3 Mult per scored RB (multiplicative, per card)", "rarity": "common"},
    {"id": "field_general", "name": "Field General", "desc": "×1.5 Mult per scored QB (multiplicative, per card)", "rarity": "uncommon"},
    {"id": "first_round_impact", "name": "First Round Impact", "desc": "×1.3 Mult per scored 1st-round pick (multiplicative, per card)", "rarity": "uncommon"},
    {"id": "pro_bowl_power", "name": "Pro Bowl Power", "desc": "×1.5 Mult per scored player with 3+ Pro Bowls (multiplicative, per card)", "rarity": "rare"},
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
    # New jokers
    {"id": "flat_mult",       "name": "Fantasy Manager",       "desc": "+4 Mult. The foundation of every great roster.",                                "rarity": "common"},
    {"id": "pair_bonus",      "name": "Red Zone Strike",        "desc": "+8 Mult if played hand is Dynamic Duo.",                                        "rarity": "common"},
    {"id": "trips_bonus",     "name": "Blitz Package",          "desc": "+12 Mult if played hand is Triple Threat.",                                     "rarity": "common"},
    {"id": "pair_chips",      "name": "Cap Space Boost",        "desc": "+300 base pts if played hand is Dynamic Duo.",                                  "rarity": "common"},
    {"id": "no_disc_mult",    "name": "Overtime",               "desc": "+15 Mult if you have 0 discards remaining when this hand is played.",           "rarity": "common"},
    {"id": "small_hand_mult", "name": "Veteran Minimum",        "desc": "+20 Mult if scoring hand has 3 or fewer cards.",                               "rarity": "common"},
    {"id": "clockwork",       "name": "Two-Minute Drill",       "desc": "Gains +1 Mult per hand played this fight, loses -1 per discard (min 0).",      "rarity": "common"},
    {"id": "deck_pts",        "name": "Home Field Advantage",   "desc": "+2 base pts per card remaining in deck.",                                       "rarity": "common"},
    {"id": "loyalty_xmult",   "name": "Franchise Tag",          "desc": "×4 Mult every 6 hands played this run (multiplicative).",                      "rarity": "uncommon"},
    {"id": "clutch_xmult",    "name": "Game Winner",            "desc": "×3 Mult on the final hand of the fight (multiplicative).",                     "rarity": "uncommon"},
    {"id": "padder_stacker",  "name": "Stat Padder",            "desc": "Gains +2 Mult when you play a Position Split. Stacks permanently.",            "rarity": "uncommon"},
    {"id": "restock_stacker", "name": "Contract Year",          "desc": "Gains +2 Mult each time the shop is restocked. Stacks permanently.",           "rarity": "uncommon"},
    {"id": "uncommon_xmult",  "name": "All-Conference",         "desc": "×1.5 Mult per Uncommon Joker owned (multiplicative).",                         "rarity": "uncommon"},
    {"id": "cavendish_mult",  "name": "The GOAT",               "desc": "×3 Mult. 1 in 1000 chance destroyed at end of each hand.",                     "rarity": "common"},
    {"id": "flush_xmult",     "name": "Super Bowl MVP",         "desc": "×3 Mult if played hand is Position Flush (multiplicative).",                   "rarity": "rare"},
    {"id": "four_xmult",      "name": "Hall of Fame",           "desc": "×4 Mult if played hand is Quad Set (multiplicative).",                         "rarity": "rare"},
    {"id": "delayed_coins",   "name": "Injury Report",          "desc": "Earn $2 at end of fight if no discards were used that fight.",                  "rarity": "common"},
    # ── On-scored per-card attribute jokers ──────────────────────────────────────
    {"id": "high_scorer_chip", "name": "Elite Stat Line",       "desc": "Each scored card with 200+ PPR adds +300 base pts.",                             "rarity": "common"},
    {"id": "pro_bowl_chip",    "name": "All-Pro Bonus",         "desc": "Each scored card with 3+ Pro Bowls adds +300 base pts.",                         "rarity": "uncommon"},
    {"id": "veteran_chip",     "name": "Grizzled Vet",          "desc": "Each scored card drafted before 2015 adds +300 base pts.",                       "rarity": "common"},
    {"id": "youth_chip",       "name": "Rookie Deal",           "desc": "Each scored card drafted 2020+ adds +300 base pts.",                             "rarity": "common"},
    {"id": "late_pick_chip",   "name": "Hidden Gem",            "desc": "Each scored card from draft rounds 3–7 adds +300 base pts.",                     "rarity": "common"},
    {"id": "top_pick_chip",    "name": "Franchise Cornerstone", "desc": "Each scored top-5 overall pick adds +300 base pts.",                             "rarity": "uncommon"},
    {"id": "teammate_chip",    "name": "Locker Room Culture",   "desc": "Each scored card sharing a team with another scored card adds +300 base pts.",   "rarity": "uncommon"},
    {"id": "sec_chip",         "name": "SEC Hotbed",            "desc": "Each scored card from an SEC school adds +300 base pts.",                        "rarity": "uncommon"},
    # Division jokers
    {"id": "div_scout",     "name": "Division Scout",      "desc": "4 same-division cards score as Division Straight (5×).",          "rarity": "uncommon"},
    {"id": "div_dynasty",   "name": "Division Dynasty",    "desc": "5 same-division cards score as Division Six (6×).",               "rarity": "rare"},
    {"id": "div_dominance", "name": "Division Dominance",  "desc": "4 cards same position & division score as Royal Flush (20×).",    "rarity": "rare"},
    {"id": "homefield",     "name": "Home Field Advantage","desc": "Division hands (Straight/Six/Royal Flush) get +4 mult.",          "rarity": "uncommon"},
    {"id": "div_stacker",   "name": "Division Stacker",    "desc": "Each scored card in a division hand adds +300 base pts.",         "rarity": "common"},
    {"id": "div_escalator", "name": "Conference Escalator","desc": "Each division hand played this run permanently adds +0.5 mult.",  "rarity": "rare"},
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
     "name": "Position Switch", "desc": "Switch a card to any other position (QB, RB, WR, or TE)", "cost": 6},
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
    _GAMES.cleanup_expired()


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
                   d.pro_bowls, d.college, d.draft_year, d.draft_round, d.draft_pick,
                   pi.pfr_id,
                   (SELECT MAX(s2.season) FROM stats s2 WHERE s2.player = s.player) AS max_season
            FROM stats s
            LEFT JOIN draft d ON s.player = d.player
            LEFT JOIN nfl_player_ids pi ON s.player = pi.pfr_name
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
        draft_pick = r[9]
        pfr_id = r[10] if len(r) > 10 else None
        max_season = r[11] if len(r) > 11 else None
        raw_college = r[6]
        college = raw_college if (raw_college and raw_college != "Unknown") else ("No college" if draft_pick is not None else None)
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
            "draft_pick": draft_pick,
            "undrafted": draft_pick is None,
            "conference": get_conference(raw_college),
            "division": get_nfl_division(r[3]),
            "pfr_id": pfr_id,
            "max_season": max_season,
            "headshot_url": f"https://www.pro-football-reference.com/req/20230307/images/headshots/{pfr_id}.jpg" if pfr_id else None,
        })
    return cards


def _build_deck(conn):
    """Fetch all qualifying player-season cards from DB."""
    rows = conn.execute("""
        SELECT s.player, s.season, s.pos, s.team, s.fantasy_ppr,
               d.pro_bowls, d.college, d.draft_year, d.draft_round, d.draft_pick,
               pi.pfr_id,
               (SELECT MAX(s2.season) FROM stats s2 WHERE s2.player = s.player) AS max_season
        FROM stats s
        LEFT JOIN draft d ON s.player = d.player
        LEFT JOIN nfl_player_ids pi ON s.player = pi.pfr_name
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
        draft_pick = r[9]
        pfr_id = r[10] if len(r) > 10 else None
        max_season = r[11] if len(r) > 11 else None
        raw_college = r[6]
        college = raw_college if (raw_college and raw_college != "Unknown") else ("No college" if draft_pick is not None else None)
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
            "draft_pick": draft_pick,
            "undrafted": draft_pick is None,
            "conference": get_conference(raw_college),
            "division": get_nfl_division(r[3]),
            "pfr_id": pfr_id,
            "max_season": max_season,
            "headshot_url": f"https://www.pro-football-reference.com/req/20230307/images/headshots/{pfr_id}.jpg" if pfr_id else None,
        })
    return cards


def _deal_for_level(state):
    """Shuffle deck_pool, deal hand_size for hand, rest into deck."""
    pool = list(state["deck_pool"])
    random.shuffle(pool)
    hand_size = state.get("max_hand_size", 7)
    state["hand"] = pool[:hand_size]
    state["deck"] = pool[hand_size:]
    state["fight_discards"] = []
    state["fight_played"] = []


def evaluate_hand(cards):
    """Evaluate hand type. Returns (type_key, scoring_cards)."""
    n = len(cards)
    if n == 0:
        return None, []

    pos_counts = Counter(c["pos"] for c in cards)

    # Division Balanced Offense: QB + 2WR + 2RB + TE all from same division (25x)
    if n == 6 and pos_counts.get("QB") == 1 and pos_counts.get("WR") == 2 and pos_counts.get("RB") == 2 and pos_counts.get("TE") == 1:
        divs = [c.get("division") or get_nfl_division(c.get("team", "")) for c in cards]
        if divs[0] and all(d == divs[0] for d in divs):
            return "division_balanced", cards

    # Royal Flush: 5-6 cards all same position AND all same division (20x)
    if n >= 5:
        divs = [c.get("division") or get_nfl_division(c.get("team", "")) for c in cards]
        if divs[0] and all(d == divs[0] for d in divs) and len(pos_counts) == 1:
            return "royal_flush", cards

    # Division Six: 6 cards all from same division (6x)
    if n == 6:
        divs = [c.get("division") or get_nfl_division(c.get("team", "")) for c in cards]
        if divs[0] and all(d == divs[0] for d in divs):
            return "division_six", cards

    # Six of a Kind: 6 of same position
    if n == 6 and len(pos_counts) == 1:
        return "six_of_a_kind", cards

    # Division Five: 5 cards all from same division (5x)
    if n == 5:
        divs = [c.get("division") or get_nfl_division(c.get("team", "")) for c in cards]
        if divs[0] and all(d == divs[0] for d in divs):
            return "division_five", cards

    # Flush: 5 of same position
    if n == 5 and len(pos_counts) == 1:
        return "flush", cards

    # Balanced Offense: exactly QB=1, WR=2, RB=2, TE=1 (needs 6 cards)
    if n == 6 and pos_counts.get("QB") == 1 and pos_counts.get("WR") == 2 and pos_counts.get("RB") == 2 and pos_counts.get("TE") == 1:
        return "balanced_offense", cards

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


def _calc_joker_mult(hand_type, scoring_cards, all_played, joker_ids, joker_state=None, floor=1, is_blueprint_call=False, joker_enhancements=None, deck_size=0, is_last_hand=False):
    if joker_state is None:
        joker_state = {}
    if joker_enhancements is None:
        joker_enhancements = {}
    bonus = 0.0
    pts_bonus = 0.0
    contributing_ids = []
    for jid in joker_ids:
        jbonus = 0.0
        jpts = 0.0
        if jid == "pro_bowl_pedigree":
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
                    bp_bonus, bp_pts, _ = _calc_joker_mult(
                        hand_type, scoring_cards, all_played, [next_jid],
                        joker_state=joker_state, floor=floor, is_blueprint_call=True,
                        joker_enhancements=joker_enhancements, deck_size=deck_size, is_last_hand=is_last_hand
                    )
                    jbonus = bp_bonus
                    jpts = bp_pts
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
            jbonus = 5 * sum(1 for c in scoring_cards if c.get("undrafted"))
        elif jid == "flat_mult":
            jbonus = 4
        elif jid == "pair_bonus":
            if hand_type == "double":
                jbonus = 8
        elif jid == "trips_bonus":
            if hand_type == "trips":
                jbonus = 12
        elif jid == "pair_chips":
            if hand_type == "double":
                jpts = 300
        elif jid == "no_disc_mult":
            jbonus = 15 if joker_state.get("_discards_remaining", 0) == 0 else 0
        elif jid == "small_hand_mult":
            if len(scoring_cards) <= 3:
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
            jpts = sum(300 for c in scoring_cards if c.get("fantasy_ppr", 0) >= 200)
        elif jid == "pro_bowl_chip":
            jpts = sum(300 for c in scoring_cards if (c.get("pro_bowls") or 0) >= 3)
        elif jid == "veteran_chip":
            jpts = sum(300 for c in scoring_cards if (c.get("draft_year") or 9999) < 2015)
        elif jid == "youth_chip":
            jpts = sum(300 for c in scoring_cards if (c.get("draft_year") or 0) >= 2020)
        elif jid == "late_pick_chip":
            jpts = sum(300 for c in scoring_cards if (c.get("draft_round") or 0) >= 3)
        elif jid == "top_pick_chip":
            jpts = sum(300 for c in scoring_cards if c.get("draft_pick") is not None and c["draft_pick"] <= 5)
        elif jid == "teammate_chip":
            _team_counts = Counter(c.get("team") for c in scoring_cards if c.get("team"))
            jpts = sum(300 for c in scoring_cards if _team_counts.get(c.get("team"), 0) >= 2)
        elif jid == "sec_chip":
            jpts = sum(300 for c in scoring_cards if get_conference(c.get("college", "")) == "SEC")
        elif jid == "homefield":
            if hand_type in ("division_five", "division_six", "royal_flush"):
                jbonus = 4
        elif jid == "div_stacker":
            if hand_type in ("division_five", "division_six", "royal_flush"):
                jpts = sum(300 for _ in scoring_cards)
        elif jid == "div_escalator":
            jbonus = joker_state.get("div_escalator_stacks", 0) * 0.5
        # Apply joker enhancements to per-joker contribution
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
    return bonus, pts_bonus, contributing_ids


_PER_CARD_XMULT_JOKERS = {
    "air_raid":          {"pos": "WR",  "factor": 1.5},
    "te_monster":        {"pos": "TE",  "factor": 1.3},
    "ground_pound":      {"pos": "RB",  "factor": 1.3},
    "field_general":     {"pos": "QB",  "factor": 1.5},
}


def _calc_per_card_xmult(scoring_cards, joker_ids):
    """Per-card multiplicative jokers. Returns (factor, events).
    events = [{"joker_id": ..., "card_id": ..., "factor": ...}, ...]
    ordered by card, so the frontend can animate one event at a time.
    """
    events = []
    for c in scoring_cards:
        for jid in joker_ids:
            if jid in _PER_CARD_XMULT_JOKERS:
                cfg = _PER_CARD_XMULT_JOKERS[jid]
                if c["pos"] == cfg["pos"]:
                    events.append({"joker_id": jid, "card_id": c["id"], "factor": cfg["factor"]})
            elif jid == "first_round_impact":
                if c.get("draft_round") == 1:
                    events.append({"joker_id": jid, "card_id": c["id"], "factor": 1.3})
            elif jid == "pro_bowl_power":
                if (c.get("pro_bowls") or 0) >= 3:
                    events.append({"joker_id": jid, "card_id": c["id"], "factor": 1.5})
    factor = 1.0
    for e in events:
        factor *= e["factor"]
    return round(factor, 4), events


def _calc_joker_mult_factor(hand_type, scoring_cards, all_played, joker_ids, joker_state=None, floor=1, is_last_hand=False):
    """Returns a multiplicative factor (default 1.0) applied to total mult."""
    joker_state = joker_state or {}
    factor = 1.0
    xmult_ids = []
    p5 = {"SEC", "Big Ten", "ACC", "Big 12", "Pac-12"}
    for jid in joker_ids:
        prev_factor = factor
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
        if factor != prev_factor:
            xmult_ids.append(jid)

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
        if hand_type == "flush":
            factor *= 3.0
            xmult_ids.append("flush_xmult")

    if "four_xmult" in joker_ids:
        if hand_type == "quad":
            factor *= 4.0
            xmult_ids.append("four_xmult")

    return round(factor, 3), xmult_ids


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


def _maybe_upgrade_hand_for_jokers(hand_type, scoring_cards, cards_played, joker_ids, joker_state):
    """Upgrade hand type if division-reducing jokers are owned."""
    if not joker_ids:
        return hand_type, scoring_cards
    n = len(cards_played)
    if n < 4:
        return hand_type, scoring_cards

    def _get_div(c):
        return c.get("division") or get_nfl_division(c.get("team", ""))

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
    hand_type, scoring_cards = _maybe_upgrade_hand_for_jokers(hand_type, scoring_cards, cards_played, joker_ids, joker_state)

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
    joker_mult, joker_pts_bonus, joker_add_ids = _calc_joker_mult(hand_type, scoring_cards, cards_played, joker_ids, joker_state=joker_state, floor=floor, joker_enhancements=joker_enhancements, deck_size=deck_size, is_last_hand=is_last_hand)
    # Per-card multiplicative jokers (×mult per qualifying card, animated one at a time)
    per_card_factor, per_card_mult_events = _calc_per_card_xmult(scoring_cards, joker_ids)
    total_mult = (hand_mult * per_card_factor) + joker_mult
    # Multiplicative factor from special jokers
    mult_factor, xmult_joker_ids = _calc_joker_mult_factor(hand_type, scoring_cards, cards_played, joker_ids, joker_state=joker_state, floor=floor, is_last_hand=is_last_hand)
    base_pts_total = base_pts + joker_pts_bonus
    score = round(base_pts_total * total_mult * mult_factor * glass_mult)

    # smash_factor: x1.5 multiplicative after all other scoring
    if "smash_factor" in joker_ids:
        score = round(score * 1.5)
        if "smash_factor" not in xmult_joker_ids:
            xmult_joker_ids.append("smash_factor")

    return {
        "score": score,
        "hand_type": hand_type,
        "hand_name": HAND_TYPES[hand_type]["name"],
        "hand_desc": HAND_TYPES[hand_type]["desc"],
        "base_pts": round(base_pts_total, 1),
        "hand_mult": hand_mult,
        "joker_mult": round(joker_mult, 1),
        "joker_add_ids": joker_add_ids,
        "per_card_mult_events": per_card_mult_events,
        "per_card_factor": per_card_factor,
        "total_mult": round(total_mult, 1),
        "mult_factor": mult_factor,
        "xmult_joker_ids": xmult_joker_ids,
        "glass_mult": glass_mult,
        "scoring_cards": scoring_cards,
        "card_contributions": card_contributions,
        "scoring_card_ids": [c["id"] for c in scoring_cards],
    }


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
    """Generate shop items grouped into sections."""
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

    # ── Section "roster": up to 4 jokers ──────────────────────────────
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
        ppr_min = 80 if floor <= 3 else (120 if floor <= 6 else 180)
        buy_rows = conn.execute("""
            SELECT s.player, s.season, s.pos, s.team, s.fantasy_ppr,
                   d.pro_bowls, d.college, d.draft_year, d.draft_round, d.draft_pick,
                   pi.pfr_id,
                   (SELECT MAX(s2.season) FROM stats s2 WHERE s2.player = s.player) AS max_season
            FROM stats s
            LEFT JOIN draft d ON s.player = d.player
            LEFT JOIN nfl_player_ids pi ON s.player = pi.pfr_name
            WHERE s.fantasy_ppr >= ?
              AND s.pos IN ('QB','RB','WR','TE')
            ORDER BY RANDOM()
            LIMIT 20
        """, (ppr_min,)).fetchall()
        existing_ids = {(c["player"], c["season"]) for c in state.get("deck_pool", [])}
        buy_candidates = [r for r in buy_rows if (r[0], r[1]) not in existing_ids]
        for i, row in enumerate(buy_candidates[:roster_player_count]):
            college = row[6]
            pfr_id = row[10] if len(row) > 10 else None
            max_season = row[11] if len(row) > 11 else None
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
                "pfr_id": pfr_id,
                "max_season": max_season,
                "headshot_url": f"https://www.pro-football-reference.com/req/20230307/images/headshots/{pfr_id}.jpg" if pfr_id else None,
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

    # ── Section "training": 2 skills + 2 effects + 2 upgrades ──────────
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

    # 2 upgrades (filter out capped ones)
    cur_hand_size = state.get("max_hand_size", 7)
    cur_discards = state.get("base_discards", 3)
    upgrade_options = [u for u in SHOP_UPGRADES if not (
        (u["stat"] == "max_hand_size" and cur_hand_size >= MAX_HAND_SIZE) or
        (u["stat"] == "base_discards" and cur_discards >= MAX_DISCARDS)
    )]
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
            "desc": "Reassign any card to a new NFL division. Slap it on!",
            "cost": scale_cost(7),
            "sold": False,
        })
        slot_idx += 1

    for tp in training_pool:
        tp["slot"] = slot_idx
        items.append(tp)
        slot_idx += 1

    # Sort by slot
    items.sort(key=lambda x: x["slot"])
    return items


def _get_fight_target(round_num, fight_num, mode="normal"):
    if mode == "infinity":
        # Exponential scaling: starts at 2000, grows ~×2.5 per fight
        fight_num_total = (round_num - 1) * 3 + fight_num
        return int(2000 * (2.5 ** (fight_num_total - 1)))
    base = ROUND_BASE_TARGETS[min(round_num - 1, len(ROUND_BASE_TARGETS) - 1)]
    scale = FIGHT_SCALE[min(fight_num - 1, len(FIGHT_SCALE) - 1)]
    return int(base * scale)


def _get_level_name(round_num, fight_num, boss_effect=None, mode="normal"):
    if mode == "infinity":
        fight_num_total = (round_num - 1) * 3 + fight_num
        if fight_num == 3:
            boss_name = BOSS_EFFECT_MAP.get(boss_effect, {}).get("name", "Boss") if boss_effect else "Boss"
            return f"∞ Wave {fight_num_total} · BOSS: {boss_name}"
        return f"∞ Wave {fight_num_total}"
    round_name = ROUND_NAMES[min(round_num - 1, len(ROUND_NAMES) - 1)]
    if fight_num == 3:
        boss_name = BOSS_EFFECT_MAP.get(boss_effect, {}).get("name", "Boss") if boss_effect else "Boss"
        return f"{round_name} · BOSS: {boss_name}"
    return f"{round_name} · Fight {fight_num}"


def _apply_boss_hand_effect(state):
    """Mark cards in hand as disabled by boss effect (red X, unplayable)."""
    boss = state.get("boss_effect")
    if not boss:
        return
    if boss == "sec_lockout":
        for c in state["hand"]:
            if c.get("conference") == "SEC":
                c["boss_disabled"] = True
    elif boss == "rookie_ban":
        for c in state["hand"]:
            if (c.get("draft_year") or 0) >= 2020:
                c["boss_disabled"] = True


def start_game(conn, mode="normal"):
    cleanup_old_games()
    deck_pool = _build_deck_pool(conn)

    gid = str(uuid.uuid4())[:8]
    state = {
        "created_at": time.time(),
        "mode": mode,
        "floor": 1,
        "round": 1,
        "fight": 1,
        "boss_effect": None,
        "target_score": _get_fight_target(1, 1, mode=mode),
        "level_name": _get_level_name(1, 1, mode=mode),
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
        "combo_boosts": {ht: 0 for ht in HAND_TYPES},
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
        "fight_discards": [],
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

    # Pre-scoring state updates
    is_last_hand = (g["hands_remaining"] == 1)
    deck_size = len(g["deck"])
    joker_state["_discards_remaining"] = g.get("discards_remaining", 0)
    joker_state["hands_played_run"] = joker_state.get("hands_played_run", 0) + 1
    joker_state["hands_played_fight"] = joker_state.get("hands_played_fight", 0) + 1
    joker_state["clockwork_stacks"] = joker_state.get("clockwork_stacks", 0) + 1

    result = score_hand(played, g["jokers"], skill_levels, combo_boosts, card_effects, joker_state=joker_state, floor=g.get("floor", 1), joker_enhancements=joker_enhancements, deck_size=deck_size, is_last_hand=is_last_hand)

    if result.get("hand_type") in ("division_five", "division_six", "royal_flush"):
        joker_state["div_escalator_stacks"] = joker_state.get("div_escalator_stacks", 0) + 1

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
    g.setdefault("fight_played", []).extend(played)

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

    # Remove played cards from hand and draw up to max hand size
    g["hand"] = [c for c in g["hand"] if c["id"] not in id_set]
    needed = g.get("max_hand_size", 7) - len(g["hand"])
    # If deck runs short, shuffle fight_discards back in
    if len(g["deck"]) < needed and g.get("fight_discards"):
        recycled = [c for c in g["fight_discards"] if c["id"] not in id_set]
        random.shuffle(recycled)
        g["deck"].extend(recycled)
        g["fight_discards"] = []
    draw_count = min(needed, len(g["deck"]))
    g["hand"].extend(g["deck"][:draw_count])
    g["deck"] = g["deck"][draw_count:]
    _apply_boss_hand_effect(g)

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

    # padder_stacker: gains +2 when position_split is played
    if "padder_stacker" in g["jokers"] and result["hand_type"] == "position_split":
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
    result["fight_discards"] = g.get("fight_discards", [])

    if g["current_score"] >= g["target_score"]:
        fight = g.get("fight", 1)
        round_num = g.get("round", 1)
        mode = g.get("mode", "normal")
        # Bonus: $1 per remaining hand when fight is won
        hand_bonus = g["hands_remaining"]
        if hand_bonus > 0:
            g["coins"] += hand_bonus
            coins_earned += hand_bonus
            result["coins"] = g["coins"]
            result["coins_earned"] = coins_earned
            result["hand_bonus"] = hand_bonus
        if mode != "infinity" and fight == 3 and round_num >= 8:
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
    """Called when won_fight. Show reward choice, then open shop after player decides."""
    g = _GAMES.get(gid)
    if not g or g["status"] != "won_fight":
        return None, "Not in won_fight state"

    fight = g.get("fight", 1)
    round_num = g.get("round", 1)

    # Determine next state: within round or new round
    if fight == 3:
        next_round = round_num + 1
        next_fight = 1
        boss_effect = None
    else:
        next_round = round_num
        next_fight = fight + 1
        boss_effect = random.choice(BOSS_EFFECTS)["id"] if next_fight == 3 else None

    # Store pending advance — resolved when player leaves shop
    g["pending_fight_advance"] = True
    g["next_round"] = next_round
    g["next_fight"] = next_fight
    g["pending_boss_effect"] = boss_effect

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


def start_infinity_mode(gid):
    """Continue a won game in infinity mode from round 9."""
    g = _GAMES.get(gid)
    if not g or g["status"] != "won_game":
        return None, "Game not in won state"

    g["mode"] = "infinity"
    next_round = g.get("round", 8) + 1
    next_fight = 1

    g["pending_fight_advance"] = True
    g["next_round"] = next_round
    g["next_fight"] = next_fight
    g["pending_boss_effect"] = None

    reward_coins = 3 + g.get("round", 8) * 2
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
        "mode": "infinity",
        "coins": g["coins"],
        "reward_coins_amount": reward_coins,
        "reward_joker_options": reward_jokers,
        "next_fight": next_fight,
        "next_boss_effect": None,
    }, None


def claim_fight_reward(gid, choice, joker_id=None, conn=None):
    """Player claims their fight reward: either coins or a free joker."""
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
        "held_cards": g.get("held_cards", []),
        "next_fight": g.get("next_fight", 1),
        "next_boss_effect": BOSS_EFFECT_MAP.get(g.get("pending_boss_effect")) if g.get("pending_boss_effect") else None,
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
    g["joker_state"]["discards_used_fight"] = g["joker_state"].get("discards_used_fight", 0) + 1
    g["joker_state"]["clockwork_stacks"] = max(0, g["joker_state"].get("clockwork_stacks", 0) - 1)
    g["hand"] = [c for c in g["hand"] if c["id"] not in id_set]
    needed = g.get("max_hand_size", 7) - len(g["hand"])
    # If deck runs short, shuffle fight_discards (minus cards being discarded now) back in
    if len(g["deck"]) < needed and g.get("fight_discards"):
        recycled = [c for c in g["fight_discards"] if c["id"] not in id_set]
        random.shuffle(recycled)
        g["deck"].extend(recycled)
        g["fight_discards"] = []
    draw_count = min(needed, len(g["deck"]))
    g["hand"].extend(g["deck"][:draw_count])
    g["deck"] = g["deck"][draw_count:]
    _apply_boss_hand_effect(g)
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
    g["shop_packs"] = shop_packs[:4]

    # Generate shop using conn - store shop items directly
    # We'll generate shop without DB for jokers already in pool
    # For full shop we need conn; we'll return a flag and generate in route
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
        "held_cards": g.get("held_cards", []),
    }, None


def generate_shop_for_game(gid, conn):
    """Generate shop items for a game (called from route with db connection)."""
    g = _GAMES.get(gid)
    if not g:
        return None
    g["shop_items"] = _generate_shop(conn, g)
    g.pop("pending_shop_generation", None)
    _GAMES[gid] = g
    return g["shop_items"]


def buy_shop_item(gid, item_type, shop_id, target_card_id=None, target_year=None, conn=None, new_pos=None):
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
        elif stat == "max_hand_size":
            new_val = min(g.get("max_hand_size", 7) + amount, MAX_HAND_SIZE)
            g["max_hand_size"] = new_val
        elif stat == "base_discards":
            new_val = min(g.get("base_discards", 3) + amount, MAX_DISCARDS)
            g["base_discards"] = new_val
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
            valid_positions = {"QB", "RB", "WR", "TE"}
            target = next((c for c in g["deck_pool"] if c["id"] == target_card_id), None)
            if not target:
                return None, "Card not found"
            chosen = new_pos if new_pos in valid_positions else None
            if not chosen or chosen == target["pos"]:
                # fallback: cycle to next position
                cycle = {"QB": "WR", "WR": "RB", "RB": "TE", "TE": "QB"}
                chosen = cycle.get(target["pos"], "WR")
            target["pos"] = chosen
            for hc in g["hand"]:
                if hc["id"] == target_card_id:
                    hc["pos"] = chosen

    elif item["type"] == "buy_card":
        card_data = item.get("card_data")
        if not card_data:
            return None, "No card data in item"
        import copy as _copy
        new_card = _copy.deepcopy(card_data)
        g.setdefault("deck_pool", []).append(new_card)
        g.setdefault("deck", []).append(new_card)

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

    _GAMES[gid] = g
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
    _GAMES[gid] = g
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
    if "restock_stacker" in g["jokers"]:
        g["joker_state"]["restock_stacks"] = g["joker_state"].get("restock_stacks", 0) + 2
    g["shop_items"] = _generate_shop(conn, g)
    # Regenerate packs
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
    _GAMES[gid] = g
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
        mode = g.get("mode", "normal")
        g["target_score"] = _get_fight_target(new_round, new_fight, mode=mode)
        g["level_name"] = _get_level_name(new_round, new_fight, boss_effect, mode=mode)
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
            "max_hand_size": g.get("max_hand_size", 7),
            "base_discards": g.get("base_discards", 3),
            "max_jokers": g.get("max_jokers", 5),
            "joker_state": g.get("joker_state", {}),
            "joker_enhancements": g.get("joker_enhancements", {}),
            "held_cards": g.get("held_cards", []),
            "deck_cards": g["deck"],
            "fight_discards": g.get("fight_discards", []),
            "fight_played": g.get("fight_played", []),
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
    mode = g.get("mode", "normal")
    g["target_score"] = _get_fight_target(new_round, 1, mode=mode)
    g["level_name"] = _get_level_name(new_round, 1, mode=mode)
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
        "max_hand_size": g.get("max_hand_size", 7),
        "base_discards": g.get("base_discards", 3),
        "max_jokers": g.get("max_jokers", 5),
        "joker_state": g.get("joker_state", {}),
        "joker_enhancements": g.get("joker_enhancements", {}),
        "held_cards": g.get("held_cards", []),
        "deck_cards": g["deck"],
        "fight_discards": g.get("fight_discards", []),
        "fight_played": g.get("fight_played", []),
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
        draft_pick = r[9]
        raw_college = r[6]
        college = raw_college if (raw_college and raw_college != "Unknown") else ("No college" if draft_pick is not None else None)
        card = {
            "id": f"{r[0]}_{r[1]}_{r[2]}_pack{idx_start + i}",
            "player": r[0], "season": r[1], "pos": r[2], "team": r[3],
            "fantasy_ppr": round(r[4], 1),
            "pro_bowls": int(r[5]) if r[5] else 0,
            "college": college, "draft_year": r[7], "draft_round": r[8], "draft_pick": draft_pick,
            "undrafted": draft_pick is None,
            "conference": get_conference(raw_college),
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
        _GAMES[gid] = g
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
