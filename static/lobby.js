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

  function seatCard(seatNo, seat, room) {
    const mine = room.my_seat === seatNo;
    const filled = !!seat;
    return `
      <div class="seat-card${mine ? ' mine' : ''}${filled ? ' filled' : ''}">
        <div class="seat-label">Player ${seatNo}</div>
        <div class="seat-name">${filled ? escapeHtml(seat.name) : 'Open Seat'}</div>
        <div class="seat-status">${filled ? (mine ? 'You are here' : 'Taken') : 'Available'}</div>
        ${filled
          ? (mine ? `<button class="seat-btn alt" data-leave="${seatNo}">Leave Seat</button>` : '')
          : `<button class="seat-btn" data-seat="${seatNo}">Take Seat</button>`}
      </div>
    `;
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
      <div class="seat-grid">
        ${[1,2,3,4].map(function (seatNo) { return seatCard(seatNo, room.seats[String(seatNo)], room); }).join('')}
      </div>
      <div class="lobby-topline">
        <div class="lobby-note">${room.filled_seat_count} player${room.filled_seat_count === 1 ? '' : 's'} seated. Host can start with any 2-4.</div>
        ${room.is_host ? `<button id="start-room-btn" class="lobby-btn" ${room.filled_seat_count < 2 ? 'disabled' : ''}>Start Game</button>` : ''}
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
