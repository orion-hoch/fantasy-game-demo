/* ── NBA Ticking Time Bomb JS ───────────────────────────────────────────────── */

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
    let gameMode       = "classic";

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
        setBombDisplay(name, "WRONG");
        flashTimer = setTimeout(function () {
            bombInner.classList.remove("flash-wrong");
            var rem = MAX_WRONG - wrongCount;
            setBombDisplay(rem, rem === 1 ? "guess left" : "guesses left");
        }, 1600);
    }

    function flashSkip() {
        clearTimeout(flashTimer);
        bombInner.classList.add("flash-skip");
        setBombDisplay("SKIP", "");
        flashTimer = setTimeout(function () {
            bombInner.classList.remove("flash-skip");
            var rem = MAX_WRONG - wrongCount;
            setBombDisplay(rem, rem === 1 ? "guess left" : "guesses left");
        }, 1200);
    }

    function triggerExplosion() {
        clearTimeout(flashTimer);
        bombBody.className = "exploded";
        setBombDisplay("BOOM", "");
        redFlash.classList.remove("flash");
        void redFlash.offsetWidth;
        redFlash.classList.add("flash");
        chainSpark.classList.add("hidden");
    }

    function triggerDefuse() {
        clearTimeout(flashTimer);
        bombBody.className = "defused";
        setBombDisplay("WIN", "defused!");
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
                '<img src="/static/img/lightbulb.svg" class="hint-icon-img" alt=""> Hide Hints <span class="hint-badge">' + hintsRevealed + "/" + allHints.length + '</span>';
        } else {
            hintsPanel.classList.add("hidden");
            hintToggleBtn.innerHTML =
                '<img src="/static/img/lightbulb.svg" class="hint-icon-img" alt=""> Show Hints <span class="hint-badge">' + hintsRevealed + "/" + allHints.length + '</span>';
        }
    };

    function unlockNextHint() {
        if (hintsRevealed < allHints.length) {
            hintsRevealed++;
            renderHintsPanel();
            // Update button text to reflect new count without closing
            if (hintsOpen) {
                hintToggleBtn.innerHTML =
                    '<img src="/static/img/lightbulb.svg" class="hint-icon-img" alt=""> Hide Hints <span class="hint-badge">' + hintsRevealed + "/" + allHints.length + '</span>';
            } else {
                hintToggleBtn.innerHTML =
                    '<img src="/static/img/lightbulb.svg" class="hint-icon-img" alt=""> Show Hints <span class="hint-badge">' + hintsRevealed + "/" + allHints.length + '</span>';
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
                    '<img src="/static/img/lightbulb.svg" class="hint-icon-img" alt=""> Hide Hints <span class="hint-badge">' + hintsRevealed + "/" + allHints.length + '</span>';
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

    var modeBtns = document.querySelectorAll(".mode-btn");

    function lockInput() {
        inputLocked = true;
        ttbInput.disabled = true;
        submitBtn.disabled = true;
        skipBtn.disabled = true;
        modeBtns.forEach(function (b) { b.disabled = true; });
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

    function unlockMode() {
        modeBtns.forEach(function (b) { b.disabled = false; });
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

        fetch("/api/nba_ttb/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: gameMode }),
        })
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
                    hintToggleBtn.innerHTML =
                        '<img src="/static/img/lightbulb.svg" class="hint-icon-img" alt=""> Show Hints <span class="hint-badge">1/' + allHints.length + '</span>';
                    hintToggleBtn.classList.remove("hidden");
                    renderHintsPanel();
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

        fetch("/api/nba_ttb/guess", {
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
            unlockMode();
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
                unlockMode();
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

        fetch("/api/nba_ttb/guess", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ game_id: gameId, guess: "", reveal: true }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                triggerExplosion();
                unlockMode();
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
        fetch("/api/nba_ttb/search?q=" + encodeURIComponent(term))
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

    // ── Mode toggle ───────────────────────────────────────────────────────────

    window.setTTBMode = function (mode) {
        if (gameActive) return;
        gameMode = mode;
        var app = document.getElementById("ttb-app");
        var classicBtn = document.getElementById("mode-classic-btn");
        var vintageBtn = document.getElementById("mode-vintage-btn");
        app.classList.remove("vintage");
        classicBtn.classList.remove("active");
        vintageBtn.classList.remove("active");
        if (mode === "vintage") {
            app.classList.add("vintage");
            vintageBtn.classList.add("active");
        } else {
            classicBtn.classList.add("active");
        }
    };

    // ── Init ──────────────────────────────────────────────────────────────────
    setBombDisplay("?", "press start");
    startBtn.classList.remove("hidden");
})();
