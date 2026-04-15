<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { SFX } from '$lib/sfx';
  import {
    finishQuiz,
    guessQuiz,
    listQuizzes,
    startQuiz,
    type QuizFinishResponse,
    type QuizSlot,
    type QuizSummary,
    type Sport
  } from '$lib/api/selected-quizzes';

  let { sport }: { sport: Sport } = $props();

  type Screen = 'list' | 'play' | 'reveal';

  let screen = $state<Screen>('list');
  let listLoading = $state(true);
  let listError = $state('');
  let quizzes = $state<QuizSummary[]>([]);

  let activeQuizId = $state<string | null>(null);
  let activeTitle = $state('');
  let activePrompt = $state('');
  let totalAnswers = $state(0);
  let deadlineMs = $state(0);
  let timeLeft = $state(0);
  let slots = $state<QuizSlot[]>([]);
  let foundBySlot = $state<(string | null)[]>([]);
  let foundCount = $derived(foundBySlot.filter((v) => v !== null).length);
  let flashSlot = $state<number | null>(null);
  let inputState = $state<'idle' | 'correct' | 'wrong'>('idle');
  let flashSlotTimer: ReturnType<typeof setTimeout> | null = null;
  let inputStateTimer: ReturnType<typeof setTimeout> | null = null;
  let lastFlash = $state<{ kind: 'match' | 'duplicate' | 'wrong'; text: string } | null>(null);
  let flashTimer: ReturnType<typeof setTimeout> | null = null;
  let countdownTimer: ReturnType<typeof setInterval> | null = null;
  let gameId = $state<string | null>(null);
  let guess = $state('');
  let starting = $state(false);
  let playError = $state('');
  let revealData = $state<QuizFinishResponse | null>(null);
  let inFlight = $state(false);
  let orderHintKey = $state('');
  let orderDirection = $state<'low' | 'high'>('low');

  const accentBySport = $derived(sport === 'nfl' ? 'yellow' : 'red');
  const title = $derived(sport === 'nfl' ? 'NFL Quizzes' : 'NBA Quizzes');

  const orderedSlotIndices = $derived.by(() => {
    const indices = Array.from({ length: slots.length }, (_, idx) => idx);
    if (!orderHintKey) return indices;
    indices.sort((a, b) => compareHintValues(slots[a]?.hints?.[orderHintKey], slots[b]?.hints?.[orderHintKey], a, b));
    return indices;
  });

  const orderedRevealIndices = $derived.by(() => {
    const answers = revealData?.answers ?? [];
    const indices = Array.from({ length: answers.length }, (_, idx) => idx);
    if (!orderHintKey) return indices;
    indices.sort((a, b) => compareHintValues(answers[a]?.hints?.[orderHintKey], answers[b]?.hints?.[orderHintKey], a, b));
    return indices;
  });

  onMount(() => {
    void loadList();
  });

  async function loadList() {
    listLoading = true;
    listError = '';
    try {
      const data = await listQuizzes(sport);
      quizzes = data.quizzes;
    } catch (error) {
      listError = error instanceof Error ? error.message : 'Could not load quizzes';
    } finally {
      listLoading = false;
    }
  }

  function clearTimers() {
    if (countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
    if (flashTimer) {
      clearTimeout(flashTimer);
      flashTimer = null;
    }
    if (flashSlotTimer) {
      clearTimeout(flashSlotTimer);
      flashSlotTimer = null;
    }
    if (inputStateTimer) {
      clearTimeout(inputStateTimer);
      inputStateTimer = null;
    }
  }

  function pulseSlot(idx: number) {
    if (flashSlotTimer) clearTimeout(flashSlotTimer);
    flashSlot = idx;
    flashSlotTimer = setTimeout(() => {
      flashSlot = null;
    }, 700);
  }

  function pulseInput(state: 'correct' | 'wrong') {
    if (inputStateTimer) clearTimeout(inputStateTimer);
    inputState = state;
    inputStateTimer = setTimeout(() => {
      inputState = 'idle';
    }, 500);
  }

  onDestroy(clearTimers);

  function startCountdown() {
    clearTimers();
    tickCountdown();
    countdownTimer = setInterval(tickCountdown, 250);
  }

  function tickCountdown() {
    const left = Math.max(0, Math.ceil((deadlineMs - Date.now()) / 1000));
    timeLeft = left;
    if (left <= 0) {
      void giveUp();
    }
  }

  function formatTime(seconds: number) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  function parseHintSortValue(value: string | null | undefined) {
    const normalized = (value ?? '').trim();
    if (!normalized) {
      return { missing: true, isNumber: false, number: 0, text: '' };
    }
    const numberMatch = normalized.match(/^-?\d+(?:\.\d+)?/);
    if (numberMatch) {
      return {
        missing: false,
        isNumber: true,
        number: Number(numberMatch[0]),
        text: normalized.toLowerCase()
      };
    }
    return {
      missing: false,
      isNumber: false,
      number: 0,
      text: normalized.toLowerCase()
    };
  }

  function compareHintValues(
    aValue: string | null | undefined,
    bValue: string | null | undefined,
    aIndex: number,
    bIndex: number
  ) {
    const a = parseHintSortValue(aValue);
    const b = parseHintSortValue(bValue);

    if (a.missing !== b.missing) return a.missing ? 1 : -1;

    let diff = 0;
    if (a.isNumber && b.isNumber) {
      diff = a.number - b.number;
    } else {
      diff = a.text.localeCompare(b.text, undefined, { numeric: true, sensitivity: 'base' });
    }
    if (diff === 0) diff = aIndex - bIndex;
    return orderDirection === 'high' ? -diff : diff;
  }

  async function startSelected(quiz: QuizSummary) {
    if (starting) return;
    starting = true;
    playError = '';
    try {
      const data = await startQuiz(sport, quiz.id);
      gameId = data.game_id;
      activeQuizId = data.quiz_id;
      activeTitle = data.title;
      activePrompt = data.prompt;
      totalAnswers = data.total_answers;
      deadlineMs = data.deadline_ms;
      slots = data.slots ?? [];
      foundBySlot = new Array(data.total_answers).fill(null);
      orderHintKey = data.order_hint_key ?? '';
      orderDirection = data.order_direction ?? 'low';
      guess = '';
      lastFlash = null;
      revealData = null;
      screen = 'play';
      startCountdown();
    } catch (error) {
      playError = error instanceof Error ? error.message : 'Could not start quiz';
    } finally {
      starting = false;
    }
  }

  function flash(kind: 'match' | 'duplicate' | 'wrong', text: string) {
    if (flashTimer) clearTimeout(flashTimer);
    lastFlash = { kind, text };
    flashTimer = setTimeout(() => {
      lastFlash = null;
    }, 1100);
  }

  async function tryGuess() {
    if (!gameId || !activeQuizId || inFlight) return;
    const value = guess.trim();
    if (!value) return;
    inFlight = true;
    try {
      const data = await guessQuiz(sport, activeQuizId, { gameId, guess: value });
      if (data.matched && data.matched_index !== null && data.matched_index !== undefined) {
        const next = foundBySlot.slice();
        next[data.matched_index] = data.matched;
        foundBySlot = next;
        guess = '';
        flash('match', data.matched);
        pulseSlot(data.matched_index);
        pulseInput('correct');
        SFX.play('correct');
      } else if (data.duplicate) {
        flash('duplicate', 'Already found');
        guess = '';
        pulseInput('wrong');
        SFX.play('wrong');
      } else {
        flash('wrong', `${value} — not a match`);
        pulseInput('wrong');
        SFX.play('wrong');
      }
      timeLeft = data.time_left_seconds;
      if (data.finished) {
        await finishAndReveal();
      }
    } catch (error) {
      playError = error instanceof Error ? error.message : 'Guess failed';
    } finally {
      inFlight = false;
    }
  }

  async function finishAndReveal() {
    if (!gameId || !activeQuizId) return;
    clearTimers();
    try {
      revealData = await finishQuiz(sport, activeQuizId, gameId);
      screen = 'reveal';
    } catch (error) {
      playError = error instanceof Error ? error.message : 'Finish failed';
    }
  }

  async function giveUp() {
    await finishAndReveal();
  }

  function backToList() {
    clearTimers();
    gameId = null;
    activeQuizId = null;
    revealData = null;
    slots = [];
    foundBySlot = [];
    orderHintKey = '';
    orderDirection = 'low';
    guess = '';
    screen = 'list';
  }

  function formatHints(hints: Record<string, string> | null | undefined): string {
    if (!hints) return '';
    const order = ['college', 'draft_year', 'team', 'year', 'season', 'position'];
    const seen = new Set<string>();
    const parts: string[] = [];
    for (const key of order) {
      if (hints[key]) {
        parts.push(hints[key]);
        seen.add(key);
      }
    }
    for (const [k, v] of Object.entries(hints)) {
      if (!seen.has(k) && v) parts.push(v);
    }
    return parts.join(' · ');
  }

  function onKey(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      event.preventDefault();
      void tryGuess();
    }
  }
</script>

<div class="quizzes-app">
  <div class="quizzes-title-bar">
    <a class="back-link" href="/?tab={sport}">&larr; Back</a>
    <h1>{title}</h1>
  </div>

  {#if screen === 'list'}
    <div class="quizzes-intro">
      <p>Sporcle-style timed quizzes. Pick a quiz, race the clock, type as many answers as you can. Capitalization and punctuation are ignored.</p>
    </div>

    {#if listLoading}
      <div class="quizzes-empty">Loading quizzes…</div>
    {:else if listError}
      <div class="quizzes-error">{listError}</div>
    {:else if !quizzes.length}
      <div class="quizzes-empty">No quizzes yet. Add JSON files under <code>quizzes/{sport}/</code>.</div>
    {:else}
      <div class="quiz-list">
        {#each quizzes as quiz}
          <button
            type="button"
            class="quiz-card accent-{accentBySport}"
            disabled={starting}
            onclick={() => startSelected(quiz)}
          >
            <div class="quiz-card-accent"></div>
            <div class="quiz-card-body">
              <strong>{quiz.title}</strong>
              <small>{quiz.prompt}</small>
              <div class="quiz-card-meta">
                <span>{quiz.total_answers} answers</span>
                <span>·</span>
                <span>{formatTime(quiz.time_limit_seconds)}</span>
              </div>
            </div>
          </button>
        {/each}
      </div>
    {/if}

    {#if playError}
      <div class="quizzes-error">{playError}</div>
    {/if}
  {/if}

  {#if screen === 'play'}
    <div class="quiz-play">
      <div class="quiz-play-header">
        <div class="quiz-play-title">
          <strong>{activeTitle}</strong>
          <small>{activePrompt}</small>
        </div>
        <div class="quiz-play-stats">
          <div class="stat-block">
            <span class="stat-label">Time</span>
            <span class="stat-value" class:warning={timeLeft <= 15}>{formatTime(timeLeft)}</span>
          </div>
          <div class="stat-block">
            <span class="stat-label">Found</span>
            <span class="stat-value">{foundCount} / {totalAnswers}</span>
          </div>
        </div>
      </div>

      <div class="quiz-input-row">
        <input
          class="quiz-input"
          class:correct={inputState === 'correct'}
          class:wrong={inputState === 'wrong'}
          type="text"
          autocomplete="off"
          spellcheck="false"
          placeholder="Type an answer…"
          bind:value={guess}
          onkeydown={onKey}
        />
        <button type="button" class="quiz-give-up" onclick={() => void giveUp()}>Give up</button>
      </div>

      {#if lastFlash}
        <div
          class="quiz-flash"
          class:duplicate={lastFlash.kind === 'duplicate'}
          class:wrong={lastFlash.kind === 'wrong'}
        >
          {lastFlash.kind === 'match' ? `+ ${lastFlash.text}` : lastFlash.text}
        </div>
      {/if}

      <div class="quiz-found-grid">
        {#each orderedSlotIndices as slotIndex, displayIndex}
          {@const slot = slots[slotIndex]}
          {@const filled = foundBySlot[slotIndex]}
          {@const hintText = formatHints(slot?.hints)}
          <div
            class="quiz-found-cell"
            class:empty={!filled}
            class:filled={!!filled}
            class:flash-correct={flashSlot === slotIndex}
          >
            <span class="cell-num">{displayIndex + 1}.</span>
            {#if filled}
              <span class="cell-name">{filled}</span>
            {:else if hintText}
              <span class="cell-hint">{hintText}</span>
            {:else}
              <span class="cell-hint placeholder">—</span>
            {/if}
          </div>
        {/each}
      </div>

      {#if playError}
        <div class="quizzes-error">{playError}</div>
      {/if}
    </div>
  {/if}

  {#if screen === 'reveal' && revealData}
    {@const r = revealData}
    <div class="quiz-reveal">
      <div class="quiz-reveal-header">
        <strong>{r.title}</strong>
        <div class="quiz-reveal-score">
          You found <span class="score">{r.found_count}</span> / {r.total_answers}
          <small>({formatTime(r.elapsed_seconds)} of {formatTime(r.time_limit_seconds)})</small>
        </div>
      </div>

      <div class="quiz-reveal-grid">
        {#each orderedRevealIndices as answerIndex, displayIndex (r.answers[answerIndex].canonical + ':' + answerIndex)}
          {@const ans = r.answers[answerIndex]}
          {@const hintText = formatHints(ans.hints)}
          <div class="quiz-reveal-cell" class:found={ans.found}>
            <span class="cell-num">{displayIndex + 1}.</span>
            <span class="cell-name">{ans.canonical}</span>
            {#if hintText}
              <span class="cell-hint">{hintText}</span>
            {/if}
          </div>
        {/each}
      </div>

      <div class="quiz-reveal-actions">
        <button type="button" class="quiz-back-btn" onclick={backToList}>Back to quizzes</button>
      </div>
    </div>
  {/if}
</div>

<style>
  .quizzes-app {
    padding: 20px 24px 40px;
    color: var(--text);
  }

  .quizzes-title-bar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 18px;
  }
  .quizzes-title-bar h1 {
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 4px;
    font-size: 1.6rem;
    margin: 0;
    color: var(--yellow);
  }
  .back-link {
    color: var(--text-dim);
    text-decoration: none;
    font-weight: 800;
    letter-spacing: 2px;
    font-size: 0.8rem;
    text-transform: uppercase;
  }
  .back-link:hover { color: var(--yellow); }

  .quizzes-intro {
    background: var(--surface);
    border: 3px solid var(--border);
    border-left: 6px solid var(--yellow);
    box-shadow: 4px 4px 0 var(--border);
    padding: 14px 18px;
    margin-bottom: 16px;
    color: var(--text-dim);
    font-size: 0.95rem;
    line-height: 1.45;
  }
  .quizzes-intro p { margin: 0; }

  .quizzes-empty,
  .quizzes-error {
    padding: 20px;
    background: var(--surface);
    border: 3px solid var(--border);
    box-shadow: 4px 4px 0 var(--border);
    color: var(--text-dim);
    font-size: 0.95rem;
  }
  .quizzes-error { border-left: 6px solid var(--red, #d33); color: var(--red-bright, #f55); }

  .quiz-list { display: flex; flex-direction: column; gap: 10px; }
  .quiz-card {
    display: flex;
    align-items: stretch;
    gap: 0;
    padding: 0;
    background: var(--surface);
    border: 3px solid var(--border);
    box-shadow: 4px 4px 0 var(--border);
    color: var(--text);
    text-align: left;
    cursor: pointer;
    font-family: inherit;
  }
  .quiz-card:hover { background: var(--surface-2); }
  .quiz-card:disabled { opacity: 0.6; cursor: progress; }
  .quiz-card-accent { width: 8px; background: var(--yellow); }
  .quiz-card.accent-red .quiz-card-accent { background: var(--red, #d33); }
  .quiz-card-body {
    flex: 1;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .quiz-card-body strong {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.15rem;
    letter-spacing: 2px;
  }
  .quiz-card-body small { color: var(--text-dim); font-size: 0.9rem; line-height: 1.4; }
  .quiz-card-meta {
    margin-top: 6px;
    display: flex;
    gap: 8px;
    color: var(--text-muted);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    font-weight: 800;
  }

  .quiz-play {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .quiz-play-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    background: var(--surface);
    border: 3px solid var(--border);
    box-shadow: 4px 4px 0 var(--border);
    padding: 14px 18px;
  }
  .quiz-play-title { display: flex; flex-direction: column; gap: 4px; flex: 1; }
  .quiz-play-title strong {
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 2px;
    font-size: 1.25rem;
  }
  .quiz-play-title small { color: var(--text-dim); font-size: 0.92rem; line-height: 1.45; }
  .quiz-play-stats { display: flex; gap: 18px; }
  .stat-block { display: flex; flex-direction: column; align-items: flex-end; }
  .stat-label {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 3px;
    color: var(--text-muted);
    font-weight: 800;
  }
  .stat-value {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.6rem;
    letter-spacing: 2px;
  }
  .stat-value.warning { color: var(--red-bright, #f55); }

  .quiz-input-row { display: flex; gap: 10px; }
  .quiz-input {
    flex: 1;
    background: var(--surface-2);
    border: 3px solid var(--border);
    color: var(--text);
    padding: 12px 14px;
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 2px;
    font-size: 1.1rem;
    text-transform: uppercase;
  }
  .quiz-input:focus { outline: none; border-color: var(--yellow); }
  .quiz-input.correct {
    border-color: #25c95b;
    background: rgba(37, 201, 91, 0.18);
    color: #aef0c2;
    box-shadow: 0 0 0 3px rgba(37, 201, 91, 0.25), 0 0 14px rgba(37, 201, 91, 0.55);
    transition: border-color 0.05s, background 0.05s, box-shadow 0.05s;
  }
  .quiz-input.wrong {
    border-color: #e0455a;
    background: rgba(224, 69, 90, 0.18);
    color: #f8c4cc;
    box-shadow: 0 0 0 3px rgba(224, 69, 90, 0.25), 0 0 14px rgba(224, 69, 90, 0.55);
    animation: shake 0.32s ease-in-out;
  }
  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    20% { transform: translateX(-6px); }
    40% { transform: translateX(5px); }
    60% { transform: translateX(-3px); }
    80% { transform: translateX(3px); }
  }
  .quiz-give-up {
    background: var(--surface);
    border: 3px solid var(--border);
    color: var(--text);
    padding: 0 18px;
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 2px;
    font-size: 1rem;
    cursor: pointer;
  }
  .quiz-give-up:hover { background: var(--red, #d33); color: #fff; }

  .quiz-flash {
    background: rgba(37, 201, 91, 0.18);
    border-left: 4px solid #25c95b;
    padding: 8px 12px;
    font-weight: 800;
    letter-spacing: 1px;
    color: #aef0c2;
  }
  .quiz-flash.duplicate {
    background: rgba(255, 255, 255, 0.06);
    border-left-color: var(--text-muted);
    color: var(--text-dim);
  }
  .quiz-flash.wrong {
    background: rgba(224, 69, 90, 0.18);
    border-left-color: #e0455a;
    color: #f8c4cc;
  }

  .quiz-found-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 6px;
  }
  .quiz-found-cell {
    background: var(--surface);
    border: 2px solid var(--border-dim, var(--border));
    padding: 8px 10px;
    font-size: 0.9rem;
    font-weight: 800;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-height: 44px;
  }
  .quiz-found-cell .cell-num {
    font-size: 0.7rem;
    color: var(--text-muted);
    letter-spacing: 1px;
  }
  .quiz-found-cell .cell-name { color: var(--text); }
  .quiz-found-cell .cell-hint {
    font-size: 0.78rem;
    color: var(--text-dim);
    font-weight: 600;
  }
  .quiz-found-cell .cell-hint.placeholder { opacity: 0.45; }
  .quiz-found-cell.empty {
    background: var(--surface-2);
    opacity: 0.85;
  }
  .quiz-found-cell.empty .cell-hint { color: var(--text-muted); }
  .quiz-found-cell.filled {
    background: rgba(37, 201, 91, 0.16);
    border-color: #25c95b;
  }
  .quiz-found-cell.filled .cell-name { color: #d3fadc; }
  .quiz-found-cell.flash-correct {
    background: rgba(37, 201, 91, 0.45);
    box-shadow: 0 0 16px rgba(37, 201, 91, 0.7);
    animation: cellPop 0.7s ease-out;
  }
  @keyframes cellPop {
    0%   { transform: scale(0.95); }
    35%  { transform: scale(1.06); }
    100% { transform: scale(1); }
  }

  .quiz-reveal {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .quiz-reveal-header {
    background: var(--surface);
    border: 3px solid var(--border);
    box-shadow: 4px 4px 0 var(--border);
    padding: 14px 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 14px;
    flex-wrap: wrap;
  }
  .quiz-reveal-header strong {
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 2px;
    font-size: 1.25rem;
  }
  .quiz-reveal-score { font-size: 0.95rem; color: var(--text-dim); }
  .quiz-reveal-score .score { font-weight: 900; color: var(--yellow); font-size: 1.1rem; }
  .quiz-reveal-score small { display: block; font-size: 0.78rem; color: var(--text-muted); margin-top: 2px; }

  .quiz-reveal-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 6px;
  }
  .quiz-reveal-cell {
    background: var(--surface);
    border: 2px solid var(--border-dim, var(--border));
    padding: 8px 10px;
    font-size: 0.92rem;
    color: var(--text-dim);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .quiz-reveal-cell .cell-num {
    font-size: 0.7rem;
    color: var(--text-muted);
    letter-spacing: 1px;
    font-weight: 800;
  }
  .quiz-reveal-cell .cell-name { font-weight: 800; }
  .quiz-reveal-cell .cell-hint {
    font-size: 0.76rem;
    color: var(--text-muted);
    font-weight: 600;
  }
  .quiz-reveal-cell.found {
    background: rgba(245, 199, 0, 0.18);
    border-color: var(--yellow);
    color: var(--text);
  }

  .quiz-reveal-actions { display: flex; justify-content: flex-end; }
  .quiz-back-btn {
    background: var(--yellow);
    border: 3px solid var(--border);
    color: var(--text-dark);
    padding: 10px 18px;
    font-family: 'Bebas Neue', sans-serif;
    letter-spacing: 2px;
    cursor: pointer;
    font-size: 1rem;
  }

</style>
