const SLOTS = [
    { key: "G1",   label: "G 1",  pos: "G" },
    { key: "G2",   label: "G 2",  pos: "G" },
    { key: "F1",   label: "F 1",  pos: "F" },
    { key: "F2",   label: "F 2",  pos: "F" },
    { key: "C",    label: "C",    pos: "C" },
    { key: "UTIL", label: "UTIL", pos: "UTIL" },
];

const BONUS_POSITIONS = ["G", "F", "C"];
const BONUS_DECADES   = [1970, 1980, 1990];

let state = {};
let playerCount = 2;
let debounceTimer = null;

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
    setStep("loading");
    document.getElementById("team-name").textContent = "Drawing...";

    const res = await fetch("/api/nba_starting5/random-team");
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
}

// ── Name search ────────────────────────────────────────────────────────────

document.getElementById("pick-input").addEventListener("input", (e) => {
    clearTimeout(debounceTimer);
    const q = e.target.value.trim();
    document.getElementById("pick-error").textContent = "";
    if (!q) { document.getElementById("pick-results").innerHTML = ""; return; }
    debounceTimer = setTimeout(() => searchPlayers(q), 200);
});

async function searchPlayers(term) {
    const res = await fetch(`/api/nba_starting5/search?q=${encodeURIComponent(term)}`);
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
    const used = state.skipsUsed[state.currentPlayer] >= 1;
    const btn = document.getElementById("pick-pass-wrap").querySelector("button");
    btn.textContent = used ? "No skips remaining" : "Pass — no valid player available";
    btn.disabled = used;
    document.getElementById("pick-pass-wrap").classList.remove("hidden");
}

async function selectName(name) {
    document.getElementById("pick-results").innerHTML = "";
    document.getElementById("pick-error").textContent = "";
    state.pendingName = name;

    const res = await fetch(
        `/api/nba_starting5/years?player=${encodeURIComponent(name)}&team=${encodeURIComponent(state.currentTeam)}`
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
        data.years.map(y => `<option value="${y}">${y + 1}</option>`).join("");
    document.getElementById("confirm-year-btn").disabled = true;
    setStep("year");
}

document.getElementById("pick-year-select").addEventListener("change", () => {
    document.getElementById("confirm-year-btn").disabled =
        document.getElementById("pick-year-select").value === "";
});

async function confirmYear() {
    const season = document.getElementById("pick-year-select").value;
    if (!season) return;

    const res = await fetch(
        `/api/nba_starting5/validate?player=${encodeURIComponent(state.pendingName)}` +
        `&team=${encodeURIComponent(state.currentTeam)}&season=${season}`
    );
    const data = await res.json();

    if (!data.valid) {
        document.getElementById("pick-error").textContent = "Something went wrong. Try again.";
        setStep("name");
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
    state.pendingName = null;
    setStep("name");
    document.getElementById("pick-input").focus();
}

// ── Turn management ────────────────────────────────────────────────────────

function passTurn() {
    if (window.SFX) SFX.play('click');
    state.skipsUsed[state.currentPlayer]++;
    state.bonus = randomBonus();
    renderRosters();
    advanceTurn();
}

function advanceTurn() {
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
                                <span class="slot-ppr">${(pick.ppr * (pick.bonusMultiplier || 1)).toFixed(0)}${gotBonus ? " ★" : ""}</span>
                            </div>
                            <span class="slot-meta">${pick.season + 1} · ${pick.team}</span>
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
            + `<div class="roster-total">Total: <strong>${total.toFixed(0)} Pts</strong></div>`
            + `<div class="roster-bonus-active">${bonusLabel(state.bonus)}</div>`;
    });
}

// ── Results ────────────────────────────────────────────────────────────────

function showResults() {
    if (window.SFX) SFX.play('confetti');
    document.getElementById("game-panel").classList.add("hidden");
    document.getElementById("results-panel").classList.remove("hidden");

    const totals = state.players.map(p => rosterTotal(p.roster));
    const maxTotal = Math.max(...totals);
    const winners = state.players.filter((_, i) => totals[i] === maxTotal);

    const winnerText = document.getElementById("winner-text");
    if (winners.length > 1) {
        winnerText.innerHTML = `<span class="tie">It's a Tie! ${maxTotal.toFixed(0)} pts each</span>`;
    } else {
        const wi = totals.indexOf(maxTotal);
        winnerText.innerHTML = `
            <span class="winner-name">${state.players[wi].name}</span> wins!
            <span class="winner-score">${maxTotal.toFixed(0)} Pts</span>`;
    }

    const container = document.getElementById("results-rosters");
    // Sort by total descending
    const order = totals.map((t, i) => ({ i, t })).sort((a, b) => b.t - a.t);

    container.innerHTML = order.map(({ i }) => {
        const p = state.players[i];
        const total = totals[i];
        const isWinner = total === maxTotal && winners.length === 1;
        return `
            <div class="result-roster">
                <div class="result-header ${isWinner ? "result-winner" : ""}">
                    <span>${p.name}</span>
                    <span>${total.toFixed(0)} pts</span>
                </div>
                ${SLOTS.map(s => {
                    const pick = p.roster[s.key];
                    const gotBonus = pick?.bonusMultiplier > 1;
                    return `
                        <div class="result-slot${gotBonus ? " bonus-slot" : ""}">
                            <span class="slot-label">${s.label}</span>
                            ${pick
                                ? `<span class="result-player">${pick.player} <small>${pick.season + 1} · ${pick.team}</small></span>
                                   <span class="result-ppr">${(pick.ppr * (pick.bonusMultiplier || 1)).toFixed(0)}${gotBonus ? " ★" : ""}</span>`
                                : `<span class="result-empty">—</span><span></span>`
                            }
                        </div>`;
                }).join("")}
            </div>`;
    }).join("");
}

function resetGame() {
    document.getElementById("results-panel").classList.add("hidden");
    document.getElementById("setup-panel").classList.remove("hidden");
}

// Close dropdown on outside click
document.addEventListener("click", (e) => {
    const wrap = document.getElementById("pick-search-wrap");
    if (wrap && !wrap.contains(e.target)) {
        document.getElementById("pick-results").innerHTML = "";
    }
});
