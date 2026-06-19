from __future__ import annotations

from typing import Any, Optional

from db.supabase import supabase

SELECT_COLUMNS = (
    "id, session_id, user_id, task_id, file_id, original_filename, "
    "content_type, size_bytes, storage_bucket, storage_path, created_at"
)


def _format_supabase_error(exc: Exception) -> str:
    text = str(exc)
    if "PGRST205" in text or "schema cache" in text.lower():
        return (
            "Supabase has not refreshed its API schema yet. "
            "Wait 1–2 minutes, or run `NOTIFY pgrst, 'reload schema';` in the SQL Editor, then retry."
        )
    return text


async def insert_implementation_document(
    *,
    session_id: str,
    user_id: str,
    task_id: str,
    file_id: str,
    original_filename: str,
    content_type: str,
    size_bytes: int,
    storage_bucket: str,
    storage_path: str,
) -> dict[str, Any]:
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "task_id": task_id,
        "file_id": file_id,
        "original_filename": original_filename,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "storage_bucket": storage_bucket,
        "storage_path": storage_path,
    }

    # Use postgrest explicitly (same as chat_history inserts elsewhere).
    response = supabase.postgrest.from_("implementation_task_documents").insert(payload).execute()

    if response.data:
        row = response.data[0] if isinstance(response.data, list) else response.data
        if isinstance(row, dict):
            return row
    return payload


async def list_implementation_documents(
    session_id: str,
    task_id: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    response = (
        supabase.postgrest.from_("implementation_task_documents")
        .select(SELECT_COLUMNS)
        .eq("session_id", session_id)
        .eq("task_id", task_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


async def get_implementation_document(
    session_id: str,
    user_id: str,
    file_id: str,
) -> Optional[dict[str, Any]]:
    response = (
        supabase.postgrest.from_("implementation_task_documents")
        .select(SELECT_COLUMNS)
        .eq("session_id", session_id)
        .eq("user_id", user_id)
        .eq("file_id", file_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None
