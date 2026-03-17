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
    let flashTimer   = null;

    const MAX_WRONG = 5;

    // ── DOM refs ──────────────────────────────────────────────────────────────
    const chainSpark    = document.getElementById("chain-spark");
    const chainNodes    = document.getElementById("chain-nodes");
    const chainTail     = document.getElementById("chain-tail");
    const bombCap       = document.getElementById("bomb-cap");
    const bombBody      = document.getElementById("bomb-body");
    const bombInner     = document.getElementById("bomb-inner");
    const bombNum       = document.getElementById("bomb-num");
    const bombLabel     = document.getElementById("bomb-label");
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

    function setGlow(n) {
        bombBody.className = n > 0 ? "glow-" + n : "";
    }

    function setBombDisplay(num, label) {
        bombNum.textContent = num;
        bombLabel.textContent = label;
    }

    /** Flash wrong player name on the bomb, then revert to turn count. */
    function flashWrong(name) {
        clearTimeout(flashTimer);
        bombInner.classList.add("flash-wrong");
        setBombDisplay(name, "❌ wrong");
        flashTimer = setTimeout(function () {
            bombInner.classList.remove("flash-wrong");
            var remaining = MAX_WRONG - wrongCount;
            setBombDisplay(remaining, remaining === 1 ? "guess left" : "guesses left");
        }, 1600);
    }

    function triggerExplosion() {
        clearTimeout(flashTimer);
        bombBody.className = "exploded";
        setBombDisplay("💥", "");
        redFlash.classList.remove("flash");
        void redFlash.offsetWidth;
        redFlash.classList.add("flash");
        chainSpark.classList.add("hidden");
    }

    function triggerDefuse() {
        clearTimeout(flashTimer);
        bombBody.className = "defused";
        setBombDisplay("✓", "defused!");
        chainSpark.classList.add("hidden");
    }

    // ── Chain node rendering ──────────────────────────────────────────────────

    /**
     * Append a teammate node to the fuse chain.
     * clue = { icon, label, text }  where text = player name, label = "YYYY Teammate"
     */
    function appendNode(clue) {
        var node = document.createElement("div");
        node.className = "chain-node";

        // Wire above pill
        var wire = document.createElement("div");
        wire.className = "chain-wire";

        // Pill
        var pill = document.createElement("div");
        pill.className = "chain-pill";

        // Year label parsed from clue.label ("2021 Teammate" → "2021")
        var yearMatch = clue.label.match(/\d{4}/);
        if (yearMatch) {
            var yr = document.createElement("span");
            yr.className = "pill-year";
            yr.textContent = yearMatch[0];
            pill.appendChild(yr);
        }

        var nameEl = document.createElement("span");
        nameEl.className = "pill-name";
        nameEl.textContent = clue.text;
        pill.appendChild(nameEl);

        node.appendChild(wire);
        node.appendChild(pill);
        chainNodes.appendChild(node);
    }

    // ── Wrong chip ────────────────────────────────────────────────────────────

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
        clearTimeout(flashTimer);
        chainNodes.innerHTML = "";
        wrongGuesses.innerHTML = "";
        hideFeedback();
        gameId      = null;
        wrongCount  = 0;
        gameActive  = false;

        // Hide fuse elements until game loads
        chainSpark.classList.add("hidden");
        chainTail.classList.add("hidden");
        bombCap.classList.add("hidden");
        bombBody.className = "";
        bombInner.classList.remove("flash-wrong");
        setBombDisplay("…", "");

        startBtn.classList.add("hidden");
        giveUpBtn.classList.add("hidden");
        playAgainBtn.classList.add("hidden");
        lockInput();

        fetch("/api/ttb/start", { method: "POST" })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) {
                    showFeedback("wrong", "Error: " + escapeHtml(data.error));
                    startBtn.classList.remove("hidden");
                    return;
                }
                gameId     = data.game_id;
                gameActive = true;
                wrongCount = 0;

                // Show fuse elements
                chainSpark.classList.remove("hidden");
                chainTail.classList.remove("hidden");
                bombCap.classList.remove("hidden");

                // Reveal first node
                data.clues.forEach(appendNode);

                setGlow(MAX_WRONG);
                setBombDisplay(MAX_WRONG, "guesses left");
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
                "&#x2713; <strong>" + escapeHtml(data.player) + "</strong> — Bomb defused!");
            playAgainBtn.classList.remove("hidden");
            return;
        }

        // Wrong guess
        wrongCount++;
        addWrongChip(playerName);
        flashWrong(playerName);

        if (data.exploded) {
            gameActive = false;
            setTimeout(function () {
                triggerExplosion();
                giveUpBtn.classList.add("hidden");
                setTimeout(function () {
                    showFeedback("reveal",
                        "&#x1F4A5; BOOM! The answer was <strong>" +
                        escapeHtml(data.player) + "</strong>.");
                    playAgainBtn.classList.remove("hidden");
                }, 900);
            }, 1700);   // let the wrong-name flash finish first
            return;
        }

        // Still alive — update glow and reveal next node
        var remaining = MAX_WRONG - wrongCount;
        setGlow(remaining);

        if (data.new_clue) {
            setTimeout(function () { appendNode(data.new_clue); }, 1700);
        }

        setTimeout(function () {
            hideFeedback();
            unlockInput();
        }, 1700);
    }

    window.ttbGiveUp = function () {
        if (!gameId || !gameActive) return;
        gameActive = false;
        clearTimeout(flashTimer);
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
                setTimeout(function () {
                    showFeedback("reveal",
                        "&#x1F3F3;&#xFE0F; You gave up. The answer was <strong>" +
                        escapeHtml(data.player || "???") + "</strong>.");
                    playAgainBtn.classList.remove("hidden");
                }, 900);
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
    setBombDisplay("?", "press start");
    startBtn.classList.remove("hidden");
})();
