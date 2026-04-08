<script lang="ts">
  import { onMount } from 'svelte';

  import '$lib/styles/bullseye.css';
  import {
    type BullseyePick,
    type BullseyePrompt,
    type BullseyeSeason,
    type BullseyeState,
    type Sport,
    fetchBullseyeSeasons,
    startBullseyeGame,
    submitBullseyePick,
    searchBullseyePlayers
  } from '$lib/api/bullseye';
  import { apiBaseUrl } from '$lib/api/config';

  type ActivePick = { promptIdx: number; playerIdx: number };
  type SearchResult = { player: string; season: number | null; team: string | null; stat_val: number };

  let { sport, roomId, soloMode }: { sport: Sport; roomId: string | null; soloMode: boolean } = $props();

  const TOKEN_KEY = 'fantasy-multiplayer-token';

  function initialPlayerCount() {
    return soloMode ? 1 : 2;
  }

  function initialPlayerNames() {
    return soloMode ? ['You'] : ['Player 1', 'Player 2'];
  }

  let gameState: BullseyeState | null = $state(null);
  let gameId = $state('');
  let playerCount = $state(initialPlayerCount());
  let playerNames: string[] = $state(initialPlayerNames());
  let setupError = $state('');
  let pickError = $state('');
  let startPending = $state(false);
  let activePick: ActivePick | null = $state(null);
  let searchTerm = $state('');
  let searchResults: SearchResult[] = $state([]);
  let seasonOptions: BullseyeSeason[] = $state([]);
  let selectedSeason = $state('');
  let pendingName: string | null = $state(null);
  let showResultFlash: { player: string; statVal: number } | null = $state(null);
  let multiplayerToken = $state('');

  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;
  let flashTimer: ReturnType<typeof setTimeout> | null = null;

  const totals = $derived.by(() => (gameState ? playerTotals(gameState) : []));
  const turn = $derived.by(() => (gameState ? currentTurn(gameState) : null));
  const turnPlayerName = $derived.by(() => {
    if (!gameState || !turn) return '';
    return gameState.players[turn.playerIdx] || '';
  });
  const rankedResults = $derived.by(() => {
    if (!gameState?.done || !gameState.winner) return [];
    const winner = gameState.winner;
    const players = gameState.players;
    return players
      .map((name, idx) => ({
        name,
        total: winner.totals[idx] ?? 0,
        diff: winner.diffs[idx] ?? 0,
        isWinner: winner.winner_indices.includes(idx)
      }))
      .sort((a, b) => a.diff - b.diff);
  });

  const backHref = $derived(sport === 'nba' ? '/?tab=nba' : '/?tab=nfl');
  const titleText = $derived(sport === 'nba' ? 'NBA Bullseye' : 'NFL Bullseye');

  function playerToken(): string {
    if (multiplayerToken) return multiplayerToken;
    if (typeof sessionStorage === 'undefined') return '';
    let value = sessionStorage.getItem(TOKEN_KEY);
    if (!value) {
      value = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem(TOKEN_KEY, value);
    }
    multiplayerToken = value;
    return value;
  }

  function setPlayerCount(nextCount: number) {
    playerCount = nextCount;
    playerNames = Array.from({ length: nextCount }, (_, idx) => playerNames[idx] || `Player ${idx + 1}`);
  }

  function updatePlayerName(index: number, value: string) {
    playerNames[index] = value;
  }

  function statLabel(stat: string) {
    const labels: Record<string, string> = {
      PTS: 'Points', AST: 'Assists', REB: 'Rebounds', STL: 'Steals', BLK: 'Blocks',
      '3PM': '3-Pointers Made', FGM: 'Field Goals Made', FTM: 'Free Throws Made', TOV: 'Turnovers',
      PPR: 'PPR Fantasy Pts', 'Pass Yds': 'Passing Yards', 'Rush Yds': 'Rushing Yards', 'Rec Yds': 'Receiving Yards',
      'Pass TD': 'Passing TDs', 'Rush TD': 'Rushing TDs', 'Rec TD': 'Receiving TDs', Receptions: 'Receptions',
      Sacks: 'Sacks', 'Solo Tackles': 'Solo Tackles', 'Def INT': 'Defensive INTs'
    };
    return labels[stat] || stat;
  }

  function seasonLabel(season: number | string | null | undefined) {
    if (season === null || season === undefined || season === '') return '';
    return sport === 'nba' ? String(Number(season) + 1) : String(season);
  }

  function teamFilterLabel(prompt: BullseyePrompt) {
    const value = prompt.team_filter_label || prompt.team_filter;
    if (!value || value === 'any' || value === 'Any Team') return 'Any Team';
    return value;
  }

  function accoladeLabel(accolade?: string | null) {
    if (!accolade) return null;
    const labels: Record<string, string> = {
      allstar: 'All-Star',
      top10_draft: 'Top-10 Pick',
      top5_draft: 'Top-5 Pick',
      pro_bowl: 'Pro Bowl',
      all_pro: 'All-Pro',
      '1st_round': '1st Round Pick',
      hof: 'Hall of Fame',
      nba_hof: 'Hall of Fame',
      all_nba: 'All-NBA',
      all_defensive: 'All-Defensive',
      all_rookie_nba: 'All-Rookie',
      all_rookie_nfl: 'All-Rookie',
      olympic_team: 'Olympic Team',
      nfl_mvp: 'NFL MVP',
      nfl_dpoy: 'DPOY',
      nba_mvp: 'NBA MVP',
      nba_fmvp: 'Finals MVP',
      nba_dpoy: 'DPOY'
    };
    return labels[accolade] || accolade;
  }

  function currentTurn(state: BullseyeState) {
    const nPlayers = state.players.length;
    for (let promptIdx = 0; promptIdx < 5; promptIdx += 1) {
      const order = promptIdx % 2 === 0
        ? Array.from({ length: nPlayers }, (_, idx) => idx)
        : Array.from({ length: nPlayers }, (_, idx) => nPlayers - 1 - idx);
      for (const playerIdx of order) {
        if (state.picks[promptIdx][playerIdx] === null) {
          return { playerIdx, promptIdx };
        }
      }
    }
    return null;
  }

  function playerTotals(state: BullseyeState) {
    const next = new Array(state.players.length).fill(0);
    for (let promptIdx = 0; promptIdx < 5; promptIdx += 1) {
      for (let playerIdx = 0; playerIdx < state.players.length; playerIdx += 1) {
        const pick = state.picks[promptIdx][playerIdx];
        if (pick) next[playerIdx] += pick.stat_val;
      }
    }
    return next;
  }

  function openCell(promptIdx: number, playerIdx: number) {
    if (!turn || playerIdx !== turn.playerIdx || promptIdx !== turn.promptIdx) return;
    activePick = { promptIdx, playerIdx };
    searchTerm = '';
    searchResults = [];
    seasonOptions = [];
    selectedSeason = '';
    pendingName = null;
    pickError = '';
  }

  function closePick() {
    activePick = null;
    searchTerm = '';
    searchResults = [];
    seasonOptions = [];
    selectedSeason = '';
    pendingName = null;
    pickError = '';
  }

  async function beginSoloOrLocalGame() {
    const names = playerNames.map((name, idx) => name.trim() || (soloMode ? 'You' : `Player ${idx + 1}`));
    setupError = '';
    startPending = true;
    try {
      const response = await startBullseyeGame(sport, names);
      gameId = response.game_id;
      gameState = response.state;
    } catch (error) {
      setupError = error instanceof Error ? error.message : 'Failed to start game';
    } finally {
      startPending = false;
    }
  }

  async function loadRoomGame() {
    if (!roomId) return;
    const token = playerToken();
    const response = await fetch(`${apiBaseUrl}/lobbies/${encodeURIComponent(roomId)}/game-state?token=${encodeURIComponent(token)}`);
    const text = await response.text();
    const data = text ? JSON.parse(text) : {};
    if (!response.ok) {
      throw new Error(data.detail || data.error || 'Could not load multiplayer game');
    }
    if (data.room?.status === 'lobby') {
      window.location.href = `/lobbies/${encodeURIComponent(roomId)}`;
      return;
    }
    if (!data.room?.game_id || !data.state) {
      throw new Error('Game is not ready yet');
    }
    gameId = data.room.game_id;
    gameState = data.state as BullseyeState;
  }

  async function loadSearchResults(term: string) {
    if (!gameId || !activePick || !term.trim()) {
      searchResults = term.trim() ? [] : [];
      return;
    }
    try {
      const data = await searchBullseyePlayers(sport, gameId, activePick.promptIdx, term.trim());
      searchResults = data.results;
    } catch {
      searchResults = [];
    }
  }

  function onSearchInput(value: string) {
    searchTerm = value;
    pickError = '';
    if (searchTimer) clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      void loadSearchResults(value);
    }, 200);
  }

  async function choosePlayer(name: string) {
    if (!activePick || !gameId) return;
    pendingName = name;
    pickError = '';
    searchResults = [];
    try {
      const data = await fetchBullseyeSeasons(sport, gameId, activePick.promptIdx, name);
      seasonOptions = data.seasons;
      if (!seasonOptions.length) {
        pickError = `${name} has no seasons available for this stat. Try another player.`;
        pendingName = null;
        selectedSeason = '';
      }
    } catch (error) {
      pickError = error instanceof Error ? error.message : 'Could not load seasons';
      pendingName = null;
    }
  }

  function backToSearch() {
    pendingName = null;
    selectedSeason = '';
    seasonOptions = [];
    pickError = '';
  }

  async function confirmPick() {
    if (!activePick || !pendingName || !selectedSeason || !gameId) return;
    pickError = '';
    try {
      const response = await submitBullseyePick(sport, {
        gameId,
        playerName: pendingName,
        season: Number(selectedSeason),
        promptIdx: activePick.promptIdx,
        playerIdx: activePick.playerIdx,
        token: roomId ? playerToken() : null
      });

      if (!response.ok || !response.state) {
        pickError = response.msg || 'Answer did not fill all requirements';
        return;
      }

      const pick = response.state.picks[activePick.promptIdx]?.[activePick.playerIdx] as BullseyePick | null;
      showResultFlash = { player: pendingName, statVal: pick?.stat_val ?? 0 };
      gameState = response.state;
      closePick();
      if (flashTimer) clearTimeout(flashTimer);
      flashTimer = setTimeout(() => {
        showResultFlash = null;
      }, 1600);
    } catch (error) {
      pickError = error instanceof Error ? error.message : 'Pick failed';
    }
  }

  async function playAgain() {
    if (!roomId) {
      gameState = null;
      gameId = '';
      closePick();
      showResultFlash = null;
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
      if (!response.ok) {
        throw new Error(data.detail || data.error || 'Failed to restart lobby');
      }
      nextUrl = data.room_url || nextUrl;
    } finally {
      window.location.href = nextUrl;
    }
  }

  function promptSummary(prompt: BullseyePrompt) {
    return [
      teamFilterLabel(prompt),
      `${prompt.year_min}-${prompt.year_max}`,
      accoladeLabel(prompt.accolade)
    ].filter(Boolean).join(' · ');
  }

  onMount(() => {
    if (roomId) {
      playerToken();
      void loadRoomGame().catch(() => undefined);
      pollTimer = setInterval(() => {
        if (activePick) return;
        void loadRoomGame().catch(() => undefined);
      }, 2500);
    }

    return () => {
      if (searchTimer) clearTimeout(searchTimer);
      if (pollTimer) clearInterval(pollTimer);
      if (flashTimer) clearTimeout(flashTimer);
    };
  });
</script>

<div id="bs-app">
  <div class="bs-title-bar">
    <a class="bs-back-link" href={backHref}>&larr; Back</a>
    <h1>{titleText}</h1>
  </div>

  {#if !gameState}
    <div class="bs-setup-card">
      <div class="bs-setup-title"><span class="bs-target-icon">●</span>{soloMode ? 'Solo Bullseye' : 'Bullseye Setup'}</div>
      <div class="bs-setup-desc">
        {sport === 'nba'
          ? 'Each round shows 5 prompts with team, era, accolade, and stat filters. Closest total to the target wins.'
          : 'Each round shows 5 prompts with team, conference, accolade, and stat filters. Closest total to the target wins.'}
      </div>

      {#if !soloMode && !roomId}
        <div class="bs-section-label">Players</div>
        <div class="bs-section-label" style="margin-bottom: 6px;">How many?</div>
        <div class="bs-player-inputs">
          <div class="bs-player-row" style="gap: 0;">
            {#each [1, 2, 3, 4] as count}
              <button
                type="button"
                class="bs-add-player-btn"
                style="margin-bottom: 0; flex: 1; {playerCount === count ? 'border-style: solid; border-color: var(--yellow); color: var(--yellow);' : ''}"
                onclick={() => setPlayerCount(count)}
              >{count} Players</button>
            {/each}
          </div>
        </div>
      {/if}

      <div class="bs-section-label">{soloMode ? 'Your Name' : 'Player Names'}</div>
      <div class="bs-player-inputs">
        {#each playerNames as name, idx}
          <div class="bs-player-row">
            <input
              class="bs-player-name-input"
              type="text"
              value={name}
              placeholder={soloMode ? 'You' : `Player ${idx + 1}`}
              oninput={(event) => updatePlayerName(idx, (event.currentTarget as HTMLInputElement).value)}
            />
          </div>
        {/each}
      </div>

      {#if setupError}
        <div class="bs-error">{setupError}</div>
      {/if}

      <button class="bs-start-btn" type="button" disabled={startPending || !!roomId} onclick={beginSoloOrLocalGame}>
        {#if roomId}
          Waiting for multiplayer room
        {:else if startPending}
          Starting...
        {:else if soloMode}
          Start Solo Game
        {:else}
          Start Game
        {/if}
      </button>
    </div>
  {:else}
    <div id="game-header">
      <div class="bs-game-header">
        <div class="bs-header-top">
          <div class="bs-game-meta">
            <div class="bs-meta-block">
              <span class="bs-meta-label">Stat</span>
              <span class="bs-meta-val">{statLabel(gameState.stat)}</span>
            </div>
            <div class="bs-meta-block highlight">
              <span class="bs-meta-label">Target</span>
              <span class="bs-meta-val target">{gameState.target.toLocaleString()}</span>
            </div>
          </div>

          {#if !gameState.done && turn}
            <div class="bs-turn-box">
              <span class="bs-turn-box-label">Current Turn</span>
              <span class="bs-turn-box-name">{turnPlayerName}</span>
            </div>
          {/if}
        </div>

        <div class="bs-scores-bar">
          {#each gameState.players as name, idx}
            {@const total = totals[idx] ?? 0}
            {@const diff = total ? total - gameState.target : 0}
            <div class="bs-score-chip" class:active={turn?.playerIdx === idx && !gameState.done}>
              <span class="bs-score-player">{name}</span>
              <span class="bs-score-total">{total.toLocaleString()}</span>
              <span class="bs-score-diff">{total ? (diff >= 0 ? `+${diff}` : `${diff}`) : '—'}</span>
            </div>
          {/each}
        </div>
      </div>

      {#if !gameState.done}
        <div class="bs-turn-banner" class:result={!!showResultFlash}>
          {#if showResultFlash}
            <span class="bs-pick-reveal-name">{showResultFlash.player}</span>
            <span class="bs-pick-reveal-sep">—</span>
            <span class="bs-pick-reveal-val">{showResultFlash.statVal.toLocaleString()}!</span>
          {:else if turn}
            <div class="bs-turn-banner-left">
              <span class="bs-turn-banner-name">{turnPlayerName}</span>
              <span class="bs-turn-banner-prompt">Up for prompt {turn.promptIdx + 1}</span>
            </div>
          {/if}
        </div>
      {/if}
    </div>

    <div id="prompt-table">
      <div class="bs-prompt-table">
        <div class="bs-table-row bs-table-header">
          <div class="bs-th bs-th-team">Team / Division</div>
          <div class="bs-th bs-th-years">Years</div>
          <div class="bs-th bs-th-accolade">Accolade</div>
          {#each gameState.players as name}
            <div class="bs-th bs-th-player">{name}</div>
          {/each}
        </div>

        {#each gameState.prompts as prompt, promptIdx}
          <div class="bs-table-row">
            <div class="bs-td bs-td-team"><span class="bs-team-badge">{teamFilterLabel(prompt)}</span></div>
            <div class="bs-td bs-td-years">{prompt.year_min}-{prompt.year_max}</div>
            <div class="bs-td bs-td-accolade">
              {#if accoladeLabel(prompt.accolade)}
                <span class="bs-accolade-tag">{accoladeLabel(prompt.accolade)}</span>
              {:else}
                <span class="bs-accolade-none">Any</span>
              {/if}
            </div>

            {#each gameState.players as _name, playerIdx}
              {@const pick = gameState.picks[promptIdx][playerIdx]}
              {#if pick}
                <div class="bs-td bs-td-pick filled">
                  <div class="bs-pick-player">{pick.player}</div>
                  <div class="bs-pick-season">{pick.team} · {seasonLabel(pick.season)}</div>
                  <div class="bs-pick-val">{pick.stat_val.toLocaleString()}</div>
                </div>
              {:else if !gameState.done && turn && turn.promptIdx === promptIdx && turn.playerIdx === playerIdx}
                <button
                  class="bs-td bs-td-pick empty"
                  class:active={activePick?.promptIdx === promptIdx && activePick?.playerIdx === playerIdx}
                  type="button"
                  onclick={() => openCell(promptIdx, playerIdx)}
                >
                  <span class="bs-add-btn">+</span>
                  <span class="bs-add-label">Pick</span>
                </button>
              {:else}
                <div class="bs-td bs-td-pick locked"><span class="bs-locked-dash">—</span></div>
              {/if}
            {/each}
          </div>
        {/each}
      </div>
    </div>

    {#if activePick && !gameState.done}
      <div id="pick-area">
        <div id="active-prompt-bar">
          <div id="active-prompt-label">Prompt {activePick.promptIdx + 1}: {promptSummary(gameState.prompts[activePick.promptIdx])}</div>
          <button id="pick-close-btn" type="button" onclick={closePick} aria-label="Close pick overlay">&times;</button>
        </div>
        {#if !pendingName}
          <div id="pick-search-wrap">
            <input
              id="pick-input"
              type="text"
              placeholder="Type a player name..."
              autocomplete="off"
              spellcheck="false"
              value={searchTerm}
              oninput={(event) => onSearchInput((event.currentTarget as HTMLInputElement).value)}
            />
            <div id="pick-results">
              {#if searchTerm.trim() && !searchResults.length}
                <div class="bs-result-empty">No players found</div>
              {/if}
              {#each searchResults as result}
                <button class="bs-result-item" type="button" onclick={() => choosePlayer(result.player)}>
                  <span class="bs-res-name">{result.player}</span>
                </button>
              {/each}
            </div>
          </div>
        {:else}
          <div id="pick-year-wrap">
            <div id="pick-year-row">
              <select id="pick-year-select" bind:value={selectedSeason}>
                <option value="">— select a season —</option>
                {#each seasonOptions as season}
                  <option value={String(season.season)}>{seasonLabel(season.season)} · {season.team}</option>
                {/each}
              </select>
              <button id="confirm-year-btn" type="button" disabled={!selectedSeason} onclick={confirmPick}>Confirm</button>
              <button id="back-to-name-btn" type="button" onclick={backToSearch}>&larr; Back</button>
            </div>
          </div>
        {/if}
        <div id="pick-error">{pickError}</div>
      </div>
    {/if}

    {#if gameState.done && gameState.winner}
      <div class="bs-results-overlay">
        <div class="bs-results-card">
          <div class="bs-results-title">
            <span class="bs-results-crown">★</span>
            {#if gameState.winner.winner_names.length === 1}
              {gameState.winner.winner_names[0]} Wins
            {:else}
              Tie: {gameState.winner.winner_names.join(' & ')}
            {/if}
            <span class="bs-results-crown">★</span>
          </div>
          <div class="bs-results-target">Target: <strong>{gameState.target.toLocaleString()}</strong> {statLabel(gameState.stat)}</div>

          <div class="bs-results-table">
            {#each rankedResults as result, idx}
              <div class="bs-results-row" class:winner={result.isWinner}>
                <span class="bs-results-rank">{idx + 1}</span>
                <span class="bs-results-name">{result.name}</span>
                <span class="bs-results-total">{result.total.toLocaleString()}</span>
                <span class="bs-results-diff">{result.total >= gameState.target ? `+${result.diff}` : `-${result.diff}`}</span>
              </div>
            {/each}
          </div>

          <button class="bs-play-again-btn" type="button" onclick={playAgain}>Play Again</button>
        </div>
      </div>
    {/if}
  {/if}
</div>
