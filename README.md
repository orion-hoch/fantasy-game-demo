# Fantasy Football Trivia

A web-based fantasy football trivia app with two games: **Chain Game** and **Starting 6**.

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

The app will build the SQLite database on first run, then start at `http://127.0.0.1:5000`.

### Data Files

The following Excel files are required and tracked via Git LFS:

```
fantasy_stats/
  QB_Fantasy/   — quarterly QB PPR stats
  WR_Fantasy/   — quarterly WR PPR stats
  TE_Fantasy/   — quarterly TE PPR stats
  RB_Fantasy/   — quarterly RB PPR stats

Total_stats/
  season_stats.xlsx          — combined passing/rushing/receiving seasons
  Draft_stats/combined.xlsx  — combined NFL Draft history
```

---

## Project Structure

```
app.py                  — Flask routes
load_data.py            — DB builder (fantasy stats + total stats)
chain_categories.py     — Chain Game category logic
templates/
  index.html            — Home page
  chain.html            — Chain Game
  starting6.html        — Starting 6
static/
  chain.js / chain.css  — Chain Game frontend
  starting6.js / starting6.css
  style.css             — Shared styles
```
