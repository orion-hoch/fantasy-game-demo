(function () {
  'use strict';

  const TOKEN_KEY = 'fantasy-multiplayer-token';
  const POLL_MS = 1500;
  const MAX_CLUE_LEN = 50;

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
    try {
      const data = await jsonFetch(`/api/codewords/state?game_id=${encodeURIComponent(gameId)}&token=${encodeURIComponent(token())}`);
      state = data.state;
      setError('');
      render();
    } catch (err) {
      setError(err.message);
      render();
    }
  }

  // ── Actions ───────────────────────────────────────────────────────────────

  async function submitClue() {
    const input = document.getElementById('cw-clue-input');
    const numInput = document.getElementById('cw-clue-number');
    if (!input || !numInput) return;
    const clueText = (input.value || '').trim();
    const number = parseInt(numInput.value, 10);
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

  function teamMembers(team) {
    if (!state || !state.players) return '';
    return state.players
      .filter(p => p.team === team)
      .map(p => `${p.name} (${p.role === 'spymaster' ? 'Clue' : 'Guess'})`)
      .join(' · ');
  }

  function statusLines() {
    if (!state) return { line: '', main: '', sub: '' };
    if (state.done) {
      return { line: 'Game Over', main: state.winner === 'A' ? 'Team Red Wins' : 'Team Yellow Wins', sub: '' };
    }
    const me = state.you;
    const myTurn = me && me.team === state.current_team;
    const phase = state.current_phase;
    const team = teamLabel(state.current_team);
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

    const me = state.you;
    const myTurn = me && me.team === state.current_team;
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
    if (!state.done && state.current_phase === 'clue' && myTurn && me.role === 'spymaster') {
      const teamRemaining = me.team === 'A'
        ? (state.team_a_total - state.team_a_revealed)
        : (state.team_b_total - state.team_b_revealed);
      html += `
        <div class="cw-clue-panel">
          <h3>Send a Clue</h3>
          <div class="cw-clue-row">
            <input id="cw-clue-input" class="cw-clue-input" type="text" maxlength="${MAX_CLUE_LEN}" placeholder="e.g. Quarterbacks who won twice" />
            <input id="cw-clue-number" class="cw-clue-number" type="number" min="1" max="${teamRemaining}" value="1" />
            <button id="cw-clue-submit" class="cw-clue-submit" type="button">Send</button>
          </div>
          <div class="cw-clue-help">Up to ${MAX_CLUE_LEN} characters · Number 1–${teamRemaining} (your remaining players). <span id="cw-clue-counter" class="cw-clue-counter">0/${MAX_CLUE_LEN}</span></div>
        </div>
      `;
    }

    // Active clue display (during guess phase, visible to everyone)
    if (!state.done && state.current_phase === 'guess' && state.current_clue) {
      const c = state.current_clue;
      const teamHere = teamLabel(state.current_team);
      const canEnd = me && me.team === state.current_team && me.role === 'guesser' && (c.guesses_made || 0) >= 1;
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
    html += '<div class="cw-board">';
    for (const cell of state.board) {
      const revealedClass = cell.revealed ? ` revealed team-${cell.team}` : '';
      let keyClass = '';
      if (!cell.revealed && cell.team) keyClass = ` key-${cell.team}`;
      const guesserActive = !state.done
        && state.current_phase === 'guess'
        && me && me.team === state.current_team
        && me.role === 'guesser'
        && !cell.revealed;
      const clickable = guesserActive ? ' clickable' : '';
      const stampLabel = cell.revealed
        ? (cell.team === 'A' ? 'RED' : (cell.team === 'B' ? 'YEL' : 'NEU'))
        : '';
      html += `
        <div class="cw-cell${revealedClass}${keyClass}${clickable}" data-index="${cell.index}">
          <div class="cw-cell-headshot">
            <img src="${escapeHtml(cell.headshot_url)}" alt="${escapeHtml(cell.name)}" loading="lazy" onerror="this.style.display='none'">
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

    // Wire up handlers
    const submitBtn = document.getElementById('cw-clue-submit');
    if (submitBtn) submitBtn.addEventListener('click', submitClue);

    const clueInput = document.getElementById('cw-clue-input');
    const counter = document.getElementById('cw-clue-counter');
    if (clueInput && counter) {
      const updateCounter = () => {
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
