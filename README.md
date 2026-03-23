# Fantasy Sports Trivia

A web-based sports trivia app with NFL, NBA, and roguelike-style challenge modes.

Built with Python/Flask and SQLite, using NFL player data sourced from [Sports Reference / Pro Football Reference](https://www.pro-football-reference.com/).

---

## Games

### ⛓ Chain Game

Build a chain of categories and name a player who fits every link.

- Each round a new category is added to the chain (team, position, college, conference, draft round, Pro Bowl, stats thresholds, era, and more)
- Name a player who satisfies **all** categories in the chain to earn points — longer chains are worth more
- Wrong answers show a per-link breakdown of what passed and what failed, with example valid answers
- **Classic mode**: one chain at a time; game ends on a wrong guess
- **Infinite mode**: a wrong guess starts a fresh chain seeded by the teammates of the player you guessed
- **Last player bonus**: if you guess correctly when only one valid player remains in the pool, you earn a +10 point bonus and the next chain is seeded by that player's teammates

### ⚡ Starting 6 — 2 Player Draft

A two-player head-to-head drafting game.

- A random NFL team is drawn each round
- Both players draft their best 6-man fantasy lineup (QB, 2 RB, 2 WR, TE) from that team's historical roster
- Score is based on each player's best PPR fantasy season with that team

---

## Data

All player, team, and stats data is sourced from **[Sports Reference / Pro Football Reference](https://www.pro-football-reference.com/)**.

The database includes:

| Table | Description |
|---|---|
| `stats` | Single-season fantasy stats (PPR) for QBs, RBs, WRs, TEs |
| `season_stats` | Season-level passing, rushing, and receiving totals |
| `draft` | NFL Draft history (1942–2025) with college, draft round, draft pick, and career stats |

---

## Setup

### Requirements

- Python 3.9+
- pip packages: `flask`, `pandas`, `openpyxl`

### Install & Run

```bash
pip install flask pandas openpyxl
python app.py
```

The app uses the consolidated SQLite data source at `fantasy.db` and starts at `http://127.0.0.1:5000`.

### Vercel Deployment

This repo now includes a Vercel entrypoint at `api/index.py` and config in `vercel.json`.

- Import the repo into Vercel as a Python project
- Attach a Vercel KV database to the project
- Make sure `KV_REST_API_URL` and `KV_REST_API_TOKEN` are available in the project environment
- Deploy; all routes are served through the Flask app and game sessions are stored in KV

Without Vercel KV, local development still works, but multi-request game state falls back to in-memory storage.

### Data Source

The canonical data source is a single SQLite database:

```
fantasy.db
```

That file contains the cleaned NFL, NBA, draft, defensive, and fantasy tables used by the app. The old raw spreadsheet folders are no longer required for runtime.

---

## Project Structure

```
app.py                  — Flask routes
load_data.py            — data cleanup and import utilities
chain_categories.py     — Chain Game category logic
dungeon_adventure.py    — roguelike dungeon mode logic
templates/
  index.html            — Home page
  chain.html            — Chain Game
  starting6.html        — Starting 6
  dungeon_adventure.html
static/
  chain.js / chain.css  — Chain Game frontend
  starting6.js / starting6.css
  dungeon_adventure.js / dungeon_adventure.css
  style.css             — Shared styles
```
