<script lang="ts">
  import { browser } from '$app/environment';
  import { onMount } from 'svelte';

  import '$lib/styles/codewords.css';
  import {
    type CodewordsState,
    fetchCodewordsState,
    submitCodewordsClue,
    submitCodewordsGuess,
    endCodewordsTurn
  } from '$lib/api/codewords';
  import { fetchLobbyGameState, rematchLobby } from '$lib/api/lobbies';

  let { sport, roomId }: { sport: 'nfl' | 'nba'; roomId: string | null } = $props();

  const TOKEN_KEY = 'fantasy-multiplayer-token';
  const POLL_MS = 1500;
  const MAX_CLUE_LEN = 50;

  let gameId = $state<string | null>(null);
  let gameState = $state<CodewordsState | null>(null);
  let errorMessage = $state('');
  let pendingAction = $state(false);
  let clueDraft = $state('');
  let clueNumber = $state(1);
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  function getToken(): string {
    if (!browser) return '';
    let value = sessionStorage.getItem(TOKEN_KEY);
    if (!value) {
      value = Math.random().toString(36).slice(2) + Date.now().toString(36);
      sessionStorage.setItem(TOKEN_KEY, value);
    }
    return value;
  }

  const isDuel = $derived(gameState?.mode === 'duel');
  const me = $derived(gameState?.you ?? null);
  const gridCols = $derived(isDuel ? 7 : 5);

  const amIClueGiver = $derived.by(() => {
    if (!gameState || !me) return false;
    if (isDuel) return me.team === gameState.current_team;
    return me.team === gameState.current_team && me.role === 'spymaster';
  });

  const amIGuesser = $derived.by(() => {
    if (!gameState || !me) return false;
    if (isDuel) {
      const guesserTeam = gameState.current_team === 'A' ? 'B' : 'A';
      return me.team === guesserTeam;
    }
    return me.team === gameState.current_team && me.role === 'guesser';
  });

  const showClueInput = $derived(!gameState?.done && gameState?.current_phase === 'clue' && amIClueGiver);
  const showActiveClue = $derived(!gameState?.done && gameState?.current_phase === 'guess' && !!gameState?.current_clue);
  const canEndTurn = $derived(amIGuesser && (gameState?.current_clue?.guesses_made ?? 0) >= 1);

  const clueAboutTeamRemaining = $derived.by(() => {
    if (!gameState || !me) return 1;
    let team: string;
    if (isDuel) {
      team = gameState.current_team === 'A' ? 'B' : 'A';
    } else {
      team = me.team;
    }
    return team === 'A'
      ? gameState.team_a_total - gameState.team_a_revealed
      : gameState.team_b_total - gameState.team_b_revealed;
  });

  const statusText = $derived.by(() => {
    if (!gameState) return { line: '', main: '', sub: '' };
    if (gameState.done) {
      return {
        line: 'Game Over',
        main: gameState.winner === 'A' ? 'Team Red Wins' : 'Team Yellow Wins',
        sub: ''
      };
    }

    const phase = gameState.current_phase;
    const teamLabel = gameState.current_team === 'A' ? 'TEAM RED' : 'TEAM YELLOW';

    if (isDuel) {
      const clueGiver = gameState.players.find((p: { team: string }) => p.team === gameState!.current_team);
      const guesserTeam = gameState.current_team === 'A' ? 'B' : 'A';
      const guesser = gameState.players.find((p: { team: string }) => p.team === guesserTeam);
      if (phase === 'clue') {
        if (amIClueGiver) {
          return { line: 'CLUE PHASE', main: 'Your turn to give a clue', sub: `Give ${guesser?.name ?? 'opponent'} a clue about their tiles.` };
        }
        return { line: 'CLUE PHASE', main: `${clueGiver?.name ?? 'Opponent'} is writing a clue`, sub: 'Wait for a clue about your tiles.' };
      }
      if (phase === 'guess') {
        if (amIGuesser) {
          return { line: 'GUESS PHASE', main: 'Your turn to guess', sub: 'Click tiles you think are yours.' };
        }
        return { line: 'GUESS PHASE', main: `${guesser?.name ?? 'Opponent'} is guessing`, sub: 'Watching…' };
      }
      return { line: '', main: '', sub: '' };
    }

    const myTurn = me && me.team === gameState.current_team;
    if (phase === 'clue') {
      const sub = myTurn
        ? (me!.role === 'spymaster' ? 'Type a clue and number for your guesser.' : 'Wait for your clue giver to send a clue.')
        : `Wait for ${teamLabel}'s clue giver.`;
      return { line: `${teamLabel} · CLUE PHASE`, main: myTurn && me!.role === 'spymaster' ? 'Your move' : teamLabel, sub };
    }
    if (phase === 'guess') {
      const sub = myTurn
        ? (me!.role === 'guesser' ? 'Click a tile that matches the clue.' : 'Watching your guesser…')
        : `${teamLabel} is guessing.`;
      return { line: `${teamLabel} · GUESS PHASE`, main: myTurn && me!.role === 'guesser' ? 'Your turn' : teamLabel, sub };
    }
    return { line: '', main: '', sub: '' };
  });

  function teamMembers(team: string): string {
    if (!gameState?.players) return '';
    return gameState.players
      .filter((p: { team: string }) => p.team === team)
      .map((p: { name: string; role: string; team: string }) => {
        if (p.role === 'dual') return p.name;
        return `${p.name} (${p.role === 'spymaster' ? 'Clue' : 'Guess'})`;
      })
      .join(' · ');
  }

  async function discoverGameId() {
    if (!roomId) {
      errorMessage = 'No room id in the URL. Open the lobby first.';
      return;
    }
    try {
      const data = await fetchLobbyGameState(roomId, getToken());
      if (data?.room?.game_id) {
        gameId = data.room.game_id;
        await loadState();
        startPolling();
        return;
      }
      setTimeout(discoverGameId, POLL_MS);
    } catch {
      setTimeout(discoverGameId, POLL_MS * 2);
    }
  }

  function startPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(loadState, POLL_MS);
  }

  async function loadState() {
    if (!gameId || pendingAction) return;
    try {
      const data = await fetchCodewordsState(gameId, getToken());
      gameState = data.state;
      if (!gameState || gameState.current_phase !== 'clue' || !amIClueGiver) {
        clueDraft = '';
        clueNumber = 1;
      }
      errorMessage = '';
    } catch (err) {
      errorMessage = err instanceof Error ? err.message : 'Failed to load gameState';
    }
  }

  async function handleSubmitClue() {
    if (pendingAction || !gameId) return;
    const text = clueDraft.trim();
    if (!text) { errorMessage = 'Type a clue first.'; return; }
    if (text.length > MAX_CLUE_LEN) { errorMessage = `Clue must be ${MAX_CLUE_LEN} characters or less.`; return; }

    pendingAction = true;
    try {
      const data = await submitCodewordsClue(gameId, getToken(), text, clueNumber);
      if (data.state) gameState = data.state;
      clueDraft = '';
      clueNumber = 1;
      errorMessage = '';
    } catch (err) {
      errorMessage = err instanceof Error ? err.message : 'Failed to submit clue';
    } finally {
      pendingAction = false;
    }
  }

  async function handleGuess(index: number) {
    if (pendingAction || !gameId || !amIGuesser) return;
    pendingAction = true;
    try {
      const data = await submitCodewordsGuess(gameId, getToken(), index);
      if (data.state) gameState = data.state;
      errorMessage = '';
    } catch (err) {
      errorMessage = err instanceof Error ? err.message : 'Failed to submit guess';
    } finally {
      pendingAction = false;
    }
  }

  async function handleEndTurn() {
    if (pendingAction || !gameId) return;
    pendingAction = true;
    try {
      const data = await endCodewordsTurn(gameId, getToken());
      if (data.state) gameState = data.state;
      errorMessage = '';
    } catch (err) {
      errorMessage = err instanceof Error ? err.message : 'Failed to end turn';
    } finally {
      pendingAction = false;
    }
  }

  async function handlePlayAgain() {
    if (!roomId) return;
    try {
      const data = await rematchLobby(roomId, getToken());
      const nextUrl = data.room_url || `/lobbies/${encodeURIComponent(roomId)}`;
      window.location.href = nextUrl;
    } catch {
      window.location.href = `/lobbies/${encodeURIComponent(roomId)}`;
    }
  }

  function cellClass(cell: { revealed: boolean; team: string | null }): string {
    let cls = 'cw-cell';
    if (cell.revealed) cls += ` revealed team-${cell.team}`;
    else if (cell.team) cls += ` key-${cell.team}`;
    if (!gameState?.done && gameState?.current_phase === 'guess' && amIGuesser && !cell.revealed) cls += ' clickable';
    return cls;
  }

  function stampLabel(cell: { revealed: boolean; team: string | null }): string {
    if (!cell.revealed) return '';
    if (cell.team === 'A') return 'RED';
    if (cell.team === 'B') return 'YEL';
    return 'NEU';
  }

  onMount(() => {
    discoverGameId();
    return () => {
      if (pollTimer) clearInterval(pollTimer);
    };
  });
</script>

<div id="cw-root">
  <a class="back-link" href="/?tab={sport}">&larr; Back</a>
  <h1 class="cw-title">{sport === 'nfl' ? 'NFL' : 'NBA'} Code Words</h1>

  {#if errorMessage}
    <div class="cw-error">{errorMessage}</div>
  {/if}

  {#if !gameState}
    <div class="cw-loading">Loading game…</div>
  {:else}
    <!-- Header: team scores and status -->
    <div class="cw-header">
      <div class="cw-team-card team-a" class:active={gameState.current_team === 'A' && !gameState.done}>
        <div class="cw-team-label">Team Red</div>
        <div class="cw-team-score">{gameState.team_a_revealed} / {gameState.team_a_total}</div>
        <div class="cw-team-roster">{teamMembers('A')}</div>
      </div>
      <div class="cw-status-card">
        <div class="cw-status-line">{statusText.line}</div>
        <div class="cw-status-main">{statusText.main}</div>
        <div class="cw-status-sub">{statusText.sub}</div>
        {#if me}
          <div class="cw-status-line" style="margin-top:4px">
            You: {me.name} · {me.team === 'A' ? 'TEAM RED' : 'TEAM YELLOW'} · {me.role === 'spymaster' ? 'Clue Giver' : me.role === 'dual' ? 'Both' : 'Guesser'}
          </div>
        {/if}
      </div>
      <div class="cw-team-card team-b" class:active={gameState.current_team === 'B' && !gameState.done}>
        <div class="cw-team-label">Team Yellow</div>
        <div class="cw-team-score">{gameState.team_b_revealed} / {gameState.team_b_total}</div>
        <div class="cw-team-roster">{teamMembers('B')}</div>
      </div>
    </div>

    <!-- Clue input (for clue giver) -->
    {#if showClueInput}
      <div class="cw-clue-panel">
        <h3>Send a Clue</h3>
        <div class="cw-clue-row">
          <input
            class="cw-clue-input"
            type="text"
            maxlength={MAX_CLUE_LEN}
            bind:value={clueDraft}
            placeholder="e.g. Quarterbacks who won twice"
            onkeydown={(e) => { if (e.key === 'Enter') handleSubmitClue(); }}
          />
          <div class="cw-clue-stepper">
            <button class="cw-clue-step-btn" type="button" disabled={clueNumber <= 1} onclick={() => (clueNumber = Math.max(1, clueNumber - 1))}>−</button>
            <div class="cw-clue-number">{clueNumber}</div>
            <button class="cw-clue-step-btn" type="button" disabled={clueNumber >= clueAboutTeamRemaining} onclick={() => (clueNumber = Math.min(clueAboutTeamRemaining, clueNumber + 1))}>+</button>
          </div>
          <button class="cw-clue-submit" type="button" disabled={pendingAction} onclick={handleSubmitClue}>Send</button>
        </div>
        <div class="cw-clue-help">
          Up to {MAX_CLUE_LEN} characters · Number 1–{clueAboutTeamRemaining}
          <span class="cw-clue-counter" class:over={clueDraft.length > MAX_CLUE_LEN}>{clueDraft.length}/{MAX_CLUE_LEN}</span>
        </div>
      </div>
    {/if}

    <!-- Active clue display (during guess phase) -->
    {#if showActiveClue && gameState.current_clue}
      <div class="cw-active-clue">
        <div class="cw-active-clue-text">"{gameState.current_clue.text}"</div>
        <div class="cw-active-clue-pill">{gameState.current_team === 'A' ? 'TEAM RED' : 'TEAM YELLOW'}</div>
        <div class="cw-active-clue-pill">Number: {gameState.current_clue.number}</div>
        <div class="cw-active-clue-pill">Guesses left: {gameState.current_clue.remaining}</div>
        {#if canEndTurn}
          <button class="cw-end-turn-btn" type="button" disabled={pendingAction} onclick={handleEndTurn}>End Turn</button>
        {/if}
      </div>
    {/if}

    <!-- Board -->
    <div class="cw-board" style="grid-template-columns: repeat({gridCols}, 1fr);">
      {#each gameState.board as cell}
        <button
          class={cellClass(cell)}
          type="button"
          disabled={gameState.done || gameState.current_phase !== 'guess' || !amIGuesser || cell.revealed || pendingAction}
          onclick={() => handleGuess(cell.index)}
        >
          <div class="cw-cell-headshot {cell.headshot_url ? 'loaded' : 'missing'}">
            <div class="cw-cell-headshot-fallback" aria-hidden="true">?</div>
            {#if cell.headshot_url}
              <img class="cw-cell-headshot-img" src={cell.headshot_url} alt={cell.name} loading="lazy" />
            {/if}
          </div>
          {#if stampLabel(cell)}
            <div class="cw-cell-stamp">{stampLabel(cell)}</div>
          {/if}
          <div class="cw-cell-name-bar"><div class="cw-cell-name">{cell.name}</div></div>
        </button>
      {/each}
    </div>

    <!-- History -->
    {#if gameState.history?.length}
      <div class="cw-history">
        <h3>History</h3>
        {#each gameState.history.slice(-6) as h}
          <div class="cw-history-row">
            <span class={h.team === 'A' ? 'cw-history-team-A' : 'cw-history-team-B'}>
              {h.team === 'A' ? 'TEAM RED' : 'TEAM YELLOW'}
            </span>
            · "{h.clue}" ({h.number}) → {(h.guesses || []).map((g: { result: string }) => g.result).join(', ') || '—'}
          </div>
        {/each}
      </div>
    {/if}

    <!-- Game over overlay -->
    {#if gameState.done}
      <div class="cw-results-overlay">
        <div class="cw-results-card">
          <div class="cw-results-title">{gameState.winner === 'A' ? 'Team Red' : 'Team Yellow'} Wins!</div>
          <div class="cw-results-sub">
            All {gameState.winner === 'A' ? gameState.team_a_total : gameState.team_b_total} players uncovered.
          </div>
          <div class="cw-results-actions">
            <button class="cw-results-back" type="button" onclick={handlePlayAgain}>Play Again</button>
            {#if roomId}
              <a href="/lobbies/{encodeURIComponent(roomId)}" class="cw-results-back alt">Back to Lobby</a>
            {/if}
          </div>
        </div>
      </div>
    {/if}
  {/if}
</div>
