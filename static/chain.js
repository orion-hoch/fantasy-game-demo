/* ── Chain Game JS ─────────────────────────────────────────────────────────── */

(function () {
    "use strict";

    // ── State ─────────────────────────────────────────────────────────────────
    let score = 0;
    let chain = [];           // [{id, value, label}, ...]
    let validCount = 0;
    let gameActive = false;
    let inputLocked = false;
    let advanceTimer = null;
    let selectedIndex = -1;
    let searchDebounce = null;
    let currentGuess = "";
    let gameMode = "classic"; // "classic" | "infinite"

    // ── DOM references ────────────────────────────────────────────────────────
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

    // ── Helpers ───────────────────────────────────────────────────────────────

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
        feedbackEl.className = type;  // "correct" or "wrong"
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
        chainInput.disabled = false;
        submitBtn.disabled = false;
        chainInput.value = "";
        currentGuess = "";
        chainInput.focus();
    }

    function closeSearchResults() {
        searchResults.innerHTML = "";
        selectedIndex = -1;
    }

    function showPointsFlash(pts) {
        pointsFlash.textContent = "+" + pts + " pt" + (pts !== 1 ? "s" : "");
        pointsFlash.classList.remove("hidden");
        // Force reflow then show
        void pointsFlash.offsetWidth;
        pointsFlash.classList.add("show");
        setTimeout(function () {
            pointsFlash.classList.remove("show");
            setTimeout(function () {
                pointsFlash.classList.add("hidden");
            }, 260);
        }, 900);
    }

    // ── Chain rendering ───────────────────────────────────────────────────────

    function renderChain() {
        // Clear
        chainBar.innerHTML = "";

        if (chain.length === 0) {
            chainBar.appendChild(chainEmptyMsg);
            chainEmptyMsg.style.display = "";
            setChainLength(0);
            return;
        }

        chainEmptyMsg.style.display = "none";
        setChainLength(chain.length);

        chain.forEach(function (link, i) {
            // Arrow between links
            if (i > 0) {
                const arrow = document.createElement("span");
                arrow.className = "chain-arrow";
                arrow.textContent = "→";
                chainBar.appendChild(arrow);
            }

            const pill = document.createElement("div");
            pill.className = "chain-link" + (i === chain.length - 1 ? " active" : "");

            const num = document.createElement("span");
            num.className = "link-num";
            num.textContent = (i + 1) + ".";

            const text = document.createTextNode(link.label);

            pill.appendChild(num);
            pill.appendChild(text);
            chainBar.appendChild(pill);
        });

        // Scroll to end
        chainBar.scrollLeft = chainBar.scrollWidth;
    }

    function updatePrompt() {
        if (chain.length === 0) {
            promptText.innerHTML = "Press <strong>Start New Chain</strong> to begin!";
            return;
        }
        if (chain.length === 1) {
            promptText.innerHTML =
                "Name a player who: <strong>" + escapeHtml(chain[0].label) + "</strong>";
        } else {
            promptText.innerHTML =
                "Name a player who fits <strong>all " + chain.length + " chain links</strong>.";
        }
    }

    // ── Mode toggle ───────────────────────────────────────────────────────────

    window.setMode = function (mode) {
        gameMode = mode;
        document.getElementById("mode-classic").classList.toggle("active", mode === "classic");
        document.getElementById("mode-infinite").classList.toggle("active", mode === "infinite");
    };

    // ── Game flow ─────────────────────────────────────────────────────────────

    window.startGame = function () {
        clearAdvanceTimer();
        clearFeedback();
        chain = [];
        setScore(0);
        setValidCount(0);
        setChainLength(0);
        renderChain();
        startBtn.classList.add("hidden");
        newChainBtn.classList.add("hidden");
        lockInput();
        promptText.innerHTML = "Loading…";

        fetch("/api/chain/start", { method: "POST" })
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
        clearAdvanceTimer();
        clearFeedback();
        newChainBtn.classList.add("hidden");
        newChainBtn.textContent = "Start New Chain";
        newChainBtn.onclick = window.startNewChain;
        chain = [];
        renderChain();
        lockInput();
        promptText.innerHTML = "Loading next chain…";

        fetch("/api/chain/start", { method: "POST" })
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
        clearAdvanceTimer();
        clearFeedback();
        newChainBtn.classList.add("hidden");
        chain = [];
        renderChain();
        lockInput();
        promptText.innerHTML = "Finding teammates of <strong>" + escapeHtml(playerName) + "</strong>…";

        fetch("/api/chain/teammate_start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ player: playerName }),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.error) {
                    // Fallback to fresh chain if no teammates found
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
        if (!guess || inputLocked || !gameActive) return;
        doGuess(guess);
    };

    function doGuess(playerName) {
        if (inputLocked || chain.length === 0) return;

        closeSearchResults();
        lockInput();

        const payload = {
            player: playerName,
            chain: chain.map(function (c) { return { id: c.id, value: c.value }; }),
        };

        fetch("/api/chain/guess", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                handleGuessResult(playerName, data);
            })
            .catch(function () {
                showFeedback("wrong", "Network error. Please try again.");
                unlockInput();
            });
    }

    function handleGuessResult(playerName, data) {
        if (data.correct) {
            const pts = data.chain_length;
            setScore(score + pts);
            showPointsFlash(pts);

            if (!data.next_category) {
                // Chain ended gracefully (no more valid categories)
                showFeedback(
                    "correct",
                    "&#x2713; Correct! +" + pts + " point" + (pts !== 1 ? "s" : "") +
                    " — Chain complete! No more valid categories."
                );
                setValidCount(data.valid_count);
                gameActive = false;
                newChainBtn.classList.remove("hidden");
            } else {
                showFeedback(
                    "correct",
                    "&#x2713; Correct! +" + pts + " point" + (pts !== 1 ? "s" : "") + " — chain grows!"
                );
                // Add the next category to the chain
                chain.push(data.next_category);
                setValidCount(data.next_category.valid_count);
                renderChain();
                updatePrompt();
                // Brief pause then unlock
                setTimeout(function () {
                    clearFeedback();
                    unlockInput();
                }, 1200);
            }
        } else {
            // Wrong answer — show per-link breakdown
            let html = "&#x2717; <strong>" + escapeHtml(playerName) + "</strong> doesn't fit the full chain:";
            if (data.link_results && data.link_results.length > 0) {
                html += "<ul class=\"link-breakdown\">";
                data.link_results.forEach(function (r) {
                    html += "<li class=\"" + (r.passed ? "link-pass" : "link-fail") + "\">" +
                        (r.passed ? "&#x2713;" : "&#x2717;") + " " + escapeHtml(r.label) +
                        "</li>";
                });
                html += "</ul>";
            }
            if (data.examples && data.examples.length > 0) {
                html += "<div class=\"examples\">Valid answers included: <strong>" +
                    data.examples.map(escapeHtml).join(", ") + "</strong></div>";
            }
            showFeedback("wrong", html);
            gameActive = false;

            if (gameMode === "infinite") {
                newChainBtn.textContent = "Continue with " + escapeHtml(playerName) + "'s teammates →";
                newChainBtn.classList.remove("hidden");
                // Store wrong player for the teammate chain
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

    function clearAdvanceTimer() {
        if (advanceTimer) {
            clearTimeout(advanceTimer);
            advanceTimer = null;
        }
    }

    // ── Search autocomplete ───────────────────────────────────────────────────

    chainInput.addEventListener("input", function () {
        currentGuess = "";
        const term = chainInput.value.trim();
        if (!term) {
            closeSearchResults();
            return;
        }
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(function () {
            fetchSearch(term);
        }, 200);
    });

    function fetchSearch(term) {
        fetch("/api/chain/search?q=" + encodeURIComponent(term))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                renderSearchResults(data.results || []);
            })
            .catch(function () { closeSearchResults(); });
    }

    function renderSearchResults(results) {
        searchResults.innerHTML = "";
        selectedIndex = -1;
        if (!results.length) return;

        results.forEach(function (r, i) {
            const item = document.createElement("div");
            item.className = "chain-result-item";
            item.textContent = r.name;
            item.addEventListener("mousedown", function (e) {
                e.preventDefault();
                selectPlayer(r.name);
            });
            searchResults.appendChild(item);
        });
    }

    function selectPlayer(name) {
        chainInput.value = name;
        currentGuess = name;
        closeSearchResults();
        doGuess(name);
    }

    // Keyboard navigation
    chainInput.addEventListener("keydown", function (e) {
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
            if (selectedIndex >= 0 && items[selectedIndex]) {
                selectPlayer(items[selectedIndex].textContent);
            } else {
                const val = chainInput.value.trim();
                if (val) doGuess(val);
            }
        } else if (e.key === "Escape") {
            closeSearchResults();
        }
    });

    function updateHighlight(items) {
        items.forEach(function (item, i) {
            item.classList.toggle("highlighted", i === selectedIndex);
        });
        if (selectedIndex >= 0 && items[selectedIndex]) {
            chainInput.value = items[selectedIndex].textContent;
        }
    }

    // Close results when clicking outside
    document.addEventListener("click", function (e) {
        if (!document.getElementById("search-wrapper").contains(e.target)) {
            closeSearchResults();
        }
    });

    // ── Utility ───────────────────────────────────────────────────────────────

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    // ── Init ──────────────────────────────────────────────────────────────────
    // Show the start button, everything else is in ready state
    startBtn.classList.remove("hidden");
    renderChain();
    updatePrompt();
})();
