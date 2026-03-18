(function () {
  var app = document.getElementById("app");
  var apiPrefix = app.dataset.apiPrefix || "/api/dungeon";
  var gameTitle = app.dataset.title || "Dungeon Adventure";
  var sportLabel = app.dataset.sport || "NFL";

  var CHARACTERS = [
    {
      id: "analyst", name: "The Analyst", subtitle: "Balanced Scholar",
      sigil: "@", hp: 36, attack: 6, bonusMult: 1.0, healPerKill: 4,
      color: "#6c9dbd",
      desc: "Steady and methodical. No weaknesses, no special powers — pure trivia mastery.",
    },
    {
      id: "blitzer", name: "The Blitzer", subtitle: "Glass Cannon",
      sigil: "!", hp: 24, attack: 10, bonusMult: 1.0, healPerKill: 2,
      color: "#e02035",
      desc: "Hits like a freight train but can't take punishment. Strike first, strike hard.",
    },
    {
      id: "veteran", name: "The Veteran", subtitle: "Iron Wall",
      sigil: "#", hp: 52, attack: 4, bonusMult: 1.2, healPerKill: 8,
      color: "#d8a84f",
      desc: "Built to last. Relics hit harder and healing is generous — patience is your weapon.",
    },
    {
      id: "wildcard", name: "The Wildcard", subtitle: "Relic Hunter",
      sigil: "~", hp: 30, attack: 5, bonusMult: 1.8, healPerKill: 3,
      color: "#9d6cdd",
      desc: "Relic-obsessed. Every item amplifies dramatically — stack deep for pure chaos.",
    },
  ];

  // Floor scene art: 7 rows each, placed at rows 6-12 in the ASCII grid
  var FLOOR_SCENES = {
    1: [
      "  .~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.",
      "  |  ~ ~ ~ ~ ~ ~ ~ ~ ~ ~  MOSSLIGHT APPROACH  ~ ~ ~ ~ ~ ~ ~ ~ ~ ~               |",
      "  |     |   |  ~~~  |   |  ~~~  crumbling walls  ~~~  |   |  ~~~  |   |         |",
      "  |    _|___|_     _|___|_                            _|___|_     _|___|_        |",
      "  |   |  #  # |   |  #  # |    mossy ruins           |  #  # |   |  #  # |     |",
      "  |    ~  #  ~     ~  #  ~     ~ ~ ruins ~ ~          ~  #  ~     ~  #  ~       |",
      "  '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~'",
    ],
    2: [
      "  .~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.",
      "  |  [ledger] [codex]  [index] [scroll]  [record] [tome]  [draft]  [list]        |",
      "  |  ======== =======  ======= ========  ======== ======  =======  ========      |",
      "  |      brass shelves lined with centuries of data and forgotten stats           |",
      "  |                                                                                |",
      "  |      every player ever drafted, signed, or benched — carved in brass          |",
      "  '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~'",
    ],
    3: [
      "  .~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.",
      "  |    *          *          *               *          *          *              |",
      "  |   /|\\        /|\\        /|\\             /|\\        /|\\        /|\\             |",
      "  |    |          |          |               |          |          |              |",
      "  |  ~~~~~~~~~~~~~~~~~~~~ EMBER GALLERY ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~         |",
      "  |    the flames reward season totals and fantasy point monsters                 |",
      "  '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~'",
    ],
    4: [
      "  .~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.",
      "  |                                                                                |",
      "  |   ~   ~   ~   ~   ~   ~   ~  water level  ~   ~   ~   ~   ~   ~   ~          |",
      "  |  ~~~     ~~~     ~~~     ~~~     ~~~     ~~~     ~~~     ~~~     ~~~           |",
      "  | ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~ ~          |",
      "  |   FLOODED RELIQUARY — ankle deep in history — skill-position answers          |",
      "  '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~'",
    ],
    5: [
      "  .~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.",
      "  |   /  /  /  /  /  /  /  /  /  /  /  /  /  /  /  /  /  /  /  /  /  /  /     |",
      "  |    \\  \\  \\  \\  \\  \\  \\  \\  \\  \\  \\  \\  \\  \\  \\  \\  \\  \\  \\  \\  \\  \\  \\    |",
      "  |    *               *            *              *               *              |",
      "  |  STORM BASTION — demands sharper recall and defense-heavy answers             |",
      "  |            lightning    thunder    wind    sacks    interceptions              |",
      "  '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~'",
    ],
    6: [
      "  .~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~.",
      "  |   ___________________________________________________________________________  |",
      "  |   |                         THRONE  ROOM                                   |  |",
      "  |   |   (torches)  /|\\                  /####\\             (torches)  /|\\    |  |",
      "  |   |              |||               /##########\\                      |||    |  |",
      "  |   |___________________________________________________________________________  |",
      "  '~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~'",
    ],
  };

  var state = {
    maxHp: 36, hp: 36, baseAttack: 6, bonusMult: 1.0, healPerKill: 4,
    selectedChar: null, infiniteMode: false,
    usedPlayerNames: new Set(),
    floor: 1, kills: 0, items: [],
    enemy: null, question: null, theme: null, usedQuestions: [],
    bossPhase: 1, gameOver: false,
    suggestions: [], activeSuggestion: -1,
    heroFrame: 0, mapOpen: false,
  };

  var els = {
    asciiView:       document.getElementById("ascii-view"),
    mapView:         document.getElementById("map-view"),
    mapOverlay:      document.getElementById("map-overlay"),
    mapToggleBtn:    document.getElementById("map-toggle-btn"),
    mapCloseBtn:     document.getElementById("map-close-btn"),
    floorLabel:      document.getElementById("floor-label"),
    themeName:       document.getElementById("theme-name"),
    themePrompt:     document.getElementById("theme-prompt"),
    enemyName:       document.getElementById("enemy-name"),
    enemyHp:         document.getElementById("enemy-hp"),
    enemyDamage:     document.getElementById("enemy-damage"),
    bossWrap:        document.getElementById("boss-wrap"),
    bossPhaseLabel:  document.getElementById("boss-phase-label"),
    questionPrompt:  document.getElementById("question-prompt"),
    questionDetail:  document.getElementById("question-detail"),
    answerForm:      document.getElementById("answer-form"),
    answerInput:     document.getElementById("answer-input"),
    searchResults:   document.getElementById("search-results"),
    battleMessage:   document.getElementById("battle-message"),
    hpLabel:         document.getElementById("hp-label"),
    killsLabel:      document.getElementById("kills-label"),
    attackLabel:     document.getElementById("attack-label"),
    baseLabel:       document.getElementById("base-label"),
    bonusLabel:      document.getElementById("bonus-label"),
    heroClassLabel:  document.getElementById("hero-class-label"),
    inventoryList:   document.getElementById("inventory-list"),
    filterCount:     document.getElementById("filter-count"),
    logList:         document.getElementById("log-list"),
    rewardPanel:     document.getElementById("reward-panel"),
    rewardOptions:   document.getElementById("reward-options"),
    rewardTitle:     document.getElementById("reward-title"),
    skipRewardBtn:   document.getElementById("skip-reward-btn"),
    restartBtn:      document.getElementById("restart-btn"),
    charCreatePanel: document.getElementById("char-create-panel"),
    charOptions:     document.getElementById("char-options"),
    beginBtn:        document.getElementById("begin-btn"),
    modeNormalBtn:   document.getElementById("mode-normal-btn"),
    modeInfiniteBtn: document.getElementById("mode-infinite-btn"),
    winPanel:        document.getElementById("win-panel"),
    winAscii:        document.getElementById("win-ascii"),
    winStats:        document.getElementById("win-stats"),
    winInfiniteBtn:  document.getElementById("win-infinite-btn"),
    winRestartBtn:   document.getElementById("win-restart-btn"),
    deathPanel:      document.getElementById("death-panel"),
    deathAscii:      document.getElementById("death-ascii"),
    deathStats:      document.getElementById("death-stats"),
    deathRestartBtn: document.getElementById("death-restart-btn"),
  };

  var searchAbort = null;

  // ── Utility ──────────────────────────────────────────────────────────────

  function totalBonus() {
    var raw = state.items.reduce(function (s, item) { return s + item.bonus; }, 0);
    return Math.round(raw * state.bonusMult);
  }

  function totalAttack() { return state.baseAttack + totalBonus(); }

  function addLog(msg) {
    var row = document.createElement("div");
    row.className = "log-entry";
    row.textContent = msg;
    els.logList.prepend(row);
  }

  function hideSearch() {
    state.suggestions = [];
    state.activeSuggestion = -1;
    els.searchResults.classList.add("hidden");
    els.searchResults.innerHTML = "";
  }

  // ── Search ───────────────────────────────────────────────────────────────

  function renderSearch() {
    els.searchResults.innerHTML = "";
    if (!state.suggestions.length) { els.searchResults.classList.add("hidden"); return; }
    state.suggestions.forEach(function (name, idx) {
      var row = document.createElement("div");
      var used = state.infiniteMode && state.usedPlayerNames.has(name);
      row.className = "search-item" + (idx === state.activeSuggestion ? " active" : "") + (used ? " used-player" : "");
      row.textContent = name + (used ? "  [used]" : "");
      row.addEventListener("mousedown", function (e) {
        e.preventDefault();
        els.answerInput.value = name;
        hideSearch();
      });
      els.searchResults.appendChild(row);
    });
    els.searchResults.classList.remove("hidden");
  }

  async function fetchSuggestions(query) {
    if (!query.trim()) { hideSearch(); return; }
    if (searchAbort) { searchAbort.abort(); }
    searchAbort = new AbortController();
    try {
      var res = await fetch(apiPrefix + "/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query, items: state.items, question: state.question }),
        signal: searchAbort.signal,
      });
      if (!res.ok) { hideSearch(); return; }
      var data = await res.json();
      state.suggestions = data.results || [];
      state.activeSuggestion = -1;
      renderSearch();
    } catch (err) {
      if (err.name !== "AbortError") { hideSearch(); }
    }
  }

  // ── Rendering ────────────────────────────────────────────────────────────

  function renderStats() {
    els.floorLabel.textContent = "Floor " + state.floor + (state.infiniteMode ? " ∞" : "");
    els.themeName.textContent = state.theme ? state.theme.name : "Entry Hall";
    els.themePrompt.textContent = state.theme ? state.theme.prompt : "Choose a starter relic to enter the run.";
    els.hpLabel.textContent = Math.max(0, state.hp) + " / " + state.maxHp;
    els.killsLabel.textContent = String(state.kills);
    els.attackLabel.textContent = "ATK " + totalAttack();
    els.baseLabel.textContent = String(state.baseAttack);
    els.bonusLabel.textContent = String(totalBonus());
    if (state.selectedChar) {
      els.heroClassLabel.textContent = state.selectedChar.name;
    }
    if (state.enemy && state.enemy.isBoss) {
      els.bossWrap.classList.remove("hidden");
      els.bossPhaseLabel.textContent = state.bossPhase + " / " + state.enemy.phaseGoal;
    } else {
      els.bossWrap.classList.add("hidden");
    }
    els.mapToggleBtn.textContent = state.mapOpen ? "Hide Map" : "Open Map";
  }

  function renderEnemy() {
    if (!state.enemy) {
      els.enemyName.textContent = "Awaiting Crawl";
      els.enemyHp.textContent = "0 / 0";
      els.enemyDamage.textContent = "0";
      return;
    }
    els.enemyName.textContent = state.enemy.name;
    els.enemyHp.textContent = state.enemy.hp + " / " + state.enemy.maxHp;
    els.enemyDamage.textContent = String(state.enemy.damage);
  }

  function renderQuestion() {
    if (!state.question) {
      els.questionPrompt.textContent = "Pick a relic to begin your run.";
      els.questionDetail.textContent = "Your answer satisfies both the encounter prompt and every active relic filter.";
      return;
    }
    els.questionPrompt.textContent = state.question.prompt;
    els.questionDetail.textContent = state.question.valid_count + " valid answers solve this prompt with your current relic build.";
  }

  function renderInventory() {
    els.inventoryList.innerHTML = "";
    els.filterCount.textContent = String(state.items.length);
    if (!state.items.length) {
      var empty = document.createElement("div");
      empty.className = "inventory-card";
      empty.setAttribute("data-tooltip", "No relics equipped. Skipping items keeps your answer pool broad but your damage modest.");
      empty.innerHTML = '<img class="inventory-icon" src="/static/img/dungeon_icons/relic.svg" alt="Empty">';
      els.inventoryList.appendChild(empty);
      return;
    }
    state.items.forEach(function (item) {
      var card = document.createElement("div");
      card.className = "inventory-card";
      card.setAttribute("data-tooltip", item.name + " - " + item.filter_text + " | " + item.rarity + " | +" + item.bonus + " ATK");
      card.innerHTML = '<img class="inventory-icon" src="' + item.icon + '" alt="' + item.name + '"><div class="inventory-info"></div>';
      els.inventoryList.appendChild(card);
    });
  }

  // ── ASCII: helpers ────────────────────────────────────────────────────────

  function place(grid, x, y, text) {
    if (y < 0 || y >= grid.length) { return; }
    for (var i = 0; i < text.length; i++) {
      var px = x + i;
      if (px >= 0 && px < grid[y].length) { grid[y][px] = text[i]; }
    }
  }

  function hpBar(current, max, width) {
    var filled = max > 0 ? Math.max(0, Math.min(width, Math.round((current / max) * width))) : 0;
    return "[" + "#".repeat(filled) + ".".repeat(width - filled) + "]";
  }

  // ── ASCII: battle scene ───────────────────────────────────────────────────

  function buildFightAscii() {
    var W = 96, H = 28;
    var grid = Array.from({ length: H }, function () { return Array(W).fill(" "); });

    // Border
    for (var x = 0; x < W; x++) {
      grid[0][x]   = (x === 0 || x === W-1) ? "+" : "-";
      grid[H-1][x] = (x === 0 || x === W-1) ? "+" : "-";
    }
    for (var y = 1; y < H-1; y++) { grid[y][0] = "|"; grid[y][W-1] = "|"; }

    // Row 1 — title + floor/status
    var status = (state.enemy && state.enemy.isBoss)
      ? "BOSS " + state.bossPhase + "/" + state.enemy.phaseGoal
      : (state.gameOver ? "FALLEN" : "BATTLE");
    var modeTag = state.infiniteMode ? " [INF]" : "";
    place(grid, 2, 1, gameTitle.toUpperCase() + " :: " + sportLabel + modeTag);
    var floorText = "FLOOR " + state.floor + "  " + status;
    place(grid, W - 2 - floorText.length, 1, floorText);

    // Row 2 — hero HP (left) + enemy HP (right)
    var heroBar = hpBar(Math.max(0, state.hp), state.maxHp, 18);
    place(grid, 2, 2, " HERO " + heroBar + " " + Math.max(0, state.hp) + "/" + state.maxHp);
    if (state.enemy) {
      var eBar = hpBar(state.enemy.hp, state.enemy.maxHp, 18);
      var eHpStr = " ENEMY " + eBar + " " + state.enemy.hp + "/" + state.enemy.maxHp;
      place(grid, W - 2 - eHpStr.length, 2, eHpStr);
    }

    // Row 3 — theme + ATK/kills/items
    var theme = state.theme ? state.theme.name : "Entry Hall";
    place(grid, 2, 3, "THEME " + theme);
    var statsStr = "ATK " + totalAttack() + " (" + state.baseAttack + "+" + totalBonus() + ")  KILLS " + state.kills + "  ITEMS " + state.items.length;
    place(grid, W - 2 - statsStr.length, 3, statsStr);

    // Row 4 — divider
    for (var xi = 1; xi < W-1; xi++) { grid[4][xi] = "-"; }
    grid[4][0] = "|"; grid[4][W-1] = "|";

    // Rows 5-13 — floor scene
    drawFloorScene(grid);

    // Row 14 — divider
    for (var xi2 = 1; xi2 < W-1; xi2++) { grid[14][xi2] = "-"; }
    grid[14][0] = "|"; grid[14][W-1] = "|";

    // Rows 15-21 — VS battle field: hero left, VS center, enemy right
    var heroGlyph  = state.gameOver ? "X" : (state.selectedChar ? state.selectedChar.sigil : "@");
    var enemyGlyph = state.enemy ? (state.enemy.isBoss ? "&" : "E") : "?";
    var heroName   = state.selectedChar ? state.selectedChar.name.substring(0, 18).toUpperCase() : "HERO";
    var enemyName  = state.enemy ? state.enemy.name.substring(0, 18).toUpperCase() : "AWAITING";
    var bob        = state.heroFrame % 2;

    // Hero box: left side cols 4-29
    place(grid, 4,  15, ".-- " + heroName + " ---.");
    place(grid, 4,  16, "|");
    place(grid, 4,  17, "|    " + heroGlyph + "    |");
    place(grid, 4,  18, "|   " + (bob ? "/|\\" : " | ") + "   |");
    place(grid, 4,  19, "|    " + (bob ? "|" : "|") + "    |");
    place(grid, 4,  20, "'---" + (state.gameOver ? " FALLEN " : "--------") + "---'");

    // VS — center col 44
    place(grid, 44, 16, "\\");
    place(grid, 44, 17, " V");
    place(grid, 44, 18, " S");
    place(grid, 44, 19, "/");

    // Enemy box: right side cols 62-90
    place(grid, 62, 15, ".-- " + enemyName + " ---.");
    place(grid, 62, 16, "|");
    place(grid, 62, 17, "|    " + enemyGlyph + "    |");
    place(grid, 62, 18, "|   " + (bob ? "/|\\" : " | ") + "   |");
    place(grid, 62, 19, "|    |    |");
    place(grid, 62, 20, "'----------'");

    // Row 22 — pool + foe info
    var pool    = state.question ? String(state.question.valid_count) : "0";
    var foeName = state.enemy ? state.enemy.name : "none";
    place(grid, 2, 22, "pool: " + pool + " valid  foe: " + foeName + "  dmg: " + (state.enemy ? state.enemy.damage : 0) + " per miss");

    // Row 23 — infinite mode used count
    if (state.infiniteMode) {
      place(grid, 2, 23, "players used this run: " + state.usedPlayerNames.size + "  (each name can only be used once)");
    }

    return grid.map(function (row) { return row.join(""); }).join("\n");
  }

  function drawFloorScene(grid) {
    var floor = Math.min(Math.max(1, ((state.floor - 1) % 6) + 1), 6);
    var scene = FLOOR_SCENES[floor] || FLOOR_SCENES[6];
    scene.forEach(function (line, i) { place(grid, 1, 6 + i, line); });
  }

  // ── ASCII: map ────────────────────────────────────────────────────────────

  function buildMapAscii() {
    var W = 96, H = 28;
    var grid = Array.from({ length: H }, function () { return Array(W).fill(" "); });

    for (var x = 0; x < W; x++) {
      grid[0][x]   = (x === 0 || x === W-1) ? "+" : "-";
      grid[H-1][x] = (x === 0 || x === W-1) ? "+" : "-";
    }
    for (var y = 1; y < H-1; y++) { grid[y][0] = "|"; grid[y][W-1] = "|"; }

    place(grid, 2, 1, gameTitle.toUpperCase() + " MAP :: " + sportLabel);
    place(grid, 68, 1, "CURRENT FLOOR " + state.floor);
    place(grid, 8, 5,  "                         .------------------------.                         ");
    place(grid, 8, 6,  "                   .-----'                        '-----.                    ");
    place(grid, 8, 7,  "               .---'                                  '---.                ");
    place(grid, 8, 8,  "             .'                                            '.              ");
    place(grid, 8, 9,  "            /                                                \\             ");
    place(grid, 8, 10, "           /                                                  \\            ");
    place(grid, 8, 11, "          |                                                    |            ");
    place(grid, 8, 12, "          |                                                    |            ");
    place(grid, 8, 13, "          |                                                    |            ");
    place(grid, 8, 14, "          |                                                    |            ");
    place(grid, 8, 15, "          |                                                    |            ");
    place(grid, 8, 16, "           \\                                                  /            ");
    place(grid, 8, 17, "            \\                                                /             ");
    place(grid, 8, 18, "             '.                                            .'              ");
    place(grid, 8, 19, "               '---.                                  .---'                ");
    place(grid, 8, 20, "                   '-----.                      .-----'                    ");
    place(grid, 8, 21, "                         '----------------------'                         ");

    var checkpoints = [
      { x: 10, y: 14, label: "1 ENTRY" },
      { x: 24, y: 8,  label: "2 ARCHIVE" },
      { x: 43, y: 6,  label: "3 EMBER" },
      { x: 63, y: 9,  label: "4 FLOOD" },
      { x: 76, y: 16, label: "5 STORM" },
      { x: 47, y: 21, label: "6 THRONE" },
    ];

    checkpoints.forEach(function (pt, i) {
      var floorNum = i + 1;
      var marker = floorNum < state.floor ? "x" : (floorNum === state.floor ? "@" : "o");
      place(grid, pt.x, pt.y, marker);
      place(grid, pt.x + 2, pt.y, pt.label);
    });

    if (state.infiniteMode && state.floor > 6) {
      place(grid, 35, 13, "INFINITE LOOP — FLOOR " + state.floor);
    }

    place(grid, 8, 23, "legend: @ current   x cleared   o upcoming");
    place(grid, 8, 24, "victories: " + state.kills + "   relics: " + state.items.length + "   boss phase: " + state.bossPhase + "   mode: " + (state.infiniteMode ? "INFINITE" : "NORMAL"));
    place(grid, 8, 25, "close map to return to the current fight screen");

    return grid.map(function (row) { return row.join(""); }).join("\n");
  }

  // ── Render all ────────────────────────────────────────────────────────────

  function renderAscii() {
    els.asciiView.textContent = buildFightAscii();
    els.mapView.textContent   = buildMapAscii();
  }

  function render() {
    renderStats();
    renderEnemy();
    renderQuestion();
    renderInventory();
    renderAscii();
    els.mapOverlay.classList.toggle("hidden", !state.mapOpen);
  }

  // ── API helpers ───────────────────────────────────────────────────────────

  async function postJson(url, body) {
    var res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      var d = await res.json().catch(function () { return {}; });
      throw new Error(d.error || "Request failed");
    }
    return res.json();
  }

  // ── Rewards ───────────────────────────────────────────────────────────────

  async function showRewards(title) {
    var data = await postJson(apiPrefix + "/rewards", { floor: state.floor, items: state.items });
    els.rewardTitle.textContent = title;
    els.rewardOptions.innerHTML = "";
    data.rewards.forEach(function (reward) {
      var card = document.createElement("div");
      card.className = "reward-card";
      card.innerHTML =
        '<div class="reward-head"><img class="reward-icon" src="' + reward.icon + '" alt="' + reward.name + '"><strong>' + reward.name + '</strong></div>' +
        '<div>' + reward.filter_text + '</div>' +
        '<div class="muted">' + reward.rarity + ' relic, +' + reward.bonus + ' ATK, pool ' + reward.base_count + ', projected ' + reward.projected_count + '</div>';
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = "Take Item";
      btn.addEventListener("click", async function () {
        state.items.push(reward);
        els.rewardPanel.classList.add("hidden");
        addLog("You take " + reward.name + ".");
        await nextEncounter();
      });
      card.appendChild(btn);
      els.rewardOptions.appendChild(card);
    });
    els.rewardPanel.classList.remove("hidden");
  }

  // ── Encounter / question ──────────────────────────────────────────────────

  async function nextEncounter() {
    state.usedQuestions = [];
    var data = await postJson(apiPrefix + "/encounter", {
      floor: state.floor,
      items: state.items,
      used_questions: state.usedQuestions,
    });
    state.theme  = data.theme;
    state.enemy  = {
      name: data.enemy.name,
      hp: data.enemy.hp, maxHp: data.enemy.hp,
      damage: data.enemy.damage,
      isBoss: Boolean(data.enemy.is_boss),
      phaseGoal: data.enemy.phase_goal || 1,
    };
    state.question  = data.question;
    state.bossPhase = 1;
    state.mapOpen   = false;
    if (data.question && data.question.key) { state.usedQuestions.push(data.question.key); }
    els.answerInput.value = "";
    hideSearch();
    els.answerInput.focus();
    els.battleMessage.textContent = state.enemy.isBoss
      ? "Boss encounter: survive multiple prompts and phases before the room breaks."
      : "Battle screen ready. Use the map button to check route progress.";
    render();
  }

  async function refreshQuestion() {
    var data = await postJson(apiPrefix + "/encounter", {
      floor: state.floor,
      items: state.items,
      used_questions: state.usedQuestions,
    });
    state.theme    = data.theme;
    state.question = data.question;
    if (data.question && data.question.key) { state.usedQuestions.push(data.question.key); }
    hideSearch();
    render();
  }

  // ── Win / death ───────────────────────────────────────────────────────────

  function buildWinAscii() {
    var lines = [
      "  +------------------------------------------------------------------+",
      "  |  * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *  |",
      "  |                                                                  |",
      "  |   ____   _   _   _   ____   ___   ___   _   _                   |",
      "  |  |    \\ | | | | | | |    \\ / __| | __| | \\ | |                  |",
      "  |  | |  | | | | | | | | || || |  _ | _|  |  \\| |                  |",
      "  |  |____/ |_| |_| |_| |____/ \\___| |___| |_|\\__|                  |",
      "  |                                                                  |",
      "  |   ____   _      ____   ___   ____   ____   ____                 |",
      "  |  /  __| | |    | ___| / _ \\ |  _ \\ | ___| |  _ \\               |",
      "  | | |     | |    | _|  | |_| || |_) || _|   | | | |              |",
      "  |  \\____| |_|___ |___| |_| |_||____/ |___| |_| |_|               |",
      "  |                                                                  |",
      "  |  * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * *  |",
      "  +------------------------------------------------------------------+",
    ];
    return lines.join("\n");
  }

  function buildDeathAscii() {
    var lines = [
      "  +------------------------------------------------------------------+",
      "  |  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  |",
      "  |                                                                  |",
      "  |   __  __  ____  _   _   ____   _   _   ____   _   _   ____      |",
      "  |  |  \\/  ||    || | | | |    \\ | | | | |  _ \\ | \\ | | /  __|     |",
      "  |  | |\\/| || |  || | | | | || | | | | | | |_) ||  \\| ||  |_       |",
      "  |  |_|  |_||____||_| |_| |____/  \\___/  |____/ |_|\\__| \\____|     |",
      "  |                                                                  |",
      "  |               the dungeon claims another soul                   |",
      "  |                                                                  |",
      "  |  - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -  |",
      "  +------------------------------------------------------------------+",
    ];
    return lines.join("\n");
  }

  function showWinScreen() {
    state.gameOver = true;
    render();
    els.winAscii.textContent = buildWinAscii();
    els.winStats.textContent =
      "Floors cleared: 6  ·  Enemies defeated: " + state.kills +
      "  ·  Relics collected: " + state.items.length +
      "  ·  Final ATK: " + totalAttack() +
      "  ·  Class: " + (state.selectedChar ? state.selectedChar.name : "Unknown");
    els.winPanel.classList.remove("hidden");
    addLog("You escape the final chamber. Dungeon cleared!");
  }

  function showDeathScreen() {
    els.deathAscii.textContent = buildDeathAscii();
    els.deathStats.textContent =
      "Reached floor " + state.floor +
      "  ·  Enemies defeated: " + state.kills +
      "  ·  Relics collected: " + state.items.length +
      "  ·  ATK at death: " + totalAttack() +
      (state.infiniteMode ? "  ·  Players used: " + state.usedPlayerNames.size : "") +
      "  ·  Class: " + (state.selectedChar ? state.selectedChar.name : "Unknown");
    els.deathPanel.classList.remove("hidden");
    addLog("Your run ends in the dungeon.");
  }

  function endRun(message) {
    state.gameOver   = true;
    state.question   = null;
    els.battleMessage.textContent = message;
    render();
    showDeathScreen();
  }

  // ── Victory / progression ─────────────────────────────────────────────────

  async function handleVictory() {
    state.kills += 1;
    state.hp = Math.min(state.maxHp, state.hp + state.healPerKill);
    addLog("The " + state.enemy.name + " falls. You recover " + state.healPerKill + " HP.");
    state.floor += 1;

    // Normal mode: win after 6 floors
    if (!state.infiniteMode && state.floor > 6) {
      showWinScreen();
      return;
    }

    render();
    var rewardTitle = (state.floor === 6 && !state.infiniteMode) ? "Boss Prep Item"
      : ("Floor " + state.floor + " Item" + (state.infiniteMode && state.floor > 6 ? " [Infinite]" : ""));
    await showRewards(rewardTitle);
  }

  async function handleBossPhaseBreak() {
    if (state.bossPhase >= state.enemy.phaseGoal) {
      await handleVictory();
      return;
    }
    state.bossPhase      += 1;
    state.enemy.hp        = state.enemy.maxHp;
    state.enemy.damage   += 1;
    addLog("Boss phase " + (state.bossPhase - 1) + " breaks. The enemy resets.");
    els.battleMessage.textContent = "Boss phase " + (state.bossPhase - 1) + " is down. New prompt incoming.";
    await refreshQuestion();
  }

  // ── Answer handling ───────────────────────────────────────────────────────

  async function handleAnswer(event) {
    event.preventDefault();
    if (state.gameOver || !state.question || !state.enemy) { return; }
    var answer = els.answerInput.value.trim();
    if (!answer) { return; }

    try {
      var result = await postJson(apiPrefix + "/answer", {
        question: state.question,
        items: state.items,
        answer: answer,
      });

      if (result.correct) {
        // Infinite mode: block duplicate players
        if (state.infiniteMode && state.usedPlayerNames.has(result.player)) {
          state.hp -= state.enemy.damage;
          els.battleMessage.textContent = result.player + " already used this run — each player can only be named once. You take " + state.enemy.damage + " damage.";
          addLog("Duplicate! Enemy hits for " + state.enemy.damage + ".");
          if (state.hp <= 0) { endRun("Your run ends — no more fresh answers."); }
          else { await refreshQuestion(); }
        } else {
          // Valid hit
          if (state.infiniteMode) { state.usedPlayerNames.add(result.player); }
          var damage = totalAttack();
          state.enemy.hp = Math.max(0, state.enemy.hp - damage);
          els.battleMessage.textContent = result.player + " fits every rule. You deal " + damage + " damage.";
          addLog(result.player + " clears the prompt for " + damage + " damage.");
          if (state.enemy.hp <= 0) {
            if (state.enemy.isBoss) { await handleBossPhaseBreak(); }
            else                    { await handleVictory(); }
            els.answerInput.value = "";
            return;
          }
          await refreshQuestion();
        }
      } else {
        state.hp -= state.enemy.damage;
        if (result.question_match && result.filter_failures.length) {
          els.battleMessage.textContent = result.player + " fits the prompt but breaks: " + result.filter_failures.join(", ") + ". You take " + state.enemy.damage + ".";
        } else {
          els.battleMessage.textContent = "That answer misses the prompt. You take " + state.enemy.damage + ".";
        }
        addLog("Enemy hits for " + state.enemy.damage + ".");
        if (state.hp <= 0) {
          endRun("Your run ends in the dungeon. Restart to try another build.");
          return;
        }
        await refreshQuestion();
      }
    } catch (err) {
      els.battleMessage.textContent = err.message;
    }

    els.answerInput.value = "";
    hideSearch();
    render();
  }

  // ── Start run ─────────────────────────────────────────────────────────────

  async function startRun(charObj, infiniteMode) {
    var ch = charObj || CHARACTERS[0];
    state.selectedChar    = ch;
    state.infiniteMode    = Boolean(infiniteMode);
    state.usedPlayerNames = new Set();
    state.maxHp           = ch.hp;
    state.hp              = ch.hp;
    state.baseAttack      = ch.attack;
    state.bonusMult       = ch.bonusMult;
    state.healPerKill     = ch.healPerKill;
    state.floor           = 1;
    state.kills           = 0;
    state.items           = [];
    state.enemy           = null;
    state.question        = null;
    state.theme           = null;
    state.usedQuestions   = [];
    state.bossPhase       = 1;
    state.gameOver        = false;
    state.heroFrame       = 0;
    state.mapOpen         = false;

    if (els.charCreatePanel) { els.charCreatePanel.classList.add("hidden"); }
    if (els.winPanel)        { els.winPanel.classList.add("hidden"); }
    if (els.deathPanel)      { els.deathPanel.classList.add("hidden"); }

    els.logList.innerHTML = "";
    els.battleMessage.textContent = "Choose one starter relic to enter the dungeon.";
    hideSearch();
    render();
    await showRewards("Starter Item");
  }

  // ── Character select ──────────────────────────────────────────────────────

  function renderCharSelect() {
    if (!els.charCreatePanel) { return; }
    state.selectedChar = null;
    if (els.beginBtn) { els.beginBtn.disabled = true; }
    if (els.charOptions) { els.charOptions.innerHTML = ""; }

    // Mode buttons sync
    var iMode = state.infiniteMode;
    if (els.modeNormalBtn)   { els.modeNormalBtn.classList.toggle("active", !iMode); }
    if (els.modeInfiniteBtn) { els.modeInfiniteBtn.classList.toggle("active",  iMode); }

    CHARACTERS.forEach(function (ch) {
      var card = document.createElement("div");
      card.className = "char-card";
      card.innerHTML =
        '<div class="char-card-top">' +
          '<div>' +
            '<div class="char-name">' + ch.name + '</div>' +
            '<div class="char-subtitle">' + ch.subtitle + '</div>' +
          '</div>' +
          '<div class="char-sigil" style="color:' + ch.color + ';border-color:' + ch.color + '44">' + ch.sigil + '</div>' +
        '</div>' +
        '<div class="char-stats">' +
          '<div class="char-stat"><span class="stat-label">HP</span><span class="stat-val">' + ch.hp + '</span></div>' +
          '<div class="char-stat"><span class="stat-label">ATK</span><span class="stat-val">' + ch.attack + '</span></div>' +
          '<div class="char-stat"><span class="stat-label">Relic ×</span><span class="stat-val">' + ch.bonusMult.toFixed(1) + '</span></div>' +
          '<div class="char-stat"><span class="stat-label">Heal/Kill</span><span class="stat-val">+' + ch.healPerKill + '</span></div>' +
        '</div>' +
        '<p class="char-desc">' + ch.desc + '</p>';
      card.addEventListener("click", function () {
        document.querySelectorAll(".char-card").forEach(function (c) { c.classList.remove("selected"); });
        card.classList.add("selected");
        state.selectedChar = ch;
        if (els.beginBtn) { els.beginBtn.disabled = false; }
      });
      if (els.charOptions) { els.charOptions.appendChild(card); }
    });

    els.charCreatePanel.classList.remove("hidden");
  }

  // ── Event listeners ───────────────────────────────────────────────────────

  els.answerForm.addEventListener("submit", handleAnswer);

  els.answerInput.addEventListener("input", function () { fetchSuggestions(els.answerInput.value); });
  els.answerInput.addEventListener("keydown", function (e) {
    if (!state.suggestions.length) { return; }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      state.activeSuggestion = (state.activeSuggestion + 1) % state.suggestions.length;
      renderSearch();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      state.activeSuggestion = state.activeSuggestion <= 0 ? state.suggestions.length - 1 : state.activeSuggestion - 1;
      renderSearch();
    } else if (e.key === "Enter" && state.activeSuggestion >= 0) {
      e.preventDefault();
      els.answerInput.value = state.suggestions[state.activeSuggestion];
      hideSearch();
    } else if (e.key === "Escape") {
      hideSearch();
    }
  });

  document.addEventListener("click", function (e) {
    if (!els.searchResults.contains(e.target) && e.target !== els.answerInput) { hideSearch(); }
  });

  els.skipRewardBtn.addEventListener("click", async function () {
    els.rewardPanel.classList.add("hidden");
    addLog("You skip the item and keep your build unchanged.");
    await nextEncounter();
  });

  els.mapToggleBtn.addEventListener("click", function () { state.mapOpen = !state.mapOpen; render(); });
  els.mapCloseBtn.addEventListener("click",  function () { state.mapOpen = false; render(); });

  els.restartBtn.addEventListener("click", function () { renderCharSelect(); });

  if (els.beginBtn) {
    els.beginBtn.addEventListener("click", function () {
      if (!state.selectedChar) { return; }
      startRun(state.selectedChar, state.infiniteMode).catch(function (err) {
        els.battleMessage.textContent = err.message;
      });
    });
  }

  if (els.modeNormalBtn) {
    els.modeNormalBtn.addEventListener("click", function () {
      state.infiniteMode = false;
      els.modeNormalBtn.classList.add("active");
      els.modeInfiniteBtn.classList.remove("active");
    });
  }
  if (els.modeInfiniteBtn) {
    els.modeInfiniteBtn.addEventListener("click", function () {
      state.infiniteMode = true;
      els.modeInfiniteBtn.classList.add("active");
      els.modeNormalBtn.classList.remove("active");
    });
  }

  if (els.winRestartBtn) {
    els.winRestartBtn.addEventListener("click", function () {
      els.winPanel.classList.add("hidden");
      renderCharSelect();
    });
  }
  if (els.winInfiniteBtn) {
    els.winInfiniteBtn.addEventListener("click", function () {
      els.winPanel.classList.add("hidden");
      // Continue with the same character in infinite mode, keeping relics
      state.infiniteMode = true;
      state.floor        = 7;
      state.gameOver     = false;
      state.usedPlayerNames = new Set();
      // Reset enemy HP; keep items and stats
      render();
      nextEncounter().catch(function (err) { els.battleMessage.textContent = err.message; });
    });
  }

  if (els.deathRestartBtn) {
    els.deathRestartBtn.addEventListener("click", function () {
      els.deathPanel.classList.add("hidden");
      renderCharSelect();
    });
  }

  // ── Animation tick ────────────────────────────────────────────────────────

  setInterval(function () { state.heroFrame += 1; renderAscii(); }, 900);

  // ── Boot ──────────────────────────────────────────────────────────────────

  renderCharSelect();

})();
