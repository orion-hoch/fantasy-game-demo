<script lang="ts">
  import { onMount } from 'svelte';
  import '$lib/styles/balatro.css';
  import type { Card, Joker, ShopItem, ShopPack, Screen, Sport, GameState } from './types';
  import {
    startBalatroGame,
    playBalatroHand,
    discardBalatroCards,
    selectBalatroJoker,
    previewBalatroHand,
    leaveBalatroShop,
    buyBalatroItem,
    sellBalatroJoker,
    restockBalatroShop,
    openBalatroPack,
    confirmBalatroPackPicks,
    advanceBalatroFight,
    claimBalatroReward,
    startBalatroInfinity,
  } from '$lib/api/balatro';

  let { sport }: { sport: Sport } = $props();

  // ── Core game state ──────────────────────────────────────────────
  let screen = $state<Screen>('start');
  let gameId = $state('');
  let hand: Card[] = $state([]);
  let jokers: Joker[] = $state([]);
  let mode = $state('normal');
  let floor = $state(1);
  let round = $state(1);
  let fight = $state(1);
  let bossEffect = $state<string | null>(null);
  let levelName = $state('Preseason');
  let targetScore = $state(0);
  let currentScore = $state(0);
  let handsRemaining = $state(4);
  let discardsRemaining = $state(3);
  let coins = $state(4);
  let skillLevels = $state<Record<string, number>>({});
  let comboBoosts = $state<Record<string, number>>({});
  let cardEffects = $state<Record<string, string[]>>({});
  let shopItems: ShopItem[] = $state([]);
  let shopPacks: ShopPack[] = $state([]);
  let maxJokers = $state(5);
  let jokerState = $state<Record<string, unknown>>({});
  let heldCards: Card[] = $state([]);
  let deckCards: Card[] = $state([]);
  let restockCount = $state(0);

  // ── UI state ─────────────────────────────────────────────────────
  let selectedIds = $state<Set<string>>(new Set());
  let actionPending = $state(false);
  let errorMsg = $state('');
  let lastPlayResult = $state<{ handName: string; score: number; basePts: number; totalMult: number } | null>(null);
  let logEntries: string[] = $state([]);
  let previewData = $state<{ hand_name?: string; score?: number; base_pts?: number; total_mult?: number } | null>(null);
  let gameWon = $state(false);

  // Reward state
  let rewardOptions: Joker[] = $state([]);
  let rewardCoins = $state(0);

  // Pack opening state
  let packCards: Card[] = $state([]);
  let packSelectedIds = $state<Set<string>>(new Set());
  let packMaxPicks = $state(1);
  let packOpen = $state(false);

  const title = $derived(sport === 'nfl' ? 'NFL Balatro' : 'NBA Balatro');

  function addLog(msg: string) {
    logEntries = [msg, ...logEntries.slice(0, 49)];
  }

  function toggleCard(id: string) {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else if (next.size < 5) next.add(id);
    selectedIds = next;
    if (next.size > 0) fetchPreview();
    else previewData = null;
  }

  async function fetchPreview() {
    if (!gameId || selectedIds.size === 0) return;
    try {
      const data = await previewBalatroHand(sport, gameId, Array.from(selectedIds));
      previewData = data;
    } catch { /* ignore preview errors */ }
  }

  // ── Apply server state ───────────────────────────────────────────
  function applyState(data: GameState) {
    if (data.hand !== undefined) hand = data.hand;
    if (data.jokers !== undefined) jokers = data.jokers;
    if (data.floor !== undefined) floor = data.floor;
    if (data.round !== undefined) round = data.round;
    if (data.fight !== undefined) fight = data.fight;
    if (data.boss_effect !== undefined) bossEffect = data.boss_effect;
    if (data.level_name !== undefined) levelName = data.level_name;
    if (data.target_score !== undefined) targetScore = data.target_score;
    if (data.cumulative_score !== undefined) currentScore = data.cumulative_score;
    if (data.current_score !== undefined) currentScore = data.current_score;
    if (data.hands_remaining !== undefined) handsRemaining = data.hands_remaining;
    if (data.discards_remaining !== undefined) discardsRemaining = data.discards_remaining;
    if (data.coins !== undefined) coins = data.coins;
    if (data.skill_levels) skillLevels = data.skill_levels;
    if (data.combo_boosts) comboBoosts = data.combo_boosts;
    if (data.card_effects) cardEffects = data.card_effects;
    if (data.shop_items) shopItems = data.shop_items;
    if (data.shop_packs) shopPacks = data.shop_packs;
    if (data.max_jokers !== undefined) maxJokers = data.max_jokers;
    if (data.joker_state) jokerState = data.joker_state;
    if (data.held_cards !== undefined) heldCards = data.held_cards;
    if (data.deck_cards !== undefined) deckCards = data.deck_cards;
    selectedIds = new Set();
    previewData = null;
    errorMsg = '';
  }

  // ── Game actions ─────────────────────────────────────────────────
  async function handleStart() {
    actionPending = true;
    errorMsg = '';
    try {
      const data = await startBalatroGame(sport, mode) as GameState;
      if (data.error) { errorMsg = data.error; return; }
      gameId = data.game_id;
      currentScore = 0;
      logEntries = [];
      restockCount = 0;
      lastPlayResult = null;
      gameWon = false;
      applyState(data);
      screen = 'playing';
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Failed to start game';
    } finally {
      actionPending = false;
    }
  }

  async function handlePlayHand() {
    if (selectedIds.size === 0 || actionPending) return;
    actionPending = true;
    try {
      const data = await playBalatroHand(sport, gameId, Array.from(selectedIds)) as GameState;
      if (data.error) { errorMsg = data.error; actionPending = false; return; }

      lastPlayResult = {
        handName: data.hand_name ?? '',
        score: data.score ?? 0,
        basePts: data.base_pts ?? 0,
        totalMult: data.total_mult ?? 0,
      };
      addLog(`${data.hand_name}: +${formatNum(data.score ?? 0)}${data.coins_earned ? ` | +$${data.coins_earned}` : ''}`);

      applyState(data);

      const status = data.status;
      if (status === 'won_fight' || status === 'won_level') {
        setTimeout(() => handleAdvanceFight(), 1200);
      } else if (status === 'won_game') {
        setTimeout(() => showGameOver(true), 1200);
      } else if (status === 'lost') {
        setTimeout(() => showGameOver(false), 1200);
      }
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Play hand failed';
    } finally {
      actionPending = false;
    }
  }

  async function handleDiscard() {
    if (selectedIds.size === 0 || discardsRemaining <= 0 || actionPending) return;
    actionPending = true;
    try {
      const data = await discardBalatroCards(sport, gameId, Array.from(selectedIds)) as GameState;
      if (data.error) { errorMsg = data.error; return; }
      addLog(`Discarded ${selectedIds.size} card(s)`);
      applyState(data);
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Discard failed';
    } finally {
      actionPending = false;
    }
  }

  async function handleAdvanceFight() {
    try {
      const data = await advanceBalatroFight(sport, gameId) as GameState;
      if (data.error) { errorMsg = data.error; return; }
      if (data.coins !== undefined) coins = data.coins;
      rewardOptions = (data.reward_options ?? []) as Joker[];
      rewardCoins = (data.reward_coins as number) ?? 0;
      screen = 'reward';
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Advance failed';
    }
  }

  async function handleClaimReward(choice: string, jokerId?: string) {
    actionPending = true;
    try {
      const data = await claimBalatroReward(sport, gameId, choice, jokerId) as GameState;
      if (data.error) { errorMsg = data.error; return; }
      applyState(data);
      shopItems = data.shop_items ?? [];
      shopPacks = data.shop_packs ?? [];
      restockCount = 0;
      screen = 'shop';
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Claim reward failed';
    } finally {
      actionPending = false;
    }
  }

  async function handleSelectJoker(jokerId: string) {
    actionPending = true;
    try {
      const data = await selectBalatroJoker(sport, gameId, jokerId) as GameState;
      if (data.error) { errorMsg = data.error; return; }
      applyState(data);
      if (data.shop_items) shopItems = data.shop_items;
      if (data.shop_packs) shopPacks = data.shop_packs;
      restockCount = 0;
      screen = 'shop';
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Select joker failed';
    } finally {
      actionPending = false;
    }
  }

  async function handleBuyItem(shopId: string, itemType: string) {
    actionPending = true;
    try {
      const data = await buyBalatroItem(sport, gameId, shopId, itemType) as GameState;
      if (data.error) { errorMsg = data.error; return; }
      applyState(data);
      if (data.shop_items) shopItems = data.shop_items;
      if (data.shop_packs) shopPacks = data.shop_packs;
      addLog(`Bought ${itemType}`);
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Buy failed';
    } finally {
      actionPending = false;
    }
  }

  async function handleSellJoker(jokerId: string) {
    actionPending = true;
    try {
      const data = await sellBalatroJoker(sport, gameId, jokerId) as GameState;
      if (data.error) { errorMsg = data.error; return; }
      applyState(data);
      addLog('Sold joker');
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Sell failed';
    } finally {
      actionPending = false;
    }
  }

  async function handleRestock() {
    actionPending = true;
    try {
      const data = await restockBalatroShop(sport, gameId) as GameState;
      if (data.error) { errorMsg = data.error; return; }
      applyState(data);
      if (data.shop_items) shopItems = data.shop_items;
      if (data.shop_packs) shopPacks = data.shop_packs;
      restockCount += 1;
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Restock failed';
    } finally {
      actionPending = false;
    }
  }

  async function handleOpenPack(packId: string) {
    actionPending = true;
    try {
      const data = await openBalatroPack(sport, gameId, packId) as Record<string, unknown>;
      if (data.error) { errorMsg = data.error as string; return; }
      packCards = (data.cards ?? []) as Card[];
      packMaxPicks = (data.max_picks as number) ?? 1;
      packSelectedIds = new Set();
      packOpen = true;
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Open pack failed';
    } finally {
      actionPending = false;
    }
  }

  async function handleConfirmPackPicks() {
    actionPending = true;
    try {
      const data = await confirmBalatroPackPicks(sport, gameId, Array.from(packSelectedIds)) as GameState;
      if (data.error) { errorMsg = data.error; return; }
      applyState(data);
      if (data.shop_items) shopItems = data.shop_items;
      if (data.shop_packs) shopPacks = data.shop_packs;
      packOpen = false;
      packCards = [];
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Confirm picks failed';
    } finally {
      actionPending = false;
    }
  }

  async function handleLeaveShop() {
    actionPending = true;
    try {
      const data = await leaveBalatroShop(sport, gameId) as GameState;
      if (data.error) { errorMsg = data.error; return; }
      currentScore = 0;
      lastPlayResult = null;
      logEntries = [];
      applyState(data);
      screen = 'playing';
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Leave shop failed';
    } finally {
      actionPending = false;
    }
  }

  function showGameOver(won: boolean) {
    gameWon = won;
    screen = 'gameover';
  }

  async function handleStartInfinity() {
    actionPending = true;
    try {
      const data = await startBalatroInfinity(sport, gameId) as GameState;
      if (data.error) { errorMsg = data.error; return; }
      currentScore = 0;
      lastPlayResult = null;
      logEntries = [];
      applyState(data);
      screen = 'playing';
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Start infinity failed';
    } finally {
      actionPending = false;
    }
  }

  function handleRestart() {
    screen = 'start';
    gameId = '';
    selectedIds = new Set();
    logEntries = [];
    lastPlayResult = null;
    previewData = null;
    errorMsg = '';
  }

  function togglePackCard(id: string) {
    const next = new Set(packSelectedIds);
    if (next.has(id)) next.delete(id);
    else if (next.size < packMaxPicks) next.add(id);
    packSelectedIds = next;
  }

  function formatNum(n: number): string {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
    return String(n);
  }

  function scorePercent(): number {
    return targetScore > 0 ? Math.min(100, (currentScore / targetScore) * 100) : 0;
  }

  const backHref = $derived(sport === 'nfl' ? '/?tab=nfl' : '/?tab=nba');
  const titleMain = $derived(sport === 'nfl' ? 'NFL BALATRO' : 'NBA BALATRO');
  const titleSub = $derived(sport === 'nfl' ? 'Skill Position Edition' : 'Hardwood Edition');

  type HandTypeRow = { name: string; mult: string; desc: string; royal?: boolean };
  const handTypes: HandTypeRow[] = $derived(sport === 'nfl' ? [
    { name: 'Highlight Reel', mult: '1x', desc: 'Best single card' },
    { name: 'Dynamic Duo', mult: '1.5x', desc: '2 of same position' },
    { name: 'Triple Threat', mult: '2x', desc: '3 of same position' },
    { name: 'Quad Set', mult: '3x', desc: '4 of same position' },
    { name: 'Balanced Offense', mult: '3.5x', desc: 'QB + 2 WRs + 2 RBs + TE' },
    { name: 'Position Split', mult: '4x', desc: '3 of one position + 3 of another' },
    { name: 'Division Straight', mult: '5x', desc: '5 cards from same division' },
    { name: 'Position Flush', mult: '5x', desc: '5 of same position' },
    { name: 'Six of a Kind', mult: '5.5x', desc: '6 of the same position' },
    { name: 'Division Six', mult: '6x', desc: '6 cards from same division' },
    { name: 'Division Balanced Offense', mult: '25x', desc: 'QB + 2 WRs + 2 RBs + TE, all same division', royal: true },
  ] : [
    { name: 'Highlight Reel', mult: '1x', desc: 'Best single card' },
    { name: 'Dynamic Duo', mult: '1.5x', desc: '2 of same position' },
    { name: 'Triple Threat', mult: '2x', desc: '3 of same position' },
    { name: 'Quad Set', mult: '3x', desc: '4 of same position' },
    { name: 'Starting Five', mult: '3.5x', desc: 'G + G + F + F + C' },
    { name: 'Position Split', mult: '4x', desc: '3 of one position + 3 of another' },
    { name: 'Conference Straight', mult: '5x', desc: '5 cards from same conference' },
    { name: 'Position Flush', mult: '5x', desc: '5 of same position' },
    { name: 'Six of a Kind', mult: '5.5x', desc: '6 of the same position' },
    { name: 'Conference Six', mult: '6x', desc: '6 cards from same conference' },
    { name: 'Conference Starting Five', mult: '25x', desc: 'G + G + F + F + C, all same conference', royal: true },
  ]);

  function posClass(pos: string): string {
    const p = (pos || '').toLowerCase();
    if (sport === 'nfl') {
      if (p === 'qb') return 'card-pos-qb';
      if (p === 'rb') return 'card-pos-rb';
      if (p === 'wr') return 'card-pos-wr';
      if (p === 'te') return 'card-pos-te';
    } else {
      if (p === 'g') return 'card-pos-qb';
      if (p === 'f') return 'card-pos-rb';
      if (p === 'c') return 'card-pos-wr';
    }
    return '';
  }

  onMount(() => {
    document.body.classList.add('bal-page');
    if (sport === 'nba') document.body.classList.add('bal-nba');
    return () => {
      document.body.classList.remove('bal-page');
      document.body.classList.remove('bal-nba');
    };
  });
</script>

<div id="bal-app">

  {#if errorMsg}
    <div class="bal-error">{errorMsg} <button type="button" onclick={() => (errorMsg = '')}>×</button></div>
  {/if}

  <!-- START SCREEN -->
  {#if screen === 'start'}
    <div id="start-screen" class="screen active">
      <div class="start-inner">
        <a href={backHref} class="back-link">&larr; Back</a>
        <div class="start-logo">
          <h1 class="start-title">{titleMain}</h1>
          <h2 class="start-sub">{titleSub}</h2>
        </div>
        <p class="start-tagline">Draft hands of {sport === 'nfl' ? 'NFL' : 'NBA'} player-season cards. Build combos to beat the {sport === 'nfl' ? 'blitz' : 'press'}!</p>
        <div class="start-mode-btns">
          <button id="start-btn" class="btn-primary" type="button" disabled={actionPending} onclick={handleStart}>
            {actionPending ? 'LOADING...' : (sport === 'nfl' ? 'KICKOFF!' : 'TIP-OFF!')}
          </button>
        </div>
        <div class="rules-preview">
          <h3 class="rules-title">HAND TYPES</h3>
          <div class="hand-types-grid">
            {#each handTypes as ht}
              <div class="ht-row" class:ht-royal={ht.royal}>
                <span class="ht-name">{ht.name}</span>
                <span class="ht-mult">{ht.mult}</span>
                <span class="ht-desc">{ht.desc}</span>
              </div>
            {/each}
          </div>
        </div>
      </div>
    </div>

  <!-- PLAYING SCREEN -->
  {:else if screen === 'playing'}
    <div id="game-screen" class="screen active">
      <!-- Top bar -->
      <div id="top-bar">
        <div id="level-info">
          <div id="level-name-display">{levelName}</div>
          <div id="floor-display">Floor {floor} · Fight {fight}</div>
        </div>
        <div id="score-section">
          <div id="score-bar-wrapper">
            <div id="score-bar" style="width: {scorePercent()}%"></div>
          </div>
          <span id="score-text">{formatNum(currentScore)} / {formatNum(targetScore)}</span>
        </div>
        <div id="actions-info">
          <div id="coins-display" class="action-badge">
            <span class="action-icon action-icon-coin">$</span>
            <span id="coins-count">{coins}</span>
            <span class="action-label">Coins</span>
          </div>
          <div class="action-badge" id="hands-badge">
            <span class="action-icon action-icon-hands">H</span>
            <span id="hands-count">{handsRemaining}</span>
            <span class="action-label">Hands</span>
          </div>
          <div class="action-badge" id="discards-badge">
            <span class="action-icon action-icon-discards">D</span>
            <span id="discards-count">{discardsRemaining}</span>
            <span class="action-label">Discards</span>
          </div>
        </div>
      </div>

      <!-- Boss Effect Banner -->
      {#if bossEffect}
        <div id="boss-effect-banner">BOSS: {bossEffect}</div>
      {/if}

      <!-- Joker Display -->
      {#if jokers.length}
        <div id="jokers-section">
          <div id="jokers-left">
            <div id="jokers-label">FANS ({jokers.length}/{maxJokers})</div>
            <div id="jokers-container">
              {#each jokers as joker}
                <div class="joker-slot filled" title={joker.description}>
                  <div class="joker-name">{joker.name}</div>
                  <div class="joker-rarity">{joker.rarity}</div>
                </div>
              {/each}
            </div>
          </div>
        </div>
      {/if}

      <!-- Hand Preview -->
      {#if previewData && selectedIds.size > 0}
        <div id="hand-preview" class="active">
          <div id="preview-hand-type">{previewData.hand_name ?? '...'}</div>
          <div id="preview-score-details">{formatNum(previewData.score ?? 0)} ({previewData.base_pts ?? 0} × {previewData.total_mult ?? 0})</div>
        </div>
      {:else}
        <div id="hand-preview">
          <div id="preview-hand-type">Select up to 5 cards to see hand type</div>
          <div id="preview-score-details"></div>
        </div>
      {/if}

      <!-- Last play result -->
      {#if lastPlayResult}
        <div id="play-log-wrapper">
          <div id="play-log">
            <div class="log-entry">{lastPlayResult.handName}: +{formatNum(lastPlayResult.score)} ({lastPlayResult.basePts} × {lastPlayResult.totalMult})</div>
          </div>
        </div>
      {/if}

      <!-- Hand Area -->
      <div id="hand-area">
        <div id="hand-area-header">
          <div id="hand-label">YOUR HAND</div>
        </div>
        <div id="hand-cards">
          {#each hand as card}
            <div
              class="card {posClass(card.pos)}"
              class:selected={selectedIds.has(card.id)}
              role="button"
              tabindex="0"
              onclick={() => toggleCard(card.id)}
              onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleCard(card.id); } }}
            >
              <div class="card-inner">
                <div class="card-front">
                  <div class="card-headshot">
                    <div class="card-pos-label">{card.pos}</div>
                  </div>
                  <div class="card-name-box">
                    <div class="card-player">{card.player}</div>
                  </div>
                  <div class="card-score-box">
                    <div class="card-score">{card.pts}</div>
                    <div class="card-score-label">PTS</div>
                  </div>
                  <div class="card-footer">
                    <span class="card-team">{card.team}</span>
                    <span class="card-season">{card.season}</span>
                  </div>
                  {#if cardEffects[card.id]?.length}
                    <div class="card-effects-badge">{cardEffects[card.id].join(', ')}</div>
                  {/if}
                </div>
              </div>
            </div>
          {/each}
        </div>
      </div>

      <!-- Action Buttons -->
      <div id="action-buttons">
        <button id="play-btn" class="btn-play" type="button" disabled={selectedIds.size === 0 || actionPending} onclick={handlePlayHand}>
          PLAY HAND ({selectedIds.size})
        </button>
        <button id="discard-btn" class="btn-discard" type="button" disabled={selectedIds.size === 0 || discardsRemaining <= 0 || actionPending} onclick={handleDiscard}>
          DISCARD ({discardsRemaining})
        </button>
      </div>

      <!-- Skill levels -->
      {#if Object.keys(skillLevels).length}
        <div class="bal-skills">
          {#each Object.entries(skillLevels) as [pos, level]}
            <div class="skill-chip">{pos} Lv.{level}</div>
          {/each}
          {#each Object.entries(comboBoosts).filter(([,v]) => v > 0) as [combo, boost]}
            <div class="skill-chip combo">{combo} +{boost}</div>
          {/each}
        </div>
      {/if}
    </div>

  <!-- REWARD SCREEN -->
  {:else if screen === 'reward'}
    <div id="reward-screen" class="screen active">
      <div class="reward-inner">
        <div class="reward-header">
          <h2 class="reward-title">FIGHT COMPLETE!</h2>
          <p class="reward-sub">Choose your reward</p>
        </div>
        <div id="reward-choice-area" class="reward-choice-area">
          <div class="reward-choice-card" id="reward-choice-coins">
            <div class="reward-choice-icon reward-icon-coins">$</div>
            <div class="reward-choice-label">TAKE THE MONEY</div>
            <div class="reward-choice-value">${rewardCoins || 3}</div>
            <div class="reward-choice-desc">Cold hard cash for the shop</div>
            <button class="btn-primary" type="button" disabled={actionPending} onclick={() => handleClaimReward('coins')}>Take Coins</button>
          </div>
          <div class="reward-choice-card reward-choice-joker-card" id="reward-choice-joker">
            <div class="reward-choice-icon reward-icon-joker">FAN</div>
            <div class="reward-choice-label">FREE FAN PACK</div>
            <div class="reward-choice-desc reward-joker-subdesc">Pick 1 of {rewardOptions.length} — keep it forever</div>
            <div id="reward-joker-options" class="reward-joker-grid">
              {#each rewardOptions as joker}
                <div class="reward-joker-option">
                  <div class="joker-name">{joker.name}</div>
                  <div class="joker-desc">{joker.description}</div>
                  <div class="joker-rarity">{joker.rarity}</div>
                  <button class="btn-secondary" type="button" disabled={actionPending} onclick={() => handleClaimReward('joker', joker.id)}>Take</button>
                </div>
              {/each}
            </div>
          </div>
        </div>
      </div>
    </div>

  <!-- SHOP SCREEN -->
  {:else if screen === 'shop'}
    <div id="shop-screen" class="screen active">
      <div class="shop-inner">
        <!-- Store Banner -->
        <div class="store-banner">
          <div class="store-marquee">OFFICIAL TEAM MERCHANDISE &nbsp;·&nbsp; ALL SALES FINAL &nbsp;·&nbsp; GAME DAY SPECIALS</div>
          <div class="store-main-header">
            <div class="store-title-area">
              <div class="store-title-main">TEAM STORE</div>
              <div class="store-title-sub">Official Game Day Merchandise</div>
            </div>
            <div class="store-controls">
              <div id="shop-coins-display" class="shop-coins">$ <span id="shop-coins-count">{coins}</span></div>
            </div>
          </div>
        </div>

        <!-- Quadrant grid -->
        <div class="shop-grid">
          <!-- Top-left: items for sale -->
          <div class="shop-q shop-q-items">
            <div id="shop-items-container">
              {#if shopItems.length}
                <div class="shop-section">
                  <div class="shop-section-label">Items for Sale</div>
                  <div class="shop-items">
                    {#each shopItems as item}
                      <div class="shop-item-card">
                        <div class="shop-item-name">{item.name}</div>
                        <div class="shop-item-desc">{item.description}</div>
                        <div class="shop-item-cost">${item.cost}</div>
                        <button class="btn-secondary" type="button" disabled={actionPending || coins < item.cost} onclick={() => handleBuyItem(item.shop_id, item.item_type)}>
                          Buy
                        </button>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
              {#if shopPacks.length}
                <div class="shop-section">
                  <div class="shop-section-label">Packs</div>
                  <div class="shop-items">
                    {#each shopPacks as pack}
                      <div class="shop-item-card pack">
                        <div class="shop-item-name">{pack.name}</div>
                        <div class="shop-item-desc">{pack.description}</div>
                        <div class="shop-item-cost">${pack.cost}</div>
                        <button class="btn-secondary" type="button" disabled={actionPending || coins < pack.cost} onclick={() => handleOpenPack(pack.pack_id)}>
                          Open
                        </button>
                      </div>
                    {/each}
                  </div>
                </div>
              {/if}
            </div>
          </div>

          <!-- Top-right: your locker -->
          <div class="shop-q shop-q-locker">
            <div id="shop-jokers-section" class="your-locker-section">
              <div class="shop-section-label">Your Jokers ({jokers.length}/{maxJokers})</div>
              <div class="joker-list">
                {#each jokers as joker}
                  <div class="joker-card shop-joker">
                    <div class="joker-name">{joker.name}</div>
                    <div class="joker-rarity">{joker.rarity}</div>
                    {#if joker.sell_value}
                      <button class="btn-secondary" type="button" disabled={actionPending} onclick={() => handleSellJoker(joker.id)}>
                        Sell ${joker.sell_value}
                      </button>
                    {/if}
                  </div>
                {/each}
              </div>
            </div>
          </div>

          <!-- Bottom-left: actions -->
          <div class="shop-q shop-q-actions">
            <button id="restock-btn" class="btn-secondary" type="button" disabled={actionPending} onclick={handleRestock}>
              Restock (${2 + restockCount})
            </button>
            <button id="leave-shop-btn" class="btn-primary" type="button" disabled={actionPending} onclick={handleLeaveShop}>
              CONTINUE →
            </button>
          </div>

          <!-- Bottom-right: NPC vendor -->
          <div class="shop-q shop-q-npc">
            <div class="npc-panel">
              <div class="npc-nameplate">Vendor Vic</div>
              <div class="npc-char">
                <div class="npc-avatar">VIC</div>
              </div>
              <div class="vendor-bubble" id="vendor-bubble">Gear up before the next game!</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Pack opening modal -->
      {#if packOpen}
        <div id="pack-opening-modal" class="full-overlay">
          <div id="pack-opening-content">
            <div id="pack-opening-title">Pick up to {packMaxPicks} card(s)</div>
            <div id="pack-cards-reveal">
              {#each packCards as card}
                <div
                  class="card {posClass(card.pos)} pack-reveal-card"
                  class:selected={packSelectedIds.has(card.id)}
                  role="button"
                  tabindex="0"
                  onclick={() => togglePackCard(card.id)}
                  onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); togglePackCard(card.id); } }}
                >
                  <div class="card-inner">
                    <div class="card-front">
                      <div class="card-headshot">
                        <div class="card-pos-label">{card.pos}</div>
                      </div>
                      <div class="card-name-box">
                        <div class="card-player">{card.player}</div>
                      </div>
                      <div class="card-score-box">
                        <div class="card-score">{card.pts}</div>
                        <div class="card-score-label">PTS</div>
                      </div>
                      <div class="card-footer">
                        <span class="card-team">{card.team}</span>
                      </div>
                    </div>
                  </div>
                </div>
              {/each}
            </div>
            <button id="pack-close-btn" class="btn-primary" type="button" disabled={actionPending} onclick={handleConfirmPackPicks}>
              Confirm ({packSelectedIds.size}/{packMaxPicks})
            </button>
          </div>
        </div>
      {/if}
    </div>

  <!-- GAME OVER SCREEN -->
  {:else if screen === 'gameover'}
    <div id="gameover-screen" class="screen active" class:won={gameWon}>
      <div id="gameover-content">
        <h2 class="gameover-title">{gameWon ? 'VICTORY!' : 'GAME OVER'}</h2>
        <div class="gameover-stats">
          Floor {floor} · Fight {fight} · Round {round}
          <br>Score: {formatNum(currentScore)} / {formatNum(targetScore)}
          <br>Coins: ${coins} · Jokers: {jokers.length}
        </div>
        <div class="gameover-actions">
          {#if gameWon}
            <button class="btn-primary" type="button" disabled={actionPending} onclick={handleStartInfinity}>Continue (Infinity)</button>
          {/if}
          <button id="restart-btn" class="btn-primary" type="button" onclick={handleRestart}>PLAY AGAIN</button>
          <a href={backHref} class="back-link" style="margin-top:16px;display:block;">&larr; Back</a>
        </div>
      </div>
    </div>
  {/if}
</div>

