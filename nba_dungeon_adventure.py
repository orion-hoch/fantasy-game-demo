import random

import nba_chain_categories as cc


ITEM_CATEGORY_IDS = ["position", "team", "college", "era", "conference", "division", "first_round", "top_10", "pts_season", "reb_season", "ast_season"]
QUESTION_CATEGORY_IDS = ["team", "college", "era", "conference", "division", "first_round", "top_10", "pts_season", "reb_season", "ast_season"]
ITEM_PREFIXES = ["Bronze", "Dust", "Stone", "Runed", "Royal", "Obsidian", "Ancient"]
ITEM_NOUNS = ["Band", "Key", "Medal", "Mask", "Charm", "Tablet", "Token"]
CUSTOM_VALUE_OPTIONS = {
    "pts_season": [15, 18, 20, 22, 25, 28, 30],
    "reb_season": [6, 8, 10, 12, 14],
    "ast_season": [5, 7, 9, 11, 13],
}
ITEM_SYMBOLS = {
    "position": "/",
    "team": "#",
    "college": "^",
    "era": ":",
    "conference": "~",
    "division": "%",
    "first_round": "!",
    "top_10": "+",
    "pts_season": ">",
    "reb_season": "=",
    "ast_season": "<",
}
ITEM_ICON_KEYS = {
    "position": "position",
    "team": "team",
    "college": "school",
    "era": "era",
    "conference": "conference",
    "division": "division",
    "first_round": "draft",
    "top_10": "draft",
    "pts_season": "scoring",
    "reb_season": "rebound",
    "ast_season": "assist",
}
TIER_RULES = {
    "starter": {"label": "Starter", "min_count": 250, "max_count": 1200, "bonus": 1, "min_projected": 80},
    "medium": {"label": "Medium", "min_count": 120, "max_count": 400, "bonus": 3, "min_projected": 40},
    "hard": {"label": "Hard", "min_count": 30, "max_count": 160, "bonus": 5, "min_projected": 14},
}
REWARD_PLANS = {0: ["starter", "starter", "starter"], 1: ["starter", "medium", "medium"], 2: ["medium", "medium", "hard"], 3: ["medium", "hard", "hard"]}
FLOOR_THEMES = {
    1: {"name": "Backcourt Gate", "enemy": "Gym Shade", "categories": ["team", "conference", "division", "position"], "prompt": "Early floors focus on broad NBA roster memory."},
    2: {"name": "Draft Gallery", "enemy": "Lottery Hound", "categories": ["college", "first_round", "top_10", "era"], "prompt": "The route shifts toward draft history and school roots."},
    3: {"name": "Scoring Vault", "enemy": "Shot Wraith", "categories": ["pts_season", "team", "era", "conference", "top_10"], "prompt": "Scorers rule this section of the dungeon."},
    4: {"name": "Glass Chamber", "enemy": "Rim Serpent", "categories": ["reb_season", "position", "division", "college", "first_round"], "prompt": "Bigs and rebounders dominate the chamber."},
    5: {"name": "Passing Court", "enemy": "Assist Lich", "categories": ["ast_season", "team", "conference", "era", "college"], "prompt": "Playmakers and table-setters take over here."},
    6: {"name": "Hall Of Legends", "enemy": "Crown Titan", "categories": ["top_10", "first_round", "pts_season", "reb_season", "ast_season", "college", "conference", "division", "era"], "prompt": "The boss cycles through three NBA prompts before it breaks.", "boss": True, "phase_goal": 3},
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
        """SELECT DISTINCT player FROM nba_stats
           UNION
           SELECT DISTINCT player FROM nba_draft
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


def _pick_value(cat_id, cat, conn):
    options = CUSTOM_VALUE_OPTIONS.get(cat_id)
    if options:
        return str(random.choice(options))
    return cat["pick"](conn, None)


def _base_bonus(tier_name, floor):
    return TIER_RULES[tier_name]["bonus"] + min(2, max(0, floor - 3))


def _candidate_key(cat_id, value):
    return f"{cat_id}:{value}"


def _make_item(cat, value, base_count, projected_count, tier_name, floor):
    return {
        "id": cat["id"],
        "value": value,
        "label": _format_label(cat, value),
        "filter_text": f"Only answers that {_lower_first(_format_label(cat, value))}",
        "name": _item_name(),
        "bonus": _base_bonus(tier_name, floor),
        "rarity": TIER_RULES[tier_name]["label"],
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
        attempts = 12 if "{value}" in cat["label"] else 4
        seen = set()
        for _ in range(attempts):
            value = _pick_value(cat_id, cat, conn)
            if value is None or value in seen:
                continue
            seen.add(value)
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
        attempts = 12 if "{value}" in cat["label"] else 4
        seen = set()
        for _ in range(attempts):
            value = _pick_value(cat_id, cat, conn)
            if value is None or value in seen:
                continue
            seen.add(value)
            players = cat["players"](conn, value)
            base_count = len(players)
            projected_count = len(players & allowed_now)
            if projected_count >= 6:
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
    plan = REWARD_PLANS[3 if len(current_items) >= 3 else len(current_items)]
    rewards = []
    used_keys = set()
    for desired_tier in plan[:count]:
        reward = None
        for tier_name in _fallback_tiers(desired_tier):
            for projected_count, base_count, cat, value in _get_item_candidates(conn, current_items, tier_name):
                key = _candidate_key(cat["id"], value)
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
            key = _candidate_key(cat["id"], value)
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
    answer_key = " ".join((answer or "").strip().lower().split())
    lookup = {" ".join(name.lower().split()): name for name in valid_players}
    return lookup.get(answer_key)


def _enemy_payload(floor, theme):
    is_boss = bool(theme.get("boss"))
    return {
        "name": theme["enemy"],
        "floor": floor,
        "hp": 7 + floor * 2 if not is_boss else 16 + floor * 3,
        "damage": 3 + floor if not is_boss else 6 + floor,
        "glyph": "E",
        "is_boss": is_boss,
        "phase_goal": theme.get("phase_goal", 1),
    }


def get_encounter(conn, floor, current_items, used_questions=None):
    used_questions = set(used_questions or [])
    allowed_players = _allowed_players(conn, current_items)
    theme = FLOOR_THEMES.get(floor, FLOOR_THEMES[6])
    best = None
    cat_ids = list(theme["categories"]) + [cat_id for cat_id in QUESTION_CATEGORY_IDS if cat_id not in theme["categories"]]
    for cat_id in cat_ids:
        cat = cc._CAT_BY_ID[cat_id]
        attempts = 12 if "{value}" in cat["label"] else 4
        seen = set()
        for _ in range(attempts):
            value = _pick_value(cat_id, cat, conn)
            key = _candidate_key(cat_id, value)
            if value is None or value in seen or key in used_questions:
                continue
            seen.add(value)
            valid_players = cat["players"](conn, value) & allowed_players
            payload = {
                "id": cat_id,
                "value": value,
                "label": _format_label(cat, value),
                "prompt": _question_prompt(_format_label(cat, value)),
                "valid_count": len(valid_players),
                "key": key,
            }
            if len(valid_players) >= 6:
                return {"enemy": _enemy_payload(floor, theme), "question": payload, "theme": theme}
            if len(valid_players) >= 2 and best is None:
                best = {"enemy": _enemy_payload(floor, theme), "question": payload, "theme": theme}
    return best


def check_answer(conn, question, current_items, answer):
    question_players = _players_for_link(conn, question)
    allowed_players = _allowed_players(conn, current_items)
    valid_players = question_players & allowed_players
    canonical = _canonicalize_answer(answer, question_players | allowed_players)
    if canonical and canonical in valid_players:
        return {"correct": True, "player": canonical, "filter_failures": [], "question_match": True}
    if canonical and canonical in question_players:
        failures = [item["label"] for item in current_items if canonical not in _players_for_link(conn, item)]
        return {"correct": False, "player": canonical, "filter_failures": failures, "question_match": True}
    return {"correct": False, "player": canonical, "filter_failures": [], "question_match": False}


def search_answers(conn, query, current_items, question=None, limit=8):
    query = " ".join((query or "").strip().lower().split())
    if not query:
        return []
    pool = _all_players(conn)
    starts = []
    contains = []
    for player in sorted(pool):
        key = " ".join(player.lower().split())
        if key.startswith(query):
            starts.append(player)
        elif query in key:
            contains.append(player)
        if len(starts) + len(contains) >= limit * 2:
            break
    return (starts + contains)[:limit]
