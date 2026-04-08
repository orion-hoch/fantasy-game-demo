<script lang="ts">
  import '$lib/styles/ttb.css';
  import { type TTBClue, type TTBHint, type Sport, guessTTB, searchTTBPlayers, startTTBGame } from '$lib/api/ttb';

  let { sport }: { sport: Sport } = $props();

  const MAX_WRONG = 5;

  let gameId = $state<string | null>(null);
  let clues: TTBClue[] = $state([]);
  let hints: TTBHint[] = $state([]);
  let revealedHints = $state(1);
  let hintsOpen = $state(false);
  let wrongCount = $state(0);
  let gameActive = $state(false);
  let currentGuess = $state('');
  let searchResults: string[] = $state([]);
  let selectedIndex = $state(-1);
  let feedback = $state<{ type: 'correct' | 'wrong'; message: string } | null>(null);
  let answer = $state('');
  let startError = $state('');
  let mode = $state<'classic' | 'vintage'>('classic');
  let includeDefense = $state(false);
  let hardMode = $state(false);
  let minDraftYear = $state<number | null>(null);
  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  let actionPending = $state(false);

  const remaining = $derived(Math.max(0, MAX_WRONG - wrongCount));
  const visibleHints = $derived(hints.slice(0, revealedHints));
  const title = $derived(sport === 'nfl' ? 'Ticking Time Bomb' : 'NBA Time Bomb');
  const hintBar = $derived(sport === 'nfl'
    ? 'Identify the mystery player from their teammates before the bomb blows.'
    : 'Identify the mystery NBA player from their teammates before the bomb blows.');

  const bombClass = $derived.by(() => {
    if (!gameActive && answer && feedback?.type === 'correct') return 'defused';
    if (!gameActive && answer && feedback?.type === 'wrong') return 'exploded';
    if (gameActive && remaining > 0) return `glow-${remaining}`;
    return '';
  });
  const bombNum = $derived.by(() => {
    if (!gameActive && answer && feedback?.type === 'correct') return 'WIN';
    if (!gameActive && answer && feedback?.type === 'wrong') return 'BOOM';
    if (gameActive) return String(remaining);
    return '?';
  });
  const bombLabel = $derived.by(() => {
    if (!gameActive && answer && feedback?.type === 'correct') return 'defused!';
    if (!gameActive && answer && feedback?.type === 'wrong') return 'boom!';
    if (gameActive) return remaining === 1 ? 'last guess' : 'guesses left';
    return 'press start';
  });

  function resetUi() {
    clues = [];
    hints = [];
    revealedHints = 1;
    hintsOpen = false;
    wrongCount = 0;
    feedback = null;
    answer = '';
    currentGuess = '';
    searchResults = [];
    selectedIndex = -1;
    startError = '';
  }

  async function startGame() {
    resetUi();
    actionPending = true;
    try {
      const data = await startTTBGame(sport, {
        mode,
        includeDefense,
        hardMode,
        minDraftYear
      });
      gameId = data.game_id;
      clues = data.clues;
      hints = data.hints;
      revealedHints = Math.min(1, data.hints.length || 1);
      gameActive = true;
    } catch (error) {
      startError = error instanceof Error ? error.message : 'Could not start game';
      gameActive = false;
    } finally {
      actionPending = false;
    }
  }

  function revealNextHint() {
    if (revealedHints < hints.length) {
      revealedHints += 1;
    }
  }

  async function submitGuess({ skip = false, reveal = false }: { skip?: boolean; reveal?: boolean } = {}) {
    if (!gameId || (!skip && !reveal && !currentGuess.trim()) || actionPending) return;
    actionPending = true;
    searchResults = [];
    selectedIndex = -1;
    try {
      const data = await guessTTB(sport, { gameId, guess: currentGuess.trim(), skip, reveal });
      if (data.error) {
        feedback = { type: 'wrong', message: data.error };
        return;
      }
      if (reveal) {
        answer = data.player || '???';
        feedback = { type: 'wrong', message: 'You gave up.' };
        gameActive = false;
        return;
      }
      if (data.correct) {
        answer = data.player || '';
        feedback = { type: 'correct', message: `${data.player} defused the bomb!` };
        gameActive = false;
        return;
      }

      wrongCount = Number(data.wrong || wrongCount + 1);
      revealNextHint();
      if (data.exploded) {
        answer = data.player || '???';
        feedback = { type: 'wrong', message: skip ? 'Bomb exploded after the skip.' : `${currentGuess || 'That guess'} blew up the bomb.` };
        gameActive = false;
        return;
      }

      if (data.new_clue) clues = [...clues, data.new_clue];
      feedback = { type: 'wrong', message: skip ? 'Skipped. Another clue has been revealed.' : `${currentGuess} was incorrect.` };
      currentGuess = '';
    } catch (error) {
      feedback = { type: 'wrong', message: error instanceof Error ? error.message : 'Request failed' };
    } finally {
      actionPending = false;
    }
  }

  async function onSearchInput(value: string) {
    currentGuess = value;
    if (searchTimer) clearTimeout(searchTimer);
    if (!value.trim()) {
      searchResults = [];
      selectedIndex = -1;
      return;
    }
    searchTimer = setTimeout(async () => {
      try {
        const data = await searchTTBPlayers(sport, value.trim());
        searchResults = data.results.map((result) => result.name);
        selectedIndex = -1;
      } catch {
        searchResults = [];
      }
    }, 200);
  }

  function choosePlayer(name: string) {
    currentGuess = name;
    searchResults = [];
    selectedIndex = -1;
    void submitGuess();
  }

  function onKeydown(event: KeyboardEvent) {
    if (!searchResults.length) {
      if (event.key === 'Enter' && currentGuess.trim()) {
        event.preventDefault();
        void submitGuess();
      }
      return;
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      selectedIndex = Math.min(selectedIndex + 1, searchResults.length - 1);
      currentGuess = searchResults[selectedIndex] || currentGuess;
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      selectedIndex = Math.max(selectedIndex - 1, -1);
      currentGuess = selectedIndex >= 0 ? searchResults[selectedIndex] : currentGuess;
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (selectedIndex >= 0) {
        choosePlayer(searchResults[selectedIndex]);
      } else if (currentGuess.trim()) {
        void submitGuess();
      }
    } else if (event.key === 'Escape') {
      searchResults = [];
      selectedIndex = -1;
    }
  }
</script>

<div id="ttb-app" class:vintage={mode === 'vintage'}>
  <div class="ttb-title-bar">
    <a class="back-link" href="/?tab={sport}">&larr; Back</a>
    <h1>{title}</h1>
  </div>

  <div id="hint-bar">{hintBar}</div>

  <div id="ttb-mode-bar">
    <button class="mode-btn" class:active={mode === 'classic'} type="button" disabled={gameActive || actionPending} onclick={() => (mode = 'classic')}>Classic</button>
    <button class="mode-btn" class:active={mode === 'vintage'} type="button" disabled={gameActive || actionPending} onclick={() => (mode = 'vintage')}>Vintage</button>
    {#if sport === 'nfl'}
      <div class="mode-bar-sep"></div>
      <button class="mode-btn mode-defense-toggle" class:defense-active={includeDefense} type="button" disabled={gameActive || actionPending} onclick={() => (includeDefense = !includeDefense)}>Defense</button>
    {/if}
    <div class="mode-bar-sep"></div>
    <button class="mode-btn mode-hard-toggle" class:hard-active={hardMode} type="button" disabled={gameActive || actionPending} onclick={() => (hardMode = !hardMode)}>Hard</button>
  </div>

  <div id="ttb-filter-bar">
    <label for="ttb-year-slider" id="ttb-filter-label">Draft class: <span>{minDraftYear ? `${minDraftYear}+` : 'All eras'}</span></label>
    <input
      id="ttb-year-slider"
      type="range"
      min={sport === 'nfl' ? '1960' : '1970'}
      max={sport === 'nfl' ? '2010' : '2010'}
      step="5"
      value={String(minDraftYear ?? (sport === 'nfl' ? 1960 : 1970))}
      disabled={gameActive || actionPending}
      oninput={(event) => {
        const year = Number((event.currentTarget as HTMLInputElement).value);
        const minVal = sport === 'nfl' ? 1960 : 1970;
        minDraftYear = year <= minVal ? null : year;
      }}
    />
  </div>

  <div id="game-area">
    <div id="fuse-chain">
      <div id="chain-spark" class:hidden={!gameActive || !clues.length}>★</div>
      <div id="chain-nodes">
        {#each clues as clue}
          <div class="chain-node">
            <div class="chain-wire"></div>
            <div class="chain-pill">
              <span class="pill-name">{clue.text}</span>
            </div>
          </div>
        {/each}
      </div>
      <div id="chain-tail" class:hidden={!gameActive || !clues.length}></div>
    </div>
    <div id="bomb-wrap">
      <div id="bomb-cap" class:hidden={!gameActive}></div>
      <div
        id="bomb-body"
        class={bombClass}
        role="button"
        tabindex="0"
        aria-label={gameActive ? `${remaining} guesses left` : 'Press start'}
        onclick={() => { if (!gameActive) startGame(); }}
        onkeydown={(e) => { if (!gameActive && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); startGame(); } }}
      >
        <div id="bomb-inner">
          <span id="bomb-num">{bombNum}</span>
          <span id="bomb-label">{bombLabel}</span>
        </div>
      </div>
    </div>
  </div>

  {#if answer}
    <div id="answer-reveal">
      <div class="answer-label">The answer was</div>
      <div id="answer-name">{answer}</div>
    </div>
  {/if}

  {#if wrongCount > 0}
    <div id="wrong-guesses">
      {#each Array.from({ length: wrongCount }) as _, idx}
        <div class="wrong-chip">Wrong {idx + 1}</div>
      {/each}
    </div>
  {/if}

  {#if hints.length}
    <div id="hints-section">
      <button class="ttb-btn ttb-btn-hint" type="button" onclick={() => (hintsOpen = !hintsOpen)}>
        💡 {hintsOpen ? 'Hide' : 'Show'} Hints <span class="hint-badge">{revealedHints}/{hints.length}</span>
      </button>
      <div id="hints-panel" class:hidden={!hintsOpen}>
        {#each visibleHints as hint}
          <div class="hint-row">
            <span class="hint-icon">{hint.icon}</span>
            <div class="hint-body">
              <span class="hint-label">{hint.label}</span>
              <span class="hint-text">{hint.text}</span>
            </div>
          </div>
        {/each}
      </div>
    </div>
  {/if}

  {#if feedback}
    <div id="ttb-feedback" class={feedback.type}>{feedback.message}</div>
  {/if}

  <div id="ttb-search-area">
    <div id="ttb-search-wrapper">
      <input
        id="ttb-input"
        type="text"
        placeholder={gameActive ? 'Search player name...' : 'Press the bomb to start'}
        value={currentGuess}
        disabled={!gameActive || actionPending}
        autocomplete="off"
        oninput={(event) => onSearchInput((event.currentTarget as HTMLInputElement).value)}
        onkeydown={onKeydown}
      />
      {#if searchResults.length}
        <div id="ttb-search-results">
          {#each searchResults as result, idx}
            <div class="ttb-result-item" class:highlighted={idx === selectedIndex} role="button" tabindex="0" onclick={() => choosePlayer(result)} onkeydown={(e) => { if (e.key === 'Enter') choosePlayer(result); }}>{result}</div>
          {/each}
        </div>
      {/if}
    </div>
    <button id="ttb-submit-btn" type="button" disabled={!gameActive || !currentGuess.trim() || actionPending} onclick={() => submitGuess()}>Guess</button>
  </div>

  <div id="ttb-action-area">
    {#if !gameActive && gameId}
      <button class="ttb-btn ttb-btn-red" type="button" disabled={actionPending} onclick={startGame}>Play Again</button>
    {:else if !gameActive}
      <button class="ttb-btn ttb-btn-red" type="button" disabled={actionPending} onclick={startGame}>Start Game</button>
    {/if}
    {#if gameActive}
      <button class="ttb-btn ttb-btn-ghost" type="button" disabled={actionPending} onclick={() => submitGuess({ skip: true })}>Skip</button>
      <button class="ttb-btn ttb-btn-ghost" type="button" disabled={actionPending} onclick={() => submitGuess({ reveal: true })}>Give Up</button>
    {/if}
  </div>

  {#if startError}
    <div id="ttb-feedback" class="wrong">{startError}</div>
  {/if}
</div>
