const SLOTS = [
    { key: "QB",   label: "QB",   pos: "QB" },
    { key: "WR1",  label: "WR 1", pos: "WR" },
    { key: "WR2",  label: "WR 2", pos: "WR" },
    { key: "RB1",  label: "RB 1", pos: "RB" },
    { key: "RB2",  label: "RB 2", pos: "RB" },
    { key: "TE",   label: "TE",   pos: "TE" },
    { key: "UTIL", label: "UTIL", pos: "UTIL" },
];

const BONUS_POSITIONS = ["QB", "WR", "RB", "TE"];
const BONUS_DECADES   = [1960, 1970, 1980];
const ROOM_ID = new URLSearchParams(window.location.search).get("room_id");
const TOKEN_KEY = "fantasy-multiplayer-token";

let state = {};
let playerCount = 2;
let debounceTimer = null;
let pollTimer = null;

function playerToken() {
    let value = sessionStorage.getItem(TOKEN_KEY);
    if (!value) {
        value = Math.random().toString(36).slice(2) + Date.now().toString(36);
        sessionStorage.setItem(TOKEN_KEY, value);
    }
    return value;
}

function isOnlineMode() {
    return !!ROOM_ID;
}

function hydrateState(nextState) {
    state = nextState || {};
    if (!(state.pickedPlayers instanceof Set)) {
        state.pickedPlayers = new Set(state.pickedPlayers || []);
    }
    if (!Array.isArray(state.skipsUsed)) {
        state.skipsUsed = [];
    }
    return state;
}

function isMyTurn() {
    if (!isOnlineMode() || !state.players || !state.players.length) return true;
    const current = state.players[state.currentPlayer];
    return !!current && current.token === playerToken();
}

function syncTurnLock() {
    if (!isOnlineMode()) return;
    const mine = isMyTurn() && !state.done;
    const input = document.getElementById("pick-input");
    const yearWrap = document.getElementById("pick-year-wrap");
    const yearSelect = document.getElementById("pick-year-select");
    const confirmBtn = document.getElementById("confirm-year-btn");
    const passBtn = document.getElementById("pick-pass-wrap").querySelector("button");
    const results = document.getElementById("pick-results");
    if (!mine && results) results.innerHTML = "";
    if (input) input.disabled = !mine || !yearWrap.classList.contains("hidden");
    if (yearSelect) yearSelect.disabled = !mine;
    if (confirmBtn) confirmBtn.disabled = !mine || !yearSelect.value;
    if (passBtn) passBtn.disabled = !mine || (state.skipsUsed[state.currentPlayer] || 0) >= 1;
}

// ── Setup screen ───────────────────────────────────────────────────────────

function setPlayerCount(n) {
    playerCount = n;
    document.querySelectorAll(".count-btn").forEach((btn, i) => {
        btn.classList.toggle("active", i + 2 === n);
    });
    renderNameInputs();
}

function renderNameInputs() {
    const wrap = document.getElementById("name-inputs-wrap");
    wrap.innerHTML = Array.from({ length: playerCount }, (_, i) => `
        <div class="name-field">
            <label>Player ${i + 1}</label>
            <input id="pname-${i}" type="text" placeholder="Player ${i + 1}" value="Player ${i + 1}" />
        </div>
    `).join("");
}

// Init setup on load
renderNameInputs();

// ── Bonus helpers ──────────────────────────────────────────────────────────

function randomBonus() {
    return {
        pos:    BONUS_POSITIONS[Math.floor(Math.random() * BONUS_POSITIONS.length)],
        decade: BONUS_DECADES[Math.floor(Math.random() * BONUS_DECADES.length)],
    };
}

function bonusLabel(b) {
    return `1.5× bonus: ${b.pos} from the ${b.decade}s`;
}

function pickMatchesBonus(pick, bonus) {
    return pick.pos === bonus.pos &&
        pick.season >= bonus.decade &&
        pick.season <= bonus.decade + 9;
}

// ── Roster helpers ─────────────────────────────────────────────────────────

function emptyRoster() {
    const r = {};
    SLOTS.forEach(s => r[s.key] = null);
    return r;
}

function neededPositions(roster) {
    const needed = {};
    SLOTS.forEach(s => { if (!roster[s.key]) needed[s.pos] = (needed[s.pos] || 0) + 1; });
    return needed;
}

function rosterFull(roster) { return SLOTS.every(s => roster[s.key] !== null); }

function rosterTotal(roster) {
    return SLOTS.reduce((sum, s) => {
        const p = roster[s.key];
        return p ? sum + (p.ppr || 0) * (p.bonusMultiplier || 1) : sum;
    }, 0);
}

function pickCount(roster) { return SLOTS.filter(s => roster[s.key] !== null).length; }

// ── Game start ─────────────────────────────────────────────────────────────

function startGame() {
    if (isOnlineMode()) return;
    const players = Array.from({ length: playerCount }, (_, i) => {
        const val = document.getElementById(`pname-${i}`).value.trim();
        return { name: val || `Player ${i + 1}`, roster: emptyRoster() };
    });

    state = {
        players,
        currentPlayer: 0,
        currentTeam: null,
        pendingName: null,
        bonus: randomBonus(),
        pickedPlayers: new Set(),   // player names already drafted
        skipsUsed: new Array(playerCount).fill(0),
    };

    document.getElementById("setup-panel").classList.add("hidden");
    document.getElementById("game-panel").classList.remove("hidden");

    buildRosterPanels();
    renderRosters();
    updateBanner();
    drawTeam();
}

// ── Dynamic roster panels ──────────────────────────────────────────────────

function buildRosterPanels() {
    const row = document.getElementById("rosters-row");
    row.innerHTML = state.players.map((p, i) => `
        <div class="roster-panel" id="roster-p${i}">
            <div class="roster-header">
                <span class="player-name">${p.name}</span>
            </div>
            <div class="roster-slots" id="slots-p${i}"></div>
        </div>
    `).join("");
}

// ── Team draw ──────────────────────────────────────────────────────────────

async function drawTeam() {
    if (isOnlineMode()) {
        document.getElementById("team-name").textContent = state.currentTeam || "-";
        updateBanner();
        if (isMyTurn()) {
            setStep("name");
        } else {
            setStep("loading");
            document.getElementById("pick-error").textContent = "Waiting for the current player to pick.";
        }
        syncTurnLock();
        return;
    }
    setStep("loading");
    document.getElementById("team-name").textContent = "Drawing...";

    const res = await fetch("/api/starting6/random-team");
    const data = await res.json();
    state.currentTeam = data.team;

    document.getElementById("team-name").textContent = data.team;
    updateBanner();
    setStep("name");
    document.getElementById("pick-input").focus();
}

// ── Banner ─────────────────────────────────────────────────────────────────

function updateBanner() {
    const p = state.players[state.currentPlayer];
    document.getElementById("turn-label").textContent = `${p.name}'s pick`;

    document.querySelectorAll(".roster-panel").forEach((panel, i) => {
        panel.classList.toggle("active-roster", i === state.currentPlayer);
    });
}

// ── UI step management ─────────────────────────────────────────────────────

function setStep(step) {
    const nameWrap = document.getElementById("pick-search-wrap");
    const yearWrap = document.getElementById("pick-year-wrap");
    const input    = document.getElementById("pick-input");
    const passWrap = document.getElementById("pick-pass-wrap");

    document.getElementById("pick-error").textContent = "";
    passWrap.classList.add("hidden");
    document.getElementById("pick-results").innerHTML = "";

    if (step === "loading") {
        nameWrap.classList.remove("hidden");
        yearWrap.classList.add("hidden");
        input.value = "";
        input.disabled = true;
    } else if (step === "name") {
        nameWrap.classList.remove("hidden");
        yearWrap.classList.add("hidden");
        input.value = "";
        input.disabled = false;
    } else if (step === "year") {
        nameWrap.classList.remove("hidden");
        yearWrap.classList.remove("hidden");
        input.value = state.pendingName;
        input.disabled = true;
    }
    syncTurnLock();
}

// ── Name search ────────────────────────────────────────────────────────────

document.getElementById("pick-input").addEventListener("input", (e) => {
    if (isOnlineMode() && !isMyTurn()) {
        e.target.value = "";
        return;
    }
    clearTimeout(debounceTimer);
    const q = e.target.value.trim();
    document.getElementById("pick-error").textContent = "";
    if (!q) { document.getElementById("pick-results").innerHTML = ""; return; }
    debounceTimer = setTimeout(() => searchPlayers(q), 200);
});

async function searchPlayers(term) {
    if (isOnlineMode() && !isMyTurn()) return;
    const suffix = isOnlineMode() ? `&game_id=${encodeURIComponent(state.game_id)}` : "";
    const res = await fetch(`/api/starting6/search?q=${encodeURIComponent(term)}${suffix}`);
    const data = await res.json();
    const container = document.getElementById("pick-results");
    if (!data.results.length) {
        container.innerHTML = `<div class="result-item"><span style="color:#556">No players found</span></div>`;
        return;
    }
    container.innerHTML = data.results.map(name => {
        const taken = state.pickedPlayers.has(name);
        return `
            <div class="result-item ${taken ? "taken" : ""}" onclick="${taken ? "" : `selectName('${name.replace(/'/g, "\\'")}')`}">
                <span>${name}</span>
                ${taken ? '<span style="color:#556;font-size:0.75rem">Already drafted</span>' : ""}
            </div>`;
    }).join("");
}

function showPassButton() {
    if (isOnlineMode() && !isMyTurn()) return;
    const used = state.skipsUsed[state.currentPlayer] >= 1;
    const btn = document.getElementById("pick-pass-wrap").querySelector("button");
    btn.textContent = used ? "No skips remaining" : "Pass — no valid player available";
    btn.disabled = used;
    document.getElementById("pick-pass-wrap").classList.remove("hidden");
}

async function selectName(name) {
    if (isOnlineMode() && !isMyTurn()) return;
    document.getElementById("pick-results").innerHTML = "";
    document.getElementById("pick-error").textContent = "";
    state.pendingName = name;

    const res = await fetch(
        isOnlineMode()
            ? `/api/starting6/years?player=${encodeURIComponent(name)}&game_id=${encodeURIComponent(state.game_id)}`
            : `/api/starting6/years?player=${encodeURIComponent(name)}&team=${encodeURIComponent(state.currentTeam)}`
    );
    const data = await res.json();

    if (!data.years.length) {
        document.getElementById("pick-error").textContent =
            `${name} didn't play for the ${state.currentTeam}. Try another name.`;
        showPassButton();
        state.pendingName = null;
        return;
    }

    const sel = document.getElementById("pick-year-select");
    sel.innerHTML = `<option value="">— select a season —</option>` +
        data.years.map(y => `<option value="${y}">${y}</option>`).join("");
    document.getElementById("confirm-year-btn").disabled = true;
    setStep("year");
}

document.getElementById("pick-year-select").addEventListener("change", () => {
    if (isOnlineMode() && !isMyTurn()) {
        document.getElementById("confirm-year-btn").disabled = true;
        return;
    }
    document.getElementById("confirm-year-btn").disabled =
        document.getElementById("pick-year-select").value === "";
});

async function confirmYear() {
    if (isOnlineMode() && !isMyTurn()) return;
    const season = document.getElementById("pick-year-select").value;
    if (!season) return;

    const res = await fetch(
        isOnlineMode()
            ? `/api/starting6/validate?player=${encodeURIComponent(state.pendingName)}&season=${season}&game_id=${encodeURIComponent(state.game_id)}&token=${encodeURIComponent(playerToken())}`
            : `/api/starting6/validate?player=${encodeURIComponent(state.pendingName)}` +
              `&team=${encodeURIComponent(state.currentTeam)}&season=${season}`
    );
    const data = await res.json();

    if (!data.valid) {
        document.getElementById("pick-error").textContent = data.msg || "Something went wrong. Try again.";
        setStep("name");
        return;
    }

    if (isOnlineMode()) {
        hydrateState(data.state);
        state.pendingName = null;
        document.getElementById("pick-year-select").value = "";
        document.getElementById("confirm-year-btn").disabled = true;
        renderRosters();
        if (state.done) {
            showResults();
            return;
        }
        updateBanner();
        drawTeam();
        return;
    }

    const roster = state.players[state.currentPlayer].roster;
    const needed = neededPositions(roster);

    if (!needed[data.pos] && !needed["UTIL"]) {
        document.getElementById("pick-error").textContent =
            `${data.pos} slots are already full — pick a different player.`;
        showPassButton();
        setStep("name");
        return;
    }

    data.bonusMultiplier = pickMatchesBonus(data, state.bonus) ? 1.5 : 1;

    const slot = SLOTS.find(s => s.pos === data.pos && !roster[s.key])
        || SLOTS.find(s => s.pos === "UTIL" && !roster[s.key]);
    if (window.SFX) SFX.play('draft_pick');
    roster[slot.key] = data;
    state.pickedPlayers.add(data.player);

    document.getElementById("pick-year-select").value = "";
    document.getElementById("confirm-year-btn").disabled = true;

    state.bonus = randomBonus();
    renderRosters();
    advanceTurn();
}

function backToName() {
    if (isOnlineMode() && !isMyTurn()) return;
    state.pendingName = null;
    setStep("name");
    document.getElementById("pick-input").focus();
}

// ── Turn management ────────────────────────────────────────────────────────

function passTurn() {
    if (isOnlineMode() && !isMyTurn()) return;
    if (isOnlineMode()) {
        fetch(`/api/starting6/pass`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ game_id: state.game_id, token: playerToken() })
        })
            .then(r => r.json())
            .then(data => {
                if (!data.ok) {
                    document.getElementById("pick-error").textContent = data.msg || "Could not pass.";
                    return;
                }
                hydrateState(data.state);
                renderRosters();
                if (state.done) {
                    showResults();
                    return;
                }
                updateBanner();
                drawTeam();
            });
        return;
    }
    if (window.SFX) SFX.play('click');
    state.skipsUsed[state.currentPlayer]++;
    state.bonus = randomBonus();
    renderRosters();
    advanceTurn();
}

function advanceTurn() {
    if (isOnlineMode()) return;
    state.pendingName = null;
    const n = state.players.length;

    if (state.players.every(p => rosterFull(p.roster))) {
        showResults();
        return;
    }

    // Advance to next player who still needs picks, cycling through all
    let next = (state.currentPlayer + 1) % n;
    let tries = 0;
    while (rosterFull(state.players[next].roster) && tries < n) {
        next = (next + 1) % n;
        tries++;
    }
    state.currentPlayer = next;
    drawTeam();
}

// ── Roster rendering ───────────────────────────────────────────────────────

function renderRosters() {
    state.players.forEach((p, i) => {
        const container = document.getElementById(`slots-p${i}`);
        if (!container) return;

        const slots = SLOTS.map(s => {
            const pick = p.roster[s.key];
            if (pick) {
                const gotBonus = pick.bonusMultiplier > 1;
                return `
                    <div class="roster-slot filled${gotBonus ? " bonus-slot" : ""}">
                        <span class="slot-label">${s.label}</span>
                        <div class="slot-content">
                            <div class="slot-top">
                                <span class="slot-player">${pick.player}</span>
                                <span class="slot-ppr">${(pick.ppr * (pick.bonusMultiplier || 1)).toFixed(1)}${gotBonus ? " ★" : ""}</span>
                            </div>
                            <span class="slot-meta">${pick.season} · ${pick.team}</span>
                        </div>
                    </div>`;
            }
            return `
                <div class="roster-slot empty">
                    <span class="slot-label">${s.label}</span>
                    <span class="slot-empty-text">—</span>
                </div>`;
        }).join("");

        const total = rosterTotal(p.roster);
        container.innerHTML = slots
            + `<div class="roster-total">Total: <strong>${total.toFixed(1)} PPR</strong></div>`
            + `<div class="roster-bonus-active">${bonusLabel(state.bonus)}</div>`;
    });
}

// ── Confetti ───────────────────────────────────────────────────────────────

let confettiRAF = null;
const CONFETTI_COLORS = ["#e8b820","#ff3c3c","#18a894","#ffffff","#a855f7","#3b82f6","#f97316"];

function startConfetti() {
    if (window.SFX) SFX.play('confetti');
    const canvas = document.getElementById("confetti-canvas");
    const ctx = canvas.getContext("2d");

    function resize() {
        canvas.width  = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener("resize", resize);

    const pieces = Array.from({ length: 120 }, () => ({
        x:     Math.random() * canvas.width,
        y:     Math.random() * -canvas.height,
        w:     6 + Math.random() * 8,
        h:     10 + Math.random() * 10,
        color: CONFETTI_COLORS[Math.floor(Math.random() * CONFETTI_COLORS.length)],
        rot:   Math.random() * Math.PI * 2,
        vx:    (Math.random() - 0.5) * 2.5,
        vy:    2.5 + Math.random() * 3.5,
        vr:    (Math.random() - 0.5) * 0.18,
    }));

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        pieces.forEach(p => {
            p.x  += p.vx;
            p.y  += p.vy;
            p.rot += p.vr;
            if (p.y > canvas.height + 20) {
                p.y  = -20;
                p.x  = Math.random() * canvas.width;
            }
            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate(p.rot);
            ctx.fillStyle = p.color;
            ctx.globalAlpha = 0.85;
            ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h);
            ctx.restore();
        });
        confettiRAF = requestAnimationFrame(draw);
    }
    draw();
}

function stopConfetti() {
    if (confettiRAF) {
        cancelAnimationFrame(confettiRAF);
        confettiRAF = null;
    }
    const canvas = document.getElementById("confetti-canvas");
    if (canvas) canvas.getContext("2d").clearRect(0, 0, canvas.width, canvas.height);
}

// ── Results ────────────────────────────────────────────────────────────────

function showResults() {
    document.getElementById("game-panel").classList.add("hidden");

    const totals = state.players.map(p => rosterTotal(p.roster));
    const maxTotal = Math.max(...totals);
    const winners = state.players.filter((_, i) => totals[i] === maxTotal);

    const overlay = document.getElementById("win-overlay");
    overlay.classList.remove("hidden");

    if (winners.length > 1) {
        document.getElementById("win-congrats").textContent = "IT'S A TIE!";
        document.getElementById("win-name").textContent = winners.map(w => w.name).join(" & ");
        const scoreEl = document.getElementById("win-score");
        scoreEl.textContent = `${maxTotal.toFixed(1)} PPR pts each`;
        scoreEl.className = "tie-score";
    } else {
        const wi = totals.indexOf(maxTotal);
        document.getElementById("win-congrats").textContent = "CONGRATULATIONS";
        document.getElementById("win-name").textContent = state.players[wi].name;
        document.getElementById("win-score").textContent = `${maxTotal.toFixed(1)} PPR pts`;
        document.getElementById("win-score").className = "";
    }

    startConfetti();
}

async function resetMultiplayerGame() {
    try {
        await fetch(`/api/lobbies/${encodeURIComponent(ROOM_ID)}/rematch`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: playerToken() })
        });
    } finally {
        window.location.href = `/lobbies/${encodeURIComponent(ROOM_ID)}`;
    }
}

function resetGame() {
    if (isOnlineMode()) {
        resetMultiplayerGame();
        return;
    }
    stopConfetti();
    document.getElementById("win-overlay").classList.add("hidden");
    document.getElementById("setup-panel").classList.remove("hidden");
    renderNameInputs();
}

// Close dropdown on outside click
document.addEventListener("click", (e) => {
    const wrap = document.getElementById("pick-search-wrap");
    if (wrap && !wrap.contains(e.target)) {
        document.getElementById("pick-results").innerHTML = "";
    }
});

async function loadOnlineState() {
    const res = await fetch(`/api/lobbies/${encodeURIComponent(ROOM_ID)}/game-state?token=${encodeURIComponent(playerToken())}`);
    const data = await res.json();
    if (!res.ok) return;
    if (data.room && data.room.status === "lobby") {
        window.location.href = `/lobbies/${encodeURIComponent(ROOM_ID)}`;
        return;
    }
    if (!data.state) return;
    hydrateState(data.state);
    document.getElementById("setup-panel").classList.add("hidden");
    document.getElementById("game-panel").classList.remove("hidden");
    buildRosterPanels();
    renderRosters();
    if (state.done) {
        showResults();
        return;
    }
    updateBanner();
    drawTeam();
}

if (isOnlineMode()) {
    loadOnlineState();
    pollTimer = window.setInterval(() => {
        if (isMyTurn()) return;
        loadOnlineState();
    }, 2500);
}
