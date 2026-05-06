import json
import logging
import os
import re
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from db.supabase import supabase

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = int(os.getenv("RESEARCH_CACHE_TTL", "21600"))  # 6 hours
TIMESTAMP_KEYS = {"completed_at", "generated_at", "timestamp", "created_at", "updated_at"}
TIMESTAMP_PATTERN = re.compile(r'"(' + "|".join(TIMESTAMP_KEYS) + r')"\s*:\s*"[^"]+"', re.IGNORECASE)


def _sanitize_string(value: str) -> str:
    if not value:
        return value
    sanitized = TIMESTAMP_PATTERN.sub(r'"\1":"__TIMESTAMP__"', value)
    sanitized = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?', "__TIMESTAMP__", sanitized)
    return sanitized


def _sanitize_value(value: Any):
    if isinstance(value, dict):
        sanitized = {}
        for key, val in value.items():
            lowered = key.lower()
            if lowered in TIMESTAMP_KEYS:
                sanitized[key] = "__TIMESTAMP__"
            else:
                sanitized[key] = _sanitize_value(val)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, str):
        return _sanitize_string(value)
    return value


def build_cache_key(*parts: Any) -> str:
    normalized = [_sanitize_value(part) for part in parts]
    raw = json.dumps(normalized, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached_entry(bucket: str, cache_key: str) -> Optional[Any]:
    try:
        response = (
            supabase.from_("research_cache")
            .select("data, expires_at")
            .eq("bucket", bucket)
            .eq("cache_key", cache_key)
            .limit(1)
            .execute()
        )
        data = response.data if hasattr(response, "data") else response.get("data")
        if not data:
            return None
        record = data[0]
        expires_at = record.get("expires_at")
        if not expires_at:
            return None
        # Parse expires_at (timezone-aware from database)
        expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        # Use timezone-aware utcnow() for comparison to avoid timezone mismatch
        now_utc = datetime.now(timezone.utc)
        if expires_dt < now_utc:
            try:
                supabase.from_("research_cache").delete().eq("bucket", bucket).eq("cache_key", cache_key).execute()
            except Exception as del_err:
                logger.warning("research_cache delete expired row skipped: %s", del_err)
            return None
        return record["data"]
    except Exception as e:
        # RLS misconfiguration or wrong API key (anon vs service_role) — do not break callers.
        logger.warning("research_cache read skipped for bucket=%s: %s", bucket, e)
        return None


def set_cached_entry(
    bucket: str,
    cache_key: str,
    data: Any,
    *,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    ttl_seconds: int = DEFAULT_TTL_SECONDS
) -> None:
    try:
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        supabase.from_("research_cache").upsert(
            {
                "bucket": bucket,
                "cache_key": cache_key,
                "session_id": session_id,
                "user_id": user_id,
                "data": data,
                "expires_at": expires_at.isoformat() + "Z",
            },
            on_conflict="bucket,cache_key",
        ).execute()
    except Exception as e:
        # Common: RLS on research_cache while using anon key, or policies blocking service inserts.
        # Callers (RAG, implementation help) still return results; only persistent cache is skipped.
        logger.warning(
            "research_cache upsert skipped for bucket=%s: %s — "
            "confirm SUPABASE_SERVICE_ROLE_KEY is the service_role JWT, or relax RLS for backend writes.",
            bucket,
            e,
        )

