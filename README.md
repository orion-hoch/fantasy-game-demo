# Sports Trivia and Games by Orion Hoch

A full-stack sports trivia arcade built around NFL and NBA history, with each mode trying to feel like its own mini-game instead of a reskin of the same quiz.

The app is built with Flask, SQLite, and vanilla JavaScript. The core idea is simple: use real player-season data as the raw material, then wrap it in game structures that feel playful, replayable, and visually distinct.

---

## What This Project Is

This repo is not a single trivia game. It is a collection of game systems that all sit on top of the same sports data layer:

- clue-chain puzzles
- timed mystery-player deduction games
- local multiplayer draft games
- roguelike dungeon runs
- Balatro-style deckbuilding runs

The project is organized so the database and routing stay shared, while each game gets its own scoring logic, frontend state, and presentation style.

---

## Design Direction

One of the main design goals is that each mode should have its own identity.

- The home page uses a tabbed arcade-style layout with bold type, heavy borders, accent bars, and sports-banner imagery so the project feels more like a curated game collection than a utility app.
- NFL and NBA are separated at the navigation level because the data, prompts, and visual cues often differ even when the underlying mechanic is similar.
- Shared styles in `static/style.css` keep the site coherent, but individual game CSS files deliberately push different moods so the games do not collapse into one generic template.
- The visual language leans on loud, poster-like contrast: dark surfaces, strong yellow/red accents, chunky borders, and condensed all-caps headings.
- The UX favors immediate readability and low-friction interaction over abstraction. Most actions are one click, one guess, or one card selection away.

In short: the codebase is shared, but the player should feel like they are entering different rooms of the same arcade.

---

## Game Modes

### Chain Game

Chain Game is built as an intersection puzzle.

- Every round adds another category to the chain
- A valid answer must satisfy every active link simultaneously
- Correct guesses extend the chain and shrink the remaining player pool
- Wrong guesses show which links passed and failed
- Classic mode ends on a miss; Infinite mode reseeds the next chain from the guessed player's teammate graph

Implementation notes:

- Category logic lives in `chain_categories.py` and `nba_chain_categories.py`
- The server samples categories from the database, builds the current constraint set, and validates guesses against all active filters
- The frontend focuses on readable chain visualization, search feedback, and failure explanation so the player understands why an answer failed

### Ticking Time Bomb

Ticking Time Bomb is the fast deduction game.

- The player has to identify a mystery player before too many wrong guesses or skips
- Each failed attempt reveals another teammate-based clue
- Optional modes like vintage, defense, and harder clue pools change who can appear and how difficult the clue set becomes

Implementation notes:

- The server chooses a target player and assembles ordered clue lists from the stats tables
- The game state tracks revealed clues, wrong guesses, skips, and end conditions per run
- The frontend is intentionally punchy and simple: big bomb visuals, clue reveals, and fast turn-by-turn feedback

### Fantasy Duel / Starting 6 / Starting 5

These are local multiplayer draft games.

- A random franchise is drawn each turn
- Players must name someone who played for that team
- After picking a player, they choose the season version they want to draft
- NFL uses fantasy-style positional roster slots; NBA uses guards, forwards, center, and utility
- Duplicate players are blocked across the whole game

Implementation notes:

- The backend validates team-player relationships first, then exposes eligible seasons for the selected player-team pair
- Once a season is chosen, that player-season gets locked into the roster state and removed from future availability
- The UI is kept lighter and more board-game-like than the other modes because these pages are meant for side-by-side drafting with friends

### Dungeon Adventure

Dungeon Adventure is the project's roguelike trivia RPG.

- Players choose a class and start a run
- Each room presents a trivia prompt plus any relic filters already collected
- Correct answers damage enemies; mistakes cost health
- Runs progress through themed encounters, reward choices, and bosses

Implementation notes:

- The backend stores a run as persistent state: class, relics, encounter, health, floor progression, and rewards
- The frontend uses its own layout and atmosphere so it feels like a small ASCII-inspired dungeon crawler rather than a normal quiz page
- This mode is intentionally more system-heavy than the others, with progression and run structure mattering as much as the trivia itself

### Balatro

Balatro is the most mechanically dense mode in the repo.

- Player seasons become collectible cards
- Each run starts from a deck pool and playable hand
- Hands are scored through position patterns, combo rules, jokers, enhancements, boss effects, and shop items
- Winning fights opens reward choices, packs, shops, and later-round bosses

Implementation notes:

- Core run logic lives in `nfl_balatro.py` and `nba_balatro.py`
- The backend handles deck generation, hand scoring, joker modifiers, rewards, shop generation, and fight progression
- The frontend handles hand interaction, overlays, reward screens, deck viewing, shop rendering, and the more elaborate card UI
- This mode is where the project most deliberately shifts from "trivia app" to "sports-data game engine"

---

## Data Layer

The app runs on a single SQLite database:

```text
fantasy.db
```

That database contains the cleaned NFL, NBA, draft, defensive, and fantasy tables used by runtime game logic.

Examples of what the data supports:

- player/team/season lookup
- historical fantasy scoring
- teammate clue generation
- draft and award filters
- card/deck generation for Balatro
- roster legality and season selection for draft modes

The value of the project comes from turning historical sports data into game rules rather than just displaying stats directly.

---

## Architecture

At a high level, the project is split into four layers:

### 1. Flask App Layer

- `app.py` wires together routes, templates, and API endpoints
- Each game exposes page routes and JSON endpoints for interactive actions

### 2. Game Logic Layer

- Python modules such as `ttb.py`, `nba_ttb.py`, `dungeon_adventure.py`, `nfl_balatro.py`, and `nba_balatro.py` hold the rules for each mode
- This keeps game-state transitions and scoring logic on the server, where they are easier to control and validate

### 3. Frontend Interaction Layer

- `static/*.js` files manage per-page interactivity, rendering, and request handling
- `static/*.css` files give each mode its own feel while inheriting the shared visual baseline from `static/style.css`

### 4. Data / Session Layer

- `fantasy.db` supplies the sports data
- `session_store.py` provides a small storage abstraction so local development can use memory while production uses KV-backed session persistence on Vercel

---

## Project Structure

```text
app.py                      Flask routes and API endpoints
load_data.py                Data cleanup and import helpers
session_store.py            Session storage abstraction for local/dev + Vercel KV

chain_categories.py         NFL chain category logic
nba_chain_categories.py     NBA chain category logic
ttb.py                      NFL Ticking Time Bomb logic
nba_ttb.py                  NBA Ticking Time Bomb logic
dungeon_adventure.py        NFL dungeon run logic
nba_dungeon_adventure.py    NBA dungeon run logic
nfl_balatro.py              NFL Balatro run logic
nba_balatro.py              NBA Balatro run logic

templates/                  HTML templates for landing page and each game mode
static/                     Shared and per-game CSS/JS/assets
api/index.py                Vercel Python entrypoint
vercel.json                 Vercel deployment config
fantasy.db                  Consolidated runtime database
```

---

## Local Setup

### Requirements

- Python 3.9+
- pip packages from the project requirements

### Install and Run

```bash
pip install -r requirements.txt
python app.py
```

The app starts locally at `http://127.0.0.1:5000`.

---

## Vercel Deployment

This repo includes a Vercel entrypoint at `api/index.py` and config in `vercel.json`.

To deploy:

- import the repo into Vercel as a Python project
- attach a KV-compatible database
- make sure `KV_REST_API_URL` and `KV_REST_API_TOKEN` are set in the project environment
- deploy from `main`

Notes:

- local development falls back to in-memory session storage
- production uses KV so multi-step games can survive across requests in a serverless environment
- static assets, templates, and the SQLite database are explicitly bundled for deployment

---

## Why It Is Structured This Way

The repo is opinionated in a few ways:

- The backend owns game rules because validation-heavy trivia modes are easier to keep consistent server-side.
- The frontend owns feel: animation, rendering, layout, card presentation, and moment-to-moment responsiveness.
- Data is centralized in SQLite because almost every mode depends on historical player-season lookups.
- Modes are split into separate Python and JS files so each game can evolve without turning one giant file into a mess.

That split has made it easier to keep adding new ideas without rewriting the entire site every time a new game mechanic appears.
