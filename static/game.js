let currentQid = null;
let validAnswers = new Set();
let guessed = new Set();
let debounceTimer = null;

async function startQuestion(qid, title, desc) {
    currentQid = qid;
    guessed = new Set();
    validAnswers = new Set();

    document.getElementById("q-title").textContent = title;
    document.getElementById("q-desc").textContent = desc;
    document.getElementById("found-count").textContent = "0";
    document.getElementById("total-count").textContent = "?";
    document.getElementById("guess-list").innerHTML = "";
    document.getElementById("search-input").value = "";
    document.getElementById("search-results").innerHTML = "";

    document.getElementById("question-select").classList.add("hidden");
    document.getElementById("game-panel").classList.remove("hidden");
    document.getElementById("search-input").focus();

    const res = await fetch(`/api/question/${qid}/answers`);
    const data = await res.json();
    data.answers.forEach(a => validAnswers.add(a));
    document.getElementById("total-count").textContent = data.count;
}

function goBack() {
    document.getElementById("game-panel").classList.add("hidden");
    document.getElementById("question-select").classList.remove("hidden");
    currentQid = null;
}

document.getElementById("search-input").addEventListener("input", (e) => {
    clearTimeout(debounceTimer);
    const q = e.target.value.trim();
    if (!q) {
        document.getElementById("search-results").innerHTML = "";
        return;
    }
    debounceTimer = setTimeout(() => searchPlayers(q), 200);
});

async function searchPlayers(term) {
    const res = await fetch(`/api/search?q=${encodeURIComponent(term)}&qid=${currentQid}`);
    const data = await res.json();
    renderResults(data.results);
}

function renderResults(results) {
    const container = document.getElementById("search-results");
    if (!results.length) {
        container.innerHTML = `<div class="result-item"><span style="color:#556">No players found</span></div>`;
        return;
    }
    container.innerHTML = results.map(r => {
        const alreadyGuessed = guessed.has(r.name);
        return `
            <div class="result-item ${alreadyGuessed ? "already-guessed" : ""}"
                 onclick="submitGuess('${r.name.replace(/'/g, "\\'")}', ${r.valid})">
                <span>${r.name}</span>
                ${alreadyGuessed ? '<span style="color:#556;font-size:0.75rem">Already guessed</span>' : ""}
            </div>
        `;
    }).join("");
}

function submitGuess(name, isValid) {
    if (guessed.has(name)) return;
    guessed.add(name);

    document.getElementById("search-input").value = "";
    document.getElementById("search-results").innerHTML = "";

    const chip = document.createElement("div");
    chip.className = `guess-chip ${isValid ? "correct" : "wrong"}`;
    chip.textContent = name;
    document.getElementById("guess-list").prepend(chip);

    if (isValid) {
        const found = parseInt(document.getElementById("found-count").textContent) + 1;
        document.getElementById("found-count").textContent = found;
    }
}

// Close search results when clicking outside
document.addEventListener("click", (e) => {
    if (!document.getElementById("search-area").contains(e.target)) {
        document.getElementById("search-results").innerHTML = "";
    }
});
