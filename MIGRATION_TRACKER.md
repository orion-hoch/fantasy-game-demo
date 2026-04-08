# Strangler Migration Tracker

This repo is migrating from Flask-rendered pages plus vanilla JS to a parallel `SvelteKit + FastAPI` stack.

The rollout strategy is strangler-first:

- Keep Flask as the live system of record while new surfaces are rebuilt in parallel.
- Cut over one surface at a time behind stable URLs and compatibility redirects.
- Track what is still coupled to Flask so the eventual full cutover stays explicit.

This tracker is based on the migration review standards from:

- `/Users/orionhoch/svelte-claude-skills`
- `/Users/orionhoch/jezweb-fastapi`

## Rollout Rules

- Preserve server-side game logic first; do not rewrite rules and UI simultaneously.
- Freeze API behavior before migrating a frontend surface.
- Keep multiplayer on polling first; move to WebSockets only after parity.
- Keep anonymous browser-token identity first; do not mix auth migration into UI migration.
- Do not remove Flask routes until the Svelte/FastAPI replacement has parity tests.

## New App Surfaces

- `backend/`: FastAPI strangler backend scaffold
- `frontend/`: SvelteKit strangler frontend scaffold

## Rollout Order

1. Home shell and shared navigation
2. Multiplayer lobby
3. Bullseye NFL/NBA
4. Fantasy Duel NFL/NBA
5. Chain NFL/NBA
6. Code Words NFL/NBA
7. TTB NFL/NBA
8. Dungeon Adventure NFL/NBA
9. Balatro NFL/NBA
10. Final Flask retirement

## Surface Tracker

Legend:

- `legacy`: still served by Flask
- `scaffolded`: target route exists in new app but not feature-complete
- `in_migration`: actively porting
- `cutover_ready`: parity complete, waiting for traffic switch
- `cutover_done`: Flask no longer serves that surface

| Surface | Current Flask Surface | Target Svelte/FastAPI Surface | Status | Notes |
| --- | --- | --- | --- | --- |
| Home | `/` | `frontend/src/routes/+page.svelte` | cutover_done | Flask now redirects into the Svelte home |
| Lobby | `/multiplayer/<game_type>`, `/lobbies/<room_id>` | `/multiplayer/nfl_bullseye`, `/lobbies/[roomId]` | cutover_done | Flask lobby pages now redirect into the migrated Svelte lobby |
| NFL Bullseye | `/nfl_bullseye` | `/games/nfl/bullseye?solo=1` | cutover_done | Flask page route now redirects into migrated Bullseye |
| NBA Bullseye | `/nba_bullseye` | `/games/nba/bullseye?solo=1` | cutover_done | Flask page route now redirects into migrated Bullseye |
| NFL Fantasy Duel | `/starting6` | `/games/nfl/fantasy-duel` | cutover_done | Flask page route now redirects into migrated Fantasy Duel |
| NBA Fantasy Duel | `/nba_starting5` | `/games/nba/fantasy-duel` | cutover_done | Flask page route now redirects into migrated Fantasy Duel |
| NFL Chain | `/chain` | `/games/nfl/chain` | cutover_done | Flask page route now redirects into migrated Chain |
| NBA Chain | `/nba_chain` | `/games/nba/chain` | cutover_done | Flask page route now redirects into migrated Chain |
| NFL Code Words | `/nfl_codewords` | `/games/nfl/codewords` | cutover_done | Flask page route now redirects into migrated Code Words |
| NBA Code Words | `/nba_codewords` | `/games/nba/codewords` | cutover_done | Flask page route now redirects into migrated Code Words |
| NFL TTB | `/ttb` | `/games/nfl/ttb` | cutover_done | Flask page route now redirects into migrated TTB |
| NBA TTB | `/nba_ttb` | `/games/nba/ttb` | cutover_done | Flask page route now redirects into migrated TTB |
| NFL Dungeon | `/dungeon_adventure` | `/games/nfl/dungeon` | cutover_done | Flask page route now redirects into migrated Dungeon Adventure |
| NBA Dungeon | `/nba_dungeon_adventure` | `/games/nba/dungeon` | cutover_done | Flask page route now redirects into migrated Dungeon Adventure |
| NFL Balatro | `/nfl_balatro` | `/games/nfl/balatro` | cutover_done | Flask page route now redirects into migrated Balatro |
| NBA Balatro | `/nba_balatro` | `/games/nba/balatro` | cutover_done | Flask page route now redirects into migrated Balatro |

## Per-Game Parity Checklist

Every surface must pass all of these before cutover:

- page loads without JS errors
- start/new game flow works
- search/autocomplete works if applicable
- invalid actions return the correct error shape
- turn progression matches Flask behavior
- results/winner state matches Flask behavior
- play again/rematch behavior matches current lobby semantics
- browser refresh or rejoin restores state correctly
- mobile layout is usable
- API payloads are JSON-serializable and typed

## Full Cutover Tasks Still To Track

These are the items that matter for the eventual Flask retirement even if the strangler rollout hides them for a while.

### Backend

- split `app.py` monolith into FastAPI domain routers
- move shared request parsing/error handling into FastAPI dependencies and exception handlers
- replace direct Flask rendering with API-only responsibilities
- standardize all JSON schemas with Pydantic v2
- migrate `session_store.py` and `lobby_store.py` to a multi-worker-safe backend everywhere
- centralize SQLite access and define the Postgres migration decision point

### Frontend

- remove template-injected globals like `window.SPORT` and `window.CHAIN_API_PREFIX`
- replace `innerHTML`/inline handlers with Svelte components/events
- centralize audio, token, display-name, and image-cache behavior in shared stores
- remove per-page duplicated NFL/NBA scaffolding where config can replace forks
- remove remaining Flask templates once all pages have cutover

### Multiplayer

- preserve browser token compatibility during rollout
- standardize polling stores before considering WebSockets
- define eventual WebSocket/SSE upgrade path for lobby and in-game sync
- preserve rematch semantics for same-lobby restarts

### Deployment

- keep Flask/Vercel deployment working during migration
- define final deployment target for SvelteKit and FastAPI
- add cutover plan for old URLs and redirects

### Testing

- backend contract tests for all migrated endpoints
- frontend Playwright smoke tests for each migrated surface
- multiplayer integration tests for create/join/start/rematch
- game-engine parity tests where behavior is subtle (Code Words, Balatro, Fantasy Duel)

## Immediate Next Slice

Recommended first implementation slice:

1. Remove remaining Flask page rendering
2. Replace compatibility bridges with native Svelte screens where it is worth the cost
3. Unify deployment so the Svelte frontend is served directly
4. Retire duplicated legacy APIs after traffic verification

## Completed In Current Strangler Slice

- FastAPI scaffold with health endpoints
- FastAPI migration inventory endpoint
- FastAPI lobby contract scaffold at `/api/v1/lobbies/*`
- FastAPI Bullseye API at `/api/v1/bullseye/{sport}/*`
- FastAPI Fantasy Duel API at `/api/v1/fantasy-duel/{sport}/*`
- FastAPI Chain API at `/api/v1/chain/{sport}/*`
- FastAPI Code Words API at `/api/v1/codewords/*`
- FastAPI TTB API at `/api/v1/ttb/{sport}/*`
- FastAPI Dungeon API at `/api/v1/dungeon/{sport}/*`
- FastAPI Balatro API at `/api/v1/balatro/{sport}/*`
- SvelteKit dashboard fetching migration inventory from backend with fallback
- migrated SvelteKit lobby routes at `/multiplayer/[gameType]` and `/lobbies/[roomId]`
- migrated SvelteKit Bullseye routes at `/games/nfl/bullseye` and `/games/nba/bullseye`
- migrated SvelteKit Fantasy Duel routes at `/games/nfl/fantasy-duel` and `/games/nba/fantasy-duel`
- migrated SvelteKit Chain routes at `/games/nfl/chain` and `/games/nba/chain`
- migrated SvelteKit Code Words routes at `/games/nfl/codewords` and `/games/nba/codewords`
- migrated SvelteKit TTB routes at `/games/nfl/ttb` and `/games/nba/ttb`
- migrated SvelteKit Dungeon routes at `/games/nfl/dungeon` and `/games/nba/dungeon`
- migrated SvelteKit Balatro routes at `/games/nfl/balatro` and `/games/nba/balatro`
- route placeholders for remaining game, multiplayer, and lobby targets
