/* ── Ticking Time Bomb JS ──────────────────────────────────────────────────── */

(function () {
    "use strict";

    // ── State ─────────────────────────────────────────────────────────────────
    let gameId       = null;
    let wrongCount   = 0;
    let gameActive   = false;
    let inputLocked  = false;
    let currentGuess = "";
    let selectedIdx  = -1;
    let searchDebounce = null;

    const MAX_WRONG = 5;

    // ── DOM refs ──────────────────────────────────────────────────────────────
    const bombWrapper   = document.getElementById("bomb-wrapper");
    const fuseContainer = document.getElementById("fuse-container");
    const turnsDisplay  = document.getElementById("turns-remaining");
    const cluesPanel    = document.getElementById("clues-panel");
    const wrongGuesses  = document.getElementById("wrong-guesses");
    const feedbackEl    = document.getElementById("ttb-feedback");
    const ttbInput      = document.getElementById("ttb-input");
    const searchResults = document.getElementById("ttb-search-results");
    const submitBtn     = document.getElementById("ttb-submit-btn");
    const startBtn      = document.getElementById("ttb-start-btn");
    const giveUpBtn     = document.getElementById("ttb-give-up-btn");
    const playAgainBtn  = document.getElementById("ttb-play-again-btn");
    const redFlash      = document.getElementById("red-flash");

    // ── Bomb helpers ──────────────────────────────────────────────────────────

    function setBombState(state) {
        // state: "idle" | "5".."1" | "exploded" | "defused"
        bombWrapper.className = "state-" + state;
    }

    function buildFuse() {
        fuseContainer.innerHTML = "";
        for (var i = 0; i < MAX_WRONG; i++) {
            var seg = document.createElement("div");
            seg.className = "fuse-seg";
            seg.id = "fseg-" + i;
            fuseContainer.appendChild(seg);
        }
    }

    function updateFuse() {
        for (var i = 0; i < MAX_WRONG; i++) {
            var seg = document.getElementById("fseg-" + i);
            if (!seg) continue;
            seg.className = "fuse-seg";
            if (i < wrongCount) {
                seg.classList.add("burnt");
            } else if (i === wrongCount && gameActive) {
                seg.classList.add("burning");
            }
        }
    }

    function syncBomb() {
        var remaining = MAX_WRONG - wrongCount;
        turnsDisplay.textContent = remaining;
        setBombState(String(remaining));
        updateFuse();
    }

    function triggerExplosion() {
        turnsDisplay.textContent = "💥";
        setBombState("exploded");
        // Burn all fuse segments
        for (var i = 0; i < MAX_WRONG; i++) {
            var seg = document.getElementById("fseg-" + i);
            if (seg) { seg.className = "fuse-seg burnt"; }
        }
        // Full-screen red flash
        redFlash.classList.remove("flash");
        void redFlash.offsetWidth;
        redFlash.classList.add("flash");
    }

    function triggerDefuse() {
        turnsDisplay.textContent = "✓";
        setBombState("defused");
        for (var i = 0; i < MAX_WRONG; i++) {
            var seg = document.getElementById("fseg-" + i);
            if (seg) { seg.className = "fuse-seg burnt"; }
        }
    }

    // ── Clue / chip rendering ─────────────────────────────────────────────────

    function appendClue(clue) {
        var card = document.createElement("div");
        card.className = "clue-card";
        card.innerHTML =
            '<div class="clue-icon">' + clue.icon + '</div>' +
            '<div class="clue-body">' +
            '<div class="clue-label">' + escapeHtml(clue.label) + '</div>' +
            '<div class="clue-text">' + escapeHtml(clue.text) + '</div>' +
            '</div>';
        cluesPanel.appendChild(card);
    }

    function addWrongChip(name) {
        var chip = document.createElement("span");
        chip.className = "wrong-chip";
        chip.textContent = name;
        wrongGuesses.appendChild(chip);
    }

    // ── Feedback ──────────────────────────────────────────────────────────────

    function showFeedback(type, html) {
        feedbackEl.className = type;
        feedbackEl.innerHTML = html;
    }

    function hideFeedback() {
        feedbackEl.className = "";
        feedbackEl.style.display = "none";
    }

    // ── Input helpers ─────────────────────────────────────────────────────────

    function lockInput() {
        inputLocked = true;
        ttbInput.disabled = true;
        submitBtn.disabled = true;
        closeSearch();
    }

    function unlockInput() {
        inputLocked = false;
        ttbInput.disabled = false;
        submitBtn.disabled = false;
        ttbInput.value = "";
        currentGuess = "";
        ttbInput.focus();
    }

    // ── Game flow ─────────────────────────────────────────────────────────────

    window.ttbStart = function () {
        // Reset
        cluesPanel.innerHTML = "";
        wrongGuesses.innerHTML = "";
        hideFeedback();
        gameId = null;
        wrongCount = 0;
        gameActive = false;

        startBtn.classList.add("hidden");
        giveUpBtn.classList.add("hidden");
        playAgainBtn.classList.add("hidden");
        lockInput();

        buildFuse();
        turnsDisplay.textContent = "?";
        setBombState("idle");

        fetch("/api/ttb/start", { method: "POST" })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) {
                    showFeedback("wrong", "Error: " + escapeHtml(data.error));
                    startBtn.classList.remove("hidden");
                    return;
                }
                gameId = data.game_id;
                data.clues.forEach(appendClue);
                gameActive = true;
                syncBomb();
                unlockInput();
                giveUpBtn.classList.remove("hidden");
            })
            .catch(function () {
                showFeedback("wrong", "Network error. Please try again.");
                startBtn.classList.remove("hidden");
            });
    };

    window.ttbSubmit = function () {
        var guess = currentGuess || ttbInput.value.trim();
        if (!guess || inputLocked || !gameActive) return;
        doGuess(guess);
    };

    function doGuess(playerName) {
        if (inputLocked || !gameActive || !gameId) return;
        closeSearch();
        lockInput();

        fetch("/api/ttb/guess", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ game_id: gameId, guess: playerName }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) { handleGuessResult(playerName, data); })
            .catch(function () {
                showFeedback("wrong", "Network error. Please try again.");
                unlockInput();
            });
    }

    function handleGuessResult(playerName, data) {
        if (data.error) {
            showFeedback("wrong", escapeHtml(data.error));
            unlockInput();
            return;
        }

        if (data.correct) {
            gameActive = false;
            triggerDefuse();
            giveUpBtn.classList.add("hidden");
            showFeedback("correct",
                "&#x2713; <strong>" + escapeHtml(data.player) +
                "</strong> — Bomb defused! Well done!");
            playAgainBtn.classList.remove("hidden");
            return;
        }

        // Wrong
        wrongCount++;
        addWrongChip(playerName);

        if (data.exploded) {
            gameActive = false;
            triggerExplosion();
            giveUpBtn.classList.add("hidden");
            setTimeout(function () {
                showFeedback("reveal",
                    "&#x1F4A5; BOOM! The answer was <strong>" +
                    escapeHtml(data.player) + "</strong>.");
                playAgainBtn.classList.remove("hidden");
            }, 800);
            return;
        }

        // Still alive — reveal next clue
        syncBomb();
        if (data.new_clue) { appendClue(data.new_clue); }

        showFeedback("wrong",
            "&#x2717; Not <strong>" + escapeHtml(playerName) +
            "</strong> — a new clue has been revealed!");
        setTimeout(function () {
            hideFeedback();
            unlockInput();
        }, 1400);
    }

    window.ttbGiveUp = function () {
        if (!gameId || !gameActive) return;
        gameActive = false;
        lockInput();
        giveUpBtn.classList.add("hidden");

        fetch("/api/ttb/guess", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ game_id: gameId, guess: "", reveal: true }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                triggerExplosion();
                var answer = data.player || "???";
                setTimeout(function () {
                    showFeedback("reveal",
                        "&#x1F3F3;&#xFE0F; You gave up. The answer was <strong>" +
                        escapeHtml(answer) + "</strong>.");
                    playAgainBtn.classList.remove("hidden");
                }, 800);
            })
            .catch(function () {
                showFeedback("wrong", "Network error.");
                playAgainBtn.classList.remove("hidden");
            });
    };

    // ── Search autocomplete ────────────────────────────────────────────────────

    ttbInput.addEventListener("input", function () {
        currentGuess = "";
        var term = ttbInput.value.trim();
        if (!term) { closeSearch(); return; }
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(function () { fetchSearch(term); }, 200);
    });

    function fetchSearch(term) {
        fetch("/api/ttb/search?q=" + encodeURIComponent(term))
            .then(function (r) { return r.json(); })
            .then(function (data) { renderSearch(data.results || []); })
            .catch(function () { closeSearch(); });
    }

    function renderSearch(results) {
        searchResults.innerHTML = "";
        selectedIdx = -1;
        if (!results.length) return;
        results.forEach(function (r) {
            var item = document.createElement("div");
            item.className = "ttb-result-item";
            item.textContent = r.name;
            item.addEventListener("mousedown", function (e) {
                e.preventDefault();
                selectPlayer(r.name);
            });
            searchResults.appendChild(item);
        });
    }

    function selectPlayer(name) {
        ttbInput.value = name;
        currentGuess = name;
        closeSearch();
        doGuess(name);
    }

    function closeSearch() {
        searchResults.innerHTML = "";
        selectedIdx = -1;
    }

    ttbInput.addEventListener("keydown", function (e) {
        var items = searchResults.querySelectorAll(".ttb-result-item");
        if (e.key === "ArrowDown") {
            e.preventDefault();
            selectedIdx = Math.min(selectedIdx + 1, items.length - 1);
            updateHighlight(items);
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            selectedIdx = Math.max(selectedIdx - 1, -1);
            updateHighlight(items);
        } else if (e.key === "Enter") {
            e.preventDefault();
            if (selectedIdx >= 0 && items[selectedIdx]) {
                selectPlayer(items[selectedIdx].textContent);
            } else {
                var val = ttbInput.value.trim();
                if (val) doGuess(val);
            }
        } else if (e.key === "Escape") {
            closeSearch();
        }
    });

    function updateHighlight(items) {
        items.forEach(function (item, i) {
            item.classList.toggle("highlighted", i === selectedIdx);
        });
        if (selectedIdx >= 0 && items[selectedIdx]) {
            ttbInput.value = items[selectedIdx].textContent;
        }
    }

    document.addEventListener("click", function (e) {
        if (!document.getElementById("ttb-search-wrapper").contains(e.target)) {
            closeSearch();
        }
    });

    // ── Utility ───────────────────────────────────────────────────────────────

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;").replace(/</g, "&lt;")
            .replace(/>/g, "&gt;").replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    // ── Init ──────────────────────────────────────────────────────────────────
    buildFuse();
    setBombState("idle");
    startBtn.classList.remove("hidden");
})();
