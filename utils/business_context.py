"""Authoritative business context from session storage — no display placeholders."""

from __future__ import annotations

from typing import Any, Callable, Awaitable

BUSINESS_CONTEXT_KEYS = ("business_name", "industry", "location", "business_type")

# Canonical questionnaire tags → context field (single source of truth).
TAGGED_QUESTION_FIELD_MAP: dict[str, tuple[str, ...]] = {
    "business_idea": ("[[Q:BUSINESS_PLAN.01]]", "[[Q:BP.01]]"),
    "business_name": ("[[Q:BUSINESS_PLAN.05]]", "[[Q:BP.05]]"),
    "industry": ("[[Q:BUSINESS_PLAN.06]]", "[[Q:BP.06]]"),
    "business_type": ("[[Q:GKY.03]]",),
    "legal_structure": ("[[Q:BUSINESS_PLAN.24]]", "[[Q:BP.24]]"),
}

_COMMAND_ANSWER_MARKERS = frozenset(
    {"support", "draft", "scrapping", "scraping", "accept", "modify", "kickstart", "help"}
)


def _is_command_like_answer(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return True
    return any(marker in lowered for marker in _COMMAND_ANSWER_MARKERS) and len(lowered) < 40


# Legacy placeholder values that must never be treated as real user data.
INVALID_CONTEXT_VALUES = frozenset(
    {
        "",
        "your business",
        "general business",
        "united states",
        "startup",
        "unsure",
        "none",
        "n/a",
        "not specified",
    }
)


def clean_context_value(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def is_meaningful_context_value(value: Any) -> bool:
    cleaned = clean_context_value(value).lower()
    return bool(cleaned) and cleaned not in INVALID_CONTEXT_VALUES


def resolve_session_business_context(session: dict | None) -> dict[str, Any]:
    """
    Merge session.business_context JSON with top-level session columns.
    Returns empty strings for missing fields — never invented defaults.
    """
    if not session or not isinstance(session, dict):
        return {key: "" for key in BUSINESS_CONTEXT_KEYS}

    stored = session.get("business_context")
    stored_dict = stored if isinstance(stored, dict) else {}

    resolved: dict[str, Any] = {}
    for key in BUSINESS_CONTEXT_KEYS:
        raw = stored_dict.get(key) if stored_dict.get(key) is not None else session.get(key)
        value = clean_context_value(raw)
        if value and value.lower() in INVALID_CONTEXT_VALUES:
            value = ""
        resolved[key] = value

    for key, value in stored_dict.items():
        if key not in resolved:
            resolved[key] = value

    return resolved


def normalize_business_context_for_api(context: dict | None) -> dict[str, Any]:
    """API response shape: core fields as strings, extra keys preserved."""
    from services.business_identity_extractor import is_valid_business_name, is_valid_industry_label

    if not context or not isinstance(context, dict):
        return {key: "" for key in BUSINESS_CONTEXT_KEYS}

    normalized: dict[str, Any] = {key: "" for key in BUSINESS_CONTEXT_KEYS}
    for key in BUSINESS_CONTEXT_KEYS:
        value = clean_context_value(context.get(key))
        if key == "business_name" and value and not is_valid_business_name(value):
            value = ""
        elif key == "industry" and value and not is_valid_industry_label(value):
            value = ""
        if is_meaningful_context_value(value):
            normalized[key] = value

    for key, value in context.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def has_meaningful_context(context: dict | None) -> bool:
    if not context or not isinstance(context, dict):
        return False
    return any(is_meaningful_context_value(context.get(key)) for key in BUSINESS_CONTEXT_KEYS)


def context_field_for_prompt(context: dict, key: str, *, empty_label: str = "") -> str:
    """Use in LLM prompts: real value or empty_label (caller supplies phrasing like 'the business')."""
    value = clean_context_value(context.get(key) if context else "")
    if is_meaningful_context_value(value):
        return value
    return empty_label


def prompt_labels(context: dict | None) -> dict[str, str]:
    """Standard phrasing for LLM prompts when a field is not yet in the database."""
    ctx = context or {}
    return {
        "business_name": context_field_for_prompt(ctx, "business_name", empty_label="the business"),
        "industry": context_field_for_prompt(ctx, "industry", empty_label="this industry"),
        "location": context_field_for_prompt(ctx, "location", empty_label="the venture's location"),
        "business_type": context_field_for_prompt(ctx, "business_type", empty_label="this venture type"),
    }


def business_context_from_session(session: dict | None) -> dict[str, Any]:
    """Resolve context from a session row already loaded from the database."""
    stored = session.get("business_context") if isinstance(session, dict) and isinstance(session.get("business_context"), dict) else {}
    resolved = resolve_session_business_context(session)
    merged = {**(stored or {}), **{k: resolved[k] for k in BUSINESS_CONTEXT_KEYS}}
    return normalize_business_context_for_api(merged)


def coerce_business_context(data: dict | None) -> dict[str, Any]:
    """Accept a session row or a flat session_data dict; return normalized context."""
    if not data:
        return normalize_business_context_for_api({})
    if isinstance(data.get("business_context"), dict) or any(k in data for k in ("asked_q", "current_phase", "id")):
        return business_context_from_session(data)
    return normalize_business_context_for_api(data)


def merge_request_context_overrides(
    base: dict[str, Any],
    overrides: dict | None,
) -> dict[str, Any]:
    """Apply request-body overrides only when values are real (not placeholders)."""
    from services.business_identity_extractor import is_valid_business_name, is_valid_industry_label

    merged = dict(base)
    if not overrides:
        return merged
    for key in BUSINESS_CONTEXT_KEYS:
        value = overrides.get(key)
        if not is_meaningful_context_value(value):
            continue
        value = clean_context_value(value)
        if key == "business_name" and not is_valid_business_name(value):
            continue
        if key == "industry" and not is_valid_industry_label(value):
            continue
        merged[key] = value
    return merged


async def fetch_authoritative_business_context(session_id: str, user_id: str) -> dict[str, Any]:
    """
    Load business context from DB; backfill from chat history when needed.
    Single entry point for routers and services.
    """
    from services.session_service import get_session, patch_session
    from services.chat_service import fetch_chat_history
    from services.angel_service import extract_business_context_from_history

    session = await get_session(session_id, user_id)
    if not session:
        raise ValueError("Session not found")

    normalized, _, _ = await ensure_session_business_context(
        session_id,
        session,
        fetch_history=fetch_chat_history,
        extract_from_history=extract_business_context_from_history,
        patch_session=lambda sid, updates: patch_session(sid, user_id, updates),
    )
    return normalized


async def ensure_session_business_context(
    session_id: str,
    session: dict,
    *,
    fetch_history: Callable[[str], Awaitable[list]],
    extract_from_history: Callable[[list], dict | None],
    patch_session: Callable[..., Awaitable[Any]],
) -> tuple[dict[str, Any], str, bool]:
    """
    Load context from DB; extract from tagged BP answers (structured LLM) and persist.
    Returns (normalized_context, source, updated).
    """
    from services.business_identity_extractor import (
        extract_authoritative_identity_from_history,
        get_tagged_user_answer,
        resolve_business_name_for_session,
    )

    stored = session.get("business_context") if isinstance(session.get("business_context"), dict) else {}
    if stored is None:
        stored = {}

    resolved = resolve_session_business_context(session)
    needs_refresh = not has_meaningful_context(resolved)

    source = "stored"
    updated = False
    history = await fetch_history(session_id)

    tagged = await extract_authoritative_identity_from_history(history)
    merged = dict(stored)

    if tagged:
        for key, value in tagged.items():
            if key == "bp05_raw_answer_hash":
                continue
            if merged.get(key) != value:
                merged[key] = value
                updated = True
        idea = tagged.get("business_idea")
        if idea and not tagged.get("business_name") and merged.get("business_name") == idea:
            merged["business_name"] = ""
            updated = True

    bp05_raw = get_tagged_user_answer(history, "business_name")
    name, bp_hash = await resolve_business_name_for_session(
        stored_name=clean_context_value(merged.get("business_name")),
        bp05_raw_answer=bp05_raw or None,
        bp05_hash=merged.get("bp05_raw_answer_hash"),
    )
    if name != clean_context_value(merged.get("business_name")):
        merged["business_name"] = name
        updated = True
    if bp_hash:
        if merged.get("bp05_raw_answer_hash") != bp_hash:
            merged["bp05_raw_answer_hash"] = bp_hash
            updated = True
    elif merged.get("business_name") and not is_meaningful_context_value(merged.get("business_name")):
        merged["business_name"] = ""
        updated = True

    if updated:
        await patch_session(session_id, {"business_context": merged})
        session = {**session, "business_context": merged}
        resolved = resolve_session_business_context(session)
        source = "tagged_history"

    if needs_refresh and not tagged.get("business_name"):
        extracted = extract_from_history(history) or {}
        if extracted:
            from services.business_identity_extractor import is_valid_business_name, is_valid_industry_label

            for key, value in extracted.items():
                if isinstance(value, str):
                    value = value.strip()
                if key in ("business_name", "bp05_raw_answer_hash"):
                    continue
                if key == "industry":
                    if not is_valid_industry_label(value):
                        continue
                if key in tagged:
                    continue
                if is_meaningful_context_value(value) and merged.get(key) != value:
                    merged[key] = value
                    updated = True
            if updated:
                await patch_session(session_id, {"business_context": merged})
                session = {**session, "business_context": merged}
                resolved = resolve_session_business_context(session)
                source = "extracted"
        elif not tagged:
            source = "empty"

    merged_for_api = business_context_from_session(session)
    if tagged:
        for k, v in tagged.items():
            if k == "bp05_raw_answer_hash":
                merged_for_api["bp05_raw_answer_hash"] = v
            elif k in BUSINESS_CONTEXT_KEYS and is_meaningful_context_value(v):
                merged_for_api[k] = v
    normalized = normalize_business_context_for_api(merged_for_api)
    return normalized, source, updated
