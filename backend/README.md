# FastAPI Strangler Backend

This app is the parallel FastAPI backend used for the Flask -> FastAPI migration.

Current scope:

- health endpoints
- migration inventory endpoints
- domain-based folder structure for future game routers

## Upstash Redis health check

The `/health` endpoint includes a Redis connectivity check when these environment
variables are present:

- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`

If Redis is configured and unreachable, `/health` returns `503` with
`"status": "degraded"`.

The existing Flask app remains the production path while this backend grows surface-by-surface.
