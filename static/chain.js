/* ── Chain Game JS ─────────────────────────────────────────────────────────── */

(function () {
    "use strict";

    const API_PREFIX = window.CHAIN_API_PREFIX || "/api/chain";
    const params = new URLSearchParams(window.location.search);
    const ROOM_ID = params.get("room_id");
    const TOKEN_KEY = "fantasy-multiplayer-token";

    let score = 0;
    let chain = [];
    let validCount = 0;
    let gameActive = false;
    let inputLocked = false;
    let advanceTimer = null;
    let selectedIndex = -1;
    let searchDebounce = null;
    let currentGuess = "";
    let gameMode = "classic";
    let usedPlayers = new Set();
    let chainGuesses = [];
    let onlineState = null;
    let pollTimer = null;

    const scoreEl = document.getElementById("score-display");
    const chainLengthEl = document.getElementById("chain-length-display");
    const validCountEl = document.getElementById("valid-count-display");
    const chainBar = document.getElementById("chain-bar");
    const chainEmptyMsg = document.getElementById("chain-empty-msg");
    const promptText = document.getElementById("prompt-text");
    const chainInput = document.getElementById("chain-input");
    const searchResults = document.getElementById("chain-search-results");
    const submitBtn = document.getElementById("submit-btn");
    const feedbackEl = document.getElementById("feedback");
    const startBtn = document.getElementById("start-btn");
    const newChainBtn = document.getElementById("new-chain-btn");
    const pointsFlash = document.getElementById("points-flash");
    const guessesArea = document.getElementById("guesses-area");
    const guessesList = document.getElementById("guesses-list");
    const modeToggle = document.getElementById("mode-toggle");
    const statsBar = document.getElementById("stats-bar");

    function isOnlineMode() {
        return !!ROOM_ID;
    }

    function playerToken() {
        let value = sessionStorage.getItem(TOKEN_KEY);
        if (!value) {
            value = Math.random().toString(36).slice(2) + Date.now().toString(36);
            sessionStorage.setItem(TOKEN_KEY, value);
        }
        return value;
    }

    function currentOnlinePlayer() {
        if (!onlineState || !onlineState.players || !onlineState.players.length) return null;
        return onlineState.players[onlineState.currentPlayer];
    }

    function isMyTurn() {
        if (!isOnlineMode()) return true;
        const current = currentOnlinePlayer();
        return !!current && current.token === playerToken();
    }

    function displayedChain() {
        if (!isOnlineMode() || !onlineState) return chain;
        if (onlineState.mode === "coop") return onlineState.chain || [];
        const current = currentOnlinePlayer();
        return current ? (current.chain || []) : [];
    }

    function displayedGuesses() {
        if (!isOnlineMode() || !onlineState) return chainGuesses;
        if (onlineState.mode === "coop") return onlineState.chainGuesses || [];
        const current = currentOnlinePlayer();
        return current ? (current.chainGuesses || []) : [];
    }

    function displayedValidCount() {
        if (!isOnlineMode() || !onlineState) return validCount;
        if (onlineState.mode === "coop") return onlineState.validCount || 0;
        const current = currentOnlinePlayer();
        return current ? (current.validCount || 0) : 0;
    }

    function setScore(n) {
        score = n;
        scoreEl.textContent = score;
    }

    function setValidCount(n) {
        validCount = n;
        validCountEl.textContent = n;
    }

    function setChainLength(n) {
        chainLengthEl.textContent = n;
    }

    function clearFeedback() {
        feedbackEl.className = "hidden";
        feedbackEl.textContent = "";
    }

    function showFeedback(type, html) {
        feedbackEl.className = type;
        feedbackEl.innerHTML = html;
    }

    function lockInput() {
        inputLocked = true;
        chainInput.disabled = true;
        submitBtn.disabled = true;
        closeSearchResults();
    }

    function unlockInput() {
        inputLocked = false;
        const enabled = !isOnlineMode() || isMyTurn();
        chainInput.disabled = !enabled;
        submitBtn.disabled = !enabled;
        chainInput.value = "";
        currentGuess = "";
        if (enabled) chainInput.focus();
    }

    function closeSearchResults() {
        searchResults.innerHTML = "";
        selectedIndex = -1;
    }

    function showPointsFlash(pts) {
        pointsFlash.textContent = "+" + pts + " pt" + (pts !== 1 ? "s" : "");
        pointsFlash.classList.remove("hidden");
        void pointsFlash.offsetWidth;
        pointsFlash.classList.add("show");
        setTimeout(function () {
            pointsFlash.classList.remove("show");
            setTimeout(function () {
                pointsFlash.classList.add("hidden");
            }, 260);
        }, 900);
    }

    function renderOnlineBoard() {
        let board = statsBar.querySelector(".mp-chain-board");
        if (!isOnlineMode() || !onlineState || !onlineState.players) {
            if (board) board.remove();
            return;
        }
        if (!board) {
            board = document.createElement("div");
            board.className = "mp-chain-board";
            board.style.display = "flex";
            board.style.flexWrap = "wrap";
            board.style.gap = "10px";
            board.style.marginLeft = "12px";
            statsBar.appendChild(board);
        }
        board.innerHTML = onlineState.players.map(function (player, idx) {
            const active = idx === onlineState.currentPlayer;
            const lives = onlineState.mode === "comp"
                ? `<div style="font-size:0.8rem;color:var(--text-dim);">Lives: ${player.lives_left}</div>`
                : "";
            return `<div style="padding:8px 12px;border:2px solid ${active ? 'var(--yellow)' : 'var(--border-dim)'};background:${active ? 'rgba(245,199,0,0.08)' : 'var(--surface-2)'};min-width:120px;">
                <div style="font-family:'Bebas Neue',Impact,sans-serif;letter-spacing:2px;">${escapeHtml(player.name)}</div>
                <div style="font-family:'Barlow Condensed',sans-serif;">Score: ${player.score}</div>
                ${lives}
            </div>`;
        }).join("");
    }

    function renderGuesses() {
        guessesList.innerHTML = "";
        const guesses = displayedGuesses();
        if (guesses.length === 0) {
            guessesArea.classList.add("hidden");
            return;
        }
        guessesArea.classList.remove("hidden");
        guesses.forEach(function (g, i) {
            const row = document.createElement("div");
            row.className = "guess-row";
            row.innerHTML =
                "<span class=\"guess-num\">" + (i + 1) + ".</span>" +
                "<span class=\"guess-name\">" + escapeHtml(g.player) + (g.by ? " <small>(" + escapeHtml(g.by) + ")</small>" : "") + "</span>" +
                "<span class=\"guess-pts\">+" + g.pts + " pt" + (g.pts !== 1 ? "s" : "") + "</span>";
            guessesList.appendChild(row);
        });
    }

    function resetGuesses() {
        chainGuesses = [];
        renderGuesses();
    }

    function renderChain() {
        const activeChain = displayedChain();
        chainBar.innerHTML = "";
        if (activeChain.length === 0) {
            chainBar.appendChild(chainEmptyMsg);
            chainEmptyMsg.style.display = "";
            setChainLength(0);
            return;
        }

        chainEmptyMsg.style.display = "none";
        setChainLength(activeChain.length);

        activeChain.forEach(function (link, i) {
            if (i > 0) {
                const arrow = document.createElement("span");
                arrow.className = "chain-arrow";
                arrow.textContent = "→";
                chainBar.appendChild(arrow);
            }
            const pill = document.createElement("div");
            pill.className = "chain-link" + (i === activeChain.length - 1 ? " active" : "");
            const num = document.createElement("span");
            num.className = "link-num";
            num.textContent = (i + 1) + ".";
            pill.appendChild(num);
            pill.appendChild(document.createTextNode(link.label));
            chainBar.appendChild(pill);
        });
        chainBar.scrollLeft = chainBar.scrollWidth;
    }

    function updatePrompt() {
        if (isOnlineMode() && onlineState) {
            if (onlineState.done) {
                const winner = onlineState.winner;
                promptText.innerHTML = winner.winner_names.length === 1
                    ? `<strong>${escapeHtml(winner.winner_names[0])}</strong> wins the match!`
                    : `Tie game: <strong>${winner.winner_names.map(escapeHtml).join(" & ")}</strong>`;
                return;
            }
            const current = currentOnlinePlayer();
            if (onlineState.mode === "coop") {
                promptText.innerHTML = `Co-op: <strong>${escapeHtml(current.name)}</strong>'s turn. Team lives left: <strong>${onlineState.lives_left}</strong>`;
            } else {
                promptText.innerHTML = `Comp: <strong>${escapeHtml(current.name)}</strong>'s chain. Lives left: <strong>${current.lives_left}</strong>`;
            }
            return;
        }

        if (chain.length === 0) {
            promptText.textContent = "Press Start to begin.";
            return;
        }
        const active = chain[chain.length - 1];
        if (chain.length === 1) promptText.innerHTML = "Name a player who <strong>" + escapeHtml(active.label) + "</strong>";
        else promptText.innerHTML = "Fits all " + chain.length + " links — latest: <strong>" + escapeHtml(active.label) + "</strong>";
    }

    window.setMode = function (mode) {
        gameMode = mode;
        document.getElementById("mode-classic").classList.toggle("active", mode === "classic");
        document.getElementById("mode-infinite").classList.toggle("active", mode === "infinite");
    };

    function hydrateOnlineState(state) {
        onlineState = state;
        usedPlayers = new Set(state.usedPlayers || []);
        setValidCount(displayedValidCount());
        if (state.mode === "coop") setScore(state.players.reduce(function (sum, p) { return sum + (p.score || 0); }, 0));
        else setScore(currentOnlinePlayer() ? currentOnlinePlayer().score : 0);
        renderOnlineBoard();
        renderChain();
        renderGuesses();
        updatePrompt();

        if (state.feedback) {
            let html = escapeHtml(state.feedback.message || "");
            if (state.feedback.link_results && state.feedback.link_results.length) {
                html += "<ul class=\"link-breakdown\">" + state.feedback.link_results.map(function (r) {
                    return "<li class=\"" + (r.passed ? "link-pass" : "link-fail") + "\">" + (r.passed ? "&#x2713;" : "&#x2717;") + " " + escapeHtml(r.label) + "</li>";
                }).join("") + "</ul>";
            }
            if (state.feedback.examples && state.feedback.examples.length) {
                html += "<div class=\"examples\">Valid answers included: <strong>" + state.feedback.examples.map(escapeHtml).join(", ") + "</strong></div>";
            }
            showFeedback(state.feedback.type || "wrong", html);
        } else {
            clearFeedback();
        }

        if (state.done) {
            lockInput();
            return;
        }
        if (isMyTurn()) unlockInput(); else lockInput();
    }

    function clearAdvanceTimer() {
        if (advanceTimer) {
            clearTimeout(advanceTimer);
            advanceTimer = null;
        }
    }

    window.startGame = function () {
        if (isOnlineMode()) return;
        clearAdvanceTimer();
        clearFeedback();
        chain = [];
        usedPlayers = new Set();
        chainGuesses = [];
        setScore(0);
        setValidCount(0);
        setChainLength(0);
        renderChain();
        resetGuesses();
        startBtn.classList.add("hidden");
        newChainBtn.classList.add("hidden");
        lockInput();
        promptText.innerHTML = "Loading…";

        fetch(API_PREFIX + "/start", { method: "POST" })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) {
                    promptText.innerHTML = "Error: " + escapeHtml(data.error);
                    startBtn.classList.remove("hidden");
                    return;
                }
                chain = [data.category];
                setValidCount(data.valid_count);
                renderChain();
                updatePrompt();
                unlockInput();
                gameActive = true;
            })
            .catch(function () {
                promptText.innerHTML = "Network error. Please try again.";
                startBtn.classList.remove("hidden");
            });
    };

    window.startNewChain = function () {
        if (isOnlineMode()) return;
        clearAdvanceTimer();
        clearFeedback();
        newChainBtn.classList.add("hidden");
        chain = [];
        usedPlayers = new Set();
        chainGuesses = [];
        renderChain();
        resetGuesses();
        lockInput();
        promptText.innerHTML = "Loading next chain…";
        fetch(API_PREFIX + "/start", { method: "POST" })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) {
                    promptText.innerHTML = "Error: " + escapeHtml(data.error);
                    newChainBtn.classList.remove("hidden");
                    return;
                }
                chain = [data.category];
                setValidCount(data.valid_count);
                renderChain();
                updatePrompt();
                unlockInput();
                gameActive = true;
            })
            .catch(function () {
                promptText.innerHTML = "Network error. Please try again.";
                newChainBtn.classList.remove("hidden");
            });
    };

    function startTeammateChain(playerName) {
        if (isOnlineMode()) return;
        clearAdvanceTimer();
        clearFeedback();
        newChainBtn.classList.add("hidden");
        chain = [];
        chainGuesses = [];
        renderChain();
        resetGuesses();
        lockInput();
        promptText.innerHTML = "Finding teammates of <strong>" + escapeHtml(playerName) + "</strong>…";

        fetch(API_PREFIX + "/teammate_start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ player: playerName }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) {
                    promptText.innerHTML = "No teammates found for " + escapeHtml(playerName) + ". Starting fresh…";
                    setTimeout(window.startNewChain, 1500);
                    return;
                }
                chain = [data.category];
                setValidCount(data.valid_count);
                renderChain();
                updatePrompt();
                unlockInput();
                gameActive = true;
            })
            .catch(function () {
                promptText.innerHTML = "Network error. Please try again.";
                newChainBtn.classList.remove("hidden");
            });
    }

    window.submitCurrentGuess = function () {
        const guess = currentGuess || chainInput.value.trim();
        if (!guess || inputLocked || (!gameActive && !isOnlineMode())) return;
        doGuess(guess);
    };

    function handleSoloGuessResult(playerName, data) {
        if (data.correct) {
            if (window.SFX) SFX.play('correct');
            usedPlayers.add(playerName);
            const pts = data.chain_length;
            setScore(score + pts);
            showPointsFlash(pts);
            chainGuesses.push({ player: playerName, pts: pts });
            renderGuesses();

            if (data.last_player) {
                const BONUS = 10;
                setScore(score + BONUS);
                showFeedback("correct", "&#x2713; Correct! +" + pts + " pts — BONUS — Last player standing! +" + BONUS + " pts! Next chain: teammates of <strong>" + escapeHtml(data.last_player) + "</strong>");
                setValidCount(1);
                gameActive = false;
                advanceTimer = setTimeout(function () { startTeammateChain(data.last_player); }, 3000);
                newChainBtn.textContent = "Continue with " + escapeHtml(data.last_player) + "'s teammates →";
                newChainBtn.onclick = function () { startTeammateChain(data.last_player); };
                newChainBtn.classList.remove("hidden");
            } else if (!data.next_category) {
                showFeedback("correct", "&#x2713; Correct! +" + pts + " point" + (pts !== 1 ? "s" : "") + " — Chain complete! No more valid categories.");
                setValidCount(data.valid_count);
                gameActive = false;
                newChainBtn.textContent = "Start New Chain";
                newChainBtn.onclick = window.startNewChain;
                newChainBtn.classList.remove("hidden");
            } else {
                showFeedback("correct", "&#x2713; Correct! +" + pts + " point" + (pts !== 1 ? "s" : "") + " — chain grows!");
                chain.push(data.next_category);
                setValidCount(data.next_category.valid_count);
                renderChain();
                updatePrompt();
                setTimeout(function () { clearFeedback(); unlockInput(); }, 1200);
            }
        } else {
            let html = "&#x2717; <strong>" + escapeHtml(playerName) + "</strong> doesn't fit the full chain:";
            if (data.link_results && data.link_results.length > 0) {
                html += "<ul class=\"link-breakdown\">";
                data.link_results.forEach(function (r) {
                    html += "<li class=\"" + (r.passed ? "link-pass" : "link-fail") + "\">" + (r.passed ? "&#x2713;" : "&#x2717;") + " " + escapeHtml(r.label) + "</li>";
                });
                html += "</ul>";
            }
            if (data.examples && data.examples.length > 0) html += "<div class=\"examples\">Valid answers included: <strong>" + data.examples.map(escapeHtml).join(", ") + "</strong></div>";
            if (window.SFX) SFX.play('wrong');
            showFeedback("wrong", html);
            gameActive = false;
            if (gameMode === "infinite") {
                newChainBtn.textContent = "Continue with " + escapeHtml(playerName) + "'s teammates →";
                newChainBtn.classList.remove("hidden");
                newChainBtn.onclick = function () { startTeammateChain(playerName); };
                advanceTimer = setTimeout(function () { startTeammateChain(playerName); }, 4000);
            } else {
                newChainBtn.textContent = "Start New Chain";
                newChainBtn.onclick = window.startNewChain;
                newChainBtn.classList.remove("hidden");
                advanceTimer = setTimeout(function () { startNewChain(); }, 3000);
            }
        }
    }

    function doGuess(playerName) {
        if (inputLocked || displayedChain().length === 0) return;
        if (usedPlayers.has(playerName)) {
            showFeedback("wrong", "&#x2717; <strong>" + escapeHtml(playerName) + "</strong> has already been used this game!");
            chainInput.value = "";
            currentGuess = "";
            closeSearchResults();
            setTimeout(clearFeedback, 2000);
            return;
        }

        closeSearchResults();
        lockInput();

        if (isOnlineMode()) {
            fetch(API_PREFIX + "/guess", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ game_id: onlineState.game_id, player: playerName, token: playerToken() }),
            })
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (!data.ok) {
                        showFeedback("wrong", escapeHtml(data.error || "Could not submit answer"));
                        if (isMyTurn()) unlockInput();
                        return;
                    }
                    if (window.SFX) SFX.play(data.state.feedback && data.state.feedback.type === "correct" ? "correct" : "wrong");
                    hydrateOnlineState(data.state);
                    if (data.state.feedback && data.state.feedback.type === "correct") showPointsFlash(displayedChain().length ? displayedChain().length - 1 || 1 : 1);
                })
                .catch(function () {
                    showFeedback("wrong", "Network error. Please try again.");
                    if (isMyTurn()) unlockInput();
                });
            return;
        }

        const payload = {
            player: playerName,
            chain: chain.map(function (c) { return { id: c.id, value: c.value }; }),
            used_players: Array.from(usedPlayers),
        };
        fetch(API_PREFIX + "/guess", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) { handleSoloGuessResult(playerName, data); })
            .catch(function () {
                showFeedback("wrong", "Network error. Please try again.");
                unlockInput();
            });
    }

    chainInput.addEventListener("input", function () {
        if (isOnlineMode() && !isMyTurn()) {
            chainInput.value = "";
            return;
        }
        currentGuess = "";
        const term = chainInput.value.trim();
        if (!term) { closeSearchResults(); return; }
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(function () { fetchSearch(term); }, 200);
    });

    function fetchSearch(term) {
        fetch(API_PREFIX + "/search?q=" + encodeURIComponent(term) + (isOnlineMode() ? "&game_id=" + encodeURIComponent(onlineState.game_id) : ""))
            .then(function (r) { return r.json(); })
            .then(function (data) { renderSearchResults(data.results || []); })
            .catch(function () { closeSearchResults(); });
    }

    function renderSearchResults(results) {
        searchResults.innerHTML = "";
        selectedIndex = -1;
        if (!results.length) return;
        results.forEach(function (r) {
            const item = document.createElement("div");
            item.className = "chain-result-item";
            item.textContent = r.name;
            item.addEventListener("mousedown", function (e) { e.preventDefault(); selectPlayer(r.name); });
            searchResults.appendChild(item);
        });
    }

    function selectPlayer(name) {
        if (isOnlineMode() && !isMyTurn()) return;
        chainInput.value = name;
        currentGuess = name;
        closeSearchResults();
        doGuess(name);
    }

    chainInput.addEventListener("keydown", function (e) {
        if (isOnlineMode() && !isMyTurn()) return;
        const items = searchResults.querySelectorAll(".chain-result-item");
        if (e.key === "ArrowDown") {
            e.preventDefault();
            selectedIndex = Math.min(selectedIndex + 1, items.length - 1);
            updateHighlight(items);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            selectedIndex = Math.max(selectedIndex - 1, -1);
            updateHighlight(items);
        } else if (e.key === "Enter") {
            e.preventDefault();
            if (selectedIndex >= 0 && items[selectedIndex]) selectPlayer(items[selectedIndex].textContent);
            else {
                const val = chainInput.value.trim();
                if (val) doGuess(val);
            }
        } else if (e.key === "Escape") {
            closeSearchResults();
        }
    });

    function updateHighlight(items) {
        items.forEach(function (item, i) { item.classList.toggle("highlighted", i === selectedIndex); });
        if (selectedIndex >= 0 && items[selectedIndex]) chainInput.value = items[selectedIndex].textContent;
    }

    document.addEventListener("click", function (e) {
        if (!document.getElementById("search-wrapper").contains(e.target)) closeSearchResults();
    });

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function loadRoomState() {
        fetch("/api/lobbies/" + encodeURIComponent(ROOM_ID) + "/game-state?token=" + encodeURIComponent(playerToken()))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.room && data.room.status === "lobby") {
                    window.location.href = "/lobbies/" + encodeURIComponent(ROOM_ID);
                    return;
                }
                if (data.state) hydrateOnlineState(data.state);
            });
    }

    if (isOnlineMode()) {
        if (modeToggle) modeToggle.style.display = "none";
        startBtn.classList.add("hidden");
        newChainBtn.classList.add("hidden");
        loadRoomState();
        pollTimer = setInterval(function () {
            if (isMyTurn()) return;
            loadRoomState();
        }, 2500);
    } else {
        startBtn.classList.remove("hidden");
        renderChain();
        updatePrompt();
    }
})();
