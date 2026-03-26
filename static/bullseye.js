/* ============================================================
   bullseye.js — Bullseye multiplayer game frontend
   Expects: window.SPORT = 'nba' | 'nfl'
   ============================================================ */

(function () {
  'use strict';

  const SPORT = window.SPORT || 'nba';
  const API = `/api/${SPORT}_bullseye`;
  const params = new URLSearchParams(window.location.search);
  const roomId = params.get('room_id');
  const TOKEN_KEY = 'fantasy-multiplayer-token';

  // ── State ──────────────────────────────────────────────────────────────────

  let gameState = null;
  let gameId = null;
  let searchDebounce = null;
  let pollTimer = null;

  function playerToken() {
    let value = sessionStorage.getItem(TOKEN_KEY);
    if (!value) {
      value = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem(TOKEN_KEY, value);
    }
    return value;
  }

  // ── Helpers ────────────────────────────────────────────────────────────────

  function $(sel, ctx) { return (ctx || document).querySelector(sel); }
  function $$(sel, ctx) { return Array.from((ctx || document).querySelectorAll(sel)); }

  function el(tag, cls, html) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }

  function statLabel(stat) {
    const labels = {
      'PTS': 'Points', 'AST': 'Assists', 'REB': 'Rebounds',
      'STL': 'Steals', 'BLK': 'Blocks',
      '3PM': '3-Pointers Made', 'FGM': 'Field Goals Made',
      'FTM': 'Free Throws Made', 'TOV': 'Turnovers',
      'PPR': 'PPR Fantasy Pts', 'Pass Yds': 'Passing Yards',
      'Rush Yds': 'Rushing Yards', 'Rec Yds': 'Receiving Yards',
      'Pass TD': 'Passing TDs', 'Rush TD': 'Rushing TDs',
      'Rec TD': 'Receiving TDs', 'Receptions': 'Receptions',
      'Sacks': 'Sacks', 'Solo Tackles': 'Solo Tackles', 'Def INT': 'Defensive INTs',
    };
    return labels[stat] || stat;
  }

  function teamFilterLabel(prompt) {
    const tf = prompt.team_filter_label || prompt.team_filter;
    if (!tf || tf === 'any' || tf === null) return 'Any Team';
    if (tf === 'Eastern') return 'Eastern Conf.';
    if (tf === 'Western') return 'Western Conf.';
    if (tf === 'AFC') return 'AFC';
    if (tf === 'NFC') return 'NFC';
    return tf;
  }

  function accoladeLabel(accolade) {
    if (!accolade) return null;
    const map = {
      'allstar': 'All-Star',
      'top10_draft': 'Top-10 Pick',
      'top5_draft': 'Top-5 Pick',
      'pro_bowl': 'Pro Bowl',
      'all_pro': 'All-Pro',
      '1st_round': '1st Round Pick',
    };
    return map[accolade] || accolade;
  }

  function currentTurn(state) {
    const nPlayers = state.players.length;
    for (let pr = 0; pr < 5; pr++) {
      const playerOrder = pr % 2 === 0
        ? Array.from({ length: nPlayers }, (_, idx) => idx)
        : Array.from({ length: nPlayers }, (_, idx) => nPlayers - 1 - idx);
      for (const pl of playerOrder) {
        if (state.picks[pr][pl] === null) return { playerIdx: pl, promptIdx: pr };
      }
    }
    return null;
  }

  function currentTurnPlayerIdx() {
    const turn = gameState ? currentTurn(gameState) : null;
    return turn ? turn.playerIdx : -1;
  }

  function playerTotals(state) {
    const totals = new Array(state.players.length).fill(0);
    for (let pr = 0; pr < 5; pr++) {
      for (let pl = 0; pl < state.players.length; pl++) {
        const pick = state.picks[pr][pl];
        if (pick) totals[pl] += pick.stat_val;
      }
    }
    return totals;
  }

  function ensureCloseButton() {
    var pickArea = document.getElementById('pick-area');
    if (!pickArea) return;
    var existing = document.getElementById('pick-close-btn');
    if (existing) {
      existing.onclick = window.bsClosePick;
      return;
    }

    var btn = document.createElement('button');
    btn.id = 'pick-close-btn';
    btn.type = 'button';
    btn.setAttribute('aria-label', 'Close pick overlay');
    btn.innerHTML = '&times;';
    btn.onclick = window.bsClosePick;
    pickArea.appendChild(btn);
  }

  // ── Setup Panel ───────────────────────────────────────────────────────────

  let playerCount = 2;

  function renderSetup() {
    const panel = $('#setup-panel');
    panel.style.display = '';
    $('#game-panel').style.display = 'none';

    const sportName = SPORT.toUpperCase();
    const rulesText = SPORT === 'nba'
      ? 'Each round shows 5 prompts (team/era/accolade + stat). Name a player who fits each one. Closest total stat score to the target wins!'
      : 'Each round shows 5 prompts (team/conference/accolade + stat). Name a player who fits each one. Closest total stat score to the target wins!';

    panel.innerHTML = `
      <div id="setup-inner">
        <div class="setup-card">
          <h2>How many players?</h2>
          <div class="count-row">
            <button class="count-btn active" onclick="bsSetCount(2)">2</button>
            <button class="count-btn" onclick="bsSetCount(3)">3</button>
            <button class="count-btn" onclick="bsSetCount(4)">4</button>
          </div>
          <div id="name-inputs-wrap"></div>
          <div class="rules">
            <strong>How to Play</strong>
            <ul>
              <li>${rulesText}</li>
              <li>All players answer each prompt in turn</li>
              <li>You can go over or under the target — closest wins</li>
            </ul>
          </div>
          <div id="setup-error" style="display:none; color:var(--red-bright); margin-bottom:12px; font-family:'Barlow Condensed',sans-serif; font-size:0.9rem;"></div>
          <button id="start-btn" onclick="bsStartGame()">Start Game</button>
        </div>
      </div>
    `;

    window.bsSetCount = function(n) {
      playerCount = n;
      document.querySelectorAll('.count-btn').forEach((btn, i) => {
        btn.classList.toggle('active', i + 2 === n);
      });
      renderNameInputs();
    };

    window.bsStartGame = startGame;

    renderNameInputs();
  }

  function renderNameInputs() {
    const wrap = $('#name-inputs-wrap');
    if (!wrap) return;
    wrap.innerHTML = Array.from({ length: playerCount }, (_, i) => `
      <div class="name-field">
        <label>Player ${i + 1}</label>
        <input id="pname-${i}" type="text" placeholder="Player ${i + 1}" value="Player ${i + 1}" />
      </div>
    `).join('');
  }

  async function startGame() {
    if (roomId) return;
    const names = Array.from({ length: playerCount }, (_, i) => {
      const inp = document.getElementById(`pname-${i}`);
      return inp ? inp.value.trim() || `Player ${i + 1}` : `Player ${i + 1}`;
    });

    const errDiv = $('#setup-error');
    errDiv.style.display = 'none';

    const startBtn = $('#start-btn');
    startBtn.disabled = true;
    startBtn.textContent = 'Starting…';

    try {
      const res = await fetch(`${API}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player_names: names }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to start game');
      gameId = data.game_id;
      gameState = data.state;
      renderGame();
    } catch (e) {
      errDiv.textContent = e.message;
      errDiv.style.display = '';
      startBtn.disabled = false;
      startBtn.textContent = 'Start Game';
    }
  }

  // ── Active pick state ─────────────────────────────────────────────────────
  // {promptIdx, playerIdx} — which cell is currently being filled
  let activePick = null;

  // ── Game Panel ────────────────────────────────────────────────────────────

  function renderGame() {
    $('#setup-panel').style.display = 'none';
    const panel = $('#game-panel');
    panel.style.display = '';
    ensureCloseButton();

    // Remove any stale bottom bar from previous render
    const oldBar = document.getElementById('bs-input-bar');
    if (oldBar) oldBar.remove();

    if (!gameState) return;

    const stat = gameState.stat;
    const target = gameState.target;
    const totals = playerTotals(gameState);

    // ── Top header: stat + target + player scores + turn box ─────────────────
    const turn = currentTurn(gameState);
    const turnPlayerIdx = turn ? turn.playerIdx : -1;
    const turnPromptIdx = turn ? turn.promptIdx : -1;
    const turnPlayerName = turnPlayerIdx >= 0 ? gameState.players[turnPlayerIdx] : '';

    let headerHtml = `
      <div class="bs-game-header">
        <div class="bs-game-meta">
          <div class="bs-meta-block">
            <span class="bs-meta-label">Stat</span>
            <span class="bs-meta-val">${statLabel(stat)}</span>
          </div>
          <div class="bs-meta-block highlight">
            <span class="bs-meta-label">Target</span>
            <span class="bs-meta-val target">${target.toLocaleString()}</span>
          </div>
        </div>
        <div class="bs-scores-bar">
          ${gameState.players.map((name, pi) => {
            const isActive = pi === turnPlayerIdx && !gameState.done;
            const diff = totals[pi] - target;
            const diffStr = totals[pi] > 0 ? (diff >= 0 ? `+${diff}` : `${diff}`) : '—';
            return `
              <div class="bs-score-chip${isActive ? ' active' : ''}">
                <span class="bs-score-player">${escapeHtml(name)}</span>
                <span class="bs-score-total">${totals[pi].toLocaleString()}</span>
                <span class="bs-score-diff">${diffStr}</span>
              </div>`;
          }).join('')}
        </div>
        ${!gameState.done ? `
        <div class="bs-turn-box">
          <div class="bs-turn-box-label">Current Turn</div>
          <div class="bs-turn-box-name">${escapeHtml(turnPlayerName)}</div>
        </div>` : ''}
      </div>
    `;
    document.getElementById('game-header').innerHTML = headerHtml;

    // ── Turn banner ───────────────────────────────────────────────────────────
    // Rendered separately; cleared after confirm to show result flash
    if (!document.getElementById('bs-turn-banner')) {
      const bannerEl = document.createElement('div');
      bannerEl.id = 'bs-turn-banner';
      bannerEl.className = 'bs-turn-banner';
      document.getElementById('game-header').after(bannerEl);
    }
    updateTurnBanner();

    // ── Prompt rows table ─────────────────────────────────────────────────────
    let tableHtml = '<div class="bs-prompt-table">';

    // Header row
    tableHtml += '<div class="bs-table-row bs-table-header">';
    tableHtml += '<div class="bs-th bs-th-team">Team</div>';
    tableHtml += '<div class="bs-th bs-th-years">Years</div>';
    tableHtml += '<div class="bs-th bs-th-accolade">Accolade</div>';
    gameState.players.forEach(name => {
      tableHtml += `<div class="bs-th bs-th-player">${escapeHtml(name)}</div>`;
    });
    tableHtml += '</div>';

    // Prompt rows
    gameState.prompts.forEach((prompt, prIdx) => {
      const teamLbl = teamFilterLabel(prompt);
      const yearRange = `${prompt.year_min}–${prompt.year_max}`;
      const accolade = accoladeLabel(prompt.accolade);

      tableHtml += `<div class="bs-table-row" data-prompt="${prIdx}">`;
      tableHtml += `<div class="bs-td bs-td-team"><span class="bs-team-badge">${escapeHtml(teamLbl)}</span></div>`;
      tableHtml += `<div class="bs-td bs-td-years">${yearRange}</div>`;
      tableHtml += `<div class="bs-td bs-td-accolade">${accolade ? `<span class="bs-accolade-tag">${escapeHtml(accolade)}</span>` : '<span class="bs-accolade-none">—</span>'}</div>`;

      gameState.players.forEach((name, plIdx) => {
        const pick = gameState.picks[prIdx][plIdx];
        const isActive = activePick && activePick.promptIdx === prIdx && activePick.playerIdx === plIdx;
        const isCurrentTurnCell = prIdx === turnPromptIdx && plIdx === turnPlayerIdx && !gameState.done;

        if (pick) {
          tableHtml += `
            <div class="bs-td bs-td-pick filled">
              <div class="bs-pick-player">${escapeHtml(pick.player)}</div>
              <div class="bs-pick-season">${escapeHtml(pick.team)} · ${pick.season}</div>
              <div class="bs-pick-val">${pick.stat_val.toLocaleString()}</div>
            </div>`;
        } else if (isCurrentTurnCell) {
          tableHtml += `
            <div class="bs-td bs-td-pick empty${isActive ? ' active' : ''}"
                 data-prompt="${prIdx}" data-player="${plIdx}" role="button" tabindex="0"
                 onclick="bsSelectCell(${prIdx},${plIdx})">
              <span class="bs-add-btn">+</span>
              <span class="bs-add-label">${escapeHtml(name)}</span>
            </div>`;
        } else {
          tableHtml += `
            <div class="bs-td bs-td-pick locked">
              <span class="bs-locked-dash">—</span>
            </div>`;
        }
      });

      tableHtml += '</div>';
    });
    tableHtml += '</div>';

    document.getElementById('prompt-table').innerHTML = tableHtml;

    // Show/hide pick area
    document.getElementById('pick-area').style.display = activePick && !gameState.done ? '' : 'none';

    if (gameState.done) renderResults();
  }

  function updateTurnBanner() {
    const banner = document.getElementById('bs-turn-banner');
    if (!banner) return;
    if (gameState.done) { banner.style.display = 'none'; return; }

    const turn = currentTurn(gameState);
    const turnPlayerIdx = turn ? turn.playerIdx : -1;
    const turnPromptIdx = turn ? turn.promptIdx : -1;
    const turnPlayerName = turnPlayerIdx >= 0 ? gameState.players[turnPlayerIdx] : '';

    if (activePick) {
      const prompt = gameState.prompts[activePick.promptIdx];
      const teamLbl = teamFilterLabel(prompt);
      const yearRange = `${prompt.year_min}–${prompt.year_max}`;
      const accolade = accoladeLabel(prompt.accolade);
      const parts = [teamLbl !== 'Any Team' ? teamLbl : null, yearRange, accolade].filter(Boolean);

      banner.className = 'bs-turn-banner active';
      banner.innerHTML = `
        <div class="bs-turn-banner-left">
          <span class="bs-turn-banner-name">${escapeHtml(turnPlayerName)}</span>
          <span class="bs-turn-banner-prompt">Prompt ${activePick.promptIdx + 1}: ${escapeHtml(parts.join(' · '))}</span>
        </div>
      `;

      // Also update the label inside pick-area
      const lbl = document.getElementById('active-prompt-label');
      if (lbl) lbl.textContent = `${turnPlayerName} — Prompt ${activePick.promptIdx + 1}: ${parts.join(' · ')}`;
    } else {
      banner.className = 'bs-turn-banner idle';
      banner.innerHTML = `<span class="bs-turn-idle">It's <strong>${escapeHtml(turnPlayerName)}</strong>'s turn — Prompt <strong>${turnPromptIdx + 1}</strong></span>`;
    }
    banner.style.display = '';
  }

  // Called from onclick in generated HTML
  window.bsSelectCell = function(promptIdx, playerIdx) {
    if (playerIdx !== currentTurnPlayerIdx()) return;
    activePick = { promptIdx, playerIdx };
    bsPendingName = null;
    renderGame();
    bsSetStep('name');
  };

  window.bsClosePick = function() {
    activePick = null;
    bsPendingName = null;
    var pickArea = document.getElementById('pick-area');
    var input = document.getElementById('pick-input');
    var results = document.getElementById('pick-results');
    var errDiv = document.getElementById('pick-error');
    var yearWrap = document.getElementById('pick-year-wrap');
    var yearSel = document.getElementById('pick-year-select');
    if (pickArea) pickArea.style.display = 'none';
    if (input) {
      input.value = '';
      input.disabled = false;
    }
    if (results) results.innerHTML = '';
    if (errDiv) errDiv.textContent = '';
    if (yearWrap) yearWrap.classList.add('hidden');
    if (yearSel) yearSel.value = '';
    renderGame();
  };

  // ── Search — same pattern as starting6.js ─────────────────────────────────

  let bsPendingName = null;

  function bsSetStep(step) {
    var yearWrap = document.getElementById('pick-year-wrap');
    var input    = document.getElementById('pick-input');
    var errDiv   = document.getElementById('pick-error');
    var results  = document.getElementById('pick-results');
    if (errDiv) errDiv.textContent = '';
    if (results) results.innerHTML = '';
    if (step === 'name') {
      if (yearWrap) yearWrap.classList.add('hidden');
      if (input) {
        input.value = '';
        input.disabled = false;
      }
    } else if (step === 'year') {
      if (yearWrap) yearWrap.classList.remove('hidden');
      if (input) { input.value = bsPendingName; input.disabled = true; }
    }
  }

  function showInvalidPickAnimation(message) {
    var errDiv = document.getElementById('pick-error');
    if (!errDiv) return;
    errDiv.classList.remove('show-invalid');
    void errDiv.offsetWidth;
    errDiv.innerHTML =
      '<div class="bs-invalid-pick">' +
      '<span class="bs-invalid-icon">&times;</span>' +
      '<span class="bs-invalid-text">' + escapeHtml(message || 'Answer did not fill all requirements') + '</span>' +
      '</div>';
    errDiv.classList.add('show-invalid');
  }

  function initSearch() {
    var input = document.getElementById('pick-input');
    if (!input) return;

    input.addEventListener('input', function(e) {
      clearTimeout(searchDebounce);
      var q = e.target.value.trim();
      var errDiv = document.getElementById('pick-error');
      if (errDiv) errDiv.textContent = '';
      searchDebounce = setTimeout(function() { bsSearchPlayers(q); }, 200);
    });

    var yearSel = document.getElementById('pick-year-select');
    if (yearSel) {
      yearSel.addEventListener('change', function() {
        var btn = document.getElementById('confirm-year-btn');
        if (btn) btn.disabled = this.value === '';
      });
    }

    document.addEventListener('click', function(e) {
      var wrap = document.getElementById('pick-search-wrap');
      if (wrap && !wrap.contains(e.target)) {
        var r = document.getElementById('pick-results');
        if (r) r.innerHTML = '';
      }
    });
  }

  function bsSearchPlayers(term) {
    if (!gameId || !activePick || gameState.done) return;
    fetch(API + '/search?game_id=' + encodeURIComponent(gameId) +
          '&prompt_idx=' + activePick.promptIdx +
          '&q=' + encodeURIComponent(term))
      .then(function(r) { return r.json(); })
      .then(function(data) {
        var results = data.results || [];
        var container = document.getElementById('pick-results');
        container.innerHTML = '';
        if (!results.length) {
          container.innerHTML = '<div class="bs-result-empty">No players found</div>';
          return;
        }
        results.forEach(function(r) {
          var div = document.createElement('div');
          div.className = 'bs-result-item';
          div.textContent = r.player;
          div.onclick = function() { bsSelectName(r.player); };
          container.appendChild(div);
        });
      })
      .catch(function() {});
  }

  function bsSelectName(name) {
    if (!activePick) return;
    document.getElementById('pick-results').innerHTML = '';
    document.getElementById('pick-error').textContent = '';
    bsPendingName = name;

    fetch(API + '/seasons?game_id=' + encodeURIComponent(gameId) +
          '&prompt_idx=' + activePick.promptIdx +
          '&player=' + encodeURIComponent(name))
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (!activePick) return;
        var seasons = data.seasons || [];
        if (!seasons.length) {
          document.getElementById('pick-error').textContent =
            name + ' has no seasons available for this stat. Try another player.';
          bsPendingName = null;
          return;
        }
        var sel = document.getElementById('pick-year-select');
        if (!sel) return;
        sel.innerHTML = '<option value="">— select a season —</option>' +
          seasons.map(function(season) {
            var label = season.season + ' · ' + season.team;
            return '<option value="' + season.season + '">' + label + '</option>';
          }).join('');
        document.getElementById('confirm-year-btn').disabled = true;
        bsSetStep('year');
      })
      .catch(function(err) {
        console.error('seasons fetch error:', err);
        var errDiv = document.getElementById('pick-error');
        if (errDiv) errDiv.textContent = 'Could not load seasons — try again.';
        bsPendingName = null;
      });
  }

  window.bsConfirmYear = function() {
    var season = document.getElementById('pick-year-select').value;
    if (!season || !bsPendingName || !activePick) return;
    confirmPick(bsPendingName, parseInt(season), 0);
    bsPendingName = null;
  };

  window.bsBackToName = function() {
    bsPendingName = null;
    bsSetStep('name');
  };

  async function confirmPick(playerName, season, statVal) {
    if (!activePick) return;
    const { promptIdx, playerIdx } = activePick;

    const input = document.getElementById('pick-input');
    const results = document.getElementById('pick-results');
    const errDiv = document.getElementById('pick-error');
    if (input) { input.disabled = true; input.value = playerName; }
    if (results) results.innerHTML = '';
    if (errDiv) errDiv.textContent = '';

    try {
      const res = await fetch(`${API}/pick`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game_id: gameId, player_name: playerName, season, prompt_idx: promptIdx, player_idx: playerIdx, token: roomId ? playerToken() : null }),
      });
      const data = await res.json();

      if (!res.ok || !data.ok) {
        bsPendingName = null;
        bsSetStep('name');
        showInvalidPickAnimation(data.msg || data.error || 'Answer did not fill all requirements');
        if (input) input.focus();
        return;
      }

      // Flash result in turn banner — use actual stat_val from server
      const actualStatVal = (data.state.picks[promptIdx] && data.state.picks[promptIdx][playerIdx])
        ? data.state.picks[promptIdx][playerIdx].stat_val
        : statVal;
      const banner = document.getElementById('bs-turn-banner');
      if (banner) {
        banner.className = 'bs-turn-banner result';
        banner.innerHTML = `
          <span class="bs-pick-reveal-name">${escapeHtml(playerName)}</span>
          <span class="bs-pick-reveal-sep">—</span>
          <span class="bs-pick-reveal-val">${Number(actualStatVal).toLocaleString()}!</span>
        `;
      }
      document.getElementById('pick-area').style.display = 'none';

      gameState = data.state;
      activePick = null;
      setTimeout(renderGame, 1600);
    } catch (e) {
      if (input) { input.disabled = false; input.value = ''; }
    }
  }

  // ── Results Screen ────────────────────────────────────────────────────────

  function renderResults() {
    const panel = $('#game-panel');
    const winner = gameState.winner;
    const target = gameState.target;
    const stat = gameState.stat;
    const players = gameState.players;

    // Sort players by closeness
    const ranked = players.map((name, i) => ({
      name,
      total: winner.totals[i],
      diff: winner.diffs[i],
      isWinner: winner.winner_indices.includes(i),
    })).sort((a, b) => a.diff - b.diff);

    let resultsHtml = `
      <div class="bs-results-overlay">
        <div class="bs-results-card">
          <div class="bs-results-title">
            <span class="bs-target-icon">&#9678;</span>
            ${winner.winner_names.length === 1
              ? `${escapeHtml(winner.winner_names[0])} wins!`
              : `Tie: ${winner.winner_names.map(escapeHtml).join(' & ')}!`}
          </div>
          <div class="bs-results-target">
            Target: <strong>${target.toLocaleString()}</strong> ${statLabel(stat)}
          </div>
          <div class="bs-results-table">
    `;

    ranked.forEach((p, rank) => {
      const diffStr = p.total >= target ? `+${p.diff}` : `-${p.diff}`;
      resultsHtml += `
        <div class="bs-results-row ${p.isWinner ? 'winner' : ''}">
          <span class="bs-results-rank">${rank + 1}</span>
          <span class="bs-results-name">${escapeHtml(p.name)}</span>
          <span class="bs-results-total">${p.total.toLocaleString()}</span>
          <span class="bs-results-diff">${diffStr}</span>
          ${p.isWinner ? '<span class="bs-results-crown">&#9670;</span>' : ''}
        </div>
      `;
    });

    resultsHtml += `
          </div>
          <button class="bs-play-again-btn" id="play-again-btn">Play Again</button>
        </div>
      </div>
    `;

    // Append results overlay after the grid
    const overlay = el('div');
    overlay.innerHTML = resultsHtml;
    panel.appendChild(overlay.firstElementChild);

    $('#play-again-btn').addEventListener('click', () => {
      gameState = null;
      gameId = null;
      renderSetup();
    });
  }

  // ── XSS safety ────────────────────────────────────────────────────────────

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  async function loadRoomGame() {
    const res = await fetch(`/api/lobbies/${encodeURIComponent(roomId)}/game-state?token=${encodeURIComponent(playerToken())}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Could not load multiplayer game');
    if (!data.room || !data.state) throw new Error('Game is not ready yet');
    gameId = data.room.game_id;
    gameState = data.state;
    renderGame();
  }

  initSearch();
  ensureCloseButton();
  if (roomId) {
    document.getElementById('setup-panel').style.display = 'none';
    document.getElementById('game-panel').style.display = '';
    loadRoomGame().catch(function () {});
    pollTimer = window.setInterval(function () {
      if (activePick) return;
      loadRoomGame().catch(function () {});
    }, 2500);
  } else {
    renderSetup();
  }

})();
