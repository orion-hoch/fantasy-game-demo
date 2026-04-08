"""Upstash Redis helpers for backend health checks."""

from functools import lru_cache
from typing import Any

from src.config import settings

try:
    from upstash_redis import Redis
except ImportError:  # pragma: no cover - exercised only when dependency is missing
    Redis = None  # type: ignore[assignment]


def redis_is_configured() -> bool:
    """Return True when the required Upstash credentials are configured."""
    return bool(settings.upstash_redis_rest_url and settings.upstash_redis_rest_token)


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    """Create and cache an Upstash Redis client."""
    if Redis is None:
        raise RuntimeError("upstash-redis dependency is not installed")

    if not redis_is_configured():
        raise RuntimeError("UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are required")

    return Redis(
        url=settings.upstash_redis_rest_url,
        token=settings.upstash_redis_rest_token,
    )


def check_redis_health() -> dict[str, Any]:
    """Validate Redis connectivity by writing and reading a test key."""
    if not redis_is_configured():
        return {"configured": False, "status": "not_configured"}

    if Redis is None:
        return {
            "configured": True,
            "status": "client_missing",
            "error": "Install upstash-redis in the backend environment",
        }

    try:
        client = get_redis_client()
        client.set("healthcheck", "ok")
        value = client.get("healthcheck")
    except Exception as exc:  # pragma: no cover - depends on external connectivity
        return {"configured": True, "status": "error", "error": str(exc)}

    if value == "ok":
        return {"configured": True, "status": "ok"}

    return {
        "configured": True,
        "status": "unexpected_response",
        "value": value,
    }
