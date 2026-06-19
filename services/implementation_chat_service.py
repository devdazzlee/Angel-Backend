from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from db.supabase import supabase

ImplementationChatMode = Literal["help", "draft", "brainstorm"]
ImplementationChatRole = Literal["user", "assistant"]

SELECT_COLUMNS = "id, role, content, mode, task_id, created_at"


def _parse_created_at(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")


async def count_implementation_chat_messages(session_id: str) -> int:
    response = (
        supabase.from_("implementation_chat_messages")
        .select("id", count="exact")
        .eq("session_id", session_id)
        .execute()
    )
    return int(response.count or 0)


async def fetch_implementation_chat_messages(
    session_id: str,
    *,
    limit: int = 500,
) -> list[dict[str, Any]]:
    response = (
        supabase.from_("implementation_chat_messages")
        .select(SELECT_COLUMNS)
        .eq("session_id", session_id)
        .order("created_at")
        .limit(limit)
        .execute()
    )
    return response.data or []


async def fetch_recent_implementation_chat_messages(
    session_id: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    response = (
        supabase.from_("implementation_chat_messages")
        .select("role, content")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = response.data or []
    rows.reverse()
    return rows


async def save_implementation_chat_message(
    session_id: str,
    user_id: str,
    role: ImplementationChatRole,
    content: str,
    *,
    mode: Optional[ImplementationChatMode] = None,
    task_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "session_id": session_id,
        "user_id": user_id,
        "role": role,
        "content": content,
        "metadata": metadata or {},
    }
    if mode:
        payload["mode"] = mode
    if task_id:
        payload["task_id"] = task_id

    response = (
        supabase.from_("implementation_chat_messages")
        .insert(payload)
        .execute()
    )
    if response.data:
        row = response.data[0] if isinstance(response.data, list) else response.data
        if isinstance(row, dict):
            return row
    return payload


async def clear_implementation_chat(session_id: str, user_id: str) -> None:
    (
        supabase.from_("implementation_chat_messages")
        .delete()
        .eq("session_id", session_id)
        .eq("user_id", user_id)
        .execute()
    )


async def import_implementation_chat_messages(
    session_id: str,
    user_id: str,
    messages: list[dict[str, Any]],
) -> int:
    """One-time import (e.g. browser localStorage migration). Skips if DB already has rows."""
    if not messages:
        return 0

    existing = await count_implementation_chat_messages(session_id)
    if existing > 0:
        return 0

    rows: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        content = (msg.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue

        row: dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "metadata": {"imported_from": "local_storage"},
        }

        mode = msg.get("mode")
        if mode in ("help", "draft", "brainstorm"):
            row["mode"] = mode

        task_id = msg.get("task_id")
        if task_id:
            row["task_id"] = str(task_id)

        created_at = msg.get("created_at") or msg.get("timestamp")
        if created_at:
            row["created_at"] = _parse_created_at(created_at)

        rows.append(row)

    if not rows:
        return 0

    supabase.from_("implementation_chat_messages").insert(rows).execute()
    return len(rows)
