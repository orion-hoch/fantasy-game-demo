// ═══════════════════════════════════════════════════════════════════════════
// TWENTY-FOUR CARD GAME  —  Card → Op → Card
// ═══════════════════════════════════════════════════════════════════════════

const SUITS = ['\u2660', '\u2665', '\u2666', '\u2663'];
const SUIT_COLORS = { '\u2660': 'black', '\u2665': 'red', '\u2666': 'red', '\u2663': 'black' };
const RANKS = ['A','2','3','4','5','6','7','8','9','10','J','Q','K'];
const RANK_VALUES = { A:1,'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,J:11,Q:12,K:13 };
const TOTAL_ROUNDS = 5;

let state = {
  cards: [],          // current cards in play
  selected1: -1,      // index of first selected card
  selectedOp: null,   // chosen operation
  history: [],
  target: 0,
  round: 0,
  score: 0,
  streak: 0,
  bestStreak: 0,
  attempts: 0,
  maxAttempts: 3,
  phase: 'start',
  roundResults: [],
  originalCards: [],
};

// ── Deck ─────────────────────────────────────────────────────────────────
function createDeck() {
  const d = [];
  for (const s of SUITS) for (const r of RANKS)
    d.push({ rank: r, suit: s, value: RANK_VALUES[r], id: `${r}${s}` });
  return d;
}
function shuffleDeck(d) {
  for (let i = d.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [d[i], d[j]] = [d[j], d[i]];
  }
  return d;
}

// ── Solver ───────────────────────────────────────────────────────────────
function solveReachable(nums, reachable) {
  if (nums.length === 1) {
    const v = nums[0];
    if (Number.isFinite(v) && Math.abs(v - Math.round(v)) < 1e-9) {
      const n = Math.round(v);
      if (n >= 24 && n <= 99) reachable.add(n);
    }
    return;
  }
  for (let i = 0; i < nums.length; i++) {
    for (let j = i + 1; j < nums.length; j++) {
      const a = nums[i], b = nums[j];
      const rest = nums.filter((_, k) => k !== i && k !== j);
      const results = [a + b, a - b, b - a, a * b];
      if (Math.abs(b) > 1e-12) results.push(a / b);
      if (Math.abs(a) > 1e-12) results.push(b / a);
      for (const r of results) solveReachable([r, ...rest], reachable);
    }
  }
}
function findReachableTargets(vals) {
  const s = new Set();
  solveReachable(vals, s);
  return s;
}
function findSolution(vals, target) {
  const steps = [];
  if (_solvePath(vals.slice(), target, steps)) return steps;
  return null;
}
function _solvePath(nums, target, steps) {
  if (nums.length === 1) return Math.abs(nums[0] - target) < 1e-9;
  const ops = [
    { sym: '+', fn: (a, b) => a + b },
    { sym: '\u2212', fn: (a, b) => a - b },
    { sym: '\u00d7', fn: (a, b) => a * b },
    { sym: '\u00f7', fn: (a, b) => a / b },
  ];
  for (let i = 0; i < nums.length; i++) {
    for (let j = 0; j < nums.length; j++) {
      if (i === j) continue;
      for (const { sym, fn } of ops) {
        if (sym === '\u00f7' && Math.abs(nums[j]) < 1e-12) continue;
        const r = fn(nums[i], nums[j]);
        const rest = nums.filter((_, k) => k !== i && k !== j);
        const fmt = v => Number.isInteger(v) ? String(v) : v.toFixed(2);
        steps.push(`${fmt(nums[i])} ${sym} ${fmt(nums[j])} = ${fmt(r)}`);
        if (_solvePath([r, ...rest], target, steps)) return true;
        steps.pop();
      }
    }
  }
  return false;
}

// ── Interaction: Card → Op → Card ────────────────────────────────────────
function pickCard(index) {
  if (state.phase !== 'playing') return;

  if (state.selected1 === -1) {
    // First card
    state.selected1 = index;
    state.selectedOp = null;
    render();
  } else if (state.selectedOp === null) {
    // Clicked another card without picking op — switch selection
    state.selected1 = index;
    render();
  } else {
    // We have card1 + op, this is card2
    if (index === state.selected1) return; // same card
    doCombine(state.selected1, index, state.selectedOp);
  }
}

function pickOp(op) {
  if (state.phase !== 'playing') return;
  if (state.selected1 === -1) return; // need a card first
  state.selectedOp = op;
  render();
}

function doCombine(i1, i2, op) {
  const a = state.cards[i1];
  const b = state.cards[i2];
  let result;
  let sym;
  switch (op) {
    case '+': result = a.value + b.value; sym = '+'; break;
    case '-': result = a.value - b.value; sym = '\u2212'; break;
    case '*': result = a.value * b.value; sym = '\u00d7'; break;
    case '/':
      if (Math.abs(b.value) < 1e-12) { clearSelection(); return; }
      result = a.value / b.value; sym = '\u00f7'; break;
    default: return;
  }

  state.history.push(JSON.parse(JSON.stringify(state.cards)));

  const disp = Math.abs(result - Math.round(result)) < 1e-9
    ? String(Math.round(result)) : result.toFixed(2);

  const merged = {
    value: result, display: disp, rank: disp, suit: '',
    isOriginal: false, id: `r-${Date.now()}`,
    label: `${a.display || a.rank}${sym}${b.display || b.rank}`,
  };

  // Remove both (higher index first so splice doesn't shift)
  const lo = Math.min(i1, i2), hi = Math.max(i1, i2);
  state.cards.splice(hi, 1);
  state.cards.splice(lo, 1, merged);

  clearSelection();
  render();

  if (state.cards.length === 1) checkFinalCard();
}

function clearSelection() {
  state.selected1 = -1;
  state.selectedOp = null;
}

function undo() {
  if (state.phase !== 'playing' || !state.history.length) return;
  state.cards = state.history.pop();
  clearSelection();
  render();
}

function resetCards() {
  if (state.phase !== 'playing') return;
  state.cards = JSON.parse(JSON.stringify(state.originalCards));
  state.history = [];
  clearSelection();
  render();
}

// ── Check ────────────────────────────────────────────────────────────────
function checkFinalCard() {
  const v = state.cards[0].value;
  const isInt = Math.abs(v - Math.round(v)) < 1e-9;
  const n = isInt ? Math.round(v) : null;
  const win = n === state.target;
  state.attempts++;

  if (win) {
    const pts = Math.max(100 - (state.attempts - 1) * 30, 10);
    state.score += pts;
    state.streak++;
    if (state.streak > state.bestStreak) state.bestStreak = state.streak;
    if (state.streak > 1) { state.score += state.streak * 10; }
    state.roundResults.push({ round: state.round, success: true, target: state.target, attempts: state.attempts });
    showOverlay(n, true);
  } else {
    state.streak = 0;
    if (state.attempts < state.maxAttempts) {
      showOverlay(n ?? state.cards[0].display, false, false);
    } else {
      state.roundResults.push({ round: state.round, success: false, target: state.target, attempts: state.attempts });
      showOverlay(n ?? state.cards[0].display, false, true);
    }
  }
  renderStatus();
}

function showOverlay(result, success, outOfAttempts) {
  const ov = document.getElementById('result-overlay');
  const c = document.getElementById('result-content');
  ov.classList.add('visible');

  if (success) {
    const pts = Math.max(100 - (state.attempts - 1) * 30, 10);
    const sb = state.streak > 1 ? state.streak * 10 : 0;
    c.innerHTML = `<div class="result-box result-success">
      <div class="result-icon">\u2713</div>
      <div class="result-number" id="count-el">0</div>
      <div class="result-text">TARGET HIT!</div>
      <div class="result-points">+${pts} pts${sb ? ` (+${sb} streak)` : ''}</div>
    </div>`;
    countUp(state.target, document.getElementById('count-el'), () => {
      setTimeout(() => { ov.classList.remove('visible'); advance(); }, 1600);
    });
  } else if (!outOfAttempts) {
    c.innerHTML = `<div class="result-box result-miss">
      <div class="result-icon">\u2717</div>
      <div class="result-number">${result}</div>
      <div class="result-text">MISS! ${result} \u2260 ${state.target}</div>
      <div class="result-detail">Attempts left: ${state.maxAttempts - state.attempts}</div>
      <button class="btn-overlay" onclick="retry()">TRY AGAIN</button>
    </div>`;
  } else {
    const sol = findSolution(state.originalCards.map(c => c.value), state.target);
    let sh = '';
    if (sol) sh = `<div class="sol-box">${sol.map((s, i) => `<div class="sol-step">${i + 1}. ${s}</div>`).join('')}</div>`;
    c.innerHTML = `<div class="result-box result-fail">
      <div class="result-icon">\u2717</div>
      <div class="result-number">${result}</div>
      <div class="result-text">OUT OF ATTEMPTS</div>
      <div class="result-detail">Target was ${state.target}</div>
      ${sh}
      <button class="btn-overlay" onclick="closeAndAdvance()">CONTINUE</button>
    </div>`;
  }
}

function retry() {
  document.getElementById('result-overlay').classList.remove('visible');
  state.cards = JSON.parse(JSON.stringify(state.originalCards));
  state.history = [];
  clearSelection();
  render();
}
function closeAndAdvance() {
  document.getElementById('result-overlay').classList.remove('visible');
  advance();
}
function advance() {
  if (state.round >= TOTAL_ROUNDS) showGameOver();
  else nextRound();
}

function countUp(target, el, cb) {
  const dur = 900, t0 = performance.now();
  (function tick(now) {
    const p = Math.min((now - t0) / dur, 1);
    el.textContent = Math.round((1 - Math.pow(1 - p, 3)) * target);
    if (p < 1) requestAnimationFrame(tick);
    else { el.textContent = target; if (cb) setTimeout(cb, 250); }
  })(t0);
}

// ── Render ───────────────────────────────────────────────────────────────
function render() {
  renderCards();
  renderOps();
  renderStatus();
  document.getElementById('undo-btn').disabled = !state.history.length;
  document.getElementById('reset-btn').disabled = !state.history.length;
}

function renderCards() {
  const row = document.getElementById('card-row');
  row.innerHTML = '';
  state.cards.forEach((card, i) => {
    const el = document.createElement('div');
    const sel = i === state.selected1 ? ' selected' : '';
    if (card.isOriginal) {
      const color = SUIT_COLORS[card.suit];
      el.className = `card ${color}${sel}`;
      el.innerHTML = `
        <span class="corner tl"><span class="rank">${card.rank}</span><span class="suit-s">${card.suit}</span></span>
        <span class="big-suit">${card.suit}</span>
        <span class="corner br"><span class="rank">${card.rank}</span><span class="suit-s">${card.suit}</span></span>
        <span class="val-badge">${card.value}</span>`;
    } else {
      el.className = `card result-card${sel}`;
      el.innerHTML = `
        <span class="res-val">${card.display}</span>
        <span class="res-from">${card.label}</span>`;
    }
    el.addEventListener('click', () => pickCard(i));
    row.appendChild(el);
  });
}

function renderOps() {
  document.querySelectorAll('.op-btn').forEach(btn => {
    const op = btn.dataset.op;
    btn.classList.toggle('active', state.selectedOp === op);
    btn.classList.toggle('enabled', state.selected1 !== -1);
  });
  // Prompt text
  const prompt = document.getElementById('prompt-text');
  if (state.phase !== 'playing') { prompt.textContent = ''; return; }
  if (state.selected1 === -1) {
    prompt.textContent = 'Select a card';
  } else if (!state.selectedOp) {
    prompt.textContent = 'Pick an operation';
  } else {
    prompt.textContent = 'Select a second card';
  }
}

function renderStatus() {
  document.getElementById('round-display').textContent = `${state.round} / ${TOTAL_ROUNDS}`;
  document.getElementById('score-display').textContent = state.score;
  document.getElementById('streak-display').textContent = state.streak;
  document.getElementById('attempts-display').textContent = `${state.attempts} / ${state.maxAttempts}`;
}

// ── Game Flow ────────────────────────────────────────────────────────────
function startGame() {
  state.round = 0; state.score = 0; state.streak = 0;
  state.bestStreak = 0; state.roundResults = [];
  document.getElementById('start-screen').classList.remove('active');
  document.getElementById('game-screen').classList.add('active');
  document.getElementById('gameover-screen').classList.remove('active');
  nextRound();
}

function nextRound() {
  state.round++;
  state.attempts = 0;
  state.history = [];
  clearSelection();
  state.phase = 'dealing';
  dealValid();
}

function dealValid() {
  let deck, hand, reach, tries = 0;
  do {
    deck = shuffleDeck(createDeck());
    hand = deck.splice(0, 5);
    reach = findReachableTargets(hand.map(c => c.value));
    tries++;
  } while (reach.size === 0 && tries < 1000);

  state.cards = hand.map(c => ({
    value: c.value, display: String(c.value), rank: c.rank,
    suit: c.suit, isOriginal: true, id: c.id,
  }));
  state.originalCards = JSON.parse(JSON.stringify(state.cards));
  const arr = [...reach];
  state.target = arr[Math.floor(Math.random() * arr.length)];

  animateDeal();
}

function animateDeal() {
  const row = document.getElementById('card-row');
  const deckEl = document.getElementById('deck-stack');
  row.innerHTML = '';
  document.getElementById('target-container').classList.remove('visible');
  document.getElementById('game-controls').classList.remove('visible');

  deckEl.classList.add('shuffling');
  setTimeout(() => {
    deckEl.classList.remove('shuffling');
    state.cards.forEach((card, i) => {
      setTimeout(() => {
        const el = document.createElement('div');
        const color = SUIT_COLORS[card.suit];
        el.className = `card ${color} deal-in`;
        el.innerHTML = `
          <span class="corner tl"><span class="rank">${card.rank}</span><span class="suit-s">${card.suit}</span></span>
          <span class="big-suit">${card.suit}</span>
          <span class="corner br"><span class="rank">${card.rank}</span><span class="suit-s">${card.suit}</span></span>
          <span class="val-badge">${card.value}</span>`;
        el.addEventListener('click', () => pickCard(i));
        row.appendChild(el);

        if (i === 4) {
          setTimeout(() => {
            state.phase = 'playing';
            document.getElementById('target-number').textContent = state.target;
            document.getElementById('target-container').classList.add('visible');
            document.getElementById('game-controls').classList.add('visible');
            render();
          }, 350);
        }
      }, i * 220);
    });
  }, 550);
}

function showGameOver() {
  state.phase = 'gameover';
  document.getElementById('game-screen').classList.remove('active');
  document.getElementById('gameover-screen').classList.add('active');
  const w = state.roundResults.filter(r => r.success).length;
  document.getElementById('final-score').textContent = state.score;
  document.getElementById('final-rounds-won').textContent = `${w} / ${TOTAL_ROUNDS}`;
  document.getElementById('final-best-streak').textContent = state.bestStreak;
  const el = document.getElementById('round-summary');
  el.innerHTML = '';
  state.roundResults.forEach(r => {
    const d = document.createElement('div');
    d.className = `summary-row ${r.success ? 'win' : 'loss'}`;
    d.innerHTML = `<span class="sr-round">R${r.round}</span>
      <span class="sr-target">Target: ${r.target}</span>
      <span class="sr-result">${r.success ? '\u2713' : '\u2717'} ${r.success ? `(${r.attempts})` : 'Failed'}</span>`;
    el.appendChild(d);
  });
}

// ── Init ─────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('start-btn').addEventListener('click', startGame);
  document.getElementById('undo-btn').addEventListener('click', undo);
  document.getElementById('reset-btn').addEventListener('click', resetCards);
  document.querySelectorAll('.op-btn').forEach(btn => {
    btn.addEventListener('click', () => pickOp(btn.dataset.op));
  });
  document.getElementById('play-again-btn').addEventListener('click', () => {
    document.getElementById('gameover-screen').classList.remove('active');
    document.getElementById('start-screen').classList.add('active');
  });
});
