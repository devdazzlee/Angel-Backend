"""
Ephemeral guest chat store.

Guest chats are intentionally NOT written to chat_sessions/chat_history until
the user claims the session after login/signup (matches product disclaimer).

Persistence is process-local (memory + optional JSON file) so a single App
Service instance can survive restarts. Multi-instance deploys should use sticky
sessions or a shared store later — claim also accepts a client snapshot so
resume still works if memory was lost.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

GUEST_MESSAGE_LIMIT = 5
GUEST_TTL_SECONDS = 24 * 60 * 60
_STORE_LOCK = threading.RLock()
_SESSIONS: dict[str, dict[str, Any]] = {}

_DATA_DIR = Path(
    os.getenv("GUEST_SESSION_DIR")
    or Path(__file__).resolve().parent.parent / ".guest_sessions"
)


def _now() -> float:
    return time.time()


def _persist_path(guest_token: str) -> Path:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR / f"{guest_token}.json"


def _write_disk(session: dict[str, Any]) -> None:
    try:
        path = _persist_path(session["guest_token"])
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(session, fh)
    except Exception as exc:  # pragma: no cover - best effort
        print(f"⚠️ Failed to persist guest session: {exc}")


def _delete_disk(guest_token: str) -> None:
    try:
        path = _persist_path(guest_token)
        if path.exists():
            path.unlink()
    except Exception as exc:  # pragma: no cover
        print(f"⚠️ Failed to delete guest session file: {exc}")


def _load_disk(guest_token: str) -> dict[str, Any] | None:
    path = _persist_path(guest_token)
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("expires_at", 0) < _now():
            _delete_disk(guest_token)
            return None
        return data
    except Exception as exc:  # pragma: no cover
        print(f"⚠️ Failed to load guest session: {exc}")
        return None


def create_guest_session(title: str = "Guest chat") -> dict[str, Any]:
    guest_token = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    session = {
        "guest_token": guest_token,
        "id": session_id,
        "title": title or "Guest chat",
        "current_phase": "GKY",
        "asked_q": "GKY.01",
        "answered_count": 0,
        "business_context": {},
        "history": [],
        "user_message_count": 0,
        "awaiting_gky_proceed": False,
        "requires_auth_to_continue": False,
        "created_at": _now(),
        "expires_at": _now() + GUEST_TTL_SECONDS,
        "claimed": False,
    }
    with _STORE_LOCK:
        _SESSIONS[guest_token] = session
        _write_disk(session)
    return deepcopy(session)


def get_guest_session(guest_token: str, session_id: str | None = None) -> dict[str, Any]:
    with _STORE_LOCK:
        session = _SESSIONS.get(guest_token)
        if session is None:
            session = _load_disk(guest_token)
            if session:
                _SESSIONS[guest_token] = session

        if not session:
            raise KeyError("Guest session not found or expired")

        if session.get("claimed"):
            raise PermissionError("Guest session already claimed")

        if session.get("expires_at", 0) < _now():
            _SESSIONS.pop(guest_token, None)
            _delete_disk(guest_token)
            raise KeyError("Guest session not found or expired")

        if session_id and session.get("id") != session_id:
            raise PermissionError("Guest token does not match session")

        return deepcopy(session)


def save_guest_session(session: dict[str, Any]) -> dict[str, Any]:
    guest_token = session["guest_token"]
    session["expires_at"] = _now() + GUEST_TTL_SECONDS
    with _STORE_LOCK:
        _SESSIONS[guest_token] = deepcopy(session)
        _write_disk(session)
    return deepcopy(session)


def mark_guest_claimed(guest_token: str) -> None:
    with _STORE_LOCK:
        session = _SESSIONS.get(guest_token) or _load_disk(guest_token)
        if session:
            session["claimed"] = True
            _SESSIONS.pop(guest_token, None)
            _delete_disk(guest_token)


def public_guest_view(session: dict[str, Any]) -> dict[str, Any]:
    """Safe fields for API responses (no internal-only secrets beyond token)."""
    return {
        "guest_token": session["guest_token"],
        "session_id": session["id"],
        "title": session.get("title"),
        "current_phase": session.get("current_phase"),
        "asked_q": session.get("asked_q"),
        "answered_count": session.get("answered_count", 0),
        "user_message_count": session.get("user_message_count", 0),
        "message_limit": GUEST_MESSAGE_LIMIT,
        "messages_remaining": max(
            0, GUEST_MESSAGE_LIMIT - int(session.get("user_message_count", 0))
        ),
        "awaiting_gky_proceed": bool(session.get("awaiting_gky_proceed")),
        "requires_auth_to_continue": bool(session.get("requires_auth_to_continue")),
        "business_context": session.get("business_context") or {},
        "history": session.get("history") or [],
        "expires_at": session.get("expires_at"),
    }
