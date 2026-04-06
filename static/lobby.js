(function () {
  'use strict';

  const app = document.getElementById('app');
  if (!app) return;

  const createMode = app.dataset.createMode === '1';
  const gameType = app.dataset.gameType;
  const roomId = app.dataset.roomId;
  const root = document.getElementById('lobby-root');
  const errorEl = document.getElementById('lobby-error');
  const TOKEN_KEY = 'fantasy-multiplayer-token';
  let pollTimer = null;

  function token() {
    let value = sessionStorage.getItem(TOKEN_KEY);
    if (!value) {
      value = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem(TOKEN_KEY, value);
    }
    return value;
  }

  function getNameFallback() {
    return localStorage.getItem('fantasy-multiplayer-name') || 'Player';
  }

  function saveName(name) {
    localStorage.setItem('fantasy-multiplayer-name', name);
  }

  function setError(msg) {
    errorEl.textContent = msg || '';
  }

  async function jsonFetch(url, options) {
    const res = await fetch(url, options);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Request failed');
    return data;
  }

  function renderCreate() {
    root.innerHTML = `
      <div class="name-field">
        <label for="host-name">Your name</label>
        <input id="host-name" type="text" value="${escapeHtml(getNameFallback())}" maxlength="24">
      </div>
      <button id="create-lobby-btn" class="lobby-btn">Create Lobby</button>
      <div class="lobby-note">You will be seated in Player 1 automatically.</div>
    `;

    document.getElementById('create-lobby-btn').addEventListener('click', async function () {
      const name = (document.getElementById('host-name').value || '').trim() || 'Host';
      saveName(name);
      setError('');
      try {
        const data = await jsonFetch('/api/lobbies/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ game_type: gameType, player_name: name, token: token() })
        });
        window.location.href = data.room_url;
      } catch (err) {
        setError(err.message);
      }
    });
  }

  function isCodewords() {
    return gameType.includes('codewords');
  }

  function isCodewordsDuel() {
    return gameType.includes('codewords_duel');
  }

  function teamLabel(team) {
    if (team === 'A') return 'Team Red';
    if (team === 'B') return 'Team Yellow';
    return '';
  }

  function roleLabel(role) {
    if (role === 'spymaster') return 'Clue Giver';
    if (role === 'guesser') return 'Guesser';
    return '';
  }

  function codewordsSummary(meta) {
    const t = meta && meta.team ? teamLabel(meta.team) : null;
    const r = meta && meta.role ? roleLabel(meta.role) : null;
    if (t && r) return `${t} · ${r}`;
    if (t) return `${t} · pick role`;
    if (r) return `pick team · ${r}`;
    return 'pick team & role';
  }

  function codewordsSeatExtras(seatNo, seat, room) {
    const mine = room.my_seat === seatNo;
    const meta = (seat && seat.meta) || {};
    const duel = isCodewordsDuel();
    if (!seat) return '';
    if (!mine) {
      if (duel) {
        const t = meta.team ? teamLabel(meta.team) : 'pick team';
        return `<div class="seat-cw-summary">${escapeHtml(t)}</div>`;
      }
      return `<div class="seat-cw-summary">${escapeHtml(codewordsSummary(meta))}</div>`;
    }
    const team = meta.team || '';
    const role = meta.role || '';
    let html = `
      <div class="seat-cw-block">
        <div class="seat-cw-label">Team</div>
        <div class="seat-cw-row">
          <button class="seat-cw-btn team-a${team === 'A' ? ' selected' : ''}" data-cw-team="A">Red</button>
          <button class="seat-cw-btn team-b${team === 'B' ? ' selected' : ''}" data-cw-team="B">Yellow</button>
        </div>`;
    if (!duel) {
      html += `
        <div class="seat-cw-label">Role</div>
        <div class="seat-cw-row">
          <button class="seat-cw-btn${role === 'spymaster' ? ' selected' : ''}" data-cw-role="spymaster">Clue Giver</button>
          <button class="seat-cw-btn${role === 'guesser' ? ' selected' : ''}" data-cw-role="guesser">Guesser</button>
        </div>`;
    }
    html += '</div>';
    return html;
  }

  function seatCard(seatNo, seat, room) {
    const mine = room.my_seat === seatNo;
    const filled = !!seat;
    return `
      <div class="seat-card${mine ? ' mine' : ''}${filled ? ' filled' : ''}">
        <div class="seat-label">Player ${seatNo}</div>
        <div class="seat-name">${filled ? escapeHtml(seat.name) : 'Open Seat'}</div>
        <div class="seat-status">${filled ? (mine ? 'You are here' : 'Taken') : 'Available'}</div>
        ${isCodewords() ? codewordsSeatExtras(seatNo, seat, room) : ''}
        ${filled
          ? (mine ? `<button class="seat-btn alt" data-leave="${seatNo}">Leave Seat</button>` : '')
          : `<button class="seat-btn" data-seat="${seatNo}">Take Seat</button>`}
      </div>
    `;
  }

  async function setSeatMeta(updates) {
    try {
      await jsonFetch(`/api/lobbies/${roomId}/seat-meta`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token(), meta: updates })
      });
      await loadRoom();
    } catch (err) {
      setError(err.message);
    }
  }

  function codewordsReady(room) {
    if (!isCodewords()) return { ready: false, reason: '' };
    const seats = room.seats || {};
    const duel = isCodewordsDuel();
    const need = duel ? 2 : 4;

    const filled = [];
    for (let i = 1; i <= need; i++) {
      const s = seats[String(i)];
      if (!s) return { ready: false, reason: `Need all ${need} players seated` };
      filled.push(s);
    }

    if (duel) {
      const teams = {};
      for (const s of filled) {
        const m = s.meta || {};
        if (!m.team) return { ready: false, reason: 'Both players need to pick a team' };
        teams[m.team] = (teams[m.team] || 0) + 1;
      }
      if (!teams.A || !teams.B || teams.A !== 1 || teams.B !== 1) {
        return { ready: false, reason: 'Each player must pick a different team (Red / Yellow)' };
      }
      return { ready: true, reason: '' };
    }

    // Teams (4-player)
    const counts = { A_spymaster: 0, A_guesser: 0, B_spymaster: 0, B_guesser: 0 };
    for (const s of filled) {
      const m = s.meta || {};
      if (!m.team || !m.role) return { ready: false, reason: 'All players need a team and role' };
      const k = `${m.team}_${m.role}`;
      counts[k] = (counts[k] || 0) + 1;
    }
    if (counts.A_spymaster !== 1 || counts.A_guesser !== 1 ||
        counts.B_spymaster !== 1 || counts.B_guesser !== 1) {
      return { ready: false, reason: 'Each team needs 1 clue giver and 1 guesser' };
    }
    return { ready: true, reason: '' };
  }

  async function claimSeat(seatNo) {
    const playerName = (document.getElementById('lobby-name-input').value || '').trim() || getNameFallback();
    saveName(playerName);
    try {
      await jsonFetch(`/api/lobbies/${roomId}/claim-seat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token(), player_name: playerName, seat_number: seatNo })
      });
      await loadRoom();
    } catch (err) {
      setError(err.message);
    }
  }

  async function leaveSeat() {
    try {
      await jsonFetch(`/api/lobbies/${roomId}/leave-seat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token() })
      });
      await loadRoom();
    } catch (err) {
      setError(err.message);
    }
  }

  async function startGame() {
    try {
      await jsonFetch(`/api/lobbies/${roomId}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token() })
      });
      await loadRoom();
    } catch (err) {
      setError(err.message);
    }
  }

  function renderRoom(room) {
    if (room.status === 'in_game' && room.redirect_url) {
      window.location.href = room.redirect_url;
      return;
    }

    const cw = isCodewords();
    const cwReady = cw ? codewordsReady(room) : { ready: false, reason: '' };
    const startDisabled = cw
      ? !cwReady.ready
      : (room.filled_seat_count < (room.min_players || 2));
    const noteText = cw
      ? (cwReady.ready
          ? 'Ready! Host can start the game.'
          : (cwReady.reason || 'Setting up Code Words…'))
      : `${room.filled_seat_count} player${room.filled_seat_count === 1 ? '' : 's'} seated. Host can start with any ${room.min_players}-${room.max_players}.`;

    root.innerHTML = `
      <div class="lobby-topline">
        <div>
          <div class="seat-label">Room Code</div>
          <div class="room-code">${escapeHtml(room.room_id)}</div>
        </div>
        <button id="copy-room-btn" class="seat-btn alt">Copy Invite Link</button>
      </div>
      <div class="name-field" style="margin-top:16px;">
        <label for="lobby-name-input">Display name</label>
        <input id="lobby-name-input" type="text" value="${escapeHtml(getNameFallback())}" maxlength="24">
      </div>
      ${cw ? `<div class="lobby-note" style="margin-bottom:12px;">${isCodewordsDuel() ? "Code Words Duel: 2 players, each picks a team. You give clues about the other player's tiles." : 'Code Words needs exactly 4 players: 2 teams, each with 1 Clue Giver and 1 Guesser.'}</div>` : ''}
      <div class="seat-grid">
        ${Array.from({ length: room.max_players }, function (_, idx) { return idx + 1; }).map(function (seatNo) { return seatCard(seatNo, room.seats[String(seatNo)], room); }).join('')}
      </div>
      <div class="lobby-topline">
        <div class="lobby-note">${escapeHtml(noteText)}</div>
        ${room.is_host ? `<button id="start-room-btn" class="lobby-btn" ${startDisabled ? 'disabled' : ''}>Start Game</button>` : ''}
      </div>
    `;

    document.getElementById('copy-room-btn').addEventListener('click', function () {
      navigator.clipboard.writeText(window.location.href);
    });

    const nameInput = document.getElementById('lobby-name-input');
    nameInput.addEventListener('change', function () { saveName(nameInput.value.trim() || 'Player'); });

    root.querySelectorAll('[data-seat]').forEach(function (btn) {
      btn.addEventListener('click', function () { claimSeat(btn.dataset.seat); });
    });
    root.querySelectorAll('[data-leave]').forEach(function (btn) {
      btn.addEventListener('click', leaveSeat);
    });
    root.querySelectorAll('[data-cw-team]').forEach(function (btn) {
      btn.addEventListener('click', function () { setSeatMeta({ team: btn.dataset.cwTeam }); });
    });
    root.querySelectorAll('[data-cw-role]').forEach(function (btn) {
      btn.addEventListener('click', function () { setSeatMeta({ role: btn.dataset.cwRole }); });
    });
    const startBtn = document.getElementById('start-room-btn');
    if (startBtn) startBtn.addEventListener('click', startGame);
  }

  async function loadRoom() {
    try {
      const data = await jsonFetch(`/api/lobbies/${roomId}?token=${encodeURIComponent(token())}`);
      setError('');
      renderRoom(data.room);
    } catch (err) {
      setError(err.message);
    }
  }

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  if (createMode) {
    renderCreate();
  } else {
    loadRoom();
    pollTimer = window.setInterval(loadRoom, 2500);
  }
})();
