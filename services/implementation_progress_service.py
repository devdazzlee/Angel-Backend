"""
Implementation progress persistence.

Source of truth: implementation_completions table (one row per task/substep).
business_context.completed_implementation_tasks is kept as a denormalized cache
for backward compatibility with roadmap and legacy sessions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from db.supabase import supabase

TABLE = "implementation_completions"
TOTAL_MAIN_TASKS = 25


def completion_key_for(task_id: str, substep_number: Optional[int] = None) -> str:
    if substep_number is not None:
        return f"{task_id}_substep_{substep_number}"
    return task_id


def parse_completion_key(key: str) -> tuple[str, Optional[int]]:
    marker = "_substep_"
    if marker in key:
        task_id, _, raw = key.partition(marker)
        try:
            return task_id, int(raw)
        except ValueError:
            return key, None
    return key, None


def _table_missing(exc: Exception) -> bool:
    text = str(exc).lower()
    return "implementation_completions" in text and (
        "pgrst205" in text or "schema cache" in text or "does not exist" in text or "not found" in text
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def rows_to_legacy_state(rows: list[dict[str, Any]]) -> tuple[list[str], dict[str, str]]:
    completed_tasks: list[str] = []
    substep_notes: dict[str, str] = {}
    seen: set[str] = set()

    for row in rows:
        key = row.get("completion_key")
        if not key or key in seen:
            continue
        seen.add(key)
        completed_tasks.append(key)
        note = (row.get("completion_notes") or "").strip()
        if note:
            substep_notes[key] = note

    return completed_tasks, substep_notes


async def fetch_completions(session_id: str) -> list[dict[str, Any]]:
    try:
        response = (
            supabase.from_(TABLE)
            .select(
                "completion_key, task_id, substep_number, phase, completion_notes, "
                "decision, actions, documents, file_id, completed_at, metadata"
            )
            .eq("session_id", session_id)
            .order("completed_at", desc=False)
            .execute()
        )
        return response.data or []
    except Exception as exc:
        if _table_missing(exc):
            return []
        raise


async def upsert_completion(
    *,
    session_id: str,
    user_id: str,
    task_id: str,
    phase: str,
    substep_number: Optional[int] = None,
    completion_notes: str = "",
    decision: str = "",
    actions: str = "",
    documents: str = "",
    file_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    key = completion_key_for(task_id, substep_number)
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "task_id": task_id,
        "substep_number": substep_number,
        "completion_key": key,
        "phase": phase,
        "completion_notes": completion_notes or None,
        "decision": decision or None,
        "actions": actions or None,
        "documents": documents or None,
        "file_id": file_id,
        "completed_at": _now_iso(),
        "metadata": metadata or {},
    }
    supabase.from_(TABLE).upsert(payload, on_conflict="session_id,completion_key").execute()


async def upsert_completions_batch(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    supabase.from_(TABLE).upsert(rows, on_conflict="session_id,completion_key").execute()


def legacy_lists_from_business_context(
    business_context: dict[str, Any],
) -> tuple[list[str], dict[str, str]]:
    completed = list(business_context.get("completed_implementation_tasks") or [])
    notes_raw = business_context.get("substep_notes") or {}
    notes = dict(notes_raw) if isinstance(notes_raw, dict) else {}
    return completed, notes


def merge_completed_task_lists(*lists: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for items in lists:
        for item in items:
            if item and item not in seen:
                seen.add(item)
                merged.append(item)
    return merged


async def load_legacy_completion_state(
    session_id: str,
    business_context: dict[str, Any],
) -> tuple[list[str], dict[str, str], str]:
    """
    Load completed_tasks + substep_notes for API responses.

    Priority:
      1. implementation_completions table (source of truth)
      2. business_context JSON (legacy / cache)
      3. implementation_tasks table (legacy secondary)
    """
    db_rows = await fetch_completions(session_id)
    if db_rows:
        completed, notes = rows_to_legacy_state(db_rows)
        return completed, notes, "database"

    legacy_completed, legacy_notes = legacy_lists_from_business_context(business_context)
    legacy_from_tasks = _legacy_from_implementation_tasks_table(session_id)
    completed = merge_completed_task_lists(legacy_completed, legacy_from_tasks)

    notes = dict(legacy_notes)
    for key in completed:
        if key not in notes:
            note = _note_from_implementation_tasks_metadata(session_id, key)
            if note:
                notes[key] = note

    return completed, notes, "legacy"


async def ensure_legacy_migrated_if_needed(
    session_id: str,
    user_id: str,
    business_context: dict[str, Any],
    *,
    phase_resolver,
) -> int:
    """
    Backfill implementation_completions when the table is empty but legacy
    session data still has completions. Safe to call on every GET /tasks.
    """
    existing = await fetch_completions(session_id)
    if existing:
        return 0

    completed, notes, source = await load_legacy_completion_state(session_id, business_context)
    if source != "legacy" or not completed:
        return 0

    try:
        written = await migrate_legacy_to_database(
            session_id=session_id,
            user_id=user_id,
            completed_tasks=completed,
            substep_notes=notes,
            phase_resolver=phase_resolver,
        )
        if written:
            print(
                f"✅ Migrated {written} implementation completion(s) to "
                f"implementation_completions for session {session_id}"
            )
        return written
    except Exception as exc:
        print(f"⚠️ implementation_completions migration failed for {session_id}: {exc}")
        return 0


def _legacy_from_implementation_tasks_table(session_id: str) -> list[str]:
    try:
        response = (
            supabase.from_("implementation_tasks")
            .select("task_name, metadata")
            .eq("session_id", session_id)
            .not_.is_("completed_at", "null")
            .execute()
        )
        items: list[str] = []
        for record in response.data or []:
            metadata = record.get("metadata") or {}
            task_id = metadata.get("task_id") if isinstance(metadata, dict) else None
            if not task_id:
                task_id = record.get("task_name")
            if not task_id:
                continue
            substep_number = metadata.get("substep_number") if isinstance(metadata, dict) else None
            key = completion_key_for(task_id, substep_number)
            items.append(key)
        return items
    except Exception:
        return []


def _note_from_implementation_tasks_metadata(session_id: str, completion_key: str) -> str:
    try:
        task_id, substep_number = parse_completion_key(completion_key)
        response = (
            supabase.from_("implementation_tasks")
            .select("metadata")
            .eq("session_id", session_id)
            .eq("task_name", task_id)
            .not_.is_("completed_at", "null")
            .execute()
        )
        for record in response.data or []:
            metadata = record.get("metadata") or {}
            if not isinstance(metadata, dict):
                continue
            meta_substep = metadata.get("substep_number")
            if substep_number is None and meta_substep:
                continue
            if substep_number is not None and meta_substep != substep_number:
                continue
            note = (metadata.get("notes") or "").strip()
            if note:
                return note
    except Exception:
        pass
    return ""


async def migrate_legacy_to_database(
    *,
    session_id: str,
    user_id: str,
    completed_tasks: list[str],
    substep_notes: dict[str, str],
    phase_resolver,
) -> int:
    """Backfill implementation_completions from legacy session data. Returns rows written."""
    existing = await fetch_completions(session_id)
    if existing:
        return 0

    rows: list[dict[str, Any]] = []
    for key in completed_tasks:
        task_id, substep_number = parse_completion_key(key)
        rows.append(
            {
                "session_id": session_id,
                "user_id": user_id,
                "task_id": task_id,
                "substep_number": substep_number,
                "completion_key": key,
                "phase": phase_resolver(task_id),
                "completion_notes": substep_notes.get(key) or None,
                "completed_at": _now_iso(),
                "metadata": {"migrated_from": "business_context"},
            }
        )

    if rows:
        await upsert_completions_batch(rows)
    return len(rows)


async def persist_completion_keys(
    *,
    session_id: str,
    user_id: str,
    task_id: str,
    phase: str,
    completion_keys: list[str],
    notes_by_key: dict[str, str],
    decision: str = "",
    actions: str = "",
    documents: str = "",
    file_id: Optional[str] = None,
    phase_resolver=None,
) -> None:
    """Write all completion keys for a complete/substep action."""
    resolve_phase = phase_resolver or (lambda _tid: phase)
    try:
        rows: list[dict[str, Any]] = []
        for key in completion_keys:
            key_task_id, substep_number = parse_completion_key(key)
            rows.append(
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "task_id": key_task_id,
                    "substep_number": substep_number,
                    "completion_key": key,
                    "phase": resolve_phase(key_task_id),
                    "completion_notes": notes_by_key.get(key) or None,
                    "decision": decision or None,
                    "actions": actions or None,
                    "documents": documents or None,
                    "file_id": file_id,
                    "completed_at": _now_iso(),
                    "metadata": {},
                }
            )
        await upsert_completions_batch(rows)
    except Exception as exc:
        if _table_missing(exc):
            print(
                "Note: implementation_completions table missing — "
                "run db/sql_schemas/implementation_completions_schema.sql"
            )
            return
        raise


def build_business_context_cache(
    business_context: dict[str, Any],
    completed_tasks: list[str],
    substep_notes: dict[str, str],
    *,
    last_completed: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Denormalized cache written alongside DB rows."""
    updated = dict(business_context)
    updated["completed_implementation_tasks"] = completed_tasks
    updated["substep_notes"] = substep_notes
    if last_completed:
        updated["last_completed_task"] = last_completed
    return updated
