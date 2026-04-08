<script lang="ts">
  import { browser } from '$app/environment';
  import { onMount } from 'svelte';

  import '$lib/styles/chain.css';
  import { apiBaseUrl } from '$lib/api/config';
  import {
    type ChainCategory,
    type ChainFeedback,
    type ChainState,
    type Sport,
    fetchChainState,
    guessChain,
    searchChainPlayers,
    startChain,
    teammateStartChain
  } from '$lib/api/chain';

  let { sport, roomId }: { sport: Sport; roomId: string | null } = $props();

  const TOKEN_KEY = 'fantasy-multiplayer-token';

  let mode = $state<'classic' | 'infinite'>('classic');
  let score = $state(0);
  let chain: ChainCategory[] = $state([]);
  let validCount = $state(0);
  let usedPlayers: string[] = $state([]);
  let chainGuesses: Array<{ player: string; pts: number; by?: string }> = $state([]);
  let currentGuess = $state('');
  let searchResults: string[] = $state([]);
  let feedback: ChainFeedback | null = $state(null);
  let promptText = $state('Name a player who fits all chain links above.');
  let gameActive = $state(false);
  let loading = $state(false);
  let onlineState: ChainState | null = $state(null);
  let tokenValue = $state('');
  let nextChainPlayer = $state<string | null>(null);
  let selectedIndex = $state(-1);
  let selectedFromResults = $state(false);
  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  const isOnlineMode = $derived(!!roomId);
  const displayedChain = $derived.by(() => {
    if (!isOnlineMode || !onlineState) return chain;
    if (onlineState.mode === 'coop') return onlineState.chain || [];
    return onlineState.players[onlineState.currentPlayer]?.chain || [];
  });
  const displayedGuesses = $derived.by(() => {
    if (!isOnlineMode || !onlineState) return chainGuesses;
    if (onlineState.mode === 'coop') return onlineState.chainGuesses || [];
    return onlineState.players[onlineState.currentPlayer]?.chainGuesses || [];
  });
  const displayedValidCount = $derived.by(() => {
    if (!isOnlineMode || !onlineState) return validCount;
    if (onlineState.mode === 'coop') return onlineState.validCount || 0;
    return onlineState.players[onlineState.currentPlayer]?.validCount || 0;
  });
  const currentOnlinePlayer = $derived.by(() => {
    if (!onlineState?.players?.length) return null;
    return onlineState.players[onlineState.currentPlayer];
  });
  const isMyTurn = $derived.by(() => {
    if (!isOnlineMode) return true;
    return currentOnlinePlayer?.token === playerToken();
  });
  const displayedScore = $derived.by(() => {
    if (!isOnlineMode || !onlineState) return score;
    if (onlineState.mode === 'coop') return onlineState.players.reduce((sum, player) => sum + (player.score || 0), 0);
    return currentOnlinePlayer?.score || 0;
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

  function clearSearch() {
    searchResults = [];
    selectedIndex = -1;
  }

  function clearFeedback() {
    feedback = null;
  }

  function updatePrompt() {
    if (isOnlineMode && onlineState) {
      if (onlineState.done && onlineState.winner) {
        promptText = onlineState.winner.winner_names.length === 1
          ? `${onlineState.winner.winner_names[0]} wins the match!`
          : `Tie game: ${onlineState.winner.winner_names.join(' & ')}`;
        return;
      }
      if (onlineState.mode === 'coop') {
        promptText = `${currentOnlinePlayer?.name}'s turn. Team lives left: ${onlineState.lives_left}`;
      } else {
        promptText = `${currentOnlinePlayer?.name}'s chain. Lives left: ${currentOnlinePlayer?.lives_left}`;
      }
      return;
    }

    if (!displayedChain.length) {
      promptText = 'Press Start to begin.';
      return;
    }
    const active = displayedChain[displayedChain.length - 1];
    promptText = displayedChain.length === 1
      ? `Name a player who ${active.label}`
      : `Fits all ${displayedChain.length} links — latest: ${active.label}`;
  }

  function hydrateOnlineState(state: ChainState) {
    onlineState = state;
    usedPlayers = [...(state.usedPlayers || [])];
    feedback = state.feedback || null;
    updatePrompt();
  }

  async function beginChain() {
    loading = true;
    clearFeedback();
    nextChainPlayer = null;
    try {
      const data = await startChain(sport);
      chain = [data.category];
      score = 0;
      validCount = data.valid_count;
      usedPlayers = [];
      chainGuesses = [];
      gameActive = true;
      currentGuess = '';
      clearSearch();
      updatePrompt();
    } catch (error) {
      feedback = { type: 'wrong', message: error instanceof Error ? error.message : 'Could not start chain' };
    } finally {
      loading = false;
    }
  }

  async function continueTeammates(playerName: string) {
    loading = true;
    clearFeedback();
    try {
      const data = await teammateStartChain(sport, playerName);
      chain = [data.category];
      validCount = data.valid_count;
      chainGuesses = [];
      gameActive = true;
      nextChainPlayer = null;
      updatePrompt();
    } catch (error) {
      feedback = { type: 'wrong', message: error instanceof Error ? error.message : 'Could not continue chain' };
    } finally {
      loading = false;
    }
  }

  async function onSearchInput(value: string) {
    currentGuess = value;
    selectedFromResults = false;
    if (searchTimer) clearTimeout(searchTimer);
    if (!value.trim()) {
      clearSearch();
      return;
    }
    searchTimer = setTimeout(async () => {
      try {
        const data = await searchChainPlayers(sport, value.trim(), isOnlineMode ? onlineState?.game_id : null);
        searchResults = data.results.map((result) => result.name);
        selectedIndex = -1;
      } catch {
        clearSearch();
      }
    }, 200);
  }

  function applySoloCorrect(playerName: string, data: Record<string, unknown>) {
    const pts = displayedChain.length;
    score += pts;
    usedPlayers = [...usedPlayers, playerName];
    chainGuesses = [...chainGuesses, { player: playerName, pts }];

    const lastPlayer = typeof data.last_player === 'string' ? data.last_player : null;
    const nextCategory = (data.next_category as ChainCategory | null) || null;
    const nextValidCount = Number(data.valid_count || 0);

    if (lastPlayer) {
      score += 10;
      feedback = { type: 'correct', message: `Correct! ${playerName} clears the chain. Bonus 10 points. Continue with teammates of ${lastPlayer}.` };
      nextChainPlayer = lastPlayer;
      validCount = 1;
      gameActive = false;
      return;
    }

    if (!nextCategory) {
      feedback = { type: 'correct', message: `Correct! ${playerName} clears the chain.` };
      validCount = nextValidCount;
      gameActive = false;
      return;
    }

    chain = [...chain, nextCategory];
    validCount = nextCategory.valid_count || nextValidCount;
    feedback = { type: 'correct', message: `Correct! ${playerName} grows the chain.` };
    gameActive = true;
  }

  function applySoloWrong(playerName: string, data: Record<string, unknown>) {
    feedback = {
      type: 'wrong',
      message: `${playerName} does not fit the full chain.`,
      examples: (data.examples as string[]) || [],
      link_results: (data.link_results as Array<{ label: string; passed: boolean }>) || []
    };
    gameActive = false;
    nextChainPlayer = mode === 'infinite' ? playerName : null;
  }

  async function submitGuess(playerName: string) {
    if (!playerName.trim()) return;
    loading = true;
    selectedFromResults = false;
    clearSearch();
    try {
      if (isOnlineMode && onlineState) {
        const data = await guessChain(sport, { player: playerName, gameId: onlineState.game_id, token: playerToken() });
        if (!data.ok) {
          feedback = { type: 'wrong', message: String(data.error || 'Could not submit answer') };
        } else {
          hydrateOnlineState(data.state as ChainState);
        }
      } else {
        const data = await guessChain(sport, { player: playerName, chain: displayedChain, usedPlayers });
        if (data.correct) applySoloCorrect(playerName, data);
        else applySoloWrong(playerName, data);
      }
      currentGuess = '';
      updatePrompt();
    } catch (error) {
      feedback = { type: 'wrong', message: error instanceof Error ? error.message : 'Could not submit answer' };
    } finally {
      loading = false;
    }
  }

  async function playAgain() {
    if (!roomId) {
      await beginChain();
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
    if (data.state) hydrateOnlineState(data.state as ChainState);
  }

  function onKeydown(event: KeyboardEvent) {
    if (!searchResults.length) {
      if (event.key === 'Enter' && selectedFromResults && currentGuess.trim()) {
        event.preventDefault();
        void submitGuess(currentGuess.trim());
      }
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, searchResults.length - 1);
      currentGuess = searchResults[selectedIndex] || currentGuess;
      selectedFromResults = selectedIndex >= 0;
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, -1);
      currentGuess = selectedIndex >= 0 ? searchResults[selectedIndex] : currentGuess;
      selectedFromResults = selectedIndex >= 0;
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (selectedIndex >= 0) {
        currentGuess = searchResults[selectedIndex];
        selectedFromResults = true;
        searchResults = [];
        selectedIndex = -1;
        void submitGuess(currentGuess.trim());
      }
    } else if (event.key === 'Escape') {
      clearSearch();
    }
  }

  onMount(() => {
    if (isOnlineMode) {
      playerToken();
      void loadRoomState();
      pollTimer = setInterval(() => {
        if (isMyTurn) return;
        void loadRoomState();
      }, 2500);
    } else {
      updatePrompt();
    }
    return () => {
      if (searchTimer) clearTimeout(searchTimer);
      if (pollTimer) clearInterval(pollTimer);
    };
  });
</script>

<div id="chain-app">
  <div style="padding: 12px 24px 0;">
    <a class="back-link" href="/?tab={sport}">&larr; Back</a>
  </div>

  {#if !isOnlineMode}
    <div id="mode-toggle">
      <button class="mode-btn" class:active={mode === 'classic'} type="button" onclick={() => (mode = 'classic')}>Classic</button>
      <button class="mode-btn" class:active={mode === 'infinite'} type="button" onclick={() => (mode = 'infinite')}>Infinite</button>
    </div>
  {/if}

  <div id="stats-bar">
    <div class="stat-box">
      <div class="stat-label">Score</div>
      <div class="stat-value">{displayedScore}</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">Chain Length</div>
      <div class="stat-value">{displayedChain.length}</div>
    </div>
    <div class="stat-box">
      <div class="stat-label">Players Left</div>
      <div class="stat-value">{displayedValidCount || '—'}</div>
    </div>
  </div>

  {#if isOnlineMode && onlineState}
    <div id="mp-board">
      {#each onlineState.players as player, idx}
        <div class="mp-player-card" class:active={idx === onlineState.currentPlayer}>
          <div class="mp-name">{player.name}</div>
          <div class="mp-stat">Score: {player.score}</div>
          {#if onlineState.mode === 'comp'}
            <div class="mp-stat">Lives: {player.lives_left}</div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}

  <div id="chain-section">
    <div class="section-label">Current Chain</div>
    <div id="chain-bar">
      {#if !displayedChain.length}
        <div id="chain-empty-msg">Start a new chain below!</div>
      {:else}
        {#each displayedChain as link, idx}
          {#if idx > 0}<span class="chain-arrow">→</span>{/if}
          <div class="chain-link" class:active={idx === displayedChain.length - 1}>
            <span class="link-num">{idx + 1}.</span>{link.label}
          </div>
        {/each}
      {/if}
    </div>
  </div>

  <div id="prompt-area">
    <div id="prompt-text">{promptText}</div>
  </div>

  <div id="search-area">
    <div id="search-wrapper">
      <input
        id="chain-input"
        type="text"
        placeholder={isOnlineMode && !isMyTurn ? 'Waiting for current player...' : 'Search player name...'}
        value={currentGuess}
        disabled={(isOnlineMode && !isMyTurn) || loading || (!isOnlineMode && !gameActive)}
        oninput={(event) => onSearchInput((event.currentTarget as HTMLInputElement).value)}
        onkeydown={onKeydown}
      />
      {#if searchResults.length}
        <div id="chain-search-results">
          {#each searchResults as result, idx}
            <button
              class="chain-result-item"
              class:highlighted={idx === selectedIndex}
              type="button"
              onclick={() => { currentGuess = result; selectedFromResults = true; searchResults = []; selectedIndex = -1; }}
            >{result}</button>
          {/each}
        </div>
      {/if}
    </div>
    <button
      id="submit-btn"
      type="button"
      disabled={loading || !selectedFromResults || !currentGuess.trim() || (isOnlineMode && !isMyTurn) || (!isOnlineMode && !gameActive)}
      onclick={() => submitGuess(currentGuess.trim())}
    >Submit</button>
  </div>

  {#if feedback}
    <div id="feedback" class:correct={feedback.type === 'correct'} class:wrong={feedback.type === 'wrong'}>
      <div>{feedback.message}</div>
      {#if feedback.link_results?.length}
        <ul class="link-breakdown">
          {#each feedback.link_results as result}
            <li class:link-pass={result.passed} class:link-fail={!result.passed}>
              {result.passed ? '✓' : '✗'} {result.label}
            </li>
          {/each}
        </ul>
      {/if}
      {#if feedback.examples?.length}
        <div class="examples">Valid answers included: <strong>{feedback.examples.join(', ')}</strong></div>
      {/if}
    </div>
  {/if}

  {#if displayedGuesses.length}
    <div id="guesses-area">
      <div class="section-label">Correct Guesses This Chain</div>
      <div id="guesses-list">
        {#each displayedGuesses as guess, idx}
          <div class="guess-row">
            <span class="guess-num">{idx + 1}.</span>
            <span class="guess-name">{guess.player}{#if guess.by} <small>({guess.by})</small>{/if}</span>
            <span class="guess-pts">+{guess.pts} pts</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  <div id="action-area">
    {#if !isOnlineMode}
      {#if !gameActive && !displayedChain.length}
        <button class="action-btn primary-btn" type="button" disabled={loading} onclick={beginChain}>Start New Chain</button>
      {/if}
      {#if !gameActive && nextChainPlayer}
        <button class="action-btn gold-btn" type="button" disabled={loading} onclick={() => { if (nextChainPlayer) void continueTeammates(nextChainPlayer); }}>Continue with {nextChainPlayer}'s teammates</button>
      {:else if !gameActive && displayedChain.length}
        <button class="action-btn gold-btn" type="button" disabled={loading} onclick={beginChain}>Start New Chain</button>
      {/if}
    {:else if onlineState?.done}
      <button class="action-btn gold-btn" type="button" onclick={playAgain}>Play Again</button>
    {/if}
  </div>
</div>
