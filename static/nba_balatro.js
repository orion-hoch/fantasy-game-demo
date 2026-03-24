(function () {
  'use strict';

  // NBA seasons are stored by start year (2023 = 2023-24). Display as end year.
  function nbaYear(s) { return s + 1; }

  // ── NBA Division lookup ─────────────────────────────────────────────
  const NBA_DIV = {
    BOS:'Atlantic',BRK:'Atlantic',BKN:'Atlantic',NYK:'Atlantic',PHI:'Atlantic',TOR:'Atlantic',NJN:'Atlantic',
    CHI:'Central',CLE:'Central',DET:'Central',IND:'Central',MIL:'Central',
    ATL:'Southeast',CHA:'Southeast',CHH:'Southeast',MIA:'Southeast',ORL:'Southeast',WAS:'Southeast',
    DEN:'Northwest',MIN:'Northwest',OKC:'Northwest',POR:'Northwest',UTA:'Northwest',SEA:'Northwest',
    GSW:'Pacific',LAC:'Pacific',LAL:'Pacific',PHX:'Pacific',PHO:'Pacific',SAC:'Pacific',
    DAL:'Southwest',HOU:'Southwest',MEM:'Southwest',NOP:'Southwest',SAS:'Southwest',NOH:'Southwest',VAN:'Southwest',NOK:'Southwest',
  };
  const NBA_DIV_LABEL = {
    'Atlantic':'ATL','Central':'CEN','Southeast':'SE',
    'Northwest':'NW','Pacific':'PAC','Southwest':'SW',
  };
  const NBA_DIV_CLASS = {
    'Atlantic':'div-atlantic','Central':'div-central','Southeast':'div-southeast',
    'Northwest':'div-northwest','Pacific':'div-pacific','Southwest':'div-southwest',
  };
  function getNbaDivInfo(team) {
    var div = team && NBA_DIV[team.toUpperCase()];
    if (!div) return null;
    return { label: NBA_DIV_LABEL[div] || div, cls: NBA_DIV_CLASS[div] || '' };
  }

  const NBA_DIVISIONS_LIST = [
    {id:'Atlantic',  label:'ATL', cls:'div-atlantic'},
    {id:'Central',   label:'CEN', cls:'div-central'},
    {id:'Southeast', label:'SE',  cls:'div-southeast'},
    {id:'Northwest', label:'NW',  cls:'div-northwest'},
    {id:'Pacific',   label:'PAC', cls:'div-pacific'},
    {id:'Southwest', label:'SW',  cls:'div-southwest'},
  ];

  // ── State ──────────────────────────────────────────────────────────
  var gameId = null;
  var currentSort = null; // 'pos', 'pts', or null
  var flippedCardIds = new Set();
  var gs = {
    hand: [],
    jokers: [],
    floor: 1,
    round: 1,
    fight: 1,
    mode: 'normal',
    bossEffect: null,
    levelName: 'Preseason',
    targetScore: 0,
    currentScore: 0,
    handsRemaining: 4,
    discardsRemaining: 3,
    status: 'idle',
    selectedIds: new Set(),
    history: [],
    rewardOptions: [],
    coins: 4,
    skillLevels: { G: 0, F: 0, C: 0 },
    comboBoosts: { six_man_rotation: 0, zone_press: 0, twin_towers: 0, starting_four: 0, pick_roll: 0, catch_shoot: 0, isolation: 0 },
    cardEffects: {},   // card_id -> [effects]
    shopItems: [],
    pendingShopItem: null,  // item waiting for target selection
    maxHandSize: 7,
    baseDiscards: 3,
    restockCount: 0,
    deckPool: [],
    maxJokers: 5,
    jokerState: {},
    shopPacks: [],
    jokerEnhancements: {},
    heldItems: [],
    pendingHeldItem: null,
    deckCards: [],
    fightDiscards: [],
    fightPlayed: [],
  };

  // ── Drag state ──────────────────────────────────────────────────────
  var dragJokerId = null;
  var dragCardId = null;
  var _isDragging = false;

  // ── Card stats cache ────────────────────────────────────────────────
  var cardStatsCache = {};

  // ── Year select pending state ────────────────────────────────────────
  var pendingYearTarget = null;  // {shopId, itemType, cardId, playerName}

  // ── Element refs ───────────────────────────────────────────────────
  var els = {
    startScreen:    document.getElementById('start-screen'),
    gameScreen:     document.getElementById('game-screen'),
    rewardScreen:   document.getElementById('reward-screen'),
    shopScreen:     document.getElementById('shop-screen'),
    gameoverScreen: document.getElementById('gameover-screen'),

    startBtn:       document.getElementById('start-btn'),
    playBtn:        document.getElementById('play-btn'),
    discardBtn:     document.getElementById('discard-btn'),
    skipJokerBtn:   document.getElementById('skip-joker-btn'),
    restartBtn:     document.getElementById('restart-btn'),
    leaveShopBtn:   document.getElementById('leave-shop-btn'),
    restockBtn:     document.getElementById('restock-btn'),
    restockCost:    document.getElementById('restock-cost'),

    levelName:      document.getElementById('level-name-display'),
    floorDisplay:   document.getElementById('floor-display'),
    scoreBar:       document.getElementById('score-bar'),
    scoreText:      document.getElementById('score-text'),
    handsCount:     document.getElementById('hands-count'),
    discardCount:   document.getElementById('discards-count'),
    handsBadge:     document.getElementById('hands-badge'),
    discardBadge:   document.getElementById('discards-badge'),
    coinsCount:     document.getElementById('coins-count'),
    shopCoinsCount: document.getElementById('shop-coins-count'),

    handCards:      document.getElementById('hand-cards'),
    jokersCont:     document.getElementById('jokers-container'),
    shopJokersSect: document.getElementById('shop-jokers-section'),
    previewType:    document.getElementById('preview-hand-type'),
    previewDets:    document.getElementById('preview-score-details'),
    playLog:        document.getElementById('play-log'),
    jokerOptions:   null, // removed — reward screen now uses reward-joker-options
    gameoverContent:document.getElementById('gameover-content'),
    scorePopup:     document.getElementById('score-popup'),
    shopItemsCont:  document.getElementById('shop-items-container'),
    statsBars:      document.getElementById('stats-bars-container'),
    statsOverlay:   document.getElementById('stats-overlay'),
    targetModal:    document.getElementById('target-modal'),
    targetModalDesc:document.getElementById('target-modal-desc'),
    targetCardsCont:document.getElementById('target-cards-container'),
    yearSelectModal:document.getElementById('year-select-modal'),
    yearModalPlayer:document.getElementById('year-modal-player'),
    yearListCont:   document.getElementById('year-list-container'),
    deckViewerOverlay: document.getElementById('deck-viewer-overlay'),
    deckViewerContent: document.getElementById('deck-viewer-content'),
  };

  // ── API helpers ────────────────────────────────────────────────────
  function apiPost(endpoint, data) {
    return fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data || {}),
    }).then(function (r) { return r.json(); });
  }

  function apiGet(endpoint) {
    return fetch(endpoint).then(function (r) { return r.json(); });
  }

  // ── Animation helpers ──────────────────────────────────────────────
  function sleep(ms) { return new Promise(function(r) { setTimeout(r, ms); }); }

  function animateCounterTo(el, target, duration) {
    return new Promise(function(resolve) {
      var start = parseFloat(el.textContent.replace(/,/g, '')) || 0;
      var startTime = null;
      var isInt = Number.isInteger(target);
      var lastTickTime = 0;
      function step(ts) {
        if (!startTime) startTime = ts;
        var prog = Math.min((ts - startTime) / duration, 1);
        var eased = 1 - Math.pow(1 - prog, 3);
        var val = start + (target - start) * eased;
        el.textContent = isInt ? Math.round(val).toLocaleString() : val.toFixed(1);
        if (window.SFX && ts - lastTickTime > 80) { SFX.play('score_tick'); lastTickTime = ts; }
        if (prog < 1) { requestAnimationFrame(step); }
        else {
          el.textContent = isInt ? target.toLocaleString() : target.toFixed(1);
          resolve();
        }
      }
      requestAnimationFrame(step);
    });
  }

  function showChipFloat(cardEl, text) {
    var rect = cardEl.getBoundingClientRect();
    var el = document.createElement('div');
    el.className = 'chip-float-el';
    el.textContent = text;
    el.style.left = (rect.left + rect.width / 2 - 20) + 'px';
    el.style.top  = (rect.top - 8) + 'px';
    document.body.appendChild(el);
    setTimeout(function() { if (el.parentNode) el.parentNode.removeChild(el); }, 700);
  }

  var _animLock = false;

  async function animateHandScore(data, playedIds) {
    if (!data.card_contributions || data.card_contributions.length === 0) return;
    _animLock = true;
    document.body.classList.add('scoring');

    var panel       = document.getElementById('score-anim-panel');
    var htLabel     = document.getElementById('anim-hand-type-label');
    var chipsEl     = document.getElementById('anim-chips-val');
    var multBox     = document.getElementById('anim-mult-box');
    var multEl      = document.getElementById('anim-mult-val');
    var xmultTimesOp = document.getElementById('anim-xmult-times-op');
    var xmultBox    = document.getElementById('anim-xmult-box');
    var xmultEl     = document.getElementById('anim-xmult-val');
    var equalsOp    = document.getElementById('anim-equals-op');
    var scoreBox    = document.getElementById('anim-score-box');
    var scoreEl     = document.getElementById('anim-score-val');

    // Reset
    htLabel.textContent   = (data.hand_name || '').toUpperCase();
    chipsEl.textContent   = '0';
    multEl.textContent    = '—';
    xmultEl.textContent   = '1';
    scoreEl.textContent   = '0';
    multBox.classList.remove('mult-popping');
    if (xmultBox) { xmultBox.classList.add('hidden'); xmultBox.classList.remove('mult-popping'); }
    if (xmultTimesOp) xmultTimesOp.classList.add('hidden');
    equalsOp.classList.add('hidden');
    scoreBox.classList.add('hidden');
    scoreBox.classList.remove('score-banging');
    panel.classList.remove('hidden', 'fading');

    var scoringIds = new Set((data.scoring_card_ids || (data.scoring_cards || []).map(function(c){return c.id;})));

    // Dim non-scoring played cards
    playedIds.forEach(function(id) {
      if (!scoringIds.has(id)) {
        var el = document.querySelector('[data-card-id="' + id + '"]');
        if (el) el.classList.add('scoring-dim');
      }
    });

    var runningChips = 0;

    // Phase 1 — card by card chips
    for (var i = 0; i < data.card_contributions.length; i++) {
      var contrib = data.card_contributions[i];
      var cardEl = document.querySelector('[data-card-id="' + contrib.id + '"]');

      if (cardEl) {
        cardEl.classList.add('scoring-active');
        showChipFloat(cardEl, '+' + Math.round(contrib.contribution));
      }

      await sleep(180);
      runningChips += contrib.contribution;
      chipsEl.classList.add('bumping');
      await animateCounterTo(chipsEl, Math.round(runningChips), 160);
      setTimeout(function() { chipsEl.classList.remove('bumping'); }, 200);

      if (cardEl) {
        cardEl.classList.remove('scoring-active');
        cardEl.classList.add('scoring-done');
      }
      await sleep(280);
    }

    await sleep(220);

    // Phase 2 — multiplier reveal + joker wiggle
    multBox.classList.add('mult-popping');
    await animateCounterTo(multEl, data.total_mult, 350);
    showChipFloat(document.getElementById('anim-mult-box'), '×' + data.total_mult);
    // Wiggle specific additive mult jokers and show float over them
    if (data.joker_mult && data.joker_mult > 0) {
      wiggleSpecificJokers(data.joker_add_ids || []);
      showMultFloat(document.getElementById('jokers-container'), '+' + data.joker_mult.toFixed(1) + ' FAN');
    }
    await sleep(420);

    // Phase 2b — xmult reveal (multiplicative jokers)
    if (data.mult_factor && data.mult_factor > 1.0) {
      if (xmultTimesOp) xmultTimesOp.classList.remove('hidden');
      if (xmultBox) {
        xmultBox.classList.remove('hidden');
        xmultBox.classList.add('mult-popping');
      }
      await animateCounterTo(xmultEl, data.mult_factor, 350);
      showChipFloat(xmultBox, '×' + data.mult_factor);
      wiggleSpecificJokers(data.xmult_joker_ids || []);
      showMultFloat(document.getElementById('jokers-container'), '×' + data.mult_factor + ' FAN');
      await sleep(420);
    }

    // Phase 3 — score bang
    equalsOp.classList.remove('hidden');
    scoreBox.classList.remove('hidden');
    void scoreBox.offsetWidth; // reflow to restart animation
    scoreBox.classList.add('score-banging');
    await animateCounterTo(scoreEl, data.score, 500);
    await sleep(800);

    // Fade out
    panel.classList.add('fading');
    await sleep(320);
    panel.classList.add('hidden');
    panel.classList.remove('fading');
    equalsOp.classList.add('hidden');
    scoreBox.classList.add('hidden');
    scoreBox.classList.remove('score-banging');
    multBox.classList.remove('mult-popping');
    if (xmultBox) { xmultBox.classList.add('hidden'); xmultBox.classList.remove('mult-popping'); }
    if (xmultTimesOp) xmultTimesOp.classList.add('hidden');

    // Cleanup card states
    document.querySelectorAll('.scoring-dim, .scoring-done, .scoring-active').forEach(function(el) {
      el.classList.remove('scoring-dim', 'scoring-done', 'scoring-active');
    });

    document.body.classList.remove('scoring');
    _animLock = false;
  }

  // ── Mult animation helpers ─────────────────────────────────────────
  function wiggleJokers() {
    document.querySelectorAll('.joker-slot.filled').forEach(function(slot) {
      slot.classList.remove('joker-wiggle');
      void slot.offsetWidth; // reflow
      slot.classList.add('joker-wiggle');
      setTimeout(function() { slot.classList.remove('joker-wiggle'); }, 500);
    });
  }

  function wiggleSpecificJokers(jokerIds) {
    if (!jokerIds || jokerIds.length === 0) return;
    var idSet = new Set(jokerIds);
    document.querySelectorAll('.joker-slot.filled[data-joker-id]').forEach(function(slot) {
      if (idSet.has(slot.getAttribute('data-joker-id'))) {
        slot.classList.remove('joker-wiggle');
        void slot.offsetWidth;
        slot.classList.add('joker-wiggle');
        setTimeout(function() { slot.classList.remove('joker-wiggle'); }, 500);
      }
    });
  }

  function showMultFloat(anchorEl, text) {
    if (!anchorEl) return;
    var rect = anchorEl.getBoundingClientRect();
    var floater = document.createElement('div');
    floater.className = 'mult-float-overlay';
    floater.textContent = text;
    document.body.appendChild(floater);
    floater.style.left = (rect.left + rect.width / 2) + 'px';
    floater.style.top = (rect.top + rect.height / 2) + 'px';
    setTimeout(function() {
      if (floater.parentNode) floater.parentNode.removeChild(floater);
    }, 1200);
  }

  // ── Game API calls ─────────────────────────────────────────────────
  function startGame() {
    els.startBtn.disabled = true;
    els.startBtn.textContent = 'LOADING...';
    apiPost('/api/nba_balatro/start', {}).then(function (data) {
      if (data.error) {
        alert('Error: ' + data.error);
        els.startBtn.disabled = false;
        els.startBtn.textContent = 'TIP OFF!';
        return;
      }
      gameId = data.game_id;
      gs.mode = 'normal';
      gs.hand = data.hand || [];
      gs.jokers = data.jokers || [];
      gs.floor = data.floor;
      gs.round = data.round || 1;
      gs.fight = data.fight || 1;
      gs.bossEffect = data.boss_effect || null;
      gs.levelName = data.level_name;
      gs.targetScore = data.target_score;
      gs.currentScore = 0;
      gs.handsRemaining = data.hands_remaining;
      gs.discardsRemaining = data.discards_remaining;
      gs.status = data.status;
      gs.selectedIds = new Set();
      gs.history = [];
      gs.rewardOptions = [];
      gs.coins = data.coins !== undefined ? data.coins : 4;
      gs.skillLevels = data.skill_levels || { G: 0, F: 0, C: 0 };
      gs.comboBoosts = data.combo_boosts || {};
      gs.cardEffects = data.card_effects || {};
      gs.shopItems = [];
      gs.maxHandSize = data.max_hand_size || 9;
      gs.baseDiscards = data.base_discards || 3;
      gs.restockCount = 0;
      gs.deckPool = data.hand || [];
      gs.maxJokers = data.max_jokers || 5;
      gs.jokerState = data.joker_state || {};
      gs.shopPacks = [];
      gs.jokerEnhancements = data.joker_enhancements || {};
      gs.heldItems = data.held_items || [];
      gs.deckCards = data.deck_cards || [];
      gs.fightDiscards = data.fight_discards || [];
      gs.fightPlayed = data.fight_played || [];
      currentSort = null;
      cardStatsCache = {};

      showScreen('game');
      renderAll();
      setTimeout(triggerDealAnimation, 60);
      els.startBtn.disabled = false;
      els.startBtn.textContent = 'TIP OFF!';
    }).catch(function (e) {
      alert('Failed to start game: ' + e);
      els.startBtn.disabled = false;
      els.startBtn.textContent = 'TIP OFF!';
    });
  }

  function playHand() {
    if (gs.selectedIds.size === 0) return;
    if (window.SFX) SFX.play('card_play');
    var ids = Array.from(gs.selectedIds);
    var oldHandIds = new Set(gs.hand.map(function(c) { return c.id; }));
    els.playBtn.disabled = true;
    els.discardBtn.disabled = true;

    apiPost('/api/nba_balatro/play_hand', {
      game_id: gameId,
      card_ids: ids,
    }).then(async function (data) {
      if (data.error) { alert(data.error); renderActionButtons(); return; }

      // Run scoring animation before updating UI
      var idsPlayed = ids.slice();
      await animateHandScore(data, idsPlayed);

      gs.hand = data.hand !== undefined ? data.hand : gs.hand;
      if (data.hand === undefined) {
        gs.hand = gs.hand.filter(function (c) { return !gs.selectedIds.has(c.id); });
      }
      gs.currentScore = data.cumulative_score;
      gs.targetScore = data.target_score;
      gs.handsRemaining = data.hands_remaining;
      gs.discardsRemaining = data.discards_remaining;
      gs.status = data.status;
      gs.selectedIds = new Set();
      flippedCardIds.clear();

      if (data.coins !== undefined) gs.coins = data.coins;
      if (data.joker_state !== undefined) gs.jokerState = data.joker_state;
      if (data.deck_cards !== undefined) gs.deckCards = data.deck_cards;
      if (data.fight_played !== undefined) gs.fightPlayed = data.fight_played;

      // Update card effects for broken cards
      if (data.broken_cards && data.broken_cards.length > 0) {
        data.broken_cards.forEach(function (cid) {
          if (gs.cardEffects[cid]) {
            gs.cardEffects[cid] = gs.cardEffects[cid].filter(function (e) { return e !== 'glass'; });
            if (gs.cardEffects[cid].length === 0) delete gs.cardEffects[cid];
          }
        });
      }

      refreshHandFromServer().then(function () {
        var logMsg = data.hand_name + ': +' + formatNum(data.score);
        if (data.coins_earned && data.coins_earned > 0) {
          logMsg += ' | +$' + data.coins_earned;
        }
        if (data.broken_cards && data.broken_cards.length > 0) {
          logMsg += ' | ' + data.broken_cards.length + ' card(s) broke';
        }
        addLogEntry(logMsg, data.score, data.coins_earned > 0);
        showScorePopup(data.score, data.hand_name, data.base_pts, data.total_mult);
        renderAll();
        if (data.status === 'playing') setTimeout(function() { triggerNewCardsAnimation(oldHandIds); }, 60);

        if (data.status === 'won_fight' || data.status === 'won_level') {
          gs.fight = data.fight || gs.fight;
          gs.round = data.round || gs.round;
          setTimeout(function () { advanceFight(); }, 2400);
        } else if (data.status === 'won_game') {
          setTimeout(function () { showGameOver(true, data); }, 2400);
        } else if (data.status === 'lost') {
          setTimeout(function () { showGameOver(false, data); }, 2400);
        }
      });
    }).catch(function (e) {
      alert('Error: ' + e);
      renderActionButtons();
    });
  }

  function discardCards() {
    if (gs.selectedIds.size === 0) return;
    if (window.SFX) SFX.play('discard');
    var ids = Array.from(gs.selectedIds);
    var oldHandIds = new Set(gs.hand.map(function(c) { return c.id; }));
    els.discardBtn.disabled = true;
    els.playBtn.disabled = true;

    apiPost('/api/nba_balatro/discard', {
      game_id: gameId,
      card_ids: ids,
    }).then(function (data) {
      if (data.error) { alert(data.error); renderActionButtons(); return; }
      gs.hand = data.hand || gs.hand;
      gs.discardsRemaining = data.discards_remaining;
      if (data.deck_cards !== undefined) gs.deckCards = data.deck_cards;
      if (data.fight_discards !== undefined) gs.fightDiscards = data.fight_discards;
      gs.selectedIds = new Set();
      flippedCardIds.clear();
      renderAll();
      setTimeout(function() { triggerNewCardsAnimation(oldHandIds); }, 60);
    }).catch(function (e) {
      alert('Error: ' + e);
      renderActionButtons();
    });
  }

  function selectJoker(jokerId) {
    apiPost('/api/nba_balatro/select_joker', {
      game_id: gameId,
      joker_id: jokerId,
    }).then(function (data) {
      if (data.error) { alert(data.error); return; }
      gs.status = data.status;
      gs.coins = data.coins !== undefined ? data.coins : gs.coins;
      gs.jokers = data.jokers || gs.jokers;
      gs.shopItems = data.shop_items || [];
      gs.restockCount = 0;
      gs.maxJokers = data.max_jokers || gs.maxJokers;
      gs.shopPacks = data.shop_packs || [];
      gs.jokerEnhancements = data.joker_enhancements || gs.jokerEnhancements;
      if (data.held_items !== undefined) gs.heldItems = data.held_items;

      if (data.status === 'shopping') {
        showShopScreen();
      }
    }).catch(function (e) { alert('Error: ' + e); });
  }

  function leaveShop() {
    apiPost('/api/nba_balatro/leave_shop', {
      game_id: gameId,
    }).then(function (data) {
      if (data.error) { alert(data.error); return; }
      gs.floor = data.floor;
      gs.round = data.round || gs.round;
      gs.fight = data.fight || 1;
      gs.bossEffect = data.boss_effect || null;
      gs.levelName = data.level_name;
      gs.targetScore = data.target_score;
      gs.currentScore = 0;
      gs.handsRemaining = data.hands_remaining;
      gs.discardsRemaining = data.discards_remaining;
      gs.status = data.status;
      gs.jokers = data.jokers || gs.jokers;
      gs.hand = data.hand || gs.hand;
      gs.coins = data.coins !== undefined ? data.coins : gs.coins;
      gs.skillLevels = data.skill_levels || gs.skillLevels;
      gs.comboBoosts = data.combo_boosts || gs.comboBoosts;
      gs.cardEffects = data.card_effects || gs.cardEffects;
      gs.maxHandSize = data.max_hand_size || gs.maxHandSize;
      gs.baseDiscards = data.base_discards || gs.baseDiscards;
      gs.maxJokers = data.max_jokers || gs.maxJokers;
      gs.jokerState = data.joker_state || gs.jokerState;
      gs.jokerEnhancements = data.joker_enhancements || gs.jokerEnhancements;
      if (data.held_items !== undefined) gs.heldItems = data.held_items;
      if (data.deck_cards !== undefined) gs.deckCards = data.deck_cards;
      if (data.fight_discards !== undefined) gs.fightDiscards = data.fight_discards;
      if (data.fight_played !== undefined) gs.fightPlayed = data.fight_played;
      gs.selectedIds = new Set();
      gs.history = [];
      currentSort = null;
      flippedCardIds.clear();
      clearLog();

      renderBossEffectBanner();
      showScreen('game');
      renderAll();
      setTimeout(triggerDealAnimation, 60);
    }).catch(function (e) { alert('Error: ' + e); });
  }

  function advanceFight() {
    apiPost('/api/nba_balatro/advance_fight', { game_id: gameId }).then(function (data) {
      if (data.error) { alert(data.error); return; }
      gs.coins = data.coins !== undefined ? data.coins : gs.coins;
      gs.nextFight = data.next_fight || (gs.fight + 1);
      gs.nextBossEffect = data.next_boss_effect !== undefined ? data.next_boss_effect : null;
      gs.status = data.status;
      showFightRewardScreen(data);
    }).catch(function (e) { alert('Error: ' + e); });
  }

  function claimRewardCoins() {
    if (window.SFX) SFX.play('buy');
    apiPost('/api/nba_balatro/claim_reward', { game_id: gameId, choice: 'coins' }).then(function (data) {
      if (data.error) { alert(data.error); return; }
      _applyShoppingData(data);
      showShopScreen();
    }).catch(function (e) { alert('Error: ' + e); });
  }

  function claimRewardJoker(jokerId) {
    apiPost('/api/nba_balatro/claim_reward', { game_id: gameId, choice: 'joker', joker_id: jokerId }).then(function (data) {
      if (data.error) { alert(data.error); return; }
      _applyShoppingData(data);
      showShopScreen();
    }).catch(function (e) { alert('Error: ' + e); });
  }

  function _applyShoppingData(data) {
    gs.status = 'shopping';
    gs.coins = data.coins !== undefined ? data.coins : gs.coins;
    gs.jokers = data.jokers || gs.jokers;
    gs.shopItems = data.shop_items || [];
    gs.restockCount = 0;
    gs.maxJokers = data.max_jokers || gs.maxJokers;
    gs.shopPacks = data.shop_packs || [];
    gs.jokerEnhancements = data.joker_enhancements || gs.jokerEnhancements;
    if (data.held_items !== undefined) gs.heldItems = data.held_items;
    if (data.next_fight !== undefined) gs.nextFight = data.next_fight;
    if (data.next_boss_effect !== undefined) gs.nextBossEffect = data.next_boss_effect;
  }

  // Item types that now go into held_items — no target needed at buy time
  var HELD_ITEM_TYPES = new Set(['skill_card', 'combo_card', 'effect_card', 'year_card', 'cut_card', 'upgrade', 'mod_card', 'buy_card']);

  function buyShopItem(shopId, itemType, needsTarget, item) {
    if (itemType === 'joker_enhancement' || (item && item.needs_joker_target)) {
      buyShopItemWithJokerTarget(shopId, itemType, item);
      return;
    }
    if (itemType === 'division_sticker') {
      openDivisionStickerModal(item);
      return;
    }
    // Items going to held_items don't need target at buy time — target selected on use
    if (needsTarget && !HELD_ITEM_TYPES.has(itemType)) {
      gs.pendingShopItem = { shopId: shopId, itemType: itemType, item: item };
      openTargetModal(item);
      return;
    }
    executeBuy(shopId, itemType, null, null);
  }

  // ── Division Sticker Modal ─────────────────────────────────────────
  var pendingDivSticker = null;

  function openDivisionStickerModal(item) {
    pendingDivSticker = { shopId: item.shop_id, cost: item.cost };

    // Pre-populate division buttons for step 2
    var divOpts = document.getElementById('sticker-div-options');
    if (divOpts) {
      divOpts.innerHTML = '';
      NBA_DIVISIONS_LIST.forEach(function(div) {
        var btn = document.createElement('button');
        btn.className = 'sticker-div-btn ' + div.cls;
        btn.textContent = div.id;
        btn.addEventListener('click', function() {
          applyDivisionSticker(div.id, div.cls, div.label);
        });
        divOpts.appendChild(btn);
      });
    }

    // Use deck viewer for card selection instead of inline mini-grid
    openDeckViewerForSelection('Pick a card to reassign its division', function(card) {
      pendingDivSticker.cardId = card.id;
      pendingDivSticker.card = card;
      document.getElementById('div-sticker-chosen-card').textContent = card.player + ' (' + card.team + ')';
      var modal = document.getElementById('div-sticker-modal');
      if (modal) {
        document.getElementById('div-sticker-step1').classList.add('hidden');
        document.getElementById('div-sticker-step2').classList.remove('hidden');
        modal.classList.remove('hidden');
      }
    });
  }

  function closeDivisionStickerModal() {
    var modal = document.getElementById('div-sticker-modal');
    if (modal) modal.classList.add('hidden');
    pendingDivSticker = null;
    // Also close deck viewer if it was open for selection
    _deckSelectCallback = null;
    if (els.deckViewerOverlay) {
      var titleEl = els.deckViewerOverlay.querySelector('.deck-viewer-title');
      if (titleEl) titleEl.textContent = 'YOUR DECK';
      els.deckViewerOverlay.classList.add('hidden');
    }
  }

  function applyDivisionSticker(newDivision, newDivCls, newDivLabel) {
    if (!pendingDivSticker || !pendingDivSticker.cardId) return;
    var shopId = pendingDivSticker.shopId;
    var cardId = pendingDivSticker.cardId;

    apiPost('/api/nba_balatro/buy_item', {
      game_id: gameId,
      shop_id: shopId,
      item_type: 'division_sticker',
      target_card_id: null,
    }).then(function(data) {
      if (data.error) { showToast(data.error, 'error'); closeDivisionStickerModal(); return; }
      gs.coins = data.coins !== undefined ? data.coins : gs.coins;
      gs.shopItems = data.shop_items || gs.shopItems;
      if (els.shopCoinsCount) els.shopCoinsCount.textContent = gs.coins;
      if (els.coinsCount) els.coinsCount.textContent = gs.coins;

      return apiPost('/api/nba_balatro/apply_division_sticker', {
        game_id: gameId,
        card_id: cardId,
        new_division: newDivision,
      });
    }).then(function(data) {
      if (!data || data.error) { closeDivisionStickerModal(); return; }
      // Update deckPool card
      if (gs.deckPool) {
        gs.deckPool.forEach(function(c) {
          if (c.id === cardId) {
            c.division = newDivision;
            c._stickerCls = newDivCls;
            c._stickerLabel = newDivLabel;
          }
        });
      }
      // Update hand if card is there
      gs.hand.forEach(function(c) {
        if (c.id === cardId) {
          c.division = newDivision;
          c._stickerCls = newDivCls;
          c._stickerLabel = newDivLabel;
        }
      });
      closeDivisionStickerModal();
      renderShop();
      renderHand();
      showToast('Division sticker applied!', 'success');
    }).catch(function() { closeDivisionStickerModal(); });
  }

  function executeBuy(shopId, itemType, targetCardId, extraData) {
    var payload = {
      game_id: gameId,
      shop_id: shopId,
      item_type: itemType,
      target_card_id: targetCardId || null,
    };
    if (extraData) {
      Object.keys(extraData).forEach(function (k) { payload[k] = extraData[k]; });
    }
    apiPost('/api/nba_balatro/buy_item', payload).then(function (data) {
      if (data.error) { alert(data.error); return; }
      if (window.SFX) SFX.play('buy');
      if (itemType === 'buy_card') showToast('Card added to your deck!', 'success');
      gs.coins = data.coins !== undefined ? data.coins : gs.coins;
      gs.shopItems = data.shop_items || [];
      gs.jokers = data.jokers || gs.jokers;
      gs.skillLevels = data.skill_levels || gs.skillLevels;
      gs.comboBoosts = data.combo_boosts || gs.comboBoosts;
      gs.cardEffects = data.card_effects || gs.cardEffects;
      if (data.hand) gs.hand = data.hand;
      if (data.max_hand_size) gs.maxHandSize = data.max_hand_size;
      if (data.base_discards) gs.baseDiscards = data.base_discards;
      if (data.max_jokers) gs.maxJokers = data.max_jokers;
      if (data.joker_enhancements) gs.jokerEnhancements = data.joker_enhancements;
      if (data.held_items !== undefined) { gs.heldItems = data.held_items; renderHeldItems(); }
      gs.pendingShopItem = null;
      closeTargetModal();
      closeYearModal();
      renderShop();
    }).catch(function (e) { alert('Error: ' + e); });
  }

  function restockShop() {
    apiPost('/api/nba_balatro/restock_shop', { game_id: gameId }).then(function (data) {
      if (data.error) { alert(data.error); return; }
      gs.coins = data.coins !== undefined ? data.coins : gs.coins;
      gs.shopItems = data.shop_items || [];
      if (data.shop_packs !== undefined) gs.shopPacks = data.shop_packs;
      gs.restockCount = (gs.restockCount || 0) + 1;
      // Update restock cost display
      if (els.restockCost) {
        els.restockCost.textContent = '$' + (data.next_restock_cost || (2 + gs.restockCount * 2));
      }
      renderShop();
    }).catch(function (e) { alert('Error: ' + e); });
  }

  function sellJoker(jokerId) {
    apiPost('/api/nba_balatro/sell_joker', { game_id: gameId, joker_id: jokerId }).then(function (data) {
      if (data.error) { alert(data.error); return; }
      gs.coins = data.coins !== undefined ? data.coins : gs.coins;
      gs.jokers = data.jokers || gs.jokers;
      showToast('Sold ' + data.sold + ' for $' + data.earned);
      // Render jokers for whatever screen we're on
      renderJokers();
      if (els.shopJokersSect) renderShopJokers();
      if (els.coinsCount) els.coinsCount.textContent = gs.coins;
      if (els.shopCoinsCount) els.shopCoinsCount.textContent = gs.coins;
    }).catch(function (e) { alert('Error: ' + e); });
  }

  function getScorePreview(cardIds) {
    if (!gameId || cardIds.length === 0) {
      clearPreview();
      return;
    }
    apiPost('/api/nba_balatro/preview', {
      game_id: gameId,
      card_ids: cardIds,
    }).then(function (data) {
      if (data.hand_type) {
        renderPreview(data);
      } else {
        clearPreview();
      }
    }).catch(function () { clearPreview(); });
  }

  function refreshHandFromServer() {
    return Promise.resolve();
  }

  // ── Card Flip ──────────────────────────────────────────────────────
  function fetchAndShowCardBack(backEl, card) {
    var cacheKey = card.player + '_' + card.season;
    if (cardStatsCache[cacheKey]) {
      renderCardBack(backEl, card, cardStatsCache[cacheKey]);
      return;
    }
    backEl.innerHTML = '<div class="card-back-loading">Loading…</div>';
    apiGet('/api/nba_balatro/card_stats?player=' + encodeURIComponent(card.player) + '&season=' + card.season)
      .then(function(stats) {
        cardStatsCache[cacheKey] = stats;
        renderCardBack(backEl, card, stats);
      })
      .catch(function() {
        backEl.innerHTML = '<div class="card-back-loading">Error</div>';
      });
  }

  function renderCardBack(backEl, card, stats) {
    stats = stats || {};

    var statsHtml =
      '<div class="stat-row"><span>PTS</span><span>' + (stats.pts_pg || 0).toFixed(1) + ' ppg</span></div>' +
      '<div class="stat-row"><span>REB</span><span>' + (stats.trb_pg || 0).toFixed(1) + ' rpg</span></div>' +
      '<div class="stat-row"><span>AST</span><span>' + (stats.ast_pg || 0).toFixed(1) + ' apg</span></div>';

    var draftHtml = (card.allstar_count && card.allstar_count > 0)
      ? '<div class="card-back-pb">★ ' + card.allstar_count + 'x All-Star</div>'
      : (card.draft_pick && card.draft_pick > 0)
        ? '<div class="card-back-pb">Pick #' + card.draft_pick + '</div>'
        : '';

    backEl.innerHTML =
      '<div class="card-back-header">' +
        '<span class="card-back-pos card-pos-' + card.pos.toLowerCase() + '">' + card.pos + '</span>' +
        '<span class="card-back-team">' + escHtml(card.team || '') + '</span>' +
      '</div>' +
      '<div class="card-back-name">' + escHtml(card.player) + '</div>' +
      '<div class="card-back-season">' + nbaYear(card.season) + '</div>' +
      '<div class="card-back-college">' + escHtml((card.college && card.college !== 'Unknown') ? card.college : 'Undrafted') + '</div>' +
      draftHtml +
      '<div class="card-back-stats">' + (stats.games ? stats.games + ' games' : '') + '</div>' +
      statsHtml +
      '<div class="card-back-ppr">' + (card.fantasy_pts !== undefined ? card.fantasy_pts.toFixed(1) : '') + '</div>';
  }

  // ── Sort Hand ──────────────────────────────────────────────────────
  var POS_ORDER = ['G', 'F', 'C'];

  function _applySortToHand(mode) {
    if (mode === 'pos') {
      gs.hand.sort(function (a, b) {
        var ai = POS_ORDER.indexOf(a.pos);
        var bi = POS_ORDER.indexOf(b.pos);
        if (ai !== bi) return ai - bi;
        return b.fantasy_pts - a.fantasy_pts;
      });
    } else if (mode === 'pts') {
      gs.hand.sort(function (a, b) {
        return b.fantasy_pts - a.fantasy_pts;
      });
    }
  }

  function sortHand(mode) {
    if (window.SFX) SFX.play('rustle');
    if (currentSort === mode) {
      currentSort = null; // deselect
    } else {
      currentSort = mode;
      _applySortToHand(mode);
    }
    // Update active button styling
    var sortBtns = document.querySelectorAll('.btn-sort');
    sortBtns.forEach(function (btn) { btn.classList.remove('active'); });
    if (currentSort) {
      var activeBtn = document.getElementById('sort-btn-' + currentSort);
      if (activeBtn) activeBtn.classList.add('active');
    }
    renderHand();
  }

  // ── Boss Effect Banner ─────────────────────────────────────────────
  function renderBossEffectBanner() {
    var banner = document.getElementById('boss-effect-banner');
    if (!banner) return;
    if (gs.bossEffect) {
      banner.classList.remove('hidden');
      banner.innerHTML =
        '<span class="boss-banner-icon">!</span>' +
        '<span class="boss-banner-name">BOSS: ' + escHtml(gs.bossEffect.name || '') + '</span>' +
        '<span class="boss-banner-desc">' + escHtml(gs.bossEffect.desc || '') + '</span>';
    } else {
      banner.classList.add('hidden');
    }
  }

  // ── Fight Timeline ─────────────────────────────────────────────────
  function renderFightTimeline() {
    var nodes = [
      document.getElementById('timeline-fight-1'),
      document.getElementById('timeline-fight-2'),
      document.getElementById('timeline-fight-3'),
    ];
    var conns = [
      document.getElementById('timeline-conn-1'),
      document.getElementById('timeline-conn-2'),
    ];
    if (!nodes[0]) return;

    var currentFight = gs.fight || 1;
    var bossEffect = gs.bossEffect;
    var bossNameEl = document.getElementById('timeline-boss-name');
    if (bossNameEl) {
      bossNameEl.textContent = bossEffect ? bossEffect.name : '';
    }

    nodes.forEach(function (node, i) {
      if (!node) return;
      node.classList.remove('complete', 'current', 'boss-current', 'boss-upcoming');
      var fightNum = i + 1;
      if (fightNum < currentFight) {
        node.classList.add('complete');
      } else if (fightNum === currentFight) {
        node.classList.add(fightNum === 3 ? 'boss-current' : 'current');
      } else if (fightNum === 3) {
        node.classList.add('boss-upcoming');
      }
    });

    conns.forEach(function (conn, i) {
      if (!conn) return;
      conn.classList.remove('complete');
      if (i + 1 < currentFight) conn.classList.add('complete');
    });
  }

  // ── Render functions ───────────────────────────────────────────────
  function renderAll() {
    renderTopBar();
    renderFightTimeline();
    renderJokers();
    renderHeldItems();
    renderHand();
    renderActionButtons();
    renderBossEffectBanner();
    renderDeckWidget();
  }

  function renderTopBar() {
    els.levelName.textContent = gs.levelName || 'Preseason';
    if (gs.mode === 'infinity') {
      var wave = (gs.round - 1) * 3 + gs.fight;
      els.floorDisplay.textContent = '\u221e INFINITY MODE \u00b7 Wave ' + wave;
    } else {
      els.floorDisplay.textContent = 'Round ' + (gs.round || 1) + ' \u00b7 Fight ' + (gs.fight || 1);
    }
    els.handsCount.textContent = gs.handsRemaining;
    els.discardCount.textContent = gs.discardsRemaining;
    if (els.coinsCount) els.coinsCount.textContent = gs.coins;

    var pct = gs.targetScore > 0 ? Math.min(100, (gs.currentScore / gs.targetScore) * 100) : 0;
    els.scoreBar.style.width = pct + '%';

    var cur = formatNum(gs.currentScore);
    var tgt = formatNum(gs.targetScore);
    els.scoreText.textContent = cur + ' / ' + tgt;

    if (gs.handsRemaining <= 1) {
      els.handsBadge.classList.add('danger');
    } else {
      els.handsBadge.classList.remove('danger');
    }
    if (gs.discardsRemaining === 0) {
      els.discardBadge.classList.add('danger');
    } else {
      els.discardBadge.classList.remove('danger');
    }
  }

  function renderJokers() {
    var cont = els.jokersCont;
    cont.innerHTML = '';
    var maxSlots = gs.maxJokers || 5;
    for (var i = 0; i < maxSlots; i++) {
      var slot = document.createElement('div');
      slot.className = 'joker-slot';
      slot.id = 'joker-slot-' + i;
      if (i < gs.jokers.length) {
        var j = gs.jokers[i];
        slot.classList.add('filled');
        slot.setAttribute('data-joker-id', j.id);
        _buildJokerSlotContent(slot, j, gs.status);
        // Drag-and-drop for filled slots
        slot.setAttribute('draggable', 'true');
        (function(jokerId) {
          slot.addEventListener('dragstart', function(e) {
            dragJokerId = jokerId;
            e.dataTransfer.effectAllowed = 'move';
          });
        })(j.id);
      } else {
        slot.classList.add('empty');
      }
      // dragover and drop for all slots
      slot.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('drag-over');
      });
      slot.addEventListener('dragleave', function() {
        this.classList.remove('drag-over');
      });
      (function(slotIndex) {
        slot.addEventListener('drop', function(e) {
          e.preventDefault();
          this.classList.remove('drag-over');
          if (!dragJokerId) return;
          var fromIdx = gs.jokers.findIndex(function(j) { return j.id === dragJokerId; });
          if (fromIdx === -1) return;
          var toJoker = slotIndex < gs.jokers.length ? gs.jokers[slotIndex] : null;
          if (toJoker && toJoker.id !== dragJokerId) {
            // Swap
            var fromJoker = gs.jokers[fromIdx];
            gs.jokers[fromIdx] = toJoker;
            gs.jokers[slotIndex] = fromJoker;
          } else if (!toJoker && slotIndex !== fromIdx) {
            // Move to empty slot
            var movingJoker = gs.jokers[fromIdx];
            gs.jokers.splice(fromIdx, 1);
            gs.jokers.splice(Math.min(slotIndex, gs.jokers.length), 0, movingJoker);
          }
          dragJokerId = null;
          renderJokers();
        });
      })(i);
      cont.appendChild(slot);
    }
  }

  function renderHeldItems() {
    var held = gs.heldItems || [];
    for (var i = 0; i < 3; i++) {
      var slot = document.getElementById('held-slot-' + i);
      if (!slot) continue;
      slot.innerHTML = '';
      slot.className = 'held-slot';
      if (i < held.length) {
        var item = held[i];
        if (item.kind === 'card') {
          slot.className = 'held-slot filled held-player-card pos-' + item.pos.toLowerCase();
          slot.innerHTML =
            '<div class="held-card-pos">' + item.pos + '</div>' +
            '<div class="held-card-name">' + item.player.split(' ').pop() + '</div>' +
            '<div class="held-card-pts">' + Math.round(item.fantasy_pts) + '</div>';
          slot.title = item.player + " '" + String(nbaYear(item.season)).slice(-2) + ' \u2014 Click to use';
        } else {
          var icon = getConsumableIcon(item.item_type, item.effect);
          slot.className = 'held-slot filled held-consumable';
          slot.innerHTML =
            '<div class="held-item-icon">' + icon + '</div>' +
            '<div class="held-item-name">' + item.name + '</div>';
          slot.title = item.name + ': ' + item.desc;
        }
        slot.classList.add('held-slot-active');
        (function(it, idx) {
          slot.addEventListener('click', function(e) {
            e.stopPropagation();
            openHeldItemPopup(it, idx, slot);
          });
        })(item, i);
      } else {
        slot.className = 'held-slot empty';
      }
    }
  }

  // ── Deck & Discard Widget ────────────────────────────────────────────
  function renderDeckWidget() {
    var deckCountEl = document.getElementById('deck-pile-count');
    var discardCountEl = document.getElementById('discard-pile-count');
    var deckVisualEl = document.getElementById('deck-pile-visual');
    var discardVisualEl = document.getElementById('discard-pile-visual');
    if (!deckCountEl) return;

    var deckCount = gs.deckCards ? gs.deckCards.length : 0;
    var discardTotal = (gs.fightDiscards ? gs.fightDiscards.length : 0) + (gs.fightPlayed ? gs.fightPlayed.length : 0);

    deckCountEl.textContent = deckCount;
    discardCountEl.textContent = discardTotal;

    function buildPileVisual(el, count, isDiscard) {
      el.innerHTML = '';
      var layers = Math.min(4, Math.max(count > 0 ? 1 : 0, Math.ceil(count / 4)));
      for (var i = 0; i < layers; i++) {
        var card = document.createElement('div');
        card.className = 'pile-card' + (isDiscard ? ' pile-card-discard' : '');
        card.style.bottom = (i * 2) + 'px';
        card.style.left = (i * 1) + 'px';
        el.appendChild(card);
      }
    }
    buildPileVisual(deckVisualEl, deckCount, false);
    buildPileVisual(discardVisualEl, discardTotal, true);

    var deckWidget = document.getElementById('deck-pile-widget');
    if (deckWidget) {
      deckWidget.style.cursor = deckCount > 0 ? 'pointer' : 'default';
      deckWidget.style.opacity = deckCount > 0 ? '1' : '0.5';
    }
    var discardWidget = document.getElementById('discard-pile-widget');
    if (discardWidget) {
      discardWidget.style.cursor = discardTotal > 0 ? 'pointer' : 'default';
      discardWidget.style.opacity = discardTotal > 0 ? '1' : '0.4';
    }
  }

  function _buildCardViewerItem(card, labelTag) {
    var el = document.createElement('div');
    el.className = 'deck-card-item card-pos-' + card.pos.toLowerCase();
    var divInfo = getNbaDivInfo(card.team || '');
    el.innerHTML =
      (labelTag ? '<div class="dci-tag ' + labelTag.cls + '">' + labelTag.text + '</div>' : '') +
      '<div class="dci-pos">' + card.pos + '</div>' +
      '<div class="dci-name">' + card.player + '</div>' +
      '<div class="dci-season">\'' + String(nbaYear(card.season)).slice(-2) + ' · ' + (card.team || '') + '</div>' +
      '<div class="dci-pts">' + Math.round(card.fantasy_pts) + ' FP</div>' +
      (divInfo ? '<div class="card-div-badge ' + divInfo.cls + '">' + divInfo.label + '</div>' : '');
    return el;
  }

  function openDeckViewer() {
    var cards = gs.deckCards || [];
    if (cards.length === 0) return;
    var overlay = document.getElementById('discard-viewer-overlay');
    var content = document.getElementById('discard-viewer-content');
    var title = overlay && overlay.querySelector('.deck-viewer-title');
    if (!overlay || !content) return;
    if (title) title.textContent = 'DRAWABLE DECK (' + cards.length + ')';
    content.innerHTML = '';
    cards.forEach(function(card) { content.appendChild(_buildCardViewerItem(card, null)); });
    overlay.classList.remove('hidden');
  }

  function openDiscardViewer() {
    var played = gs.fightPlayed || [];
    var discarded = gs.fightDiscards || [];
    var total = played.length + discarded.length;
    if (total === 0) return;
    var overlay = document.getElementById('discard-viewer-overlay');
    var content = document.getElementById('discard-viewer-content');
    var title = overlay && overlay.querySelector('.deck-viewer-title');
    if (!overlay || !content) return;
    if (title) title.textContent = '\u267B\uFE0F PLAYED & DISCARDED (' + total + ')';
    content.innerHTML = '';
    played.forEach(function(card) {
      content.appendChild(_buildCardViewerItem(card, { text: 'PLAYED', cls: 'dci-tag-played' }));
    });
    discarded.forEach(function(card) {
      content.appendChild(_buildCardViewerItem(card, { text: 'DISCARDED', cls: 'dci-tag-discarded' }));
    });
    overlay.classList.remove('hidden');
  }

  function closeDiscardViewer() {
    var overlay = document.getElementById('discard-viewer-overlay');
    if (overlay) overlay.classList.add('hidden');
  }

  // ── Fight-start deal animation ────────────────────────────────────────
  var _dealAnimPending = false;

  function triggerDealAnimation() {
    _dealAnimPending = false;
    var deckEl = document.getElementById('deck-pile-widget');
    if (!deckEl) return;
    var deckRect = deckEl.getBoundingClientRect();
    var deckCX = deckRect.left + deckRect.width / 2;
    var deckCY = deckRect.top + deckRect.height / 2;

    // Ruffle the deck pile
    deckEl.classList.add('pile-ruffling');
    setTimeout(function() { deckEl.classList.remove('pile-ruffling'); }, 700);

    var cards = document.querySelectorAll('#hand-cards > .card');
    cards.forEach(function(card, i) {
      var rect = card.getBoundingClientRect();
      var cardCX = rect.left + rect.width / 2;
      var cardCY = rect.top + rect.height / 2;
      var dx = deckCX - cardCX;
      var dy = deckCY - cardCY;
      var angle = (Math.random() * 30 - 15);

      card.style.transition = 'none';
      card.style.transform = 'translate(' + dx + 'px, ' + dy + 'px) rotate(' + angle + 'deg) scale(0.45)';
      card.style.opacity = '0';
      card.style.zIndex = '50';

      var delay = 120 + i * 90;
      setTimeout((function(c) {
        return function() {
          c.style.transition = 'transform 0.42s cubic-bezier(0.22, 0.68, 0, 1.2), opacity 0.28s ease-out';
          c.style.transform = '';
          c.style.opacity = '';
          setTimeout(function() { c.style.transition = ''; c.style.zIndex = ''; }, 500);
        };
      })(card), delay);
    });
  }

  function triggerNewCardsAnimation(oldIds) {
    var deckEl = document.getElementById('deck-pile-widget');
    if (!deckEl) return;
    var deckRect = deckEl.getBoundingClientRect();
    var deckCX = deckRect.left + deckRect.width / 2;
    var deckCY = deckRect.top + deckRect.height / 2;

    var newCards = [];
    document.querySelectorAll('#hand-cards > .card').forEach(function(card) {
      if (!oldIds.has(card.dataset.id)) newCards.push(card);
    });

    newCards.forEach(function(card, i) {
      var rect = card.getBoundingClientRect();
      var cardCX = rect.left + rect.width / 2;
      var cardCY = rect.top + rect.height / 2;
      var dx = deckCX - cardCX;
      var dy = deckCY - cardCY;
      var angle = (Math.random() * 30 - 15);

      card.style.transition = 'none';
      card.style.transform = 'translate(' + dx + 'px, ' + dy + 'px) rotate(' + angle + 'deg) scale(0.45)';
      card.style.opacity = '0';
      card.style.zIndex = '50';

      var delay = i * 90;
      setTimeout((function(c) {
        return function() {
          c.style.transition = 'transform 0.42s cubic-bezier(0.22, 0.68, 0, 1.2), opacity 0.28s ease-out';
          c.style.transform = '';
          c.style.opacity = '';
          setTimeout(function() { c.style.transition = ''; c.style.zIndex = ''; }, 500);
        };
      })(card), delay);
    });
  }

  function getConsumableIcon(itype, effect) {
    if (itype === 'upgrade') return 'UP';
    if (itype === 'skill_card') return 'SK';
    if (itype === 'combo_card') return 'CO';
    if (itype === 'effect_card') {
      if (effect === 'gold') return 'GD';
      if (effect === 'glass') return 'GL';
      if (effect === 'foil') return '\u2728';
      return 'EF';
    }
    if (itype === 'year_card') return '\u23F3';
    if (itype === 'cut_card') return '\u2702\uFE0F';
    if (itype === 'mod_card') return 'MD';
    return 'IT';
  }

  var heldPopupVisible = false;
  var heldPopupItem = null;

  function openHeldItemPopup(item, idx, anchorEl) {
    closeHeldItemPopup();
    var popup = document.getElementById('held-item-popup');
    if (!popup) return;
    heldPopupItem = item;
    heldPopupVisible = true;
    var isCard = item.kind === 'card';
    var icon = isCard ? '' : getConsumableIcon(item.item_type, item.effect);
    var useBtnText = isCard ? 'ADD TO HAND' : 'USE';
    var descText = isCard
      ? (item.player + " '" + String(nbaYear(item.season)).slice(-2) + ' \xB7 ' + item.pos + ' \xB7 ' + item.fantasy_pts + ' FP')
      : item.desc;
    popup.innerHTML =
      '<div class="held-popup-header">' +
        '<span class="held-popup-icon">' + icon + '</span>' +
        '<span class="held-popup-name">' + (isCard ? item.player : item.name) + '</span>' +
      '</div>' +
      '<div class="held-popup-desc">' + descText + '</div>' +
      '<div class="held-popup-btns">' +
        '<button class="held-popup-use btn-primary" id="held-use-btn">' + useBtnText + '</button>' +
        '<button class="held-popup-discard btn-secondary" id="held-discard-btn">DISCARD</button>' +
      '</div>';
    var rect = anchorEl.getBoundingClientRect();
    popup.style.left = Math.max(4, rect.left - 80) + 'px';
    popup.style.top = (rect.top - 130) + 'px';
    popup.classList.remove('hidden');
    document.getElementById('held-use-btn').addEventListener('click', function() {
      executeUseHeldItem(item, false);
    });
    document.getElementById('held-discard-btn').addEventListener('click', function() {
      executeUseHeldItem(item, true);
    });
    setTimeout(function() {
      document.addEventListener('click', closeHeldItemPopupOnOutside);
    }, 0);
  }

  function closeHeldItemPopup() {
    var popup = document.getElementById('held-item-popup');
    if (popup) popup.classList.add('hidden');
    heldPopupVisible = false;
    heldPopupItem = null;
    document.removeEventListener('click', closeHeldItemPopupOnOutside);
  }

  function closeHeldItemPopupOnOutside(e) {
    var popup = document.getElementById('held-item-popup');
    if (popup && !popup.contains(e.target)) {
      closeHeldItemPopup();
    }
  }

  function executeUseHeldItem(item, discardOnly) {
    closeHeldItemPopup();
    var needsTarget = !discardOnly && item.needs_target;
    if (needsTarget) {
      gs.pendingHeldItem = { item: item, discardOnly: false };
      openTargetModalForHeld(item);
      return;
    }
    doUseHeldItemApi(item.held_id, null, null, discardOnly);
  }

  function openTargetModalForHeld(item) {
    gs.pendingHeldItem = { item: item };
    var modal = document.getElementById('target-modal');
    if (!modal) return;
    var desc = document.getElementById('target-modal-desc');
    if (desc) desc.textContent = item.desc || 'Select a target card.';
    var container = document.getElementById('target-cards-container');
    if (!container) return;
    modal.classList.remove('hidden');

    container.innerHTML = '';
    var pool = gs.hand || [];
    var byPos = { G: [], F: [], C: [] };
    pool.forEach(function(card) { if (byPos[card.pos]) byPos[card.pos].push(card); });
    POS_ORDER.forEach(function(pos) {
      var cards = byPos[pos];
      if (!cards || cards.length === 0) return;
      var section = document.createElement('div');
      section.className = 'target-pos-section';
      var header = document.createElement('div');
      header.className = 'target-pos-header card-pos-' + pos.toLowerCase();
      header.textContent = pos;
      section.appendChild(header);
      var grid = document.createElement('div');
      grid.className = 'target-cards-grid';
      cards.forEach(function(card) {
        var cardEl = buildCardEl(card, {
          noSelect: true,
          overrideEffects: gs.cardEffects[card.id] || [],
          onSelect: function(selectedCard) {
            if (item.item_type === 'year_card') {
              gs.pendingHeldItem.targetCardId = selectedCard.id;
              gs.pendingHeldItem.targetCard = selectedCard;
              closeTargetModalForHeld();
              openYearModalForHeld(selectedCard, item);
            } else if (item.effect === 'pos_switch') {
              closeTargetModalForHeld();
              openPosSwitchPicker(selectedCard, function(newPos) {
                doUseHeldItemApi(item.held_id, selectedCard.id, null, false, newPos);
              }, ['G', 'F', 'C']);
            } else {
              closeTargetModalForHeld();
              doUseHeldItemApi(item.held_id, selectedCard.id, null, false);
            }
          }
        });
        grid.appendChild(cardEl);
      });
      section.appendChild(grid);
      container.appendChild(section);
    });
  }

  function closeTargetModalForHeld() {
    var modal = document.getElementById('target-modal');
    if (modal) modal.classList.add('hidden');
    gs.pendingHeldItem = null;
  }

  function openYearModalForHeld(card, item) {
    var modal = document.getElementById('year-select-modal');
    if (!modal) return;
    var playerEl = document.getElementById('year-modal-player');
    if (playerEl) playerEl.textContent = 'Choose a season for ' + card.player;
    var container = document.getElementById('year-list-container');
    if (container) container.innerHTML = '<div class="loading-msg">Loading seasons...</div>';
    modal.classList.remove('hidden');
    apiGet('/api/nba_balatro/player_seasons?game_id=' + encodeURIComponent(gameId) + '&card_id=' + encodeURIComponent(card.id))
      .then(function(data) {
        if (!container) return;
        container.innerHTML = '';
        (data.seasons || []).forEach(function(s) {
          var btn = document.createElement('button');
          btn.className = 'btn-secondary year-option-btn';
          btn.textContent = nbaYear(s.season) + ' \xB7 ' + s.team + ' \xB7 ' + s.fantasy_pts + ' FP';
          btn.addEventListener('click', function() {
            closeYearModalForHeld();
            doUseHeldItemApi(item.held_id, card.id, s.season, false);
          });
          container.appendChild(btn);
        });
      }).catch(function() { closeYearModalForHeld(); });
  }

  function closeYearModalForHeld() {
    var modal = document.getElementById('year-select-modal');
    if (modal) modal.classList.add('hidden');
    gs.pendingHeldItem = null;
  }

  // ── Position Switch Picker ─────────────────────────────────────────
  var _posPick = null; // { card, onConfirm }

  function openPosSwitchPicker(card, onConfirm, positions) {
    _posPick = { card: card, onConfirm: onConfirm };
    document.getElementById('pos-pick-player').textContent = card.player + ' (' + card.pos + ')';
    var opts = document.getElementById('pos-pick-options');
    opts.innerHTML = '';
    positions.forEach(function(pos) {
      if (pos === card.pos) return; // skip current
      var btn = document.createElement('button');
      btn.className = 'sticker-div-btn card-pos-' + pos.toLowerCase();
      btn.textContent = pos;
      btn.style.minWidth = '64px';
      btn.addEventListener('click', function() {
        var cb = _posPick && _posPick.onConfirm;
        closePosPickModal();
        if (cb) cb(pos);
      });
      opts.appendChild(btn);
    });
    document.getElementById('pos-pick-modal').classList.remove('hidden');
  }

  function closePosPickModal() {
    document.getElementById('pos-pick-modal').classList.add('hidden');
    _posPick = null;
  }

  function doUseHeldItemApi(heldId, targetCardId, targetYear, discardOnly, newPos) {
    apiPost('/api/nba_balatro/use_held_item', {
      game_id: gameId,
      held_id: heldId,
      target_card_id: targetCardId || null,
      target_year: targetYear || null,
      discard_only: discardOnly,
      new_pos: newPos || null,
    }).then(function(data) {
      if (data.error) { showToast(data.error, 'error'); return; }
      gs.heldItems = data.held_items || [];
      if (data.hand) gs.hand = data.hand;
      if (data.skill_levels) gs.skillLevels = data.skill_levels;
      if (data.combo_boosts) gs.comboBoosts = data.combo_boosts;
      if (data.card_effects) gs.cardEffects = data.card_effects;
      if (data.max_hand_size) gs.maxHandSize = data.max_hand_size;
      if (data.base_discards) gs.baseDiscards = data.base_discards;
      if (data.max_jokers) gs.maxJokers = data.max_jokers;
      if (data.deck_pool) gs.deckPool = data.deck_pool;
      renderHeldItems();
      renderHand();
      renderTopBar();
      showToast(discardOnly ? 'Discarded' : 'Used!', discardOnly ? 'info' : 'success');
    }).catch(function() { showToast('Error', 'error'); });
  }

  function renderShopJokers() {
    if (!els.shopJokersSect) return;
    els.shopJokersSect.innerHTML = '';
    if (gs.jokers.length === 0) return;

    var header = document.createElement('div');
    header.className = 'shop-section-header';
    header.style.cssText = 'margin-bottom:10px;padding-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.12);';
    header.innerHTML = '<span class="shop-section-title" style="color:#9b59b6;">YOUR LOCKER</span><span style="font-size:0.6rem;color:var(--nb-dim);margin-left:auto;font-family:Arial,sans-serif;">click SELL to sell</span>';
    els.shopJokersSect.appendChild(header);

    var row = document.createElement('div');
    row.style.cssText = 'display:flex;gap:8px;flex-wrap:wrap;';
    gs.jokers.forEach(function (j) {
      var slot = document.createElement('div');
      slot.className = 'joker-slot filled';
      _buildJokerSlotContent(slot, j, 'shopping');
      row.appendChild(slot);
    });
    els.shopJokersSect.appendChild(row);
  }

  function _buildJokerSlotContent(slot, j, screenStatus) {
    var img = document.createElement('img');
    img.className = 'joker-fan-img';
    img.src = '/static/img/basketball_fan.png';
    img.alt = 'Fan';
    slot.appendChild(img);

    var dot = document.createElement('div');
    dot.className = 'joker-rarity-dot dot-' + (j.rarity || 'common');
    slot.appendChild(dot);

    var name = document.createElement('div');
    name.className = 'joker-name';
    name.textContent = j.name;
    slot.appendChild(name);

    var tooltip = document.createElement('div');
    tooltip.className = 'joker-desc-tooltip';
    tooltip.textContent = j.desc;
    slot.appendChild(tooltip);

    // Enhancement badges
    var enhs = gs.jokerEnhancements[j.id] || [];
    if (enhs.length > 0) {
      var enhDiv = document.createElement('div');
      enhDiv.className = 'joker-enhancements';
      var enhLabels = { 'boost_sticker': 'BOOST', 'multiplier_sticker': 'MULT', 'echo_sticker': 'ECHO', 'gold_wire': 'GOLD' };
      enhs.forEach(function(enh) {
        var span = document.createElement('span');
        span.className = 'joker-enh-badge';
        span.textContent = enhLabels[enh] || enh;
        span.title = enh.replace(/_/g, ' ');
        enhDiv.appendChild(span);
      });
      slot.appendChild(enhDiv);
    }

    // Sell button - available in shopping and playing
    var sellPrice = ({common: 2, uncommon: 3, rare: 4})[j.rarity] || 2;
    var jokerId = j.id;

    var sellBtn = document.createElement('button');
    sellBtn.className = 'joker-sell-btn';
    sellBtn.textContent = 'SELL';
    sellBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      slot.classList.add('sell-confirming');
    });
    slot.appendChild(sellBtn);

    var confirmOverlay = document.createElement('div');
    confirmOverlay.className = 'joker-sell-confirm';
    var cancelBtn = document.createElement('button');
    cancelBtn.className = 'joker-sell-cancel';
    cancelBtn.textContent = '✕';
    cancelBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      slot.classList.remove('sell-confirming');
    });
    var okBtn = document.createElement('button');
    okBtn.className = 'joker-sell-ok';
    okBtn.textContent = '$' + sellPrice;
    okBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      slot.classList.remove('sell-confirming');
      sellJoker(jokerId);
    });
    confirmOverlay.appendChild(cancelBtn);
    confirmOverlay.appendChild(okBtn);
    slot.appendChild(confirmOverlay);
  }

  function renderHand() {
    if (currentSort) {
      _applySortToHand(currentSort);
    }
    els.handCards.innerHTML = '';
    gs.hand.forEach(function (card) {
      var cardEl = buildCardEl(card);
      // Drag-to-reorder hand cards
      cardEl.setAttribute('draggable', 'true');
      cardEl.addEventListener('dragstart', function(e) {
        _isDragging = true;
        dragCardId = card.id;
        e.dataTransfer.effectAllowed = 'move';
        cardEl.classList.add('dragging');
      });
      cardEl.addEventListener('dragend', function() {
        _isDragging = false;
        dragCardId = null;
        cardEl.classList.remove('dragging');
      });
      cardEl.addEventListener('dragover', function(e) {
        e.preventDefault();
        cardEl.classList.add('drag-over');
      });
      cardEl.addEventListener('dragleave', function() {
        cardEl.classList.remove('drag-over');
      });
      cardEl.addEventListener('drop', function(e) {
        e.preventDefault();
        cardEl.classList.remove('drag-over');
        if (!dragCardId || dragCardId === card.id) return;
        var fromIdx = gs.hand.findIndex(function(c) { return c.id === dragCardId; });
        var toIdx = gs.hand.findIndex(function(c) { return c.id === card.id; });
        if (fromIdx === -1 || toIdx === -1) return;
        var tmp = gs.hand[fromIdx];
        gs.hand[fromIdx] = gs.hand[toIdx];
        gs.hand[toIdx] = tmp;
        dragCardId = null;
        renderHand();
      });
      els.handCards.appendChild(cardEl);
    });
  }

  var POS_ICON = { G: 'G', F: 'F', C: 'C' };

  function buildCardEl(card, opts) {
    opts = opts || {};
    var posClass = 'card-pos-' + card.pos.toLowerCase();
    var el = document.createElement('div');
    el.className = 'card ' + posClass;
    el.dataset.id = card.id;
    el.dataset.cardId = card.id;

    // Apply card effects classes
    var effects = opts.overrideEffects !== undefined ? opts.overrideEffects : (gs.cardEffects[card.id] || []);
    if (effects.indexOf('gold') !== -1) el.classList.add('card-gold');
    if (effects.indexOf('glass') !== -1) el.classList.add('card-glass');
    if (effects.indexOf('foil') !== -1) el.classList.add('card-foil');
    if (effects.indexOf('trained') !== -1) el.classList.add('card-trained');

    if (!opts.noSelect && gs.selectedIds.has(card.id)) {
      el.classList.add('selected');
    }

    // Card inner (for 3D flip)
    var inner = document.createElement('div');
    inner.className = 'card-inner';

    // ── Card Front ──────────────────────────────────────────────────
    var front = document.createElement('div');
    front.className = 'card-front';

    // Player name split
    var parts = card.player.split(' ');
    var firstName = parts[0] || '';
    var lastName = parts.slice(1).join(' ') || firstName;
    if (parts.length === 1) { firstName = ''; lastName = parts[0]; }

    // ── Top row: [Year · Team / Name box] [Stars / Points box] ──────
    var topRow = document.createElement('div');
    topRow.className = 'card-top-row';

    // Left: name box
    var nameBox = document.createElement('div');
    nameBox.className = 'card-name-box';

    var yearLine = document.createElement('div');
    yearLine.className = 'card-year-line';
    yearLine.textContent = (card.season ? "'" + String(nbaYear(card.season)).slice(-2) : '') +
                           (card.team ? ' · ' + card.team : '');
    nameBox.appendChild(yearLine);

    if (firstName) {
      var nameFirst = document.createElement('div');
      nameFirst.className = 'card-player-first';
      nameFirst.textContent = firstName;
      nameBox.appendChild(nameFirst);
    }
    var nameLast = document.createElement('div');
    nameLast.className = 'card-player-last';
    nameLast.textContent = lastName;
    nameBox.appendChild(nameLast);
    topRow.appendChild(nameBox);

    // Right: stars box + score box
    var topRight = document.createElement('div');
    topRight.className = 'card-top-right';

    if (card.allstar_count && card.allstar_count > 0) {
      var starsBox = document.createElement('div');
      starsBox.className = 'card-stars-box';
      starsBox.textContent = '★'.repeat(Math.min(card.allstar_count, 5));
      starsBox.title = card.allstar_count + 'x NBA All-Star';
      topRight.appendChild(starsBox);
    }
    var scoreBox = document.createElement('div');
    scoreBox.className = 'card-score-box';
    scoreBox.textContent = card.fantasy_pts !== undefined ? String(Math.round(card.fantasy_pts)) : '';
    topRight.appendChild(scoreBox);
    topRow.appendChild(topRight);

    front.appendChild(topRow);

    // Effect badges (absolute overlay on headshot)
    if (effects.length > 0) {
      var badgesDiv = document.createElement('div');
      badgesDiv.className = 'card-effect-badges';
      effects.forEach(function (eff) {
        var b = document.createElement('span');
        b.className = 'effect-badge effect-' + eff;
        b.textContent = eff === 'gold' ? 'GD' : eff === 'glass' ? 'GL' : eff === 'trained' ? 'TR' : 'FO';
        badgesDiv.appendChild(b);
      });
      front.appendChild(badgesDiv);
    }

    // ── Headshot ─────────────────────────────────────────────────────
    var headshotDiv = document.createElement('div');
    headshotDiv.className = 'card-headshot';

    var img = document.createElement('img');
    img.alt = '';
    img.className = 'card-headshot-img card-headshot-loading';
    img.onload = function() { this.classList.remove('card-headshot-loading'); };
    if (card.headshot_url) {
      img.onerror = function() {
        this.onerror = null;
        this.classList.add('card-headshot-blank');
        this.src = '/static/img/blank_player.png';
      };
      img.src = card.headshot_url;
    } else {
      img.classList.add('card-headshot-blank');
      img.src = '/static/img/blank_player.png';
    }
    headshotDiv.appendChild(img);

    // Flip button overlaid on headshot
    var flipBtn = document.createElement('button');
    flipBtn.className = 'card-flip-btn';
    flipBtn.title = 'View stats';
    flipBtn.textContent = '↩';
    headshotDiv.appendChild(flipBtn);

    front.appendChild(headshotDiv);

    // ── Bottom row: [Division]  [Position] ───────────────────────────
    var bottomRow = document.createElement('div');
    bottomRow.className = 'card-bottom-row';

    var divWrapper = document.createElement('div');
    divWrapper.className = 'card-footer-div';
    var divInfo = getNbaDivInfo(card.team || '');
    if (divInfo || card._stickerCls) {
      if (divInfo && card._stickerCls) {
        var divBadgeEl = document.createElement('div');
        divBadgeEl.className = 'card-div-badge ' + divInfo.cls + ' div-badge-faded';
        divBadgeEl.textContent = divInfo.label;
        divWrapper.appendChild(divBadgeEl);
        var stickerEl = document.createElement('div');
        stickerEl.className = 'card-div-badge card-div-sticker ' + card._stickerCls;
        stickerEl.textContent = card._stickerLabel || card.division || '';
        divWrapper.appendChild(stickerEl);
      } else {
        var badgeEl = document.createElement('div');
        var bInfo = divInfo || { cls: card._stickerCls, label: card._stickerLabel };
        badgeEl.className = 'card-div-badge ' + (bInfo.cls || '');
        badgeEl.textContent = bInfo.label || '';
        divWrapper.appendChild(badgeEl);
      }
    }
    bottomRow.appendChild(divWrapper);

    var posBadge = document.createElement('span');
    posBadge.className = 'card-pos-badge';
    posBadge.textContent = card.pos;
    bottomRow.appendChild(posBadge);

    front.appendChild(bottomRow);

    // ── Card Back ───────────────────────────────────────────────────
    var back = document.createElement('div');
    back.className = 'card-back';
    back.innerHTML = '<div class="card-back-loading">...</div>';

    // Assemble
    inner.appendChild(front);
    inner.appendChild(back);
    el.appendChild(inner);

    // Restore flipped state from set
    if (flippedCardIds.has(card.id)) {
      el.classList.add('flipped');
      fetchAndShowCardBack(back, card);
    }

    // Flip button click
    flipBtn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (flippedCardIds.has(card.id)) {
        flippedCardIds.delete(card.id);
        el.classList.remove('flipped');
      } else {
        flippedCardIds.add(card.id);
        el.classList.add('flipped');
        fetchAndShowCardBack(back, card);
      }
    });

    // Card click — select/deselect (not when clicking flip btn)
    if (!opts.noSelect) {
      el.addEventListener('click', function (e) {
        if (e.target === flipBtn || flipBtn.contains(e.target)) return;
        // Ignore click if it was preceded by a drag
        if (_isDragging) { _isDragging = false; return; }
        // Clicking a flipped card body → unflip it
        if (flippedCardIds.has(card.id)) {
          flippedCardIds.delete(card.id);
          el.classList.remove('flipped');
          return;
        }
        toggleCardSelect(card.id);
      });
    } else if (opts.onSelect) {
      el.addEventListener('click', function (e) {
        if (e.target === flipBtn || flipBtn.contains(e.target)) return;
        // Clicking a flipped card body → unflip it
        if (flippedCardIds.has(card.id)) {
          flippedCardIds.delete(card.id);
          el.classList.remove('flipped');
          return;
        }
        opts.onSelect(card);
      });
      el.style.cursor = 'pointer';
    }

    return el;
  }

  function toggleCardSelect(cardId) {
    if (gs.status !== 'playing') return;
    if (_animLock) return;
    if (window.SFX) SFX.play('card_sel');
    if (gs.selectedIds.has(cardId)) {
      gs.selectedIds.delete(cardId);
    } else {
      if (gs.selectedIds.size >= 5) return;
      gs.selectedIds.add(cardId);
    }
    renderHand();
    renderActionButtons();
    getScorePreview(Array.from(gs.selectedIds));
  }

  function renderActionButtons() {
    var n = gs.selectedIds.size;
    var isPlaying = gs.status === 'playing';
    els.playBtn.disabled = !isPlaying || n === 0;
    els.discardBtn.disabled = !isPlaying || n === 0 || gs.discardsRemaining <= 0;
  }

  function renderPreview(data) {
    els.previewType.textContent = data.hand_name || '';
    els.previewType.classList.add('active');

    var html = '';
    html += '<div class="preview-chunk">';
    html += '<span class="preview-label">Base</span>';
    html += '<span class="preview-val">' + (data.base_pts || 0) + '</span>';
    html += '</div>';
    html += '<span style="color:var(--nb-border)">×</span>';
    html += '<div class="preview-chunk">';
    html += '<span class="preview-label">Mult</span>';
    html += '<span class="preview-val">' + (data.total_mult || 0) + '</span>';
    html += '</div>';
    html += '<span style="color:var(--nb-border)">=</span>';
    html += '<div class="preview-chunk">';
    html += '<span class="preview-total">~' + formatNum(data.score || 0) + '</span>';
    html += '</div>';
    els.previewDets.innerHTML = html;
  }

  function clearPreview() {
    els.previewType.textContent = 'Select up to 6 cards to see hand type';
    els.previewType.classList.remove('active');
    els.previewDets.innerHTML = '';
  }

  // ── Score Popup ────────────────────────────────────────────────────
  function showScorePopup(score, handName, basePts, mult) {
    var popup = els.scorePopup;
    popup.classList.remove('hidden', 'showing');

    popup.innerHTML =
      '<div class="popup-hand-name">' + escHtml(handName || '') + '</div>' +
      '<div class="popup-score">+' + formatNum(score) + '</div>' +
      '<div class="popup-details">' + (basePts || 0) + ' pts × ' + (mult || 0) + 'x mult</div>';

    void popup.offsetWidth;
    popup.classList.add('showing');

    setTimeout(function () {
      popup.classList.add('hidden');
      popup.classList.remove('showing');
    }, 2300);
  }

  // ── Play Log ───────────────────────────────────────────────────────
  function addLogEntry(text, score, hasCoin) {
    var entry = document.createElement('div');
    entry.className = 'log-entry log-good';
    if (hasCoin) entry.classList.add('log-coin');
    entry.textContent = text;
    els.playLog.appendChild(entry);
    var entries = els.playLog.querySelectorAll('.log-entry');
    if (entries.length > 6) {
      entries[0].remove();
    }
  }

  function clearLog() {
    els.playLog.innerHTML = '';
  }

  // ── Toast ──────────────────────────────────────────────────────────
  function showToast(msg, type) {
    var existing = document.querySelector('.toast');
    if (existing) existing.remove();
    var t = document.createElement('div');
    t.className = 'toast' + (type === 'error' ? ' toast-error' : '');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 2500);
  }

  // ── Reward Screen (level/boss win) ─────────────────────────────────
  function showRewardScreen() {
    var titleEl = document.getElementById('reward-title');
    if (titleEl) titleEl.textContent = 'ROUND COMPLETE!';
    var subMsg = document.getElementById('reward-sub-msg');
    if (subMsg) subMsg.textContent = '';
    showScreen('reward');
  }

  function showFightRewardScreen(data) {
    if (window.SFX) SFX.play('reward');
    var isBossWin = (gs.fight === 3);
    var titleEl = document.getElementById('reward-title');
    if (titleEl) titleEl.textContent = isBossWin ? 'ROUND COMPLETE!' : 'FIGHT COMPLETE!';

    var subMsg = document.getElementById('reward-sub-msg');
    if (subMsg) subMsg.textContent = 'Choose your reward';

    // Coins option
    var coinsVal = document.getElementById('reward-coins-value');
    if (coinsVal) coinsVal.textContent = '$' + (data.reward_coins_amount || 0);

    // Joker options
    var jokerGrid = document.getElementById('reward-joker-options');
    if (jokerGrid) {
      jokerGrid.innerHTML = '';
      var jokerOpts = data.reward_joker_options || [];
      jokerOpts.forEach(function(j) {
        var btn = document.createElement('div');
        btn.className = 'reward-joker-option';
        var rarityClass = 'rarity-' + (j.rarity || 'common');
        btn.innerHTML = '<div class="rjo-name ' + rarityClass + '">' + escHtml(j.name) + '</div>' +
                        '<div class="rjo-desc">' + escHtml(j.desc) + '</div>';
        btn.onclick = (function(jid) { return function() { claimRewardJoker(jid); }; })(j.id);
        jokerGrid.appendChild(btn);
      });
      // Disable joker option if full
      var jokerCard = document.getElementById('reward-choice-joker');
      if (jokerCard) {
        var isFull = gs.jokers.length >= gs.maxJokers;
        jokerCard.classList.toggle('reward-choice-disabled', isFull);
        if (isFull) {
          var fullNote = document.createElement('div');
          fullNote.className = 'reward-full-note';
          fullNote.textContent = 'Fan slots full!';
          jokerGrid.appendChild(fullNote);
        }
      }
    }

    // Boss warning
    var bossWarn = document.getElementById('reward-boss-warning');
    if (bossWarn) {
      if (data.next_boss_effect) {
        bossWarn.textContent = '! NEXT: BOSS — ' + escHtml(data.next_boss_effect.name);
        bossWarn.classList.remove('hidden');
      } else if (isBossWin) {
        bossWarn.textContent = 'Advancing to next round!';
        bossWarn.classList.remove('hidden');
      } else {
        bossWarn.classList.add('hidden');
      }
    }

    showScreen('reward');
  }

  // ── Shop Screen ────────────────────────────────────────────────────
  function showShopScreen() {
    showScreen('shop');
    renderShop();
  }

  // ── Shop item icon/bg config ────────────────────────────────────
  var ITEM_ICON = {
    joker: 'Fan', skill_card: 'Skill', combo_card: 'CMB', effect_card: 'Effect',
    year_card: 'YR', cut_card: 'CUT', upgrade: 'UP', mod_card: 'MOD',
    joker_enhancement: 'ENH', buy_card: 'PLR',
  };
  var POS_BG = { G: '#0a1e40', F: '#1a2e10', C: '#3a0a1a' };
  var ITEM_BG = {
    joker: '#1e0a40', skill_card: '#0a1e3c', combo_card: '#0a1e3c',
    effect_card: '#0a1e3c', year_card: '#0a1e3c', cut_card: '#2e0a10',
    upgrade: '#0a2e12', mod_card: '#0a2e12', joker_enhancement: '#0a2e12',
    buy_card: '#2e1500',
  };
  var ITEM_TYPE_LABEL = {
    joker: 'FAN', skill_card: 'SKILL', combo_card: 'COMBO',
    effect_card: 'EFFECT', year_card: 'SEASON', cut_card: 'RELEASE',
    upgrade: 'UPGRADE', mod_card: 'MOD', joker_enhancement: 'ENHANCE',
    buy_card: 'PLAYER CARD',
  };
  var VENDOR_LINES = [
    'Stock up before tip-off!',
    'Fresh talent just arrived!',
    'Get \'em while they last!',
    'Best roster in the league!',
    'Playoffs gear is here!',
    'Limited stock — act fast!',
    'Today\'s deals won\'t last!',
    'Draft your dream team!',
    'Championship season calls!',
    'That last quarter was ELITE!',
    'Running low on coins? Choose wisely!',
    'A new fan could change everything!',
    'Trust the process. Buy the pack.',
    'Your opponents are upgrading — are you?',
    'Every great offense needs a playmaker!',
    'Stack your fans before the boss round!',
    'You\'re one pack away from a dynasty.',
    'The best time to restock is NOW!',
    'I\'ve seen your lineup. You need this.',
  ];

  function buildShopItemEl(item, isPack) {
    var el = document.createElement('div');
    el.className = 'shop-item';

    if (item.sold) {
      el.classList.add('sold');
      var soldLbl = document.createElement('div');
      soldLbl.className = 'shop-item-sold-label';
      soldLbl.textContent = 'SOLD OUT';
      el.appendChild(soldLbl);
      return el;
    }

    var canAfford = gs.coins >= item.cost;
    if (!canAfford) el.classList.add('cant-afford');

    // Price badge floating above card
    var priceBadge = document.createElement('div');
    priceBadge.className = 'shop-price-badge' + (canAfford ? '' : ' cant-afford');
    priceBadge.textContent = '$' + item.cost;
    el.appendChild(priceBadge);

    // Icon area
    var iconArea = document.createElement('div');
    iconArea.className = 'shop-item-icon-area';
    if (isPack) {
      iconArea.style.background = 'linear-gradient(135deg, #1a0a2e, #0a1a3e)';
    } else {
      var pos = item.card_data ? item.card_data.pos : null;
      var bg = pos ? (POS_BG[pos] || ITEM_BG[item.type] || '#1a1a3e') : (ITEM_BG[item.type] || '#1a1a3e');
      iconArea.style.background = 'linear-gradient(135deg, ' + bg + ', #1a1a3e)';
    }

    if (!isPack && item.type === 'joker') {
      var fanImg = document.createElement('img');
      fanImg.src = '/static/img/basketball_fan.png';
      fanImg.alt = 'Fan';
      fanImg.style.cssText = 'width:44px;height:44px;object-fit:cover;border-radius:50%;border:2px solid rgba(0,0,0,0.3);';
      iconArea.appendChild(fanImg);
    } else {
      var iconEmoji = document.createElement('span');
      if (isPack) {
        iconEmoji.textContent = 'Pack';
      } else if (item.type === 'buy_card' && item.card_data && item.card_data.fantasy_pts != null) {
        iconEmoji.textContent = item.card_data.fantasy_pts;
        iconEmoji.style.fontSize = '1.1rem';
        iconEmoji.style.fontFamily = 'Impact, sans-serif';
        iconEmoji.style.fontWeight = '900';
      } else {
        var pos2 = item.card_data ? item.card_data.pos : null;
        iconEmoji.textContent = (pos2 && POS_ICON[pos2]) ? POS_ICON[pos2] : (ITEM_ICON[item.type] || 'ITM');
      }
      iconArea.appendChild(iconEmoji);
    }

    // Rarity bar
    if (item.rarity) {
      var rarBar = document.createElement('div');
      rarBar.className = 'shop-item-rarity-bar';
      var rarColors = { common: '#7ab87a', uncommon: '#5599ee', rare: '#cc44ee', legendary: '#f5c700' };
      rarBar.style.background = rarColors[item.rarity] || 'transparent';
      iconArea.appendChild(rarBar);
    }

    el.appendChild(iconArea);

    // Body
    var body = document.createElement('div');
    body.className = 'shop-item-body';

    var typeLabel = isPack ? 'PACK' : (ITEM_TYPE_LABEL[item.type] || (item.type || 'ITEM').toUpperCase());
    if (item.tier_name) typeLabel += ' · ' + item.tier_name;
    var typeEl = document.createElement('div');
    typeEl.className = 'shop-item-type';
    typeEl.textContent = typeLabel;
    body.appendChild(typeEl);

    var nameEl = document.createElement('div');
    nameEl.className = 'shop-item-name';
    nameEl.textContent = item.name;
    body.appendChild(nameEl);

    var descEl = document.createElement('div');
    descEl.className = 'shop-item-desc';
    descEl.textContent = item.desc;
    body.appendChild(descEl);

    el.appendChild(body);

    // Footer
    var footer = document.createElement('div');
    footer.className = 'shop-item-footer';

    var buyBtn = document.createElement('button');
    buyBtn.className = 'btn-buy';
    buyBtn.textContent = canAfford ? (isPack ? 'OPEN' : 'BUY') : 'NO $';
    buyBtn.disabled = !canAfford;
    footer.appendChild(buyBtn);
    el.appendChild(footer);

    return el;
  }

  function renderShop() {
    if (els.shopCoinsCount) els.shopCoinsCount.textContent = gs.coins;

    var nextRestockCost = 2 + (gs.restockCount || 0) * 2;
    if (els.restockCost) els.restockCost.textContent = '$' + nextRestockCost;

    // Random vendor line
    var vendorBubble = document.getElementById('vendor-bubble');
    if (vendorBubble) {
      vendorBubble.textContent = VENDOR_LINES[Math.floor(Math.random() * VENDOR_LINES.length)];
    }

    renderShopJokers();

    var cont = els.shopItemsCont;
    cont.innerHTML = '';

    // Bucket items into sections using item.section field
    var sections = [
      { key: 'roster',   label: 'FANS & PLAYERS',  icon: '', color: '#9b59b6', items: [] },
      { key: 'training', label: 'SKILLS & UPGRADES',  icon: '', color: '#27ae60', items: [] },
      { key: 'packs',    label: 'PACKS',              icon: '', color: '#e74c3c', items: [] },
    ];
    var sectionMap = {};
    sections.forEach(function(s) { sectionMap[s.key] = s; });

    (gs.shopItems || []).forEach(function(item) {
      var sec = item.section || 'training';
      if (sectionMap[sec]) {
        sectionMap[sec].items.push({ item: item, isPack: false });
      }
    });

    (gs.shopPacks || []).forEach(function(pack) {
      sectionMap.packs.items.push({ item: pack, isPack: true });
    });

    sections.forEach(function(section) {
      if (section.items.length === 0) return;

      var sectionEl = document.createElement('div');
      sectionEl.className = 'shop-section';
      sectionEl.style.setProperty('--section-color', section.color);

      var header = document.createElement('div');
      header.className = 'shop-section-header';
      header.innerHTML =
        '<span class="shop-section-icon">' + section.icon + '</span>' +
        '<span class="shop-section-title">' + section.label + '</span>';
      sectionEl.appendChild(header);

      var grid = document.createElement('div');
      grid.className = 'shop-section-items';

      section.items.forEach(function(entry) {
        var el = buildShopItemEl(entry.item, entry.isPack);
        // Wire up buy button
        if (!entry.item.sold) {
          var btn = el.querySelector('.btn-buy');
          if (btn) {
            (function(it, isPk) {
              btn.addEventListener('click', function() {
                if (isPk) {
                  buyPack(it.id);
                } else {
                  buyShopItem(it.shop_id, it.type, !!it.needs_target, it);
                }
              });
            })(entry.item, entry.isPack);
          }
        }
        grid.appendChild(el);
      });

      sectionEl.appendChild(grid);
      cont.appendChild(sectionEl);
    });
  }

  // ── Target Selection (via Deck Viewer) ────────────────────────────
  function openTargetModal(item) {
    openDeckViewerForSelection(item.desc || 'Select a card to apply this effect.', function(selectedCard) {
      var pending = gs.pendingShopItem;
      if (!pending) return;
      gs.pendingShopItem = null;
      if (pending.item && pending.item.type === 'year_card') {
        openYearSelectModal(pending.shopId, pending.itemType, selectedCard.id, selectedCard.player, selectedCard.season);
      } else {
        executeBuy(pending.shopId, pending.itemType, selectedCard.id, null);
      }
    });
  }

  function closeTargetModal() {
    // Deck viewer replaced the old target modal — close deck viewer + clear state
    _deckSelectCallback = null;
    gs.pendingShopItem = null;
    if (els.deckViewerOverlay) {
      var titleEl = els.deckViewerOverlay.querySelector('.deck-viewer-title');
      if (titleEl) titleEl.textContent = 'YOUR DECK';
      els.deckViewerOverlay.classList.add('hidden');
    }
  }

  // ── Year Select Modal ──────────────────────────────────────────────
  function openYearSelectModal(shopId, itemType, cardId, playerName, currentSeason) {
    pendingYearTarget = { shopId: shopId, itemType: itemType, cardId: cardId };
    if (els.yearModalPlayer) els.yearModalPlayer.textContent = 'Choose a season for ' + playerName;
    if (els.yearListCont) els.yearListCont.innerHTML = '<div class="loading-msg">Loading seasons...</div>';
    els.yearSelectModal.classList.remove('hidden');

    apiGet('/api/nba_balatro/player_seasons?game_id=' + encodeURIComponent(gameId) + '&card_id=' + encodeURIComponent(cardId))
      .then(function (data) {
        if (data.error) { alert(data.error); closeYearModal(); return; }
        renderYearList(data.seasons || [], data.current_season || currentSeason);
      })
      .catch(function (e) { alert('Error: ' + e); closeYearModal(); });
  }

  function renderYearList(seasons, currentSeason) {
    if (!els.yearListCont) return;
    els.yearListCont.innerHTML = '';
    if (seasons.length === 0) {
      els.yearListCont.innerHTML = '<div class="loading-msg">No seasons found</div>';
      return;
    }
    var list = document.createElement('div');
    list.className = 'year-list';
    seasons.forEach(function (s) {
      var opt = document.createElement('div');
      opt.className = 'year-option' + (s.season === currentSeason ? ' current' : '');
      opt.innerHTML =
        '<span class="year-num">' + nbaYear(s.season) + '</span>' +
        '<span class="year-team">' + escHtml(s.team || '') + '</span>' +
        '<span class="year-ppr">' + s.fantasy_pts + ' FPT</span>';
      (function (season) {
        opt.addEventListener('click', function () {
          selectYear(season);
        });
      })(s.season);
      list.appendChild(opt);
    });
    els.yearListCont.appendChild(list);
  }

  function selectYear(year) {
    if (!pendingYearTarget) return;
    executeBuy(pendingYearTarget.shopId, pendingYearTarget.itemType, pendingYearTarget.cardId, { target_year: year });
    pendingYearTarget = null;
    closeYearModal();
  }

  function closeYearModal() {
    if (els.yearSelectModal) els.yearSelectModal.classList.add('hidden');
    pendingYearTarget = null;
  }

  // ── Stats Overlay ──────────────────────────────────────────────────
  function toggleStatsOverlay() {
    if (els.statsOverlay.classList.contains('hidden')) {
      renderStatsOverlay();
      els.statsOverlay.classList.remove('hidden');
    } else {
      els.statsOverlay.classList.add('hidden');
    }
  }

  function renderStatsOverlay() {
    var cont = els.statsBars;
    cont.innerHTML = '';

    var POS_COLORS = { G: 'g', F: 'f', C: 'c' };
    var BASE_MULTS = { G: 1.0, F: 1.5, C: 2.5 };

    POS_ORDER.forEach(function (pos) {
      var level = gs.skillLevels[pos] || 0;
      var ptsBoost = Math.round(level * 8);
      var multBonus = (level * 0.12).toFixed(2);
      var baseMult = BASE_MULTS[pos];
      var effMult = (baseMult + level * 0.12).toFixed(2);
      var barFill = Math.min(10, level);

      var row = document.createElement('div');
      row.className = 'stats-row';

      var posLabel = document.createElement('div');
      posLabel.className = 'stats-pos-badge pos-badge-' + POS_COLORS[pos];
      posLabel.textContent = pos;
      row.appendChild(posLabel);

      var info = document.createElement('div');
      info.className = 'stats-info';

      var levelLabel = document.createElement('div');
      levelLabel.className = 'stats-level';
      levelLabel.textContent = 'Level ' + level;
      info.appendChild(levelLabel);

      var barWrap = document.createElement('div');
      barWrap.className = 'stats-bar-wrap';
      for (var i = 0; i < 10; i++) {
        var seg = document.createElement('div');
        seg.className = 'stats-bar-seg' + (i < barFill ? ' filled pos-fill-' + POS_COLORS[pos] : '');
        barWrap.appendChild(seg);
      }
      info.appendChild(barWrap);

      var boosts = document.createElement('div');
      boosts.className = 'stats-boosts';
      boosts.textContent = '+' + ptsBoost + '% Pts  ×' + effMult + ' Mult';
      info.appendChild(boosts);

      row.appendChild(info);
      cont.appendChild(row);
    });

    // Show hand size and discards
    var extraRow = document.createElement('div');
    extraRow.className = 'stats-row';
    extraRow.style.flexDirection = 'column';
    extraRow.style.alignItems = 'flex-start';
    extraRow.innerHTML =
      '<div class="stats-boosts" style="margin-bottom:4px">Hand Size: ' + (gs.maxHandSize || 9) + ' cards</div>' +
      '<div class="stats-boosts">Discards/Level: ' + (gs.baseDiscards || 3) + '</div>';
    cont.appendChild(extraRow);
  }

  // ── Deck Viewer ────────────────────────────────────────────────────
  var _deckSelectCallback = null;

  function openDeckViewerForSelection(desc, callback) {
    _deckSelectCallback = callback;
    if (!els.deckViewerOverlay) return;
    var titleEl = els.deckViewerOverlay.querySelector('.deck-viewer-title');
    if (titleEl) titleEl.textContent = desc || 'Select a Card';
    renderDeckViewer();
    els.deckViewerOverlay.classList.remove('hidden');
  }

  function toggleDeckViewer() {
    if (!els.deckViewerOverlay) return;
    if (els.deckViewerOverlay.classList.contains('hidden')) {
      _deckSelectCallback = null;
      var titleEl = els.deckViewerOverlay.querySelector('.deck-viewer-title');
      if (titleEl) titleEl.textContent = 'YOUR DECK';
      renderDeckViewer();
      els.deckViewerOverlay.classList.remove('hidden');
    } else {
      _deckSelectCallback = null;
      var titleEl = els.deckViewerOverlay.querySelector('.deck-viewer-title');
      if (titleEl) titleEl.textContent = 'YOUR DECK';
      els.deckViewerOverlay.classList.add('hidden');
    }
  }

  function renderDeckViewer() {
    if (!els.deckViewerContent) return;
    var isSelectMode = !!_deckSelectCallback;
    var selectCallback = _deckSelectCallback;
    els.deckViewerContent.innerHTML = '<div class="loading-msg">Loading deck...</div>';

    // Fetch the current pool from server to ensure accuracy
    apiPost('/api/nba_balatro/get_pool', { game_id: gameId }).then(function (data) {
      if (data.error) {
        els.deckViewerContent.innerHTML = '<div class="loading-msg">Error loading deck</div>';
        return;
      }
      var pool = data.deck_pool || [];
      var serverEffects = data.card_effects || {};
      els.deckViewerContent.innerHTML = '';

      var byPos = { G: [], F: [], C: [] };
      pool.forEach(function (card) {
        if (byPos[card.pos]) byPos[card.pos].push(card);
      });

      var totalEl = document.createElement('div');
      totalEl.style.cssText = 'font-size:0.7rem;color:var(--nb-dim);letter-spacing:2px;text-transform:uppercase;margin-bottom:16px;';
      totalEl.textContent = isSelectMode ? 'Click a card to select it' : pool.length + ' cards in deck';
      els.deckViewerContent.appendChild(totalEl);

      POS_ORDER.forEach(function (pos) {
        var cards = byPos[pos];
        if (!cards || cards.length === 0) return;
        // Sort highest fantasy pts first
        cards.sort(function(a, b) { return b.fantasy_pts - a.fantasy_pts; });

        var group = document.createElement('div');
        group.className = 'deck-pos-group';

        var hdr = document.createElement('div');
        hdr.className = 'deck-pos-header pos-' + pos.toLowerCase();
        hdr.textContent = pos + ' (' + cards.length + ')';
        group.appendChild(hdr);

        var grid = document.createElement('div');
        grid.className = 'deck-cards-grid';

        cards.forEach(function (card) {
          var cardEffectsForCard = serverEffects[card.id] || [];
          var cardEl = buildCardEl(card, {
            noSelect: true,
            overrideEffects: cardEffectsForCard,
            onSelect: isSelectMode ? function(selectedCard) {
              _deckSelectCallback = null;
              var titleEl = els.deckViewerOverlay.querySelector('.deck-viewer-title');
              if (titleEl) titleEl.textContent = 'YOUR DECK';
              els.deckViewerOverlay.classList.add('hidden');
              selectCallback(selectedCard);
            } : null,
          });
          if (!isSelectMode) cardEl.style.cursor = 'default';
          grid.appendChild(cardEl);
        });

        group.appendChild(grid);
        els.deckViewerContent.appendChild(group);
      });
    }).catch(function () {
      els.deckViewerContent.innerHTML = '<div class="loading-msg">Error loading deck</div>';
    });
  }

  // ── Game Over Screen ───────────────────────────────────────────────
  function showGameOver(won, data) {
    if (window.SFX) SFX.play(won ? 'win' : 'lose');
    showScreen('gameover');
    var html = '';
    var isInfinity = gs.mode === 'infinity';
    var waveNum = (gs.round - 1) * 3 + gs.fight;
    if (won && !isInfinity) {
      html += '<div class="go-title win">CHAMPION!</div>';
      html += '<div class="go-sub">You defeated all 8 rounds!</div>';
    } else if (isInfinity) {
      html += '<div class="go-title lose">GAME OVER</div>';
      html += '<div class="go-sub">\u221e Survived ' + (waveNum - 1) + ' waves of infinity!</div>';
    } else {
      html += '<div class="go-title lose">GAME OVER</div>';
      html += '<div class="go-sub">The shot clock got you at level ' + gs.floor + '</div>';
    }

    html += '<div class="go-stats">';
    if (isInfinity) {
      html += '<div class="go-stat"><div class="go-stat-label">Waves Survived</div><div class="go-stat-val">' + (waveNum - 1) + '</div></div>';
    } else {
      html += '<div class="go-stat"><div class="go-stat-label">Level Reached</div><div class="go-stat-val">' + gs.floor + ' / 8</div></div>';
    }
    html += '<div class="go-stat"><div class="go-stat-label">Fans</div><div class="go-stat-val">' + gs.jokers.length + ' / 5</div></div>';
    html += '<div class="go-stat"><div class="go-stat-label">Final Score</div><div class="go-stat-val">' + formatNum(gs.currentScore) + '</div></div>';
    html += '<div class="go-stat"><div class="go-stat-label">Target</div><div class="go-stat-val">' + formatNum(gs.targetScore) + '</div></div>';
    html += '<div class="go-stat"><div class="go-stat-label">Coins</div><div class="go-stat-val">$' + gs.coins + '</div></div>';
    html += '</div>';

    els.gameoverContent.innerHTML = html;

    // Show infinity button only on a normal-mode win
    var existingInfBtn = document.getElementById('go-infinity-btn');
    if (existingInfBtn) existingInfBtn.remove();
    if (won && !isInfinity) {
      var infBtn = document.createElement('button');
      infBtn.id = 'go-infinity-btn';
      infBtn.className = 'btn-infinity';
      infBtn.textContent = '\u221e CONTINUE IN INFINITY MODE';
      infBtn.addEventListener('click', startInfinityMode);
      els.restartBtn.parentNode.insertBefore(infBtn, els.restartBtn);
    }
  }

  function startInfinityMode() {
    var infBtn = document.getElementById('go-infinity-btn');
    if (infBtn) infBtn.disabled = true;
    apiPost('/api/nba_balatro/start_infinity', { game_id: gameId }).then(function(data) {
      if (data.error) { alert(data.error); if (infBtn) infBtn.disabled = false; return; }
      gs.mode = 'infinity';
      gs.coins = data.coins !== undefined ? data.coins : gs.coins;
      gs.nextFight = data.next_fight || 1;
      gs.nextBossEffect = null;
      gs.status = data.status;
      showFightRewardScreen(data);
    }).catch(function(e) {
      alert('Error: ' + e);
      if (infBtn) infBtn.disabled = false;
    });
  }

  // ── Screen management ──────────────────────────────────────────────
  function showScreen(name) {
    ['start', 'game', 'reward', 'shop', 'gameover'].forEach(function (s) {
      var el = els[s + 'Screen'];
      if (el) el.classList.remove('active');
    });
    var target = els[name + 'Screen'];
    if (target) target.classList.add('active');
  }

  // ── Event listeners ────────────────────────────────────────────────
  var rewardCoinsBtn = document.getElementById('reward-choice-coins');
  if (rewardCoinsBtn) rewardCoinsBtn.addEventListener('click', claimRewardCoins);

  els.startBtn.addEventListener('click', startGame);

  els.playBtn.addEventListener('click', function () {
    if (!els.playBtn.disabled) playHand();
  });

  els.discardBtn.addEventListener('click', function () {
    if (!els.discardBtn.disabled) discardCards();
  });

  if (els.skipJokerBtn) {
    els.skipJokerBtn.addEventListener('click', function () {
      selectJoker('skip');
    });
  }

  els.restartBtn.addEventListener('click', function () {
    showScreen('start');
    gameId = null;
    gs.selectedIds = new Set();
    gs.history = [];
    cardStatsCache = {};
    clearLog();
    clearPreview();
  });

  els.leaveShopBtn.addEventListener('click', function () {
    leaveShop();
  });

  if (els.restockBtn) {
    els.restockBtn.addEventListener('click', function () {
      restockShop();
    });
  }

  // ── Utility ────────────────────────────────────────────────────────
  function formatNum(n) {
    return Math.round(n).toLocaleString('en-US');
  }

  function escHtml(str) {
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // ── Pack System ────────────────────────────────────────────────────
  function buyPack(packId) {
    apiPost('/api/nba_balatro/open_pack', { game_id: gameId, pack_id: packId })
      .then(function(data) {
        if (data.error) { showToast(data.error, 'error'); return; }
        gs.coins = data.coins;
        if (els.shopCoinsCount) els.shopCoinsCount.textContent = gs.coins;
        if (els.coinsCount) els.coinsCount.textContent = gs.coins;
        // Update card effects
        if (data.card_effects) {
          Object.assign(gs.cardEffects, data.card_effects);
        }
        showPackOpeningAnimation(data);
      });
  }

  var _packSelectedIds = [];
  var _packPicksAllowed = 1;
  var _pendingPackGameId = null;

  function showPackOpeningAnimation(data) {
    var modal = document.getElementById('pack-opening-modal');
    var title = document.getElementById('pack-opening-title');
    var reveal = document.getElementById('pack-cards-reveal');
    var msg = document.getElementById('pack-result-msg');
    var closeBtn = document.getElementById('pack-close-btn');

    _packSelectedIds = [];
    _packPicksAllowed = data.picks_allowed || 1;
    _pendingPackGameId = gameId;

    title.textContent = 'OPENING: ' + data.pack_name;
    reveal.innerHTML = '';
    msg.classList.add('hidden');
    closeBtn.classList.add('hidden');
    closeBtn.textContent = 'Confirm Picks (0/' + _packPicksAllowed + ')';
    modal.classList.remove('hidden');

    var isJokerPack = !!data.is_joker_pack;
    var candidates = data.candidates || data.new_cards || [];
    var effects = data.card_effects || {};

    // Create display elements (joker slots or player cards)
    var cardEls = candidates.map(function(item) {
      var wrapper = document.createElement('div');
      wrapper.className = 'pack-reveal-card';

      var displayEl;
      if (isJokerPack) {
        // Show as joker slot
        displayEl = document.createElement('div');
        displayEl.className = 'joker-slot filled';
        displayEl.style.width = '100%';
        displayEl.style.height = '100%';
        _buildJokerSlotContent(displayEl, item, 'shopping');
        // Remove sell button from pack display
        var sellBtn = displayEl.querySelector('.joker-sell-btn');
        if (sellBtn) sellBtn.remove();
      } else {
        displayEl = buildCardEl(item, { noSelect: true, overrideEffects: effects[item.id] || [] });
        displayEl.style.width = '100%';
        displayEl.style.height = '100%';
        displayEl.classList.add('flipped');
      }

      wrapper.appendChild(displayEl);
      reveal.appendChild(wrapper);

      // Click to select after reveal
      wrapper.addEventListener('click', function() {
        if (wrapper.classList.contains('pack-selecting')) {
          var itemId = item.id;
          var idx = _packSelectedIds.indexOf(itemId);
          if (idx !== -1) {
            _packSelectedIds.splice(idx, 1);
            wrapper.classList.remove('pack-selected');
          } else if (_packSelectedIds.length < _packPicksAllowed) {
            _packSelectedIds.push(itemId);
            wrapper.classList.add('pack-selected');
          }
          closeBtn.textContent = 'Confirm Picks (' + _packSelectedIds.length + '/' + _packPicksAllowed + ')';
          closeBtn.disabled = _packSelectedIds.length === 0;
        }
      });
      return { wrapper: wrapper, displayEl: displayEl, item: item, isJokerPack: isJokerPack };
    });

    // Animate: drop in face-down, then flip to reveal one by one
    var delay = 0;
    cardEls.forEach(function(entry) {
      setTimeout(function() { entry.wrapper.classList.add('dropping'); }, delay);
      delay += 300;
      if (!entry.isJokerPack) {
        setTimeout((function(de) { return function() { de.classList.remove('flipped'); }; })(entry.displayEl), delay + 400);
      }
      delay += 600;
    });

    // After all revealed: show selection prompt
    setTimeout(function() {
      msg.textContent = 'Pick ' + _packPicksAllowed + ' card' + (_packPicksAllowed > 1 ? 's' : '') + ' to add to your deck:';
      msg.classList.remove('hidden');
      closeBtn.classList.remove('hidden');
      closeBtn.disabled = true;
      cardEls.forEach(function(item) { item.wrapper.classList.add('pack-selecting'); });
    }, delay + 200);
  }

  function closePackModal() {
    if (_packSelectedIds.length === 0) {
      // Don't close if nothing selected
      showToast('Pick at least 1 card!', 'error');
      return;
    }
    var modal = document.getElementById('pack-opening-modal');
    apiPost('/api/nba_balatro/confirm_pack_picks', {
      game_id: _pendingPackGameId,
      selected_ids: _packSelectedIds,
    }).then(function(data) {
      if (data.error) { showToast(data.error, 'error'); return; }
      if (modal) modal.classList.add('hidden');
      if (data.added_jokers) {
        gs.jokers = data.jokers || gs.jokers;
        showToast(data.added_jokers.length + ' fan(s) added!');
        renderShopJokers();
      } else {
        showToast((data.added_cards || []).length + ' player(s) added to deck!');
      }
      renderShop();
    });
  }

  // ── Joker Enhancement System ───────────────────────────────────────
  function buyShopItemWithJokerTarget(shopId, itemType, item) {
    if (gs.jokers.length === 0) {
      showToast('No fans to enhance', 'error');
      return;
    }
    openJokerPickerModal(shopId, itemType, item);
  }

  function openJokerPickerModal(shopId, itemType, item) {
    // Reuse target modal with joker slots instead of player cards
    if (els.targetModalDesc) {
      els.targetModalDesc.textContent = (item && item.desc) ? item.desc + ' — Select a fan to enhance:' : 'Select a fan to enhance:';
    }
    if (els.targetCardsCont) {
      els.targetCardsCont.innerHTML = '';
      var row = document.createElement('div');
      row.style.cssText = 'display:flex;gap:10px;flex-wrap:wrap;justify-content:center;padding:12px;';
      gs.jokers.forEach(function(j) {
        var slot = document.createElement('div');
        slot.className = 'joker-slot filled';
        slot.style.cursor = 'pointer';
        _buildJokerSlotContent(slot, j, 'shopping');
        // Remove sell button from picker
        var sellBtn = slot.querySelector('.joker-sell-btn');
        if (sellBtn) sellBtn.remove();
        slot.addEventListener('click', function() {
          closeTargetModal();
          executeBuy(shopId, itemType, j.id, null);
        });
        row.appendChild(slot);
      });
      els.targetCardsCont.appendChild(row);
    }
    els.targetModal.classList.remove('hidden');
    gs.pendingShopItem = { shopId: shopId, itemType: itemType, item: item };
  }

  // ── Expose globals for inline HTML onclick handlers ────────────────
  window.sortHand = sortHand;
  window.toggleStatsOverlay = toggleStatsOverlay;
  window.closeTargetModal = closeTargetModal;
  window.closeYearModal = closeYearModal;
  window.toggleDeckViewer = toggleDeckViewer;
  window.closePackModal = closePackModal;
  window.closeDivisionStickerModal = closeDivisionStickerModal;
  window.closePosPickModal = closePosPickModal;

  // ── Init ───────────────────────────────────────────────────────────
  showScreen('start');

}());
