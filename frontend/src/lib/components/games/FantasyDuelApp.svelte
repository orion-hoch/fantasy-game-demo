<script lang="ts">
  import { browser } from '$app/environment';
  import { onMount } from 'svelte';

  import '$lib/styles/starting6.css';
  import { apiBaseUrl } from '$lib/api/config';
  import {
    fetchFantasyDuelYears,
    passFantasyDuelTurn,
    searchFantasyDuelPlayers,
    startFantasyDuelGame,
    submitFantasyDuelPick,
    type FantasyDuelPick,
    type FantasyDuelPlayer,
    type FantasyDuelState,
    type Sport
  } from '$lib/api/fantasy-duel';

  type SlotDef = { key: string; label: string; pos: string };

  let { sport, roomId }: { sport: Sport; roomId: string | null } = $props();

  const TOKEN_KEY = 'fantasy-multiplayer-token';

  function getConfig(currentSport: Sport) {
    return currentSport === 'nfl'
      ? {
          title: 'Starting 6',
          subtitle: 'Draft your best team, one random franchise at a time',
          scoreLabel: 'PPR',
          slots: [
            { key: 'QB', label: 'QB', pos: 'QB' },
            { key: 'WR1', label: 'WR 1', pos: 'WR' },
            { key: 'WR2', label: 'WR 2', pos: 'WR' },
            { key: 'RB1', label: 'RB 1', pos: 'RB' },
            { key: 'RB2', label: 'RB 2', pos: 'RB' },
            { key: 'TE', label: 'TE', pos: 'TE' },
            { key: 'UTIL', label: 'UTIL', pos: 'UTIL' }
          ] as SlotDef[],
          backHref: '/?tab=nfl'
        }
      : {
          title: 'Starting 5',
          subtitle: 'Draft your best NBA team, one random franchise at a time',
          scoreLabel: 'Pts',
          slots: [
            { key: 'G1', label: 'G 1', pos: 'G' },
            { key: 'G2', label: 'G 2', pos: 'G' },
            { key: 'F1', label: 'F 1', pos: 'F' },
            { key: 'F2', label: 'F 2', pos: 'F' },
            { key: 'C', label: 'C', pos: 'C' },
            { key: 'UTIL', label: 'UTIL', pos: 'UTIL' }
          ] as SlotDef[],
          backHref: '/?tab=nba'
        };
  }

  const config = $derived.by(() => getConfig(sport));

  let gameState: FantasyDuelState | null = $state(null);
  let playerCount = $state(2);
  let playerNames: string[] = $state(['Player 1', 'Player 2']);
  let setupError = $state('');
  let pending = $state(false);
  let inputValue = $state('');
  let searchResults: string[] = $state([]);
  let pendingName: string | null = $state(null);
  let seasonOptions: number[] = $state([]);
  let selectedSeason = $state('');
  let pickError = $state('');
  let tokenValue = $state('');
  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  const isOnlineMode = $derived(!!roomId);
  const currentPlayer = $derived.by(() => (gameState ? gameState.players[gameState.currentPlayer] : null));
  const isMyTurn = $derived.by(() => {
    if (!gameState || !isOnlineMode) return true;
    return currentPlayer?.token === playerToken();
  });

  function playerToken() {
    if (tokenValue) return tokenValue;
    if (!browser) return '';
    let value = sessionStorage.getItem(TOKEN_KEY);
    if (!value) {
      value = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem(TOKEN_KEY, value);
    }
    tokenValue = value;
    return value;
  }

  function setPlayerCount(count: number) {
    playerCount = count;
    playerNames = Array.from({ length: count }, (_, idx) => playerNames[idx] || `Player ${idx + 1}`);
  }

  function updatePlayerName(idx: number, value: string) {
    playerNames[idx] = value;
  }

  function bonusLabel(bonus: { pos: string; decade: number }) {
    return `1.5x bonus: ${bonus.pos} from the ${bonus.decade}s`;
  }

  function seasonLabel(season: number) {
    return sport === 'nba' ? String(season + 1) : String(season);
  }

  function rosterTotal(player: FantasyDuelPlayer) {
    return config.slots.reduce((sum, slot) => {
      const pick = player.roster[slot.key] as FantasyDuelPick | null;
      return sum + (pick ? Number(pick.ppr || 0) * Number(pick.bonusMultiplier || 1) : 0);
    }, 0);
  }

  async function startGame() {
    setupError = '';
    pending = true;
    try {
      const names = playerNames.map((name, idx) => name.trim() || `Player ${idx + 1}`);
      const response = await startFantasyDuelGame(sport, names);
      gameState = response.state;
    } catch (error) {
      setupError = error instanceof Error ? error.message : 'Failed to start game';
    } finally {
      pending = false;
    }
  }

  async function loadRoomState() {
    if (!roomId) return;
    const response = await fetch(`${apiBaseUrl}/lobbies/${encodeURIComponent(roomId)}/game-state?token=${encodeURIComponent(playerToken())}`);
    const text = await response.text();
    const data = text ? JSON.parse(text) : {};
    if (!response.ok) return;
    if (data.room?.status === 'lobby') {
      window.location.href = `/lobbies/${encodeURIComponent(roomId)}`;
      return;
    }
    if (data.state) gameState = data.state as FantasyDuelState;
  }

  function clearPickUi() {
    inputValue = '';
    searchResults = [];
    pendingName = null;
    seasonOptions = [];
    selectedSeason = '';
    pickError = '';
  }

  async function onSearchInput(value: string) {
    inputValue = value;
    pickError = '';
    if (searchTimer) clearTimeout(searchTimer);
    if (!gameState?.game_id || !value.trim()) {
      searchResults = [];
      return;
    }
    searchTimer = setTimeout(async () => {
      try {
        const response = await searchFantasyDuelPlayers(sport, gameState!.game_id, value.trim());
        searchResults = response.results;
      } catch {
        searchResults = [];
      }
    }, 200);
  }

  async function choosePlayer(name: string) {
    if (!gameState?.game_id) return;
    pendingName = name;
    pickError = '';
    searchResults = [];
    try {
      const response = await fetchFantasyDuelYears(sport, gameState.game_id, name);
      seasonOptions = response.years;
      if (!seasonOptions.length) {
        pickError = `${name} did not play for ${gameState.currentTeam}. Try another name.`;
        pendingName = null;
      }
    } catch (error) {
      pickError = error instanceof Error ? error.message : 'Could not load seasons';
      pendingName = null;
    }
  }

  async function confirmPick() {
    if (!gameState?.game_id || !pendingName || !selectedSeason) return;
    pending = true;
    try {
      const response = await submitFantasyDuelPick(sport, {
        gameId: gameState.game_id,
        playerName: pendingName,
        season: Number(selectedSeason),
        token: isOnlineMode ? playerToken() : null
      });
      if (!response.ok || !response.state) {
        pickError = response.msg || 'Pick failed';
        return;
      }
      gameState = response.state;
      clearPickUi();
    } catch (error) {
      pickError = error instanceof Error ? error.message : 'Pick failed';
    } finally {
      pending = false;
    }
  }

  async function passTurn() {
    if (!gameState?.game_id) return;
    pending = true;
    pickError = '';
    try {
      const response = await passFantasyDuelTurn(sport, gameState.game_id, isOnlineMode ? playerToken() : null);
      if (!response.ok || !response.state) {
        pickError = response.msg || 'Could not pass';
        return;
      }
      gameState = response.state;
      clearPickUi();
    } catch (error) {
      pickError = error instanceof Error ? error.message : 'Could not pass';
    } finally {
      pending = false;
    }
  }

  async function playAgain() {
    if (!roomId) {
      gameState = null;
      clearPickUi();
      return;
    }
    let nextUrl = `/lobbies/${encodeURIComponent(roomId)}`;
    try {
      const response = await fetch(`${apiBaseUrl}/lobbies/${encodeURIComponent(roomId)}/rematch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: playerToken() })
      });
      const text = await response.text();
      const data = text ? JSON.parse(text) : {};
      if (response.ok && data.room_url) nextUrl = data.room_url;
    } finally {
      window.location.href = nextUrl;
    }
  }

  onMount(() => {
    if (isOnlineMode) {
      playerToken();
      void loadRoomState();
      pollTimer = setInterval(() => {
        if (isMyTurn || gameState?.done) return;
        void loadRoomState();
      }, 2500);
      document.body.classList.add('online-mode-starting6');
    }
    return () => {
      if (searchTimer) clearTimeout(searchTimer);
      if (pollTimer) clearInterval(pollTimer);
      document.body.classList.remove('online-mode-starting6');
    };
  });
</script>

<div id="s6-app">
  <header class="s6-title-bar">
    <a class="nav-back" href={config.backHref}>&larr; Back</a>
    <h1>{config.title}</h1>
    <span class="header-sub">{config.subtitle}</span>
  </header>

  {#if !gameState}
    <div id="setup-panel">
      <div class="setup-card">
        <h2>How many players?</h2>
        {#if !isOnlineMode}
          <div class="count-row">
            {#each [2, 3, 4, 5] as count}
              <button class="count-btn" class:active={playerCount === count} type="button" onclick={() => setPlayerCount(count)}>{count}</button>
            {/each}
          </div>
        {/if}

        <div id="name-inputs-wrap">
          {#each playerNames as name, idx}
            <div class="name-field">
              <label for={`duel-player-${idx}`}>Player {idx + 1}</label>
              <input id={`duel-player-${idx}`} type="text" value={name} oninput={(event) => updatePlayerName(idx, (event.currentTarget as HTMLInputElement).value)} />
            </div>
          {/each}
        </div>

        <div class="rules">
          <strong>How to Play</strong>
          <ul>
            <li>Each turn draws a random franchise. Name a player from that team.</li>
            <li>Select the season to lock in the player-year version of your pick.</li>
            <li>Each player can only be drafted once across the whole game.</li>
            <li>{config.title === 'Starting 6' ? 'Fill 1 QB, 2 WR, 2 RB, 1 TE, and 1 UTIL.' : 'Fill 2G, 2F, 1C, and 1 UTIL.'}</li>
            <li>Old heads bonus applies 1.5x to a highlighted position/decade combo.</li>
          </ul>
        </div>

        {#if setupError}
          <div id="setup-error">{setupError}</div>
        {/if}

        <button id="start-btn" type="button" disabled={pending || isOnlineMode} onclick={startGame}>
          {#if isOnlineMode}
            Waiting for multiplayer room
          {:else if pending}
            Starting...
          {:else}
            Start Game
          {/if}
        </button>
      </div>
    </div>
  {:else}
    <div id="game-panel">
      <div id="round-banner">
        <div id="team-display">
          <span id="team-name">{gameState.currentTeam || '—'}</span>
          <span id="turn-label">{gameState.players[gameState.currentPlayer]?.name}'s pick · {bonusLabel(gameState.bonus)}</span>
        </div>
      </div>

      <div id="main-area">
        <div id="pick-area-wrap">
          <div id="pick-area">
            {#if !pendingName}
              <div id="pick-search-wrap">
                <input
                  id="pick-input"
                  type="text"
                  placeholder={isMyTurn ? 'Type a player name...' : 'Waiting for current player...'}
                  value={inputValue}
                  disabled={!isMyTurn || !!gameState.done}
                  autocomplete="off"
                  oninput={(event) => onSearchInput((event.currentTarget as HTMLInputElement).value)}
                />
                {#if searchResults.length}
                  <div id="pick-results">
                    {#each searchResults as result}
                      <button class="result-item" type="button" onclick={() => choosePlayer(result)}>{result}</button>
                    {/each}
                  </div>
                {/if}
              </div>
            {:else}
              <div id="pick-selected-name">{pendingName}</div>
              <div id="pick-year-row">
                <select id="pick-year-select" bind:value={selectedSeason} disabled={!isMyTurn || !!gameState.done}>
                  <option value="">— select a season —</option>
                  {#each seasonOptions as season}
                    <option value={String(season)}>{seasonLabel(season)}</option>
                  {/each}
                </select>
                <button id="confirm-year-btn" type="button" disabled={!selectedSeason || pending || !isMyTurn} onclick={confirmPick}>Confirm</button>
                <button id="back-to-name-btn" type="button" disabled={pending || !isMyTurn} onclick={clearPickUi}>&larr; Back</button>
              </div>
            {/if}

            {#if pickError}
              <div id="pick-error">{pickError}</div>
            {/if}

            <div id="pick-pass-wrap">
              <button type="button" disabled={!isMyTurn || pending || !!gameState.done || (gameState.skipsUsed[gameState.currentPlayer] || 0) >= 1} onclick={passTurn}>
                {(gameState.skipsUsed[gameState.currentPlayer] || 0) >= 1 ? 'No skips remaining' : 'Pass — no valid player available'}
              </button>
            </div>
          </div>
        </div>

        <div id="rosters-row">
          {#each gameState.players as player, idx}
            <div
              class="roster-panel"
              class:active-roster={idx === gameState.currentPlayer && !gameState.done}
              class:my-roster={isOnlineMode && player.token === playerToken()}
            >
              <div class="roster-header">
                <span class="player-name">{player.name}</span>
                {#if isOnlineMode && player.token === playerToken()}
                  <span class="roster-you">You</span>
                {/if}
              </div>
              {#each config.slots as slot}
                {@const pick = player.roster[slot.key] as FantasyDuelPick | null}
                <div
                  class="roster-slot"
                  class:filled={!!pick}
                  class:bonus-slot={!!pick && (pick.bonusMultiplier || 1) > 1}
                >
                  <span class="slot-label">{slot.label}</span>
                  {#if pick}
                    <div class="slot-content">
                      <div class="slot-top">
                        <span class="slot-player">{pick.player}</span>
                        <span class="slot-ppr">{(Number(pick.ppr) * Number(pick.bonusMultiplier || 1)).toFixed(sport === 'nfl' ? 1 : 0)}{(pick.bonusMultiplier || 1) > 1 ? ' ★' : ''}</span>
                      </div>
                      <span class="slot-meta">{seasonLabel(pick.season)} · {pick.team}</span>
                    </div>
                  {:else}
                    <span class="slot-empty-text">—</span>
                  {/if}
                </div>
              {/each}
              <div class="roster-total">Total: <strong>{rosterTotal(player).toFixed(sport === 'nfl' ? 1 : 0)} {config.scoreLabel}</strong></div>
            </div>
          {/each}
        </div>
      </div>
    </div>

    {#if gameState.done && gameState.winner}
      <div id="win-overlay">
        <div id="win-content">
          <div id="win-congrats">
            {#if gameState.winner.winner_names.length === 1}
              Congratulations
            {:else}
              Tie Game
            {/if}
          </div>
          <div id="win-name">
            {#if gameState.winner.winner_names.length === 1}
              {gameState.winner.winner_names[0]}
            {:else}
              {gameState.winner.winner_names.join(' & ')}
            {/if}
          </div>
          <div id="win-score" class:tie-score={gameState.winner.winner_names.length > 1}>
            {#each gameState.players as player, idx}
              {player.name}: {(gameState.winner.totals[idx] || 0).toFixed(sport === 'nfl' ? 1 : 0)} {config.scoreLabel}{idx < gameState.players.length - 1 ? ' · ' : ''}
            {/each}
          </div>
          <button id="play-again-btn" type="button" onclick={playAgain}>Play Again</button>
        </div>
      </div>
    {/if}
  {/if}
</div>
