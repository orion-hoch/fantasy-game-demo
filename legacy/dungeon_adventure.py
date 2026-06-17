import random

import chain_categories as cc


ITEM_CATEGORY_IDS = [
    "position",
    "team",
    "college",
    "conference",
    "pro_bowl",
    "all_pro",
    "round_1",
    "top_10",
    "era",
    "afc_nfc",
    "division",
    "pass_yds",
    "pass_td",
    "rush_yds",
    "rec_yds",
    "rec_100",
    "high_ppr",
    "sacks",
    "interceptions",
    "hof",
    "sb_champion",
    "sb_appearance",
    "nfl_award",
    "all_rookie_nfl",
]

QUESTION_CATEGORY_IDS = [
    "team",
    "college",
    "conference",
    "pro_bowl",
    "all_pro",
    "round_1",
    "top_10",
    "pass_yds",
    "pass_td",
    "rush_yds",
    "rec_yds",
    "rec_100",
    "era",
    "afc_nfc",
    "division",
    "high_ppr",
    "sacks",
    "interceptions",
    "hof",
    "sb_champion",
    "sb_appearance",
    "nfl_award",
    "all_rookie_nfl",
]

ENEMY_NAMES = [
    "Dust Rat",
    "Crypt Wolf",
    "Stat Wraith",
    "Ash Serpent",
    "Iron Minotaur",
    "Rune Lich",
    "Depth Tyrant",
]

ITEM_PREFIXES = ["Bent", "Ashen", "Iron", "Runed", "Ancient", "Cinder", "Grim"]
ITEM_NOUNS = ["Lantern", "Dagger", "Helm", "Charm", "Totem", "Sigil", "Compass"]
POWER_FOUR_COLLEGES = set().union(*cc.CONFERENCE_SCHOOLS.values())
CUSTOM_VALUE_OPTIONS = {
    "pass_yds": [3000, 3500, 4000, 4500, 5000],
    "pass_td": [20, 25, 30, 35, 40],
    "rush_yds": [500, 750, 1000, 1200, 1500],
    "rec_yds": [600, 800, 1000, 1200, 1400],
    "high_ppr": [180, 220, 260, 300, 340],
    "sacks": [5, 8, 10, 12, 15],
    "interceptions": [3, 5, 7, 9],
}
ITEM_SYMBOLS = {
    "position": "/",
    "team": "#",
    "college": "^",
    "conference": "~",
    "pro_bowl": "*",
    "all_pro": "=",
    "round_1": "!",
    "top_10": "+",
    "era": ":",
    "afc_nfc": "%",
    "division": "&",
    "pass_yds": ">",
    "pass_td": ")",
    "rush_yds": "<",
    "rec_yds": "[",
    "rec_100": "]",
    "high_ppr": "$",
    "sacks": "x",
    "interceptions": "?",
    "hof": "@",
    "sb_champion": "W",
    "sb_appearance": "S",
    "nfl_award": "A",
    "all_rookie_nfl": "R",
}
ITEM_ICON_KEYS = {
    "position": "position",
    "team": "team",
    "college": "school",
    "conference": "conference",
    "pro_bowl": "award",
    "all_pro": "award",
    "round_1": "draft",
    "top_10": "draft",
    "era": "era",
    "afc_nfc": "division",
    "division": "division",
    "pass_yds": "pass",
    "pass_td": "pass",
    "rush_yds": "rush",
    "rec_yds": "receive",
    "rec_100": "receive",
    "high_ppr": "award",
    "sacks": "defense",
    "interceptions": "defense",
    "hof": "award",
    "sb_champion": "award",
    "sb_appearance": "award",
    "nfl_award": "award",
    "all_rookie_nfl": "draft",
}

TIER_RULES = {
    "starter": {"label": "Starter", "min_count": 1000, "max_count": 2000, "bonus": 1, "min_projected": 160},
    "medium": {"label": "Medium", "min_count": 500, "max_count": 1000, "bonus": 3, "min_projected": 90},
    "hard": {"label": "Hard", "min_count": 100, "max_count": 500, "bonus": 5, "min_projected": 40},
}

REWARD_PLANS = {
    0: ["starter", "starter", "starter"],
    1: ["starter", "medium", "medium"],
    2: ["medium", "medium", "hard"],
    3: ["medium", "hard", "hard"],
}

FLOOR_THEMES = {
    1: {
        "name": "Mosslight Approach",
        "scene": "moss",
        "enemy": "Dust Rat",
        "categories": ["team", "afc_nfc", "division", "college", "conference"],
        "prompt": "The low ruins ask broad roster knowledge.",
    },
    2: {
        "name": "Archive Of Brass",
        "scene": "archive",
        "enemy": "Crypt Wolf",
        "categories": ["conference", "college", "round_1", "top_10", "pro_bowl", "all_rookie_nfl"],
        "prompt": "The records shift toward draft and pedigree clues.",
    },
    3: {
        "name": "Ember Gallery",
        "scene": "ember",
        "enemy": "Stat Wraith",
        "categories": ["pass_td", "pass_yds", "high_ppr", "era", "team", "round_1", "top_10"],
        "prompt": "The flames reward season totals and fantasy monsters.",
    },
    4: {
        "name": "Flooded Reliquary",
        "scene": "river",
        "enemy": "Ash Serpent",
        "categories": ["rush_yds", "rec_yds", "rec_100", "college", "division", "pro_bowl", "sb_appearance"],
        "prompt": "The water hall leans into skill-position production.",
    },
    5: {
        "name": "Storm Bastion",
        "scene": "storm",
        "enemy": "Iron Minotaur",
        "categories": ["sacks", "interceptions", "all_pro", "era", "conference", "team", "division", "nfl_award", "sb_champion"],
        "prompt": "The upper keep demands sharper recall and defense-heavy answers.",
    },
    6: {
        "name": "Throne Of Names",
        "scene": "boss",
        "enemy": "Depth Tyrant",
        "categories": ["top_10", "all_pro", "conference", "pass_td", "pass_yds", "rec_yds", "rush_yds", "sacks", "interceptions", "high_ppr", "pro_bowl", "era", "hof", "nfl_award", "sb_champion"],
        "prompt": "The boss fight cycles through three themed questions before it breaks.",
        "boss": True,
        "phase_goal": 3,
    },
}


def _format_label(cat, value):
    if value:
        return cat["label"].replace("{value}", str(value))
    return cat["label"]


def _lower_first(text):
    if not text:
        return text
    return text[0].lower() + text[1:]


def _players_for_link(conn, link):
    cat = cc._CAT_BY_ID.get(link["id"])
    if not cat:
        return frozenset()
    return cat["players"](conn, link.get("value", ""))


def _all_players(conn):
    rows = conn.execute(
        """SELECT DISTINCT player FROM stats
           UNION
           SELECT DISTINCT player FROM season_stats
           UNION
           SELECT DISTINCT player FROM draft
           UNION
           SELECT DISTINCT player FROM def_stats
           ORDER BY player"""
    ).fetchall()
    return frozenset(row[0] for row in rows if row[0])


def _allowed_players(conn, items):
    allowed = None
    for item in items:
        players = _players_for_link(conn, item)
        allowed = players if allowed is None else allowed & players
    if allowed is None:
        allowed = _all_players(conn)
    return allowed


def _item_name():
    return f"{random.choice(ITEM_PREFIXES)} {random.choice(ITEM_NOUNS)}"


def _plan_for_items(item_count):
    if item_count >= 3:
        return REWARD_PLANS[3]
    return REWARD_PLANS[item_count]


def _base_bonus(tier_name, floor):
    return TIER_RULES[tier_name]["bonus"] + min(2, max(0, floor - 3))


def _is_allowed_value(cat_id, value):
    if cat_id == "college":
        return value in POWER_FOUR_COLLEGES
    return True


def _pick_value(cat_id, cat, conn):
    options = CUSTOM_VALUE_OPTIONS.get(cat_id)
    if options:
        return str(random.choice(options))
    return cat["pick"](conn, None)


def _question_key(cat_id, value):
    return f"{cat_id}:{value}"


def _make_item(cat, value, base_count, projected_count, tier_name, floor):
    label = _format_label(cat, value)
    tier = TIER_RULES[tier_name]
    return {
        "id": cat["id"],
        "value": value,
        "label": label,
        "filter_text": f"Only answers that {_lower_first(label)}",
        "name": _item_name(),
        "bonus": _base_bonus(tier_name, floor),
        "rarity": tier["label"],
        "tier": tier_name,
        "base_count": base_count,
        "projected_count": projected_count,
        "symbol": ITEM_SYMBOLS.get(cat["id"], "+"),
        "icon": f"/static/img/dungeon_icons/{ITEM_ICON_KEYS.get(cat['id'], 'relic')}.svg",
    }


def _get_item_candidates(conn, current_items, tier_name):
    rules = TIER_RULES[tier_name]
    used_ids = cc._expand_excluded([item["id"] for item in current_items])
    allowed_now = _allowed_players(conn, current_items)
    candidates = []

    for cat_id in ITEM_CATEGORY_IDS:
        if cat_id in used_ids:
            continue
        cat = cc._CAT_BY_ID[cat_id]
        attempts = 14 if "{value}" in cat["label"] else 4
        seen = set()
        for _ in range(attempts):
            value = _pick_value(cat_id, cat, conn)
            if value is None or value in seen:
                continue
            seen.add(value)
            if not _is_allowed_value(cat_id, value):
                continue
            players = cat["players"](conn, value)
            base_count = len(players)
            projected_count = len(players & allowed_now)
            if rules["min_count"] <= base_count <= rules["max_count"] and projected_count >= rules["min_projected"]:
                candidates.append((projected_count, base_count, cat, value))

    random.shuffle(candidates)
    candidates.sort(key=lambda entry: (-entry[0], entry[1]))
    return candidates


def _get_fallback_candidates(conn, current_items):
    used_ids = cc._expand_excluded([item["id"] for item in current_items])
    allowed_now = _allowed_players(conn, current_items)
    candidates = []
    for cat_id in ITEM_CATEGORY_IDS:
        if cat_id in used_ids:
            continue
        cat = cc._CAT_BY_ID[cat_id]
        attempts = 14 if "{value}" in cat["label"] else 4
        seen = set()
        for _ in range(attempts):
            value = _pick_value(cat_id, cat, conn)
            if value is None or value in seen:
                continue
            seen.add(value)
            if not _is_allowed_value(cat_id, value):
                continue
            players = cat["players"](conn, value)
            base_count = len(players)
            projected_count = len(players & allowed_now)
            if projected_count >= 8:
                candidates.append((projected_count, base_count, cat, value, "medium"))
    random.shuffle(candidates)
    candidates.sort(key=lambda entry: (-entry[0], entry[1]))
    return candidates


def _fallback_tiers(tier_name):
    if tier_name == "starter":
        return ["starter", "medium", "hard"]
    if tier_name == "medium":
        return ["medium", "starter", "hard"]
    return ["hard", "medium", "starter"]


def get_reward_options(conn, floor, current_items, count=3):
    plan = _plan_for_items(len(current_items))
    used_keys = set()
    rewards = []

    for desired_tier in plan[:count]:
        reward = None
        for tier_name in _fallback_tiers(desired_tier):
            candidates = _get_item_candidates(conn, current_items, tier_name)
            for projected_count, base_count, cat, value in candidates:
                key = _question_key(cat["id"], value)
                if key in used_keys:
                    continue
                reward = _make_item(cat, value, base_count, projected_count, tier_name, floor)
                used_keys.add(key)
                break
            if reward:
                break
        if reward:
            rewards.append(reward)

    if len(rewards) < count:
        for projected_count, base_count, cat, value, tier_name in _get_fallback_candidates(conn, current_items):
            key = _question_key(cat["id"], value)
            if key in used_keys:
                continue
            rewards.append(_make_item(cat, value, base_count, projected_count, tier_name, floor))
            used_keys.add(key)
            if len(rewards) == count:
                break

    return rewards


def _question_prompt(label):
    return f"Name a player who {_lower_first(label)}."


def _canonicalize_answer(answer, valid_players):
    from name_utils import normalize_name
    answer_key = normalize_name(answer)
    lookup = {normalize_name(name): name for name in valid_players}
    return lookup.get(answer_key)


def _theme_for_floor(floor):
    return FLOOR_THEMES.get(floor, FLOOR_THEMES[6])


def _enemy_payload(floor, theme):
    is_boss = bool(theme.get("boss"))
    hp = 7 + floor * 2 if not is_boss else 16 + floor * 3
    damage = 3 + floor if not is_boss else 6 + floor
    return {
        "name": theme.get("enemy") or ENEMY_NAMES[min(len(ENEMY_NAMES) - 1, max(0, floor - 1))],
        "floor": floor,
        "hp": hp,
        "damage": damage,
        "glyph": "E",
        "is_boss": is_boss,
        "phase_goal": theme.get("phase_goal", 1),
    }


def _iter_question_categories(theme):
    preferred = list(theme.get("categories", []))
    fallback = [cat_id for cat_id in QUESTION_CATEGORY_IDS if cat_id not in preferred]
    random.shuffle(preferred)
    random.shuffle(fallback)
    return preferred + fallback


def get_encounter(conn, floor, current_items, used_questions=None):
    used_questions = set(used_questions or [])
    allowed_players = _allowed_players(conn, current_items)
    theme = _theme_for_floor(floor)
    enemy = _enemy_payload(floor, theme)

    best = None
    for cat_id in _iter_question_categories(theme):
        cat = cc._CAT_BY_ID[cat_id]
        attempts = 14 if "{value}" in cat["label"] else 4
        seen = set()
        for _ in range(attempts):
            value = _pick_value(cat_id, cat, conn)
            key = _question_key(cat_id, value)
            if value is None or value in seen or key in used_questions:
                continue
            seen.add(value)
            if not _is_allowed_value(cat_id, value):
                continue
            label = _format_label(cat, value)
            question_players = cat["players"](conn, value)
            valid_players = question_players & allowed_players
            count = len(valid_players)
            payload = {
                "id": cat_id,
                "value": value,
                "label": label,
                "prompt": _question_prompt(label),
                "valid_count": count,
                "key": key,
            }
            if count >= 8:
                return {"enemy": enemy, "question": payload, "theme": theme}
            if count >= 3 and best is None:
                best = {"enemy": enemy, "question": payload, "theme": theme}
    return best


def check_answer(conn, question, current_items, answer):
    question_players = _players_for_link(conn, question)
    allowed_players = _allowed_players(conn, current_items)
    valid_players = question_players & allowed_players
    canonical = _canonicalize_answer(answer, question_players | allowed_players)

    if canonical and canonical in valid_players:
        return {"correct": True, "player": canonical, "filter_failures": [], "question_match": True}

    if canonical and canonical in question_players:
        failures = []
        for item in current_items:
            if canonical not in _players_for_link(conn, item):
                failures.append(item["label"])
        return {"correct": False, "player": canonical, "filter_failures": failures, "question_match": True}

    return {"correct": False, "player": canonical, "filter_failures": [], "question_match": False}


def search_answers(conn, query, current_items, question=None, limit=8):
    from name_utils import normalize_name
    key = normalize_name(query)
    if not key:
        return []
    pool = _all_players(conn)
    starts, contains = [], []
    for player in sorted(pool):
        nk = normalize_name(player)
        if nk.startswith(key):
            starts.append(player)
        elif key in nk:
            contains.append(player)
    return (starts + contains)[:limit]
