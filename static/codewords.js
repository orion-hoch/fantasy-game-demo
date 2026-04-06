(function () {
  'use strict';

  const TOKEN_KEY = 'fantasy-multiplayer-token';
  const POLL_MS = 1500;
  const MAX_CLUE_LEN = 50;
  const NFL_HEADSHOT_CACHE_KEY = 'nfl_codewords_headshot_cache_v1';

  const root = document.getElementById('cw-root');
  if (!root) return;

  const params = new URLSearchParams(location.search);
  const roomId = params.get('room_id') || '';
  const sport = window.SPORT || 'nfl';

  let gameId = null;
  let state = null;
  let pollTimer = null;
  let lastError = '';
  let pendingAction = false;
  let lastRenderedStateSig = null;
  let lastRenderedError = null;
  let clueDraftText = '';
  let clueDraftNumber = 1;
  const nflHeadshotCache = (function () {
    try {
      return JSON.parse(localStorage.getItem(NFL_HEADSHOT_CACHE_KEY)) || {};
    } catch (err) {
      return {};
    }
  })();
  const nflHeadshotPending = {};

  function token() {
    let value = sessionStorage.getItem(TOKEN_KEY);
    if (!value) {
      value = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem(TOKEN_KEY, value);
    }
    return value;
  }

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  async function jsonFetch(url, options) {
    const res = await fetch(url, options);
    let data = null;
    try { data = await res.json(); } catch (e) { /* ignore */ }
    if (!res.ok) {
      const msg = (data && data.error) || 'Request failed';
      const err = new Error(msg);
      err.payload = data;
      throw err;
    }
    return data;
  }

  function setError(msg) {
    lastError = msg || '';
  }

  function resetClueDraft() {
    clueDraftText = '';
    clueDraftNumber = 1;
  }

  function captureClueDraft() {
    const clueInput = document.getElementById('cw-clue-input');
    if (clueInput) clueDraftText = clueInput.value || '';
    const clueNumberEl = document.getElementById('cw-clue-number');
    if (clueNumberEl) clueDraftNumber = getClueNumber();
  }

  function shouldDeferInteractiveRender() {
    const active = document.activeElement;
    if (!active) return false;
    const cluePanel = root.querySelector('.cw-clue-panel');
    return !!cluePanel && cluePanel.contains(active);
  }

  function stateSignature(nextState) {
    try {
      return JSON.stringify(nextState || null);
    } catch (err) {
      return null;
    }
  }

  function saveNflHeadshotCache() {
    try {
      localStorage.setItem(NFL_HEADSHOT_CACHE_KEY, JSON.stringify(nflHeadshotCache));
    } catch (err) {
      // Ignore cache persistence failures.
    }
  }

  function extractPfrId(headshotUrl) {
    const match = String(headshotUrl || '').match(/\/headshots\/([^/_?]+)(?:_\d{4})?\.jpg/i);
    return match ? match[1] : '';
  }

  function resolveNflHeadshotUrl(pfrId, callback) {
    if (!pfrId) {
      callback(null);
      return;
    }
    if (Object.prototype.hasOwnProperty.call(nflHeadshotCache, pfrId)) {
      callback(nflHeadshotCache[pfrId]);
      return;
    }
    if (nflHeadshotPending[pfrId]) {
      nflHeadshotPending[pfrId].push(callback);
      return;
    }

    nflHeadshotPending[pfrId] = [callback];

    const newBase = 'https://www.pro-football-reference.com/req/20230307/images/headshots/';
    const oldBase = 'https://www.pro-football-reference.com/req/20180910/images/headshots/';
    const currentYear = new Date().getFullYear();
    const urls = [newBase + pfrId + '.jpg'];
    for (let year = currentYear; year >= 2000; year--) {
      urls.push(newBase + pfrId + '_' + year + '.jpg');
    }
    urls.push(oldBase + pfrId + '.jpg');

    let index = 0;
    function finish(url) {
      nflHeadshotCache[pfrId] = url;
      saveNflHeadshotCache();
      const callbacks = nflHeadshotPending[pfrId] || [];
      delete nflHeadshotPending[pfrId];
      callbacks.forEach(function (cb) { cb(url); });
    }
    function tryNext() {
      if (index >= urls.length) {
        finish(null);
        return;
      }
      const probe = new Image();
      probe.onload = function () { finish(urls[index]); };
      probe.onerror = function () {
        index += 1;
        tryNext();
      };
      probe.src = urls[index];
    }
    tryNext();
  }

  function markHeadshotLoaded(wrap) {
    wrap.classList.remove('missing');
    wrap.classList.add('loaded');
  }

  function markHeadshotMissing(wrap) {
    wrap.classList.remove('loaded');
    wrap.classList.add('missing');
  }

  function getInitialHeadshotUrl(directUrl, pfrId) {
    if (sport === 'nfl' && pfrId && Object.prototype.hasOwnProperty.call(nflHeadshotCache, pfrId)) {
      return nflHeadshotCache[pfrId] || '';
    }
    return directUrl || '';
  }

  function setHeadshotLoaded(img, url) {
    const wrap = img.closest('.cw-cell-headshot');
    if (!wrap) return;
    if (!url) {
      markHeadshotMissing(wrap);
      return;
    }
    img.onload = function () {
      markHeadshotLoaded(wrap);
    };
    img.onerror = function () {
      markHeadshotMissing(wrap);
    };
    if (img.getAttribute('src') === url) {
      if (img.complete) {
        if (img.naturalWidth > 0) markHeadshotLoaded(wrap);
        else markHeadshotMissing(wrap);
      }
      return;
    }
    img.src = url;
  }

  function initHeadshots() {
    root.querySelectorAll('.cw-cell-headshot').forEach(function (wrap) {
      const img = wrap.querySelector('.cw-cell-headshot-img');
      if (!img) return;

      const directUrl = img.dataset.src || '';
      const pfrId = img.dataset.pfrId || '';
      const initialUrl = img.getAttribute('src') || '';
      if (initialUrl) {
        setHeadshotLoaded(img, initialUrl);
        return;
      }

      markHeadshotMissing(wrap);

      if (sport === 'nfl' && pfrId) {
        resolveNflHeadshotUrl(pfrId, function (resolvedUrl) {
          if (!img.isConnected) return;
          if (!resolvedUrl) return;
          setHeadshotLoaded(img, resolvedUrl);
        });
        return;
      }
      if (directUrl) {
        setHeadshotLoaded(img, directUrl);
      }
    });
  }

  function getClueNumber() {
    const numberEl = document.getElementById('cw-clue-number');
    if (!numberEl) return 1;
    const value = parseInt(numberEl.dataset.value || numberEl.textContent || '1', 10);
    return Number.isFinite(value) && value >= 1 ? value : 1;
  }

  function setClueNumber(nextValue) {
    const numberEl = document.getElementById('cw-clue-number');
    const decBtn = document.getElementById('cw-clue-decrease');
    const incBtn = document.getElementById('cw-clue-increase');
    if (!numberEl) return;
    const maxValue = Math.max(1, parseInt(numberEl.dataset.max || '1', 10) || 1);
    const safeValue = Math.min(maxValue, Math.max(1, nextValue || 1));
    clueDraftNumber = safeValue;
    numberEl.dataset.value = String(safeValue);
    numberEl.textContent = String(safeValue);
    if (decBtn) decBtn.disabled = safeValue <= 1;
    if (incBtn) incBtn.disabled = safeValue >= maxValue;
  }

  // ── Bootstrap: discover the game id by polling the lobby ──────────────────

  async function discoverGameId() {
    if (!roomId) {
      root.innerHTML = '<div class="cw-error">No room id in the URL. Open the lobby first.</div>';
      return;
    }
    try {
      const data = await jsonFetch(`/api/lobbies/${roomId}/game-state?token=${encodeURIComponent(token())}`);
      if (data && data.room && data.room.game_id) {
        gameId = data.room.game_id;
        await loadState();
        startPolling();
        return;
      }
      root.innerHTML = '<div class="cw-loading">Waiting for the host to start the game…</div>';
      setTimeout(discoverGameId, POLL_MS);
    } catch (err) {
      root.innerHTML = `<div class="cw-error">${escapeHtml(err.message)}</div>`;
      setTimeout(discoverGameId, POLL_MS * 2);
    }
  }

  // ── Polling ───────────────────────────────────────────────────────────────

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(loadState, POLL_MS);
  }

  async function loadState() {
    if (pendingAction) return;
    if (shouldDeferInteractiveRender()) return;
    try {
      const data = await jsonFetch(`/api/codewords/state?game_id=${encodeURIComponent(gameId)}&token=${encodeURIComponent(token())}`);
      state = data.state;
      if (!state || state.current_phase !== 'clue' || !amIClueGiver()) resetClueDraft();
      setError('');
      const nextSig = stateSignature(state);
      if (nextSig === lastRenderedStateSig && lastRenderedError === '') return;
      render();
    } catch (err) {
      setError(err.message);
      const nextSig = stateSignature(state);
      if (nextSig === lastRenderedStateSig && lastRenderedError === lastError) return;
      render();
    }
  }

  // ── Actions ───────────────────────────────────────────────────────────────

  async function submitClue() {
    if (pendingAction) return;
    const input = document.getElementById('cw-clue-input');
    const numInput = document.getElementById('cw-clue-number');
    if (!input || !numInput) return;
    const clueText = (input.value || '').trim();
    const number = getClueNumber();
    if (!clueText) { setError('Type a clue first.'); render(); return; }
    if (clueText.length > MAX_CLUE_LEN) { setError(`Clue must be ${MAX_CLUE_LEN} characters or less.`); render(); return; }
    if (!Number.isFinite(number) || number < 1) { setError('Pick a number ≥ 1.'); render(); return; }

    pendingAction = true;
    try {
      const data = await jsonFetch('/api/codewords/clue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game_id: gameId, token: token(), clue: clueText, number: number })
      });
      state = data.state;
      resetClueDraft();
      setError('');
    } catch (err) {
      setError(err.message);
      if (err.payload && err.payload.state) state = err.payload.state;
    } finally {
      pendingAction = false;
      render();
    }
  }

  async function submitGuess(idx) {
    if (pendingAction) return;
    pendingAction = true;
    try {
      const data = await jsonFetch('/api/codewords/guess', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game_id: gameId, token: token(), index: idx })
      });
      state = data.state;
      setError('');
    } catch (err) {
      setError(err.message);
      if (err.payload && err.payload.state) state = err.payload.state;
    } finally {
      pendingAction = false;
      render();
    }
  }

  async function endTurn() {
    if (pendingAction) return;
    pendingAction = true;
    try {
      const data = await jsonFetch('/api/codewords/end_turn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game_id: gameId, token: token() })
      });
      state = data.state;
      setError('');
    } catch (err) {
      setError(err.message);
      if (err.payload && err.payload.state) state = err.payload.state;
    } finally {
      pendingAction = false;
      render();
    }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  function teamLabel(t) {
    if (t === 'A') return 'TEAM RED';
    if (t === 'B') return 'TEAM YELLOW';
    return '';
  }

  function isDuel() {
    return state && state.mode === 'duel';
  }

  function teamMembers(team) {
    if (!state || !state.players) return '';
    return state.players
      .filter(p => p.team === team)
      .map(p => {
        if (p.role === 'dual') return p.name;
        return `${p.name} (${p.role === 'spymaster' ? 'Clue' : 'Guess'})`;
      })
      .join(' · ');
  }

  /* In duel mode:
     - current_team = the team whose player is giving the clue
     - clue giver = player on current_team (gives clue about OTHER team's tiles)
     - guesser    = player on OTHER team (guessing their OWN tiles)
  */
  function duelClueGiverTeam() { return state.current_team; }
  function duelGuesserTeam() { return state.current_team === 'A' ? 'B' : 'A'; }

  function amIClueGiver() {
    const me = state.you;
    if (!me) return false;
    if (isDuel()) return me.team === duelClueGiverTeam();
    return me.team === state.current_team && me.role === 'spymaster';
  }

  function amIGuesser() {
    const me = state.you;
    if (!me) return false;
    if (isDuel()) return me.team === duelGuesserTeam();
    return me.team === state.current_team && me.role === 'guesser';
  }

  function statusLines() {
    if (!state) return { line: '', main: '', sub: '' };
    if (state.done) {
      return { line: 'Game Over', main: state.winner === 'A' ? 'Team Red Wins' : 'Team Yellow Wins', sub: '' };
    }
    const me = state.you;
    const phase = state.current_phase;

    if (isDuel()) {
      const clueGiver = state.players.find(p => p.team === duelClueGiverTeam());
      const guesser = state.players.find(p => p.team === duelGuesserTeam());
      if (phase === 'clue') {
        if (amIClueGiver()) {
          return { line: 'CLUE PHASE', main: 'Your turn to give a clue', sub: `Give ${guesser ? guesser.name : 'opponent'} a clue about their tiles.` };
        }
        return { line: 'CLUE PHASE', main: `${clueGiver ? clueGiver.name : 'Opponent'} is writing a clue`, sub: 'Wait for a clue about your tiles.' };
      }
      if (phase === 'guess') {
        if (amIGuesser()) {
          return { line: 'GUESS PHASE', main: 'Your turn to guess', sub: 'Click tiles you think are yours.' };
        }
        return { line: 'GUESS PHASE', main: `${guesser ? guesser.name : 'Opponent'} is guessing`, sub: 'Watching…' };
      }
      return { line: '', main: '', sub: '' };
    }

    // Teams mode
    const team = teamLabel(state.current_team);
    const myTurn = me && me.team === state.current_team;
    if (phase === 'clue') {
      const sub = myTurn
        ? (me.role === 'spymaster' ? 'Type a clue and number for your guesser.' : 'Wait for your clue giver to send a clue.')
        : `Wait for ${team}'s clue giver.`;
      return { line: `${team} · CLUE PHASE`, main: myTurn && me.role === 'spymaster' ? 'Your move' : team, sub };
    }
    if (phase === 'guess') {
      const sub = myTurn
        ? (me.role === 'guesser' ? 'Click a tile that matches the clue.' : 'Watching your guesser…')
        : `${team} is guessing.`;
      return { line: `${team} · GUESS PHASE`, main: myTurn && me.role === 'guesser' ? 'Your turn' : team, sub };
    }
    return { line: '', main: '', sub: '' };
  }

  function render() {
    if (!state) {
      root.innerHTML = '<div class="cw-loading">Loading game…</div>';
      return;
    }

    captureClueDraft();

    const me = state.you;
    const status = statusLines();

    let html = '';

    if (lastError) {
      html += `<div class="cw-error">${escapeHtml(lastError)}</div>`;
    }

    // Header score / turn area
    html += `
      <div class="cw-header">
        <div class="cw-team-card team-a${state.current_team === 'A' && !state.done ? ' active' : ''}">
          <div class="cw-team-label">Team Red</div>
          <div class="cw-team-score">${state.team_a_revealed} / ${state.team_a_total}</div>
          <div class="cw-team-roster">${escapeHtml(teamMembers('A'))}</div>
        </div>
        <div class="cw-status-card">
          <div class="cw-status-line">${escapeHtml(status.line)}</div>
          <div class="cw-status-main">${escapeHtml(status.main)}</div>
          <div class="cw-status-sub">${escapeHtml(status.sub)}</div>
          ${me ? `<div class="cw-status-line" style="margin-top:4px;">You: ${escapeHtml(me.name)} · ${escapeHtml(teamLabel(me.team))} · ${escapeHtml(me.role === 'spymaster' ? 'Clue Giver' : 'Guesser')}</div>` : ''}
        </div>
        <div class="cw-team-card team-b${state.current_team === 'B' && !state.done ? ' active' : ''}">
          <div class="cw-team-label">Team Yellow</div>
          <div class="cw-team-score">${state.team_b_revealed} / ${state.team_b_total}</div>
          <div class="cw-team-roster">${escapeHtml(teamMembers('B'))}</div>
        </div>
      </div>
    `;

    // Clue input panel
    if (!state.done && state.current_phase === 'clue' && amIClueGiver()) {
      let clueAboutTeam;
      if (isDuel()) {
        clueAboutTeam = duelGuesserTeam();
      } else {
        clueAboutTeam = me.team;
      }
      const teamRemaining = clueAboutTeam === 'A'
        ? (state.team_a_total - state.team_a_revealed)
        : (state.team_b_total - state.team_b_revealed);
      const clueNumber = Math.min(teamRemaining, Math.max(1, clueDraftNumber || 1));
      const helpText = isDuel()
        ? `Give your opponent a clue about their tiles.`
        : `Up to ${MAX_CLUE_LEN} characters · Number 1–${teamRemaining} (remaining players).`;
      html += `
        <div class="cw-clue-panel">
          <h3>Send a Clue</h3>
          <div class="cw-clue-row">
            <input id="cw-clue-input" class="cw-clue-input" type="text" maxlength="${MAX_CLUE_LEN}" value="${escapeHtml(clueDraftText)}" placeholder="e.g. Quarterbacks who won twice" />
            <div class="cw-clue-stepper" aria-label="Clue number selector">
              <button id="cw-clue-decrease" class="cw-clue-step-btn" type="button" aria-label="Decrease clue number">-</button>
              <div id="cw-clue-number" class="cw-clue-number" data-value="${clueNumber}" data-max="${teamRemaining}" aria-live="polite">${clueNumber}</div>
              <button id="cw-clue-increase" class="cw-clue-step-btn" type="button" aria-label="Increase clue number">+</button>
            </div>
            <button id="cw-clue-submit" class="cw-clue-submit" type="button">Send</button>
          </div>
          <div class="cw-clue-help">${escapeHtml(helpText)} <span id="cw-clue-counter" class="cw-clue-counter">0/${MAX_CLUE_LEN}</span></div>
        </div>
      `;
    }

    // Active clue display (during guess phase, visible to everyone)
    if (!state.done && state.current_phase === 'guess' && state.current_clue) {
      const c = state.current_clue;
      const teamHere = teamLabel(state.current_team);
      const canEnd = amIGuesser() && (c.guesses_made || 0) >= 1;
      html += `
        <div class="cw-active-clue">
          <div class="cw-active-clue-text">"${escapeHtml(c.text)}"</div>
          <div class="cw-active-clue-pill">${escapeHtml(teamHere)}</div>
          <div class="cw-active-clue-pill">Number: ${c.number}</div>
          <div class="cw-active-clue-pill">Guesses left: ${c.remaining}</div>
          ${canEnd ? `<button id="cw-end-turn" class="cw-end-turn-btn" type="button">End Turn</button>` : ''}
        </div>
      `;
    }

    // Board
    const gridCols = isDuel() ? 7 : 5;
    html += `<div class="cw-board" style="grid-template-columns:repeat(${gridCols},1fr);">`;
    for (const cell of state.board) {
      const revealedClass = cell.revealed ? ` revealed team-${cell.team}` : '';
      let keyClass = '';
      if (!cell.revealed && cell.team) keyClass = ` key-${cell.team}`;
      const clickable = (!state.done && state.current_phase === 'guess' && amIGuesser() && !cell.revealed) ? ' clickable' : '';
      const stampLabel = cell.revealed
        ? (cell.team === 'A' ? 'RED' : (cell.team === 'B' ? 'YEL' : 'NEU'))
        : '';
      const pfrId = sport === 'nfl' ? extractPfrId(cell.headshot_url) : '';
      const initialHeadshotUrl = getInitialHeadshotUrl(cell.headshot_url, pfrId);
      const headshotStateClass = initialHeadshotUrl ? ' loaded' : ' missing';
      html += `
        <div class="cw-cell${revealedClass}${keyClass}${clickable}" data-index="${cell.index}">
          <div class="cw-cell-headshot${headshotStateClass}">
            <div class="cw-cell-headshot-fallback" aria-hidden="true">?</div>
            <img class="cw-cell-headshot-img" src="${escapeHtml(initialHeadshotUrl)}" data-src="${escapeHtml(cell.headshot_url)}" data-pfr-id="${escapeHtml(pfrId)}" alt="${escapeHtml(cell.name)}" loading="lazy">
          </div>
          ${stampLabel ? `<div class="cw-cell-stamp">${stampLabel}</div>` : ''}
          <div class="cw-cell-name-bar"><div class="cw-cell-name">${escapeHtml(cell.name)}</div></div>
        </div>
      `;
    }
    html += '</div>';

    // History (last 6)
    if (state.history && state.history.length) {
      html += '<div class="cw-history"><h3>History</h3>';
      const recent = state.history.slice(-6);
      for (const h of recent) {
        const cls = h.team === 'A' ? 'cw-history-team-A' : 'cw-history-team-B';
        const tlabel = teamLabel(h.team);
        const guessSummary = (h.guesses || []).map(g => g.result).join(', ') || '—';
        html += `<div class="cw-history-row"><span class="${cls}">${escapeHtml(tlabel)}</span> · "${escapeHtml(h.clue)}" (${h.number}) → ${escapeHtml(guessSummary)}</div>`;
      }
      html += '</div>';
    }

    // Game over overlay
    if (state.done) {
      const winName = state.winner === 'A' ? 'Team Red' : 'Team Yellow';
      html += `
        <div class="cw-results-overlay">
          <div class="cw-results-card">
            <div class="cw-results-title">${escapeHtml(winName)} Wins!</div>
            <div class="cw-results-sub">All ${state.winner === 'A' ? state.team_a_total : state.team_b_total} players uncovered.</div>
            <a href="/lobbies/${encodeURIComponent(roomId)}" class="cw-results-back">Back to Lobby</a>
          </div>
        </div>
      `;
    }

    root.innerHTML = html;
    lastRenderedStateSig = stateSignature(state);
    lastRenderedError = lastError;
    initHeadshots();

    // Wire up handlers
    const submitBtn = document.getElementById('cw-clue-submit');
    if (submitBtn) submitBtn.addEventListener('click', submitClue);

    const decBtn = document.getElementById('cw-clue-decrease');
    const incBtn = document.getElementById('cw-clue-increase');
    if (decBtn) decBtn.addEventListener('click', function () { setClueNumber(getClueNumber() - 1); });
    if (incBtn) incBtn.addEventListener('click', function () { setClueNumber(getClueNumber() + 1); });
    if (decBtn || incBtn) setClueNumber(getClueNumber());

    const clueInput = document.getElementById('cw-clue-input');
    const counter = document.getElementById('cw-clue-counter');
    if (clueInput && counter) {
      const updateCounter = () => {
        clueDraftText = clueInput.value || '';
        counter.textContent = `${clueInput.value.length}/${MAX_CLUE_LEN}`;
        counter.classList.toggle('over', clueInput.value.length > MAX_CLUE_LEN);
      };
      clueInput.addEventListener('input', updateCounter);
      clueInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          submitClue();
        }
      });
      updateCounter();
    }

    const endBtn = document.getElementById('cw-end-turn');
    if (endBtn) endBtn.addEventListener('click', endTurn);

    root.querySelectorAll('.cw-cell.clickable').forEach(el => {
      el.addEventListener('click', () => {
        const idx = parseInt(el.dataset.index, 10);
        if (Number.isFinite(idx)) submitGuess(idx);
      });
    });
  }

  discoverGameId();
})();
