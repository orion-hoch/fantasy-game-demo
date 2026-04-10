<script lang="ts">
  import { onMount, tick } from 'svelte';
  import '$lib/styles/balatro.css';
  import type { Card, Joker, ShopItem, ShopPack, Screen, Sport, GameState, CardStats, PlayResult } from './types';
  import { SFX } from '$lib/sfx';
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
    getBalatroCardStats,
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
  let bossEffect = $state<unknown>(null);
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
  let deckPool: Card[] = $state([]);
  let restockCount = $state(0);
  let maxHandSize = $state(9);
  let baseDiscards = $state(3);

  // ── UI state ─────────────────────────────────────────────────────
  let selectedIds = $state<Set<string>>(new Set());
  let actionPending = $state(false);
  let errorMsg = $state('');
  let lastPlayResult = $state<PlayResult | null>(null);
  let logEntries: string[] = $state([]);
  let previewData = $state<{ hand_name?: string; score?: number; base_pts?: number; total_mult?: number } | null>(null);
  let gameWon = $state(false);
  let sfxMuted = $state(SFX.isMuted());
  let statsOpen = $state(false);
  let deckViewOpen = $state(false);

  // Card flip state
  let flippedCardIds = $state<Set<string>>(new Set());
  let cardStatsCache: Record<string, CardStats> = {};

  // Scoring animation state
  let scoringActive = $state(false);
  let animHandType = $state('');
  let animChips = $state(0);
  let animDisplayChips = $state(0);
  let animMult = $state(0);
  let animXmult = $state(0);
  let animScore = $state(0);
  let animDisplayScore = $state(0);
  let animShowMult = $state(false);
  let animShowXmult = $state(false);
  let animShowScore = $state(false);
  let animScoringIds = $state<Set<string>>(new Set());
  let animActiveId = $state('');
  let animDimIds = $state<Set<string>>(new Set());
  let animDoneIds = $state<Set<string>>(new Set());
  let animChipsBumping = $state(false);
  let animScoreBurst = $state(false);

  // Reward state
  let rewardOptions: Joker[] = $state([]);
  let rewardCoins = $state(0);

  // Pack opening state
  let packCards: Card[] = $state([]);
  let packJokerOptions: Joker[] = $state([]);
  let packIsJoker = $state(false);
  let packSelectedIds = $state<Set<string>>(new Set());
  let packMaxPicks = $state(1);
  let packOpen = $state(false);

  // Deal animation state
  let dealAnimating = $state(false);
  let cardAnimDelays: Record<string, number> = $state({});

  const title = $derived(sport === 'nfl' ? 'NFL Balatro' : 'NBA Balatro');

  // ── Division lookup ──────────────────────────────────────────────
  const NBA_DIV: Record<string, string> = {
    BOS:'Atlantic',BRK:'Atlantic',BKN:'Atlantic',NYK:'Atlantic',PHI:'Atlantic',TOR:'Atlantic',NJN:'Atlantic',
    CHI:'Central',CLE:'Central',DET:'Central',IND:'Central',MIL:'Central',
    ATL:'Southeast',CHA:'Southeast',CHH:'Southeast',MIA:'Southeast',ORL:'Southeast',WAS:'Southeast',
    DEN:'Northwest',MIN:'Northwest',OKC:'Northwest',POR:'Northwest',UTA:'Northwest',SEA:'Northwest',
    GSW:'Pacific',LAC:'Pacific',LAL:'Pacific',PHX:'Pacific',PHO:'Pacific',SAC:'Pacific',
    DAL:'Southwest',HOU:'Southwest',MEM:'Southwest',NOP:'Southwest',SAS:'Southwest',NOH:'Southwest',VAN:'Southwest',NOK:'Southwest',
  };
  const NBA_DIV_LABEL: Record<string, string> = {
    'Atlantic':'ATL','Central':'CEN','Southeast':'SE',
    'Northwest':'NW','Pacific':'PAC','Southwest':'SW',
  };
  const NBA_DIV_CLASS: Record<string, string> = {
    'Atlantic':'div-atlantic','Central':'div-central','Southeast':'div-southeast',
    'Northwest':'div-northwest','Pacific':'div-pacific','Southwest':'div-southwest',
  };

  // NFL Division lookup
  const NFL_DIV: Record<string, string> = {
    BUF:'AFC East',MIA:'AFC East',NE:'AFC East',NYJ:'AFC East',
    BAL:'AFC North',CIN:'AFC North',CLE:'AFC North',PIT:'AFC North',
    HOU:'AFC South',IND:'AFC South',JAX:'AFC South',TEN:'AFC South',
    DEN:'AFC West',KC:'AFC West',LV:'AFC West',LAC:'AFC West',OAK:'AFC West',SD:'AFC West',
    DAL:'NFC East',NYG:'NFC East',PHI:'NFC East',WAS:'NFC East',
    CHI:'NFC North',DET:'NFC North',GB:'NFC North',MIN:'NFC North',
    ATL:'NFC South',CAR:'NFC South',NO:'NFC South',TB:'NFC South',
    ARI:'NFC West',LAR:'NFC West',SF:'NFC West',SEA:'NFC West',STL:'NFC West',
  };
  const NFL_DIV_LABEL: Record<string, string> = {
    'AFC East':'AFCE','AFC North':'AFCN','AFC South':'AFCS','AFC West':'AFCW',
    'NFC East':'NFCE','NFC North':'NFCN','NFC South':'NFCS','NFC West':'NFCW',
  };

  function getDivInfo(team: string) {
    if (!team) return null;
    const t = team.toUpperCase();
    if (sport === 'nba') {
      const div = NBA_DIV[t];
      if (!div) return null;
      return { label: NBA_DIV_LABEL[div] || div, cls: NBA_DIV_CLASS[div] || '' };
    } else {
      const div = NFL_DIV[t];
      if (!div) return null;
      return { label: NFL_DIV_LABEL[div] || div, cls: '' };
    }
  }

  function displayYear(season: number): string {
    if (sport === 'nba') return String(season + 1);
    return String(season);
  }

  function bossName(effect: unknown): string {
    if (!effect) return '';
    if (typeof effect === 'string') return effect.replace(/_/g, ' ').toUpperCase();
    if (typeof effect === 'object' && effect && 'name' in effect) return String((effect as { name: unknown }).name);
    return String(effect);
  }

  function bossDesc(effect: unknown): string {
    if (typeof effect === 'object' && effect && 'desc' in effect) return String((effect as { desc: unknown }).desc);
    return '';
  }

  function getDeckGroups(): Array<{ pos: string; cards: Card[] }> {
    const posOrder = sport === 'nfl' ? ['QB', 'RB', 'WR', 'TE'] : ['G', 'F', 'C'];
    const seen = new Set<string>();
    const merged = [...hand, ...deckCards, ...heldCards].filter((card) => {
      if (!card?.id || seen.has(card.id)) return false;
      seen.add(card.id);
      return true;
    });

    const groups = posOrder.map((pos) => ({
      pos,
      cards: merged
        .filter((card) => (card.pos || '').toUpperCase() === pos)
        .sort((a, b) => (b.fantasy_pts || b.pts || 0) - (a.fantasy_pts || a.pts || 0)),
    }));

    const otherCards = merged
      .filter((card) => !posOrder.includes((card.pos || '').toUpperCase()))
      .sort((a, b) => (b.fantasy_pts || b.pts || 0) - (a.fantasy_pts || a.pts || 0));

    if (otherCards.length) {
      groups.push({ pos: 'OTHER', cards: otherCards });
    }

    return groups.filter((group) => group.cards.length > 0);
  }

  const deckGroups = $derived.by(() => getDeckGroups());

  // Normalize pack objects from backend (uses "id") to frontend (uses "pack_id")
  function normalizePacks(packs: ShopPack[]): ShopPack[] {
    return (packs || []).map(p => {
      const raw = p as Record<string, unknown>;
      if (!p.pack_id && raw.id) {
        return { ...p, pack_id: raw.id as string };
      }
      return p;
    });
  }

  function addLog(msg: string) {
    logEntries = [msg, ...logEntries.slice(0, 49)];
  }

  function toggleCard(id: string) {
    if (scoringActive) return;
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else if (next.size < 5) next.add(id);
    selectedIds = next;
    SFX.play('card_sel');
    if (next.size > 0) fetchPreview();
    else previewData = null;
  }

  function flipCard(id: string, card: Card) {
    const next = new Set(flippedCardIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
      fetchCardBack(card);
    }
    flippedCardIds = next;
  }

  async function fetchCardBack(card: Card) {
    const key = card.player + '_' + card.season;
    if (cardStatsCache[key]) return;
    try {
      const stats = await getBalatroCardStats(sport, card.player, String(card.season));
      cardStatsCache[key] = stats as CardStats;
      // Force reactivity
      cardStatsCache = { ...cardStatsCache };
    } catch { /* ignore */ }
  }

  function getCardStats(card: Card): CardStats | null {
    return cardStatsCache[card.player + '_' + card.season] || null;
  }

  let previewTimer: ReturnType<typeof setTimeout> | null = null;

  function fetchPreview() {
    if (!gameId || selectedIds.size === 0) { previewData = null; return; }
    if (previewTimer) clearTimeout(previewTimer);
    previewTimer = setTimeout(async () => {
      try {
        const data = await previewBalatroHand(sport, gameId, Array.from(selectedIds));
        previewData = data;
      } catch { /* ignore preview errors */ }
    }, 250);
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
    if (data.shop_packs) shopPacks = normalizePacks(data.shop_packs);
    if (data.max_jokers !== undefined) maxJokers = data.max_jokers;
    if (data.joker_state) jokerState = data.joker_state;
    if (data.held_cards !== undefined) heldCards = data.held_cards;
    if (data.deck_cards !== undefined) deckCards = data.deck_cards;
    if (data.deck_pool !== undefined) deckPool = data.deck_pool as Card[];
    if (data.max_hand_size !== undefined) maxHandSize = data.max_hand_size;
    if (data.base_discards !== undefined) baseDiscards = data.base_discards;
    selectedIds = new Set();
    previewData = null;
    errorMsg = '';
  }

  // ── Sleep helper ─────────────────────────────────────────────────
  function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)); }

  // Smooth counter: animate from current displayed value to target over duration
  function tweenCounter(
    getCurrent: () => number,
    setter: (v: number) => void,
    target: number,
    duration: number = 300,
  ) {
    const start = getCurrent();
    const diff = target - start;
    if (diff === 0) { setter(target); return; }
    const t0 = performance.now();
    function frame() {
      const elapsed = performance.now() - t0;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out quad
      const eased = 1 - (1 - progress) * (1 - progress);
      setter(Math.round(start + diff * eased));
      if (progress < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  // ── Scoring animation ───────────────────────────────────────────
  async function animateScore(data: PlayResult, playedIds: string[]) {
    if (!data.card_contributions || data.card_contributions.length === 0) return;
    scoringActive = true;

    try {
    const scoringIds = new Set(data.scoring_card_ids || data.card_contributions.map(c => c.id));
    animScoringIds = scoringIds;
    animDimIds = new Set(playedIds.filter(id => !scoringIds.has(id)));
    animDoneIds = new Set();
    animHandType = (data.hand_name || '').toUpperCase();
    animChips = 0;
    animDisplayChips = 0;
    animMult = 0;
    animXmult = 1;
    animScore = 0;
    animDisplayScore = 0;
    animShowMult = false;
    animShowXmult = false;
    animShowScore = false;
    animActiveId = '';
    animChipsBumping = false;
    animScoreBurst = false;

    await tick();
    await sleep(100);

    // Phase 1: card by card chips — smooth counter tween per card
    let runningChips = 0;
    for (const contrib of data.card_contributions) {
      animActiveId = contrib.id;
      await sleep(60);
      runningChips += contrib.contribution;
      animChips = Math.round(runningChips);
      // Bump effect on chips box
      animChipsBumping = false;
      await tick();
      animChipsBumping = true;
      tweenCounter(() => animDisplayChips, (v) => animDisplayChips = v, animChips, 180);
      SFX.play('score_tick');
      animDoneIds = new Set([...animDoneIds, contrib.id]);
      animActiveId = '';
      await sleep(140);
    }
    animChipsBumping = false;
    await sleep(80);

    // Phase 2: mult reveal
    animShowMult = true;
    animMult = data.total_mult || 0;
    SFX.play('score_tick');
    await sleep(300);

    // Phase 2b: xmult
    if (data.mult_factor && data.mult_factor > 1.0) {
      animShowXmult = true;
      animXmult = data.mult_factor;
      SFX.play('score_tick');
      await sleep(300);
    }

    // Phase 3: score bang — smooth count up to final score
    animShowScore = true;
    animScore = data.score || 0;
    animScoreBurst = true;
    tweenCounter(() => animDisplayScore, (v) => animDisplayScore = v, animScore, 500);
    SFX.play('reward');
    await sleep(800);
    animScoreBurst = false;

    } finally {
      // Fade out — always reset even if animation errors
      scoringActive = false;
      animScoringIds = new Set();
      animDimIds = new Set();
      animDoneIds = new Set();
      animActiveId = '';
    }
  }

  // ── Deal animation ──────────────────────────────────────────────
  async function triggerDealAnimation() {
    dealAnimating = true;
    const delays: Record<string, number> = {};
    hand.forEach((card, i) => {
      delays[card.id] = i;
    });
    cardAnimDelays = delays;
    SFX.play('rustle');
    await tick();
    // After animation completes
    setTimeout(() => {
      dealAnimating = false;
      cardAnimDelays = {};
    }, 120 + hand.length * 90 + 500);
  }

  async function triggerNewCardsAnimation(oldIds: Set<string>) {
    const delays: Record<string, number> = {};
    let idx = 0;
    hand.forEach((card) => {
      if (!oldIds.has(card.id)) {
        delays[card.id] = idx++;
      }
    });
    if (idx > 0) {
      dealAnimating = true;
      cardAnimDelays = delays;
      SFX.play('rustle');
      await tick();
      setTimeout(() => {
        dealAnimating = false;
        cardAnimDelays = {};
      }, idx * 90 + 500);
    }
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
      flippedCardIds = new Set();
      cardStatsCache = {};
      applyState(data);
      screen = 'playing';
      await tick();
      triggerDealAnimation();
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Failed to start game';
    } finally {
      actionPending = false;
    }
  }

  async function handlePlayHand() {
    if (selectedIds.size === 0 || actionPending || scoringActive) return;
    actionPending = true;
    SFX.play('card_play');
    const ids = Array.from(selectedIds);
    const oldHandIds = new Set(hand.map(c => c.id));
    try {
      const data = await playBalatroHand(sport, gameId, ids) as GameState & PlayResult;
      if (data.error) { errorMsg = data.error; actionPending = false; return; }

      // Run scoring animation BEFORE updating UI
      await animateScore(data, ids);

      lastPlayResult = {
        hand_name: data.hand_name ?? '',
        score: data.score ?? 0,
        base_pts: data.base_pts ?? 0,
        total_mult: data.total_mult ?? 0,
      };
      addLog(`${data.hand_name}: +${formatNum(data.score ?? 0)}${data.coins_earned ? ` | +$${data.coins_earned}` : ''}`);

      applyState(data);
      flippedCardIds = new Set();

      const status = data.status;
      if (status === 'playing') {
        await tick();
        triggerNewCardsAnimation(oldHandIds);
      } else if (status === 'won_fight' || status === 'won_level') {
        setTimeout(() => handleAdvanceFight(), 1200);
      } else if (status === 'won_game') {
        SFX.play('win');
        setTimeout(() => showGameOver(true), 1200);
      } else if (status === 'lost') {
        SFX.play('lose');
        setTimeout(() => showGameOver(false), 1200);
      }
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Play hand failed';
    } finally {
      actionPending = false;
    }
  }

  async function handleDiscard() {
    if (selectedIds.size === 0 || discardsRemaining <= 0 || actionPending || scoringActive) return;
    actionPending = true;
    SFX.play('discard');
    const oldHandIds = new Set(hand.map(c => c.id));
    try {
      const data = await discardBalatroCards(sport, gameId, Array.from(selectedIds)) as GameState;
      if (data.error) { errorMsg = data.error; return; }
      addLog(`Discarded ${selectedIds.size} card(s)`);
      applyState(data);
      flippedCardIds = new Set();
      await tick();
      triggerNewCardsAnimation(oldHandIds);
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
      SFX.play('reward');
      screen = 'reward';
    } catch (err) {
      errorMsg = err instanceof Error ? err.message : 'Advance failed';
    }
  }

  async function handleClaimReward(choice: string, jokerId?: string) {
    actionPending = true;
    SFX.play('buy');
    try {
      const data = await claimBalatroReward(sport, gameId, choice, jokerId) as GameState;
      if (data.error) { errorMsg = data.error; return; }
      applyState(data);
      shopItems = data.shop_items ?? [];
      shopPacks = normalizePacks(data.shop_packs ?? []);
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
      if (data.shop_packs) shopPacks = normalizePacks(data.shop_packs);
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
      if (data.error) { errorMsg = data.error; actionPending = false; return; }
      SFX.play('buy');
      applyState(data);
      if (data.shop_items) shopItems = data.shop_items;
      if (data.shop_packs) shopPacks = normalizePacks(data.shop_packs);
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
      SFX.play('buy');
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
      SFX.play('buy');
      applyState(data);
      if (data.shop_items) shopItems = data.shop_items;
      if (data.shop_packs) shopPacks = normalizePacks(data.shop_packs);
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
      SFX.play('buy');

      if (data.shop_packs) shopPacks = normalizePacks(data.shop_packs as ShopPack[]);

      const candidates = (Array.isArray(data.candidates) ? data.candidates : data.cards ?? []) as Record<string, unknown>[];
      const isJokerPack = Boolean(data.is_joker_pack) || (candidates.length > 0 && !('player' in candidates[0]));

      packIsJoker = isJokerPack;
      if (isJokerPack) {
        packJokerOptions = candidates as unknown as Joker[];
        packCards = [];
      } else {
        packCards = candidates as unknown as Card[];
        packJokerOptions = [];
      }

      packMaxPicks = Number(data.picks_allowed ?? data.max_picks ?? 1);
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
      if (data.shop_packs) shopPacks = normalizePacks(data.shop_packs);
      packOpen = false;
      packCards = [];
      packJokerOptions = [];
      packIsJoker = false;
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
      flippedCardIds = new Set();
      applyState(data);
      screen = 'playing';
      await tick();
      triggerDealAnimation();
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
      flippedCardIds = new Set();
      applyState(data);
      screen = 'playing';
      await tick();
      triggerDealAnimation();
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
    flippedCardIds = new Set();
    cardStatsCache = {};
  }

  function togglePackCard(id: string) {
    const next = new Set(packSelectedIds);
    if (next.has(id)) next.delete(id);
    else if (next.size < packMaxPicks) next.add(id);
    packSelectedIds = next;
  }

  function toggleMute() {
    SFX.toggleMute();
    sfxMuted = SFX.isMuted();
  }

  function formatNum(n: number): string {
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
    return String(Math.round(n));
  }

  function formatFull(n: number): string {
    return Math.round(n).toLocaleString();
  }

  function scorePercent(): number {
    return targetScore > 0 ? Math.min(100, (currentScore / targetScore) * 100) : 0;
  }

  const backHref = $derived(sport === 'nfl' ? '/?tab=nfl' : '/?tab=nba');
  const titleMain = $derived(sport === 'nfl' ? 'NFL BALATRO' : 'NBA BALATRO');
  const titleSub = $derived(sport === 'nfl' ? 'Skill Position Edition' : 'Fantasy Draft Edition');
  const sportLogoSrc = $derived(sport === 'nfl' ? '/img/football_logo_nobg.png' : '/img/basketball_logo_nobg.png');

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
    { name: 'Isolation', mult: '1x', desc: 'Best single card' },
    { name: 'Catch & Shoot', mult: '1.5x', desc: '2 of same position' },
    { name: 'Pick & Roll', mult: '2x', desc: '3 of same position' },
    { name: 'Starting Four', mult: '3x', desc: '4 of same position' },
    { name: 'Twin Towers', mult: '2.5x', desc: '3 of one position + 2 of another' },
    { name: 'Zone Press', mult: '5.5x', desc: '5 of same position' },
    { name: 'Division Court', mult: '6x', desc: '5+ cards from same division' },
    { name: 'Division Starting Lineup', mult: '25x', desc: 'G + F + C all present (5+ cards) same division', royal: true },
  ]);

  function posClass(pos: string): string {
    const p = (pos || '').toLowerCase();
    if (sport === 'nfl') {
      if (p === 'qb') return 'card-pos-qb';
      if (p === 'rb') return 'card-pos-rb';
      if (p === 'wr') return 'card-pos-wr';
      if (p === 'te') return 'card-pos-te';
    } else {
      if (p === 'g') return 'card-pos-g';
      if (p === 'f') return 'card-pos-f';
      if (p === 'c') return 'card-pos-c';
    }
    return '';
  }

  function getCardAnimStyle(card: Card): string {
    if (!dealAnimating || !(card.id in cardAnimDelays)) return '';
    const idx = cardAnimDelays[card.id];
    const delay = 90 + idx * 70;
    return `animation: card-deal-in 0.55s cubic-bezier(0.22, 1, 0.36, 1) ${delay}ms both;`;
  }

  // Vendor lines for the shop
  const VENDOR_LINES = [
    'Stock up before tip-off!', 'Fresh talent just arrived!', "Get 'em while they last!",
    'Best roster in the league!', 'Playoffs gear is here!', 'Limited stock - act fast!',
    "Today's deals won't last!", 'Draft your dream team!', 'Championship season calls!',
    'That last quarter was ELITE!', 'Running low on coins? Choose wisely!',
    'A new fan could change everything!', 'Trust the process. Buy the pack.',
  ];
  let vendorLine = $state(VENDOR_LINES[0]);

  function randomVendorLine() {
    vendorLine = VENDOR_LINES[Math.floor(Math.random() * VENDOR_LINES.length)];
  }

  // Item type labels and icons for shop
  const ITEM_ICON: Record<string, string> = {
    joker: 'Fan', skill_card: 'SK', combo_card: 'CMB', effect_card: 'EF',
    year_card: 'YR', cut_card: 'CUT', upgrade: 'UP', mod_card: 'MOD',
    joker_enhancement: 'ENH', buy_card: 'PLR',
  };
  const ITEM_TYPE_LABEL: Record<string, string> = {
    joker: 'FAN', skill_card: 'SKILL', combo_card: 'COMBO',
    effect_card: 'EFFECT', year_card: 'SEASON', cut_card: 'RELEASE',
    upgrade: 'UPGRADE', mod_card: 'MOD', joker_enhancement: 'ENHANCE',
    buy_card: 'PLAYER CARD',
  };

  // Position levels config
  const POS_LIST = $derived(sport === 'nfl' ? ['QB', 'RB', 'WR', 'TE'] : ['G', 'F', 'C']);
  const BASE_MULTS = $derived<Record<string, number>>(sport === 'nfl'
    ? { QB: 1.0, RB: 1.5, WR: 1.5, TE: 2.0 }
    : { G: 1.0, F: 1.5, C: 2.5 });

  // Sort hand
  let currentSort = $state<string | null>(null);
  function sortHand(mode: string) {
    SFX.play('rustle');
    if (currentSort === mode) {
      currentSort = null;
      return;
    }
    currentSort = mode;
    if (mode === 'pos') {
      hand = [...hand].sort((a, b) => {
        const order = POS_LIST;
        const ai = order.indexOf(a.pos);
        const bi = order.indexOf(b.pos);
        if (ai !== bi) return ai - bi;
        return (b.fantasy_pts || b.pts || 0) - (a.fantasy_pts || a.pts || 0);
      });
    } else if (mode === 'pts') {
      hand = [...hand].sort((a, b) => (b.fantasy_pts || b.pts || 0) - (a.fantasy_pts || a.pts || 0));
    }
  }

  // Shop item sections
  function getShopSections() {
    const sections = [
      { key: 'roster', label: 'FANS & PLAYERS', color: '#9b59b6', items: [] as (ShopItem | ShopPack)[] },
      { key: 'training', label: 'SKILLS & UPGRADES', color: '#27ae60', items: [] as (ShopItem | ShopPack)[] },
      { key: 'packs', label: 'PACKS', color: '#e74c3c', items: [] as (ShopItem | ShopPack)[] },
    ];
    const sectionMap: Record<string, typeof sections[0]> = {};
    sections.forEach(s => sectionMap[s.key] = s);

    (shopItems || []).forEach(item => {
      if ((item as Record<string, unknown>).sold) return;
      const sec = (item as Record<string, unknown>).section as string || 'training';
      if (sectionMap[sec]) sectionMap[sec].items.push(item);
    });

    (shopPacks || []).forEach(pack => {
      if ((pack as Record<string, unknown>).sold) return;
      sectionMap.packs.items.push(pack);
    });

    return sections.filter(s => s.items.length > 0);
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
    <div class="bal-error">{errorMsg} <button type="button" onclick={() => (errorMsg = '')}>x</button></div>
  {/if}

  <!-- START SCREEN -->
  {#if screen === 'start'}
    <div id="start-screen" class="screen active">
      <div class="start-inner">
        <a href={backHref} class="back-link">&larr; Back</a>
        <button class="sfx-mute-btn" type="button" onclick={toggleMute} title={sfxMuted ? 'Unmute' : 'Mute'}>
          {sfxMuted ? 'UNMUTE' : 'MUTE'}
        </button>
        <div class="start-logo">
          <img src={sportLogoSrc} alt={title} class="start-logo-img">
          <h1 class="start-title">{titleMain}</h1>
          <h2 class="start-sub">{titleSub}</h2>
        </div>
        <p class="start-tagline">Draft hands of {sport === 'nfl' ? 'NFL' : 'NBA'} player-season cards. Build combos to beat the {sport === 'nfl' ? 'blitz' : 'shot clock'}!</p>
        <button id="start-btn" class="btn-primary" type="button" disabled={actionPending} onclick={handleStart}>
          {actionPending ? 'LOADING...' : (sport === 'nfl' ? 'KICKOFF!' : 'TIP OFF!')}
        </button>
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
    <div id="game-screen" class="screen active" class:scoring={scoringActive}>

      <!-- Top bar -->
      <div id="top-bar">
        <div id="level-info">
          <div id="level-name-display">{levelName}</div>
          <div id="floor-display">Floor {floor} &middot; Fight {fight}</div>
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
            <button class="btn-stats" type="button" onclick={() => statsOpen = !statsOpen}>STATS</button>
            <button class="btn-stats" type="button" onclick={() => (deckViewOpen = true)}>
              DECK ({Math.max(hand.length + deckCards.length + heldCards.length, hand.length)})
            </button>
            <button class="sfx-mute-btn" type="button" onclick={toggleMute} title={sfxMuted ? 'Unmute' : 'Mute'}>
              {sfxMuted ? 'UNMUTE' : 'MUTE'}
            </button>
        </div>
      </div>

      <!-- Stats Overlay (Position Levels as Bars) -->
      {#if statsOpen}
        <div id="stats-overlay" class="stats-overlay">
          <div class="stats-overlay-header">
            <span class="stats-overlay-title">POSITION LEVELS</span>
            <button class="overlay-close" type="button" onclick={() => statsOpen = false}>x</button>
          </div>
          <div id="stats-bars-container">
            {#each POS_LIST as pos}
              {@const level = skillLevels[pos] || 0}
              {@const ptsBoost = Math.round(level * 8)}
              {@const baseMult = BASE_MULTS[pos] || 1}
              {@const effMult = (baseMult + level * 0.12).toFixed(2)}
              {@const barFill = Math.min(10, level)}
              <div class="stats-row">
                <div class="stats-pos-badge pos-badge-{pos.toLowerCase()}">{pos}</div>
                <div class="stats-info">
                  <div class="stats-level">Level {level}</div>
                  <div class="stats-bar-wrap">
                    {#each Array(10) as _, i}
                      <div class="stats-bar-seg {i < barFill ? 'filled pos-fill-' + pos.toLowerCase() : ''}"></div>
                    {/each}
                  </div>
                  <div class="stats-boosts">+{ptsBoost}% Pts x{effMult} Mult</div>
                </div>
              </div>
            {/each}
            <div class="stats-row" style="flex-direction:column;align-items:flex-start;">
              <div class="stats-boosts" style="margin-bottom:4px">Hand Size: {maxHandSize} cards</div>
              <div class="stats-boosts">Discards/Level: {baseDiscards}</div>
            </div>
            {#if Object.entries(comboBoosts).filter(([,v]) => v > 0).length > 0}
              <div class="stats-combos">
                <div class="stats-combos-title">COMBO BOOSTS</div>
                {#each Object.entries(comboBoosts).filter(([,v]) => v > 0) as [combo, boost]}
                  <div class="stats-combo-row">{combo}: +{boost}</div>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Boss Effect Banner -->
      {#if bossEffect}
        <div id="boss-effect-banner">
          <span class="boss-banner-icon">⚠</span>
          <span class="boss-banner-name">BOSS: {bossName(bossEffect)}</span>
          {#if bossDesc(bossEffect)}
            <span class="boss-banner-desc">{bossDesc(bossEffect)}</span>
          {/if}
        </div>
      {/if}

      <!-- Joker Display -->
      {#if jokers.length}
        <div id="jokers-section">
          <div id="jokers-left">
            <div id="jokers-label">FANS ({jokers.length}/{maxJokers})</div>
            <div id="jokers-container">
              {#each jokers as joker}
                <div class="joker-slot filled" title={joker.description} data-joker-id={joker.id}>
                  <img class="joker-fan-img" src={sport === 'nfl' ? '/img/football_fan.png' : '/img/basketball_fan.png'} alt="Fan">
                  <div class="joker-name">{joker.name}</div>
                  <div class="joker-rarity rarity-{joker.rarity}">{joker.rarity}</div>
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
        </div>
      {:else}
        <div id="hand-preview">
          <div id="preview-hand-type">Select up to 5 cards to see hand type</div>
        </div>
      {/if}

      <!-- Score Animation Panel -->
      {#if scoringActive}
        <div id="score-anim-panel" class="anim-panel-glow">
          <div id="anim-hand-type-label">{animHandType}</div>
          <div id="anim-counters-row">
            <div class="anim-counter-box anim-chips-color" class:chip-bump={animChipsBumping} id="anim-chips-box">
              <div class="anim-counter-label">CHIPS</div>
              <div class="anim-counter-val">{formatFull(animDisplayChips)}</div>
            </div>
            <div class="anim-op">x</div>
            {#if animShowMult}
              <div class="anim-counter-box mult-popping anim-mult-color" id="anim-mult-box">
                <div class="anim-counter-label">MULT</div>
                <div class="anim-counter-val">{animMult}</div>
              </div>
            {:else}
              <div class="anim-counter-box" id="anim-mult-box">
                <div class="anim-counter-label">MULT</div>
                <div class="anim-counter-val anim-val-pending">--</div>
              </div>
            {/if}
            {#if animShowXmult}
              <div class="anim-op">x</div>
              <div class="anim-counter-box mult-popping anim-xmult-color" id="anim-xmult-box">
                <div class="anim-counter-label">XMULT</div>
                <div class="anim-counter-val">{animXmult}</div>
              </div>
            {/if}
            {#if animShowScore}
              <div class="anim-op">=</div>
              <div class="anim-counter-box score-banging anim-score-color" class:score-burst={animScoreBurst} id="anim-score-box">
                <div class="anim-counter-label">SCORE</div>
                <div class="anim-counter-val anim-score-val">{formatFull(animDisplayScore)}</div>
              </div>
            {/if}
          </div>
        </div>
      {/if}

      <!-- Last play result -->
      {#if lastPlayResult && !scoringActive}
        <div id="play-log-wrapper">
          <div id="play-log">
            <div class="log-entry">{lastPlayResult.hand_name}: +{formatFull(lastPlayResult.score ?? 0)} ({formatFull(lastPlayResult.base_pts ?? 0)} x {lastPlayResult.total_mult})</div>
          </div>
        </div>
      {/if}

      <!-- Hand Area -->
      <div id="hand-area">
        <div id="hand-area-header">
          <div id="hand-label">YOUR HAND</div>
          <div id="sort-buttons">
            <button class="btn-sort" class:active={currentSort === 'pos'} type="button" onclick={() => sortHand('pos')}>Sort Position</button>
            <button class="btn-sort" class:active={currentSort === 'pts'} type="button" onclick={() => sortHand('pts')}>Sort Points</button>
          </div>
        </div>
        <div id="hand-cards" style={`--hand-count: ${Math.max(hand.length, 1)};`}>
          {#each hand as card (card.id)}
            {@const effects = cardEffects[card.id] || []}
            {@const isFlipped = flippedCardIds.has(card.id)}
            {@const stats = getCardStats(card)}
            {@const divInfo = getDivInfo(card.team)}
            {@const splitName = card.player.split(' ')}
            {@const firstName = splitName.length > 1 ? splitName[0] : ''}
            {@const lastName = splitName.length > 1 ? splitName.slice(1).join(' ') : splitName[0]}
            {@const pts = card.fantasy_pts !== undefined ? Math.round(card.fantasy_pts) : card.pts}
            <div
              class="card {posClass(card.pos)}"
              class:selected={selectedIds.has(card.id)}
              class:flipped={isFlipped}
              class:card-gold={effects.includes('gold')}
              class:card-glass={effects.includes('glass')}
              class:card-foil={effects.includes('foil')}
              class:card-trained={effects.includes('trained')}
              class:boss-disabled={card.boss_disabled}
              class:scoring-active={animActiveId === card.id}
              class:scoring-dim={animDimIds.has(card.id)}
              class:scoring-done={animDoneIds.has(card.id)}
              data-card-id={card.id}
              data-id={card.id}
              role="button"
              tabindex="0"
              style={getCardAnimStyle(card)}
              onclick={(e) => {
                if ((e.target as HTMLElement).closest('.card-flip-btn')) return;
                if (isFlipped) { flipCard(card.id, card); return; }
                toggleCard(card.id);
              }}
              onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleCard(card.id); } }}
            >
              <div class="card-inner">
                <!-- Card Front -->
                <div class="card-front">
                  <!-- Top row: name + score -->
                  <div class="card-top-row">
                    <div class="card-name-box">
                      <div class="card-year-line">
                        {card.season ? "'" + String(displayYear(card.season)).slice(-2) : ''}
                        {card.team ? ' \u00B7 ' + card.team : ''}
                      </div>
                      {#if firstName}
                        <div class="card-player-first">{firstName}</div>
                      {/if}
                      <div class="card-player-last">{lastName}</div>
                    </div>
                    <div class="card-top-right">
                      {#if card.allstar_count && card.allstar_count > 0}
                        <div class="card-stars-box" title="{card.allstar_count}x {sport === 'nfl' ? 'Pro Bowl' : 'All-Star'}">
                          {'★'.repeat(Math.min(card.allstar_count, 5))}
                        </div>
                      {/if}
                      <div class="card-score-box">{pts}</div>
                    </div>
                  </div>

                  <!-- Effect badges -->
                  {#if effects.length > 0}
                    <div class="card-effect-badges">
                      {#each effects as eff}
                        <span class="effect-badge effect-{eff}">
                          {eff === 'gold' ? 'GD' : eff === 'glass' ? 'GL' : eff === 'trained' ? 'TR' : 'FO'}
                        </span>
                      {/each}
                    </div>
                  {/if}

                  <!-- Headshot -->
                  <div class="card-headshot">
                    {#if card.headshot_url}
                      <img
                        class="card-headshot-img"
                        src={card.headshot_url}
                        alt=""
                        onerror={(e) => { (e.target as HTMLImageElement).src = '/img/blank_player.png'; (e.target as HTMLImageElement).classList.add('card-headshot-blank'); }}
                      >
                    {:else}
                      <img class="card-headshot-img card-headshot-blank" src="/img/blank_player.png" alt="">
                    {/if}
                    <button class="card-flip-btn" type="button" title="View stats" onclick={(e) => { e.stopPropagation(); flipCard(card.id, card); }}>
                      &#8617;
                    </button>
                  </div>

                  <!-- Bottom row: division + position -->
                  <div class="card-bottom-row">
                    <div class="card-footer-div">
                      {#if divInfo}
                        <div class="card-div-badge {divInfo.cls}">{divInfo.label}</div>
                      {/if}
                    </div>
                    <span class="card-pos-badge">{card.pos}</span>
                  </div>
                </div>

                <!-- Card Back -->
                <div class="card-back">
                  {#if stats}
                    <div class="card-back-header">
                      <span class="card-back-pos card-pos-{card.pos.toLowerCase()}">{card.pos}</span>
                      <span class="card-back-team">{card.team}</span>
                    </div>
                    <div class="card-back-name">{card.player}</div>
                    <div class="card-back-season">{displayYear(card.season)}</div>
                    <div class="card-back-college">{(card.college && card.college !== 'Unknown') ? card.college : 'Undrafted'}</div>
                    {#if card.allstar_count && card.allstar_count > 0}
                      <div class="card-back-pb">★ {card.allstar_count}x {sport === 'nfl' ? 'Pro Bowl' : 'All-Star'}</div>
                    {:else if card.draft_pick && card.draft_pick > 0}
                      <div class="card-back-pb">Pick #{card.draft_pick}</div>
                    {/if}
                    <div class="card-back-stats">
                      {#if sport === 'nba'}
                        <div class="stat-row"><span>PTS</span><span>{(stats.pts_pg || 0).toFixed(1)} ppg</span></div>
                        <div class="stat-row"><span>REB</span><span>{(stats.trb_pg || 0).toFixed(1)} rpg</span></div>
                        <div class="stat-row"><span>AST</span><span>{(stats.ast_pg || 0).toFixed(1)} apg</span></div>
                      {:else}
                        {#if stats.pts_pg}<div class="stat-row"><span>FP</span><span>{stats.pts_pg}</span></div>{/if}
                      {/if}
                    </div>
                    <div class="card-back-ppr">{card.fantasy_pts !== undefined ? card.fantasy_pts.toFixed(1) : pts} FP</div>
                  {:else}
                    <div class="card-back-loading">Loading...</div>
                  {/if}
                </div>
              </div>
            </div>
          {/each}
        </div>
      </div>

      <!-- Action Buttons -->
      <div id="action-buttons">
        <button id="play-btn" class="btn-play" type="button" disabled={selectedIds.size === 0 || actionPending || scoringActive} onclick={handlePlayHand}>
          PLAY HAND ({selectedIds.size})
        </button>
        <button id="discard-btn" class="btn-discard" type="button" disabled={selectedIds.size === 0 || discardsRemaining <= 0 || actionPending || scoringActive} onclick={handleDiscard}>
          DISCARD ({discardsRemaining})
        </button>
      </div>

      {#if deckViewOpen}
        <div class="full-overlay" id="deck-viewer-overlay">
          <div class="deck-viewer-header">
            <div class="deck-viewer-title">Deck View</div>
            <button class="btn-secondary" type="button" onclick={() => (deckViewOpen = false)}>Close</button>
          </div>

          {#if deckGroups.length === 0}
            <div class="deck-empty-msg">No deck cards available yet.</div>
          {:else}
            {#each deckGroups as group}
              <div class="deck-pos-group">
                <div class="deck-pos-header pos-{group.pos.toLowerCase()}">{group.pos} ({group.cards.length})</div>
                <div class="deck-cards-grid">
                  {#each group.cards as card}
                    {@const divInfo = getDivInfo(card.team)}
                    {@const splitName = card.player.split(' ')}
                    {@const firstName = splitName.length > 1 ? splitName[0] : ''}
                    {@const lastName = splitName.length > 1 ? splitName.slice(1).join(' ') : splitName[0]}
                    {@const pts = card.fantasy_pts !== undefined ? Math.round(card.fantasy_pts) : card.pts}
                    <div class="card {posClass(card.pos)}">
                      <div class="card-inner">
                        <div class="card-front">
                          <div class="card-top-row">
                            <div class="card-name-box">
                              <div class="card-year-line">
                                {card.season ? "'" + String(displayYear(card.season)).slice(-2) : ''}
                                {card.team ? ' · ' + card.team : ''}
                              </div>
                              {#if firstName}<div class="card-player-first">{firstName}</div>{/if}
                              <div class="card-player-last">{lastName}</div>
                            </div>
                            <div class="card-top-right">
                              <div class="card-score-box">{pts}</div>
                            </div>
                          </div>
                          <div class="card-headshot">
                            {#if card.headshot_url}
                              <img class="card-headshot-img" src={card.headshot_url} alt="" onerror={(e) => { (e.target as HTMLImageElement).src = '/img/blank_player.png'; }}>
                            {:else}
                              <img class="card-headshot-img card-headshot-blank" src="/img/blank_player.png" alt="">
                            {/if}
                          </div>
                          <div class="card-bottom-row">
                            <div class="card-footer-div">
                              {#if divInfo}
                                <div class="card-div-badge {divInfo.cls}">{divInfo.label}</div>
                              {/if}
                            </div>
                            <span class="card-pos-badge">{card.pos}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  {/each}
                </div>
              </div>
            {/each}
          {/if}
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
          {#if rewardOptions.length > 0}
            <div class="reward-choice-card reward-choice-joker-card" id="reward-choice-joker">
              <div class="reward-choice-icon reward-icon-joker">FAN</div>
              <div class="reward-choice-label">FREE FAN PACK</div>
              <div class="reward-choice-desc reward-joker-subdesc">Pick 1 of {rewardOptions.length} - keep it forever</div>
              <div id="reward-joker-options" class="reward-joker-grid">
                {#each rewardOptions as joker}
                  <div class="reward-joker-option">
                    <div class="joker-name">{joker.name}</div>
                    <div class="joker-desc">{joker.description}</div>
                    <div class="joker-rarity rarity-{joker.rarity}">{joker.rarity}</div>
                    <button class="btn-secondary" type="button" disabled={actionPending} onclick={() => handleClaimReward('joker', joker.id)}>Take</button>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      </div>
    </div>

  <!-- SHOP SCREEN -->
  {:else if screen === 'shop'}
    <div id="shop-screen" class="screen active">
      <div class="shop-inner">
        <!-- Store Banner -->
        <div class="store-banner">
          <div class="store-marquee">OFFICIAL TEAM MERCHANDISE &nbsp;&middot;&nbsp; ALL SALES FINAL &nbsp;&middot;&nbsp; GAME DAY SPECIALS</div>
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

        <!-- Shop content: sections of items -->
        <div class="shop-content">
          <div class="shop-items-area">
            {#each getShopSections() as section}
              <div class="shop-section" style="--section-color: {section.color}">
                <div class="shop-section-header">
                  <span class="shop-section-title">{section.label}</span>
                </div>
                <div class="shop-items-row">
                  {#each section.items as item}
                    {@const isPack = 'pack_id' in item}
                    {@const cost = item.cost}
                    {@const canAfford = coins >= cost}
                    {@const itemType = isPack ? 'pack' : ((item as ShopItem).item_type || '')}
                    {@const shopId = isPack ? (item as ShopPack).pack_id : (item as ShopItem).shop_id}
                    {@const rarity = (item as Record<string, unknown>).rarity as string}
                    {@const cardData = (item as Record<string, unknown>).card_data as Record<string, unknown> | undefined}
                    {@const headshotUrl = cardData?.headshot_url as string | undefined}
                    {@const cardPos = (cardData?.pos as string | undefined)?.toLowerCase()}
                    <div class="shop-item" class:cant-afford={!canAfford}>
                      <div class="shop-price-badge" class:cant-afford={!canAfford}>${cost}</div>
                      <div class="shop-item-icon-area">
                        {#if itemType === 'joker'}
                          <img class="shop-item-img joker-fan-img" src={sport === 'nfl' ? '/img/football_fan.png' : '/img/basketball_fan.png'} alt="Fan">
                        {:else if itemType === 'buy_card' && headshotUrl}
                          <img class="shop-item-img headshot-img" src={headshotUrl} alt={cardData?.player as string ?? ''} onerror={(e) => { (e.target as HTMLImageElement).src = '/img/blank_player.png'; }}>
                          {#if cardPos}
                            <div class="shop-item-pos-badge card-pos-{cardPos}">{(cardData?.pos as string ?? '').toUpperCase()}</div>
                          {/if}
                        {:else}
                          <span class="shop-item-icon-text">{isPack ? 'PACK' : (ITEM_ICON[itemType] || 'ITM')}</span>
                        {/if}
                        {#if rarity}
                          <div class="shop-item-rarity-bar rarity-bar-{rarity}"></div>
                        {/if}
                      </div>
                      <div class="shop-item-body">
                        <div class="shop-item-type">{isPack ? 'PACK' : (ITEM_TYPE_LABEL[itemType] || itemType.toUpperCase())}</div>
                        <div class="shop-item-name">{item.name}</div>
                        <div class="shop-item-desc">{item.description || (item as Record<string, unknown>).desc}</div>
                      </div>
                      <div class="shop-item-footer">
                        <button class="btn-buy" type="button" disabled={!canAfford || actionPending}
                          onclick={() => {
                            if (isPack) handleOpenPack(shopId);
                            else handleBuyItem(shopId, itemType);
                          }}>
                          {canAfford ? (isPack ? 'OPEN' : 'BUY') : 'NO $'}
                        </button>
                      </div>
                    </div>
                  {/each}
                </div>
              </div>
            {/each}
          </div>

          <!-- Your Locker (Jokers) -->
          {#if jokers.length > 0}
            <div class="shop-locker-section">
              <div class="shop-section-header">
                <span class="shop-section-title" style="color:#9b59b6;">YOUR LOCKER</span>
                <span class="shop-sell-hint">click SELL to sell</span>
              </div>
              <div class="joker-list">
                {#each jokers as joker}
                  <div class="joker-slot filled shop-joker">
                    <img class="joker-fan-img" src={sport === 'nfl' ? '/img/football_fan.png' : '/img/basketball_fan.png'} alt="Fan">
                    <div class="joker-name">{joker.name}</div>
                    <div class="joker-desc">{joker.description}</div>
                    <div class="joker-rarity rarity-{joker.rarity}">{joker.rarity}</div>
                    {#if joker.sell_value}
                      <button class="btn-sell" type="button" disabled={actionPending} onclick={() => handleSellJoker(joker.id)}>
                        Sell ${joker.sell_value}
                      </button>
                    {/if}
                  </div>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Your Roster (Deck Pool Cards) -->
          {#if deckPool.length > 0}
            <div class="shop-locker-section">
              <div class="shop-section-header">
                <span class="shop-section-title" style="color:#2980b9;">YOUR ROSTER ({deckPool.length} cards)</span>
              </div>
              <div class="roster-cards-grid">
                {#each deckPool as card}
                  {@const divInfo = getDivInfo(card.team)}
                  {@const splitName = card.player.split(' ')}
                  {@const lastName = splitName.length > 1 ? splitName.slice(1).join(' ') : splitName[0]}
                  {@const pts = card.fantasy_pts !== undefined ? Math.round(card.fantasy_pts) : card.pts}
                  <div class="roster-card {posClass(card.pos)}">
                    <div class="roster-card-headshot">
                      {#if card.headshot_url}
                        <img class="roster-headshot-img" src={card.headshot_url} alt="" onerror={(e) => { (e.target as HTMLImageElement).src = '/img/blank_player.png'; }}>
                      {:else}
                        <img class="roster-headshot-img" src="/img/blank_player.png" alt="">
                      {/if}
                    </div>
                    <div class="roster-card-info">
                      <div class="roster-card-name">{lastName}</div>
                      <div class="roster-card-meta">
                        <span class="card-pos-badge" style="font-size:0.6rem;padding:1px 4px;">{card.pos}</span>
                        {#if divInfo}<span class="card-div-badge {divInfo.cls}" style="font-size:0.55rem;padding:1px 3px;">{divInfo.label}</span>{/if}
                        <span class="roster-card-pts">{pts} FP</span>
                      </div>
                    </div>
                  </div>
                {/each}
              </div>
            </div>
          {/if}

          <!-- Shop Actions -->
          <div class="shop-actions">
            <button id="restock-btn" class="btn-secondary" type="button" disabled={actionPending || coins < (2 + restockCount * 2)}
              onclick={handleRestock}>
              Restock (${2 + restockCount * 2})
            </button>
            <button id="leave-shop-btn" class="btn-primary" type="button" disabled={actionPending} onclick={handleLeaveShop}>
              NEXT FIGHT &rarr;
            </button>
          </div>

          <!-- Vendor NPC -->
          <div class="npc-panel">
            <div class="npc-nameplate">Vendor Vic</div>
            <div class="npc-char">
              <div class="npc-avatar">VIC</div>
            </div>
            <div class="vendor-bubble">{vendorLine}</div>
          </div>
        </div>
      </div>

      <!-- Pack opening modal -->
      {#if packOpen}
        <div id="pack-opening-modal" class="full-overlay">
          <div id="pack-opening-content">
            <div id="pack-opening-title">Pick up to {packMaxPicks} card(s)</div>
            {#if packIsJoker}
              <div class="reward-joker-grid">
                {#each packJokerOptions as joker}
                  <div class="reward-joker-option" class:selected={packSelectedIds.has(joker.id)}>
                    <div class="joker-name">{joker.name}</div>
                    <div class="joker-desc">{joker.description}</div>
                    <div class="joker-rarity rarity-{joker.rarity}">{joker.rarity}</div>
                    <button class="btn-secondary" type="button" onclick={() => togglePackCard(joker.id)}>
                      {packSelectedIds.has(joker.id) ? 'Selected' : 'Pick'}
                    </button>
                  </div>
                {/each}
              </div>
            {:else}
              <div id="pack-cards-reveal">
                {#each packCards as card}
                {@const divInfo = getDivInfo(card.team)}
                {@const splitName = card.player.split(' ')}
                {@const firstName = splitName.length > 1 ? splitName[0] : ''}
                {@const lastName = splitName.length > 1 ? splitName.slice(1).join(' ') : splitName[0]}
                {@const pts = card.fantasy_pts !== undefined ? Math.round(card.fantasy_pts) : card.pts}
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
                      <div class="card-top-row">
                        <div class="card-name-box">
                          <div class="card-year-line">
                            {card.season ? "'" + String(displayYear(card.season)).slice(-2) : ''}
                            {card.team ? ' \u00B7 ' + card.team : ''}
                          </div>
                          {#if firstName}<div class="card-player-first">{firstName}</div>{/if}
                          <div class="card-player-last">{lastName}</div>
                        </div>
                        <div class="card-top-right">
                          <div class="card-score-box">{pts}</div>
                        </div>
                      </div>
                      <div class="card-headshot">
                        {#if card.headshot_url}
                          <img class="card-headshot-img" src={card.headshot_url} alt=""
                            onerror={(e) => { (e.target as HTMLImageElement).src = '/img/blank_player.png'; }}>
                        {:else}
                          <img class="card-headshot-img card-headshot-blank" src="/img/blank_player.png" alt="">
                        {/if}
                      </div>
                      <div class="card-bottom-row">
                        <div class="card-footer-div">
                          {#if divInfo}
                            <div class="card-div-badge {divInfo.cls}">{divInfo.label}</div>
                          {/if}
                        </div>
                        <span class="card-pos-badge">{card.pos}</span>
                      </div>
                    </div>
                  </div>
                </div>
                {/each}
              </div>
            {/if}
            <div class="pack-actions">
              <button id="pack-close-btn" class="btn-primary" type="button" disabled={actionPending || packSelectedIds.size === 0} onclick={handleConfirmPackPicks}>
                Confirm ({packSelectedIds.size}/{packMaxPicks})
              </button>
              <button class="btn-secondary" type="button" disabled={actionPending} onclick={() => { packOpen = false; packCards = []; packJokerOptions = []; packIsJoker = false; }}>
                Skip
              </button>
            </div>
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
          Floor {floor} &middot; Fight {fight} &middot; Round {round}
          <br>Score: {formatNum(currentScore)} / {formatNum(targetScore)}
          <br>Coins: ${coins} &middot; Jokers: {jokers.length}
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
