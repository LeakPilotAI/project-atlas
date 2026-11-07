"""Shared async Redis client for Project Atlas."""

from __future__ import annotations

from typing import Optional

import structlog

from app.core.config import get_settings

log = structlog.get_logger(__name__)

_redis = None


async def init_redis():
    """Create and ping Redis. Safe to call once at startup."""
    global _redis
    if _redis is not None:
        return _redis
    settings = get_settings()
    try:
        import redis.asyncio as redis

        client = redis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        _redis = client
        log.info("Redis connected successfully", url=settings.redis_url)
        return _redis
    except Exception as e:
        log.warning("Redis connection failed", error=str(e))
        _redis = None
        raise


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        try:
            await _redis.aclose()
        except Exception as primary_error:
            try:
                await _redis.close()
            except Exception as fallback_error:
                # Retain ownership for retry; a failed close is not a closed client.
                log.error("Redis client cleanup failed",
                          primary_type=type(primary_error).__name__,
                          fallback_type=type(fallback_error).__name__)
                raise fallback_error from primary_error
        _redis = None
        log.info("Redis client closed")


def get_redis():
    return _redis


async def get_redis_client():
    """Lazy get-or-create for services that don't go through lifespan."""
    global _redis
    if _redis is not None:
        return _redis
    try:
        return await init_redis()
    except Exception:
        return None
