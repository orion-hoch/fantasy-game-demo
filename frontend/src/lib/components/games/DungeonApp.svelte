<script lang="ts">
  import { onMount } from 'svelte';
  import '$lib/styles/dungeon_adventure.css';
  import {
    type DungeonItem,
    type DungeonQuestion,
    type Sport,
    fetchDungeonRewards,
    fetchDungeonEncounter,
    submitDungeonAnswer,
    searchDungeonPlayers
  } from '$lib/api/dungeon';

  let { sport }: { sport: Sport } = $props();

  const CHARACTERS = [
    { id: 'analyst', name: 'The Analyst', subtitle: 'Balanced Scholar', sigil: '@', hp: 36, attack: 6, bonusMult: 1.0, healPerKill: 4, color: '#6c9dbd', desc: 'Steady and methodical. No weaknesses, no special powers — pure trivia mastery.' },
    { id: 'blitzer', name: 'The Blitzer', subtitle: 'Glass Cannon', sigil: '!', hp: 24, attack: 10, bonusMult: 1.0, healPerKill: 2, color: '#e02035', desc: 'Hits like a freight train but can\'t take punishment. Strike first, strike hard.' },
    { id: 'veteran', name: 'The Veteran', subtitle: 'Iron Wall', sigil: '#', hp: 52, attack: 4, bonusMult: 1.2, healPerKill: 8, color: '#d8a84f', desc: 'Built to last. Relics hit harder and healing is generous — patience is your weapon.' },
    { id: 'wildcard', name: 'The Wildcard', subtitle: 'Relic Hunter', sigil: '~', hp: 30, attack: 5, bonusMult: 1.8, healPerKill: 3, color: '#9d6cdd', desc: 'Relic-obsessed. Every item amplifies dramatically — stack deep for pure chaos.' },
  ] as const;

  type Character = (typeof CHARACTERS)[number];

  // Game phases
  type Phase = 'char-select' | 'reward' | 'battle' | 'win' | 'death';

  let phase = $state<Phase>('char-select');
  let selectedChar = $state<Character | null>(null);
  let infiniteMode = $state(false);

  // Stats
  let maxHp = $state(36);
  let hp = $state(36);
  let baseAttack = $state(6);
  let bonusMult = $state(1.0);
  let healPerKill = $state(4);
  let floor = $state(1);
  let kills = $state(0);
  let items: DungeonItem[] = $state([]);
  let usedQuestions: string[] = $state([]);
  let usedPlayerNames = $state<Set<string>>(new Set());

  // Enemy
  let enemyName = $state('');
  let enemyHp = $state(0);
  let enemyMaxHp = $state(0);
  let enemyDamage = $state(0);
  let isBoss = $state(false);
  let bossPhaseGoal = $state(1);
  let bossPhase = $state(1);

  // Question & theme
  let question = $state<DungeonQuestion | null>(null);
  let themeName = $state('Entry Hall');
  let themePrompt = $state('');

  // UI state
  let battleMessage = $state('');
  let rewards: DungeonItem[] = $state([]);
  let rewardTitle = $state('');
  let answerInput = $state('');
  let searchResults: string[] = $state([]);
  let selectedSearchIdx = $state(-1);
  let log: string[] = $state([]);
  let searchTimer: ReturnType<typeof setTimeout> | null = null;
  let actionPending = $state(false);
  let mapOpen = $state(false);

  const totalBonus = $derived(Math.round(items.reduce((s, item) => s + ((item as Record<string, number>).bonus ?? 0), 0) * bonusMult));
  const totalAttack = $derived(baseAttack + totalBonus);
  const title = $derived(sport === 'nfl' ? 'Dungeon Adventure' : 'NBA Dungeon');
  const sportLabel = $derived(sport === 'nfl' ? 'NFL' : 'NBA');

  function addLog(msg: string) {
    log = [msg, ...log];
  }

  function startCharSelect() {
    phase = 'char-select';
    selectedChar = null;
    mapOpen = false;
  }

  async function beginRun() {
    if (!selectedChar) return;
    const ch = selectedChar;
    maxHp = ch.hp;
    hp = ch.hp;
    baseAttack = ch.attack;
    bonusMult = ch.bonusMult;
    healPerKill = ch.healPerKill;
    floor = 1;
    kills = 0;
    items = [];
    usedQuestions = [];
    usedPlayerNames = new Set();
    question = null;
    bossPhase = 1;
    mapOpen = false;
    log = [];
    battleMessage = 'Choose one starter relic to enter the dungeon.';
    await showRewards('Starter Item');
  }

  async function showRewards(title: string) {
    rewardTitle = title;
    actionPending = true;
    try {
      const data = await fetchDungeonRewards(sport, floor, items);
      rewards = data.rewards;
      phase = 'reward';
    } catch (err) {
      battleMessage = err instanceof Error ? err.message : 'Failed to fetch rewards';
    } finally {
      actionPending = false;
    }
  }

  async function pickReward(reward: DungeonItem) {
    items = [...items, reward];
    addLog(`You take ${(reward as Record<string, string>).name ?? 'an item'}.`);
    await nextEncounter();
  }

  async function skipReward() {
    addLog('You skip the item and keep your build unchanged.');
    await nextEncounter();
  }

  async function nextEncounter() {
    usedQuestions = [];
    actionPending = true;
    try {
      const data = await fetchDungeonEncounter(sport, floor, items, usedQuestions);
      themeName = data.theme?.name ?? 'Unknown';
      themePrompt = data.theme?.prompt ?? '';
      const e = data.enemy;
      enemyName = e.name;
      enemyHp = e.hp;
      enemyMaxHp = e.hp;
      enemyDamage = e.damage ?? 3;
      isBoss = !!e.is_boss;
      bossPhaseGoal = e.phase_goal ?? 1;
      bossPhase = 1;
      question = data.question;
      if (data.question?.id) usedQuestions = [...usedQuestions, data.question.id];
      answerInput = '';
      searchResults = [];
      mapOpen = false;
      battleMessage = isBoss
        ? 'Boss encounter: survive multiple phases.'
        : 'Battle screen ready. Answer trivia to deal damage.';
      phase = 'battle';
    } catch (err) {
      battleMessage = err instanceof Error ? err.message : 'Failed to load encounter';
    } finally {
      actionPending = false;
    }
  }

  async function refreshQuestion() {
    try {
      const data = await fetchDungeonEncounter(sport, floor, items, usedQuestions);
      themeName = data.theme?.name ?? themeName;
      question = data.question;
      if (data.question?.id) usedQuestions = [...usedQuestions, data.question.id];
      searchResults = [];
    } catch (err) {
      battleMessage = err instanceof Error ? err.message : 'Failed to refresh question';
    }
  }

  async function handleAnswer() {
    const answer = answerInput.trim();
    if (!answer || !question || actionPending) return;
    actionPending = true;
    searchResults = [];

    try {
      const result = await submitDungeonAnswer(sport, question, items, answer);

      if (result.correct) {
        const playerName = (result as Record<string, string>).player ?? answer;

        if (infiniteMode && usedPlayerNames.has(playerName)) {
          hp -= enemyDamage;
          battleMessage = `${playerName} already used this run. You take ${enemyDamage} damage.`;
          addLog(`Duplicate! Enemy hits for ${enemyDamage}.`);
          if (hp <= 0) { endRun('Your run ends — no more fresh answers.'); return; }
          await refreshQuestion();
        } else {
          if (infiniteMode) usedPlayerNames = new Set([...usedPlayerNames, playerName]);
          const damage = totalAttack;
          enemyHp = Math.max(0, enemyHp - damage);
          battleMessage = `${playerName} fits every rule. You deal ${damage} damage.`;
          addLog(`${playerName} clears the prompt for ${damage} damage.`);

          if (enemyHp <= 0) {
            if (isBoss) {
              await handleBossPhaseBreak();
            } else {
              await handleVictory();
            }
            answerInput = '';
            actionPending = false;
            return;
          }
          await refreshQuestion();
        }
      } else {
        hp -= enemyDamage;
        const filterFails = (result as Record<string, string[]>).filter_failures ?? [];
        const questionMatch = (result as Record<string, boolean>).question_match ?? false;
        const playerName = (result as Record<string, string>).player ?? answer;
        if (questionMatch && filterFails.length) {
          battleMessage = `${playerName} fits the prompt but breaks: ${filterFails.join(', ')}. You take ${enemyDamage}.`;
        } else {
          battleMessage = `That answer misses the prompt. You take ${enemyDamage}.`;
        }
        addLog(`Enemy hits for ${enemyDamage}.`);
        if (hp <= 0) { endRun('Your run ends in the dungeon.'); return; }
        await refreshQuestion();
      }
    } catch (err) {
      battleMessage = err instanceof Error ? err.message : 'Request failed';
    } finally {
      answerInput = '';
      actionPending = false;
    }
  }

  async function handleVictory() {
    kills += 1;
    hp = Math.min(maxHp, hp + healPerKill);
    addLog(`The ${enemyName} falls. You recover ${healPerKill} HP.`);
    floor += 1;

    if (!infiniteMode && floor > 6) {
      phase = 'win';
      addLog('You escape the final chamber. Dungeon cleared!');
      return;
    }

    const rTitle = (floor === 6 && !infiniteMode) ? 'Boss Prep Item' : `Floor ${floor} Item`;
    await showRewards(rTitle);
  }

  async function handleBossPhaseBreak() {
    if (bossPhase >= bossPhaseGoal) {
      await handleVictory();
      return;
    }
    bossPhase += 1;
    enemyHp = enemyMaxHp;
    enemyDamage += 1;
    addLog(`Boss phase ${bossPhase - 1} breaks. The enemy resets.`);
    battleMessage = `Boss phase ${bossPhase - 1} is down. New prompt incoming.`;
    await refreshQuestion();
  }

  function endRun(message: string) {
    phase = 'death';
    question = null;
    battleMessage = message;
  }

  function continueInfinite() {
    infiniteMode = true;
    floor = 7;
    phase = 'battle';
    usedPlayerNames = new Set();
    nextEncounter();
  }

  async function onSearchInput(value: string) {
    answerInput = value;
    if (searchTimer) clearTimeout(searchTimer);
    if (!value.trim()) { searchResults = []; selectedSearchIdx = -1; return; }
    searchTimer = setTimeout(async () => {
      try {
        const data = await searchDungeonPlayers(sport, value.trim(), items, question);
        searchResults = data.results;
        selectedSearchIdx = -1;
      } catch { searchResults = []; }
    }, 200);
  }

  function chooseSearchResult(name: string) {
    answerInput = name;
    searchResults = [];
    selectedSearchIdx = -1;
  }

  function onKeydown(event: KeyboardEvent) {
    if (!searchResults.length) {
      if (event.key === 'Enter' && answerInput.trim()) { event.preventDefault(); handleAnswer(); }
      return;
    }
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      selectedSearchIdx = Math.min(selectedSearchIdx + 1, searchResults.length - 1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      selectedSearchIdx = Math.max(selectedSearchIdx - 1, -1);
    } else if (event.key === 'Enter') {
      event.preventDefault();
      if (selectedSearchIdx >= 0) { chooseSearchResult(searchResults[selectedSearchIdx]); }
      else { handleAnswer(); }
    } else if (event.key === 'Escape') {
      searchResults = [];
      selectedSearchIdx = -1;
    }
  }

  function hpPercent(current: number, max: number): number {
    return max > 0 ? Math.max(0, Math.min(100, (current / max) * 100)) : 0;
  }

  onMount(() => {
    document.body.classList.add('dungeon-mode');
    return () => document.body.classList.remove('dungeon-mode');
  });
</script>

<div class="dungeon-page">
  <!-- CHARACTER SELECT -->
  {#if phase === 'char-select'}
    <section class="char-create-panel">
      <div class="char-shell">
        <a href="/?tab={sport}" class="back-link">&larr; Back</a>
        <div class="char-header">
          <p class="char-eyebrow">{sportLabel} Roguelike Trivia</p>
          <h1 class="char-title">{title}</h1>
          <p class="char-intro">Choose your class before entering the dungeon. Your choice shapes HP, attack power, relic synergy, and healing.</p>
        </div>
        <div class="mode-row">
          <button type="button" class="mode-btn" class:active={!infiniteMode} onclick={() => (infiniteMode = false)}>Normal — 6 Floors</button>
          <button type="button" class="mode-btn" class:active={infiniteMode} onclick={() => (infiniteMode = true)}>Infinite — Until Death</button>
        </div>
        <div class="char-options">
          {#each CHARACTERS as ch}
            <button
              type="button"
              class="char-card"
              class:selected={selectedChar?.id === ch.id}
              onclick={() => (selectedChar = ch)}
            >
              <div class="char-card-top">
                <div>
                  <div class="char-name">{ch.name}</div>
                  <div class="char-subtitle">{ch.subtitle}</div>
                </div>
                <div class="char-sigil">{ch.sigil}</div>
              </div>
              <div class="char-stats">
                <div class="char-stat"><span class="stat-label">HP</span><span class="stat-val">{ch.hp}</span></div>
                <div class="char-stat"><span class="stat-label">ATK</span><span class="stat-val">{ch.attack}</span></div>
                <div class="char-stat"><span class="stat-label">Relic ×</span><span class="stat-val">{ch.bonusMult.toFixed(1)}</span></div>
                <div class="char-stat"><span class="stat-label">Heal/Kill</span><span class="stat-val">+{ch.healPerKill}</span></div>
              </div>
              <p class="char-desc">{ch.desc}</p>
            </button>
          {/each}
        </div>
        <button class="begin-btn" type="button" disabled={!selectedChar} onclick={beginRun}>Enter the Dungeon</button>
      </div>
    </section>

  <!-- WIN SCREEN -->
  {:else if phase === 'win'}
    <section class="outcome-panel">
      <div class="outcome-shell">
        <pre class="outcome-ascii">{"  DUNGEON CLEARED  "}</pre>
        <p class="eyebrow">Victory</p>
        <h2 class="outcome-title win-title">Dungeon Cleared!</h2>
        <p class="outcome-stats">
          Floors cleared: 6 · Enemies defeated: {kills} · Relics: {items.length} · Final ATK: {totalAttack} · Class: {selectedChar?.name ?? 'Unknown'}
        </p>
        <div class="outcome-actions">
          <button class="begin-btn outcome-btn-alt" type="button" onclick={continueInfinite}>Continue in Infinite Mode</button>
          <button class="begin-btn" type="button" onclick={startCharSelect}>New Run</button>
        </div>
      </div>
    </section>

  <!-- DEATH SCREEN -->
  {:else if phase === 'death'}
    <section class="outcome-panel">
      <div class="outcome-shell">
        <pre class="outcome-ascii">{"  THE DUNGEON CLAIMS ANOTHER SOUL  "}</pre>
        <p class="eyebrow">Defeated</p>
        <h2 class="outcome-title death-title">Your Run Ends Here</h2>
        <p class="outcome-stats">
          Reached floor {floor} · Enemies defeated: {kills} · Relics: {items.length} · ATK: {totalAttack}
          {#if infiniteMode} · Players used: {usedPlayerNames.size}{/if}
          · Class: {selectedChar?.name ?? 'Unknown'}
        </p>
        <button class="begin-btn" type="button" onclick={startCharSelect}>Try Again</button>
      </div>
    </section>

  <!-- BATTLE / REWARD PHASE -->
  {:else}
    <header class="dungeon-header">
      <div>
        <p class="eyebrow">{sportLabel} Desktop Roguelike Trivia</p>
        <h1>{title}</h1>
        <p class="subhead">Collect relics that filter your answers and deal more damage.</p>
      </div>
      <a href="/?tab={sport}" class="back-link">&larr; Back</a>
    </header>

    <main class="dungeon-layout">
      <section class="battle-column panel">
        <div class="battle-topbar">
          <div>
            <p class="label">Zone</p>
            <strong>{themeName}</strong>
          </div>
          <div>
            <p class="label">Floor</p>
            <strong>Floor {floor}{infiniteMode && floor > 6 ? ' ∞' : ''}</strong>
          </div>
          {#if isBoss}
            <div>
              <p class="label">Boss Phase</p>
              <strong>{bossPhase} / {bossPhaseGoal}</strong>
            </div>
          {:else}
            <div></div>
          {/if}
          <button type="button" class="map-btn" onclick={() => (mapOpen = !mapOpen)}>{mapOpen ? 'Close Map' : 'Open Map'}</button>
        </div>

        <div class="ascii-stage">
          <pre class="ascii-view">{enemyName ? `\n   Encounter: ${enemyName}\n   HP ${enemyHp} / ${enemyMaxHp}\n   DMG ${enemyDamage}` : '\n   Awaiting encounter...'}</pre>
          {#if mapOpen}
            <div class="map-overlay">
              <div class="map-overlay-head">
                <strong>Run Map</strong>
                <button type="button" class="ghost-btn" onclick={() => (mapOpen = false)}>Close</button>
              </div>
              <pre class="map-view">
{#each [1,2,3,4,5,6] as f}
  {f < floor ? '×' : f === floor ? '@' : '○'}  Floor {f}{f === floor ? '  ← here' : ''}
{/each}{#if infiniteMode && floor > 6}
  ∞  Floor {floor}  ← here
{/if}

  Victories: {kills}
  Relics: {items.length}
  Mode: {infiniteMode ? 'Infinite' : 'Normal'}
              </pre>
            </div>
          {/if}
        </div>

        <div class="encounter-strip">
          <div>
            <p class="label">Enemy</p>
            <h2>{enemyName || 'Awaiting Crawl'}</h2>
            <p class="muted">{themePrompt || 'Choose a relic to begin the run.'}</p>
          </div>
          <div class="encounter-stats">
            <div class="meter-box"><p class="label">Enemy HP</p><strong>{enemyHp} / {enemyMaxHp}</strong></div>
            <div class="meter-box"><p class="label">Enemy DMG</p><strong>{enemyDamage}</strong></div>
          </div>
        </div>

        <div class="question-box">
          <p class="label">Prompt</p>
          <p>{question ? ((question as Record<string, string>).prompt ?? question.text) : 'Pick a relic to begin your run.'}</p>
          {#if question}
            <p class="muted">{(question as Record<string, number>).valid_count ?? 0} valid answers solve this prompt with your current relic build.</p>
          {/if}
        </div>

        <form class="answer-form" autocomplete="off" onsubmit={(e) => { e.preventDefault(); handleAnswer(); }}>
          <div class="answer-stack">
            <input
              type="text"
              placeholder="Type a player name"
              value={answerInput}
              disabled={actionPending || phase !== 'battle'}
              oninput={(e) => onSearchInput((e.currentTarget as HTMLInputElement).value)}
              onkeydown={onKeydown}
            />
            {#if searchResults.length}
              <div class="search-results">
                {#each searchResults as result, idx}
                  <div
                    class="search-item"
                    class:active={idx === selectedSearchIdx}
                    class:used-player={infiniteMode && usedPlayerNames.has(result)}
                    role="button"
                    tabindex="0"
                    onmousedown={(e) => { e.preventDefault(); chooseSearchResult(result); }}
                    onkeydown={(e) => { if (e.key === 'Enter') chooseSearchResult(result); }}
                  >
                    {result}{infiniteMode && usedPlayerNames.has(result) ? ' [used]' : ''}
                  </div>
                {/each}
              </div>
            {/if}
          </div>
          <button type="submit" disabled={!answerInput.trim() || actionPending || phase !== 'battle'}>Strike</button>
        </form>

        <div class="battle-message">{battleMessage || 'Choose one starter relic to enter the dungeon.'}</div>
      </section>

      <aside class="sidebar-column">
        <section class="panel stat-panel">
          <div class="panel-head">
            <span>{selectedChar?.name ?? 'Hero'}</span>
            <span>ATK {totalAttack}</span>
          </div>
          <div class="stat-grid">
            <div><p class="label">Health</p><strong>{Math.max(0, hp)} / {maxHp}</strong></div>
            <div><p class="label">Victories</p><strong>{kills}</strong></div>
            <div><p class="label">Base</p><strong>{baseAttack}</strong></div>
            <div><p class="label">Bonus</p><strong>{totalBonus}</strong></div>
          </div>
        </section>

        <section class="panel inventory-panel">
          <div class="panel-head">
            <span>Inventory</span>
            <span>{items.length}</span>
          </div>
          <div class="inventory-list">
            {#each items as item}
              <div class="inventory-card" data-tooltip="{(item as Record<string, string>).name} — {(item as Record<string, string>).filter_text} | +{(item as Record<string, number>).bonus} ATK">
                <strong style="color:var(--yellow);font-family:'Bebas Neue',sans-serif;letter-spacing:1px;font-size:0.78rem;text-align:center;">{(item as Record<string, string>).name}</strong>
              </div>
            {/each}
          </div>
        </section>

        <section class="panel log-panel">
          <div class="panel-head">
            <span>Run Log</span>
            <button type="button" class="ghost-btn" onclick={startCharSelect}>Restart</button>
          </div>
          <div class="log-list">
            {#each log.slice(0, 20) as entry}
              <div class="log-entry">{entry}</div>
            {/each}
          </div>
        </section>
      </aside>
    </main>

    {#if phase === 'reward'}
      <section class="reward-panel">
        <div class="reward-shell panel">
          <p class="eyebrow">Spoils</p>
          <h2 id="reward-title">{rewardTitle}</h2>
          <p class="muted">Each run rolls a wider relic pool. Take one for more damage or skip to keep your answer pool open.</p>
          <div class="reward-options">
            {#each rewards as reward}
              <div class="reward-card">
                <div class="reward-head">
                  <strong>{(reward as Record<string, string>).name}</strong>
                </div>
                <div class="muted" style="font-size:0.82rem;line-height:1.4;">{(reward as Record<string, string>).filter_text ?? ''}</div>
                <div class="muted" style="font-size:0.7rem;margin-top:6px;">
                  {(reward as Record<string, string>).rarity ?? 'common'} relic · +{(reward as Record<string, number>).bonus ?? 0} ATK
                </div>
                <button type="button" onclick={() => pickReward(reward)}>Take Item</button>
              </div>
            {/each}
          </div>
          <button type="button" class="skip-btn" onclick={skipReward}>Skip Item</button>
        </div>
      </section>
    {/if}
  {/if}
</div>
