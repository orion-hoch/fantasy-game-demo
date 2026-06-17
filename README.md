# Sports Trivia and Games by Orion Hoch

Live at **[oriontrivia.org](https://oriontrivia.org)**.

## Data Credit

All player, team, and season data is sourced from [Sports Reference](https://www.sports-reference.com/) (Pro Football Reference and Basketball Reference). This project is not affiliated with or endorsed by Sports Reference; their data is used here for a non-commercial trivia project, with full credit to them as the source.

## Local Setup

Requirements: Python 3.9+ and Node.

```bash
# Backend (FastAPI, serves the API and loads the game engines)
cd backend && pip install . && python -m uvicorn src.main:app --reload --port 8000

# Frontend (in a second terminal)
cd frontend && npm install && npm run dev
```

The frontend runs at `http://127.0.0.1:5173` and the backend at `http://127.0.0.1:8000`. The backend reads its database from `data/fantasy.db`.
