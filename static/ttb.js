/* ── Ticking Time Bomb JS ──────────────────────────────────────────────────── */

(function () {
    "use strict";

    // ── State ─────────────────────────────────────────────────────────────────
    let gameId         = null;
    let wrongCount     = 0;
    let gameActive     = false;
    let inputLocked    = false;
    let currentGuess   = "";
    let selectedIdx    = -1;
    let searchDebounce = null;
    let flashTimer     = null;
    let allHints       = [];      // all 5 bio hints (received at start)
    let hintsRevealed  = 1;       // how many hints are currently unlocked
    let hintsOpen      = false;   // toggle state

    const MAX_WRONG = 5;

    // ── DOM refs ──────────────────────────────────────────────────────────────
    const chainSpark     = document.getElementById("chain-spark");
    const chainNodes     = document.getElementById("chain-nodes");
    const chainTail      = document.getElementById("chain-tail");
    const bombCap        = document.getElementById("bomb-cap");
    const bombBody       = document.getElementById("bomb-body");
    const bombInner      = document.getElementById("bomb-inner");
    const bombNum        = document.getElementById("bomb-num");
    const bombLabel      = document.getElementById("bomb-label");
    const answerReveal   = document.getElementById("answer-reveal");
    const answerName     = document.getElementById("answer-name");
    const wrongGuesses   = document.getElementById("wrong-guesses");
    const hintSection    = document.getElementById("hints-section");
    const hintToggleBtn  = document.getElementById("hints-toggle-btn");
    const hintsPanel     = document.getElementById("hints-panel");
    const feedbackEl     = document.getElementById("ttb-feedback");
    const ttbInput       = document.getElementById("ttb-input");
    const searchResults  = document.getElementById("ttb-search-results");
    const submitBtn      = document.getElementById("ttb-submit-btn");
    const startBtn       = document.getElementById("ttb-start-btn");
    const skipBtn        = document.getElementById("ttb-skip-btn");
    const giveUpBtn      = document.getElementById("ttb-give-up-btn");
    const playAgainBtn   = document.getElementById("ttb-play-again-btn");
    const redFlash       = document.getElementById("red-flash");

    // ── Bomb helpers ──────────────────────────────────────────────────────────

    function setGlow(n) {
        bombBody.className = n > 0 ? "glow-" + n : "";
    }

    function setBombDisplay(num, lbl) {
        bombNum.textContent   = num;
        bombLabel.textContent = lbl;
    }

    function flashWrong(name) {
        clearTimeout(flashTimer);
        bombInner.classList.add("flash-wrong");
        setBombDisplay(name, "✗ wrong");
        flashTimer = setTimeout(function () {
            bombInner.classList.remove("flash-wrong");
            var rem = MAX_WRONG - wrongCount;
            setBombDisplay(rem, rem === 1 ? "guess left" : "guesses left");
        }, 1600);
    }

    function flashSkip() {
        clearTimeout(flashTimer);
        bombInner.classList.add("flash-skip");
        setBombDisplay("⏭", "skipped");
        flashTimer = setTimeout(function () {
            bombInner.classList.remove("flash-skip");
            var rem = MAX_WRONG - wrongCount;
            setBombDisplay(rem, rem === 1 ? "guess left" : "guesses left");
        }, 1200);
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

    function appendNode(clue) {
        var node = document.createElement("div");
        node.className = "chain-node";

        var wire = document.createElement("div");
        wire.className = "chain-wire";

        var pill = document.createElement("div");
        pill.className = "chain-pill";

        var nameEl = document.createElement("span");
        nameEl.className = "pill-name";
        nameEl.textContent = clue.text;
        pill.appendChild(nameEl);

        node.appendChild(wire);
        node.appendChild(pill);
        chainNodes.appendChild(node);
    }

    // ── Hints panel ───────────────────────────────────────────────────────────

    function renderHintsPanel() {
        hintsPanel.innerHTML = "";
        var visible = allHints.slice(0, hintsRevealed);
        visible.forEach(function (h) {
            var row = document.createElement("div");
            row.className = "hint-row";
            row.innerHTML =
                '<span class="hint-icon">' + h.icon + '</span>' +
                '<div class="hint-body">' +
                '<span class="hint-label">' + escapeHtml(h.label) + '</span>' +
                '<span class="hint-text">'  + escapeHtml(h.text)  + '</span>' +
                '</div>';
            hintsPanel.appendChild(row);
        });

        // Badge on toggle button
        hintToggleBtn.querySelector(".hint-badge").textContent = hintsRevealed + "/" + allHints.length;
    }

    window.toggleHints = function () {
        hintsOpen = !hintsOpen;
        if (hintsOpen) {
            hintsPanel.classList.remove("hidden");
            hintToggleBtn.innerHTML =
                '&#x1F4A1; Hide Hints <span class="hint-badge">' + hintsRevealed + "/" + allHints.length + '</span>';
        } else {
            hintsPanel.classList.add("hidden");
            hintToggleBtn.innerHTML =
                '&#x1F4A1; Show Hints <span class="hint-badge">' + hintsRevealed + "/" + allHints.length + '</span>';
        }
    };

    function unlockNextHint() {
        if (hintsRevealed < allHints.length) {
            hintsRevealed++;
            renderHintsPanel();
            // Update button text to reflect new count without closing
            if (hintsOpen) {
                hintToggleBtn.innerHTML =
                    '&#x1F4A1; Hide Hints <span class="hint-badge">' + hintsRevealed + "/" + allHints.length + '</span>';
            } else {
                hintToggleBtn.innerHTML =
                    '&#x1F4A1; Show Hints <span class="hint-badge">' + hintsRevealed + "/" + allHints.length + '</span>';
            }
        }
    }

    // ── Answer reveal ─────────────────────────────────────────────────────────

    function showAnswerReveal(name) {
        answerName.textContent = name;
        answerReveal.classList.remove("hidden");
        // Also show all hints
        if (allHints.length > 0) {
            hintsRevealed = allHints.length;
            renderHintsPanel();
            if (!hintsOpen) {
                hintsPanel.classList.remove("hidden");
                hintsOpen = true;
                hintToggleBtn.innerHTML =
                    '&#x1F4A1; Hide Hints <span class="hint-badge">' + hintsRevealed + "/" + allHints.length + '</span>';
            }
        }
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
        skipBtn.disabled = true;
        closeSearch();
    }

    function unlockInput() {
        inputLocked = false;
        ttbInput.disabled = false;
        submitBtn.disabled = false;
        skipBtn.disabled = false;
        ttbInput.value = "";
        currentGuess = "";
        ttbInput.focus();
    }

    // ── Game flow ─────────────────────────────────────────────────────────────

    window.ttbStart = function () {
        clearTimeout(flashTimer);
        chainNodes.innerHTML  = "";
        wrongGuesses.innerHTML = "";
        hintsPanel.innerHTML  = "";
        answerReveal.classList.add("hidden");
        hideFeedback();

        gameId        = null;
        wrongCount    = 0;
        gameActive    = false;
        allHints      = [];
        hintsRevealed = 1;
        hintsOpen     = false;

        chainSpark.classList.add("hidden");
        chainTail.classList.add("hidden");
        bombCap.classList.add("hidden");
        bombBody.className = "";
        bombInner.classList.remove("flash-wrong", "flash-skip");
        setBombDisplay("…", "");

        hintsPanel.classList.add("hidden");
        hintToggleBtn.classList.add("hidden");

        startBtn.classList.add("hidden");
        skipBtn.classList.add("hidden");
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
                allHints   = data.hints || [];

                chainSpark.classList.remove("hidden");
                chainTail.classList.remove("hidden");
                bombCap.classList.remove("hidden");

                data.clues.forEach(appendNode);

                setGlow(MAX_WRONG);
                setBombDisplay(MAX_WRONG, "guesses left");

                // Set up hints toggle button
                if (allHints.length > 0) {
                    hintsRevealed = 1;
                    renderHintsPanel();
                    hintToggleBtn.innerHTML =
                        '&#x1F4A1; Show Hints <span class="hint-badge">1/' + allHints.length + '</span>';
                    hintToggleBtn.classList.remove("hidden");
                }

                unlockInput();
                skipBtn.classList.remove("hidden");
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
        doGuess(guess, false);
    };

    window.ttbSkip = function () {
        if (inputLocked || !gameActive) return;
        doGuess("", true);
    };

    function doGuess(playerName, skip) {
        if (inputLocked || !gameActive || !gameId) return;
        closeSearch();
        lockInput();

        fetch("/api/ttb/guess", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ game_id: gameId, guess: playerName, skip: skip }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) { handleGuessResult(playerName, data, skip); })
            .catch(function () {
                showFeedback("wrong", "Network error. Please try again.");
                unlockInput();
            });
    }

    function handleGuessResult(playerName, data, wasSkip) {
        if (data.error) {
            showFeedback("wrong", escapeHtml(data.error));
            unlockInput();
            return;
        }

        if (data.correct) {
            gameActive = false;
            triggerDefuse();
            skipBtn.classList.add("hidden");
            giveUpBtn.classList.add("hidden");
            showFeedback("correct",
                "&#x2713; <strong>" + escapeHtml(data.player) + "</strong> — Bomb defused!");
            playAgainBtn.classList.remove("hidden");
            return;
        }

        // Wrong or skip
        wrongCount++;
        unlockNextHint();

        if (wasSkip) {
            flashSkip();
        } else {
            addWrongChip(playerName);
            flashWrong(playerName);
        }

        var delay = wasSkip ? 1300 : 1700;

        if (data.exploded) {
            gameActive = false;
            setTimeout(function () {
                triggerExplosion();
                skipBtn.classList.add("hidden");
                giveUpBtn.classList.add("hidden");
                setTimeout(function () {
                    showAnswerReveal(data.player);
                    playAgainBtn.classList.remove("hidden");
                }, 900);
            }, delay);
            return;
        }

        // Still alive — update glow and reveal next node
        var remaining = MAX_WRONG - wrongCount;
        setGlow(remaining);

        if (data.new_clue) {
            setTimeout(function () { appendNode(data.new_clue); }, delay);
        }
        setTimeout(function () {
            hideFeedback();
            unlockInput();
        }, delay);
    }

    window.ttbGiveUp = function () {
        if (!gameId || !gameActive) return;
        gameActive = false;
        clearTimeout(flashTimer);
        lockInput();
        skipBtn.classList.add("hidden");
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
                    showAnswerReveal(data.player || "???");
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
        doGuess(name, false);
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
                if (val) doGuess(val, false);
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
