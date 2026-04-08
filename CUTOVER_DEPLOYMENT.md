# Cutover Deployment Notes

The repo is now in a frontend-first cutover state.

## Current Roles

- `frontend/`: primary user-facing SvelteKit app
- `backend/`: primary FastAPI API app
- `app.py` + `api/index.py`: compatibility layer for old URLs and legacy API aliases

## Local Development

1. Start FastAPI:

```bash
cd backend
python -m uvicorn src.main:app --reload --port 8000
```

2. Start SvelteKit:

```bash
cd frontend
npm run dev
```

3. Optional Flask compatibility layer:

```bash
python app.py
```

Local Flask redirects default to `http://127.0.0.1:5173`.

## Production Recommendation

Recommended final topology:

- deploy `frontend/` as the primary app host
- deploy `backend/` as the primary API host
- keep the Flask/Vercel layer only as a temporary redirect bridge if old URLs still need to resolve

## Compatibility Layer Requirement

If the Flask layer is still deployed, set:

```bash
FRONTEND_BASE_URL=https://your-frontend-host
```

Without this, page-route redirects outside local dev will not know where the frontend lives.

## Remaining Cleanup Candidates

- replace Balatro compatibility iframe with a native Svelte Balatro screen
- replace Dungeon compatibility shell with a native Svelte Dungeon screen
- replace Code Words compatibility shell with a native Svelte Code Words screen
- remove legacy API aliases after traffic is fully cut over
- retire `app.py`, `api/index.py`, and `vercel.json` when the compatibility layer is no longer needed
