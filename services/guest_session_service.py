"""Guest chat orchestration — reuses Angel GKY logic without touching /angel auth flow."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import HTTPException

from services.angel_service import get_angel_reply
from services.guest_session_store import (
    GUEST_MESSAGE_LIMIT,
    create_guest_session,
    get_guest_session,
    mark_guest_claimed,
    public_guest_view,
    save_guest_session,
)
from services.session_service import create_session, patch_session
from services.chat_service import save_chat_message
from db.supabase import supabase


def _session_for_angel(guest: dict[str, Any]) -> dict[str, Any]:
    """Shape guest record like a chat_sessions row for get_angel_reply."""
    return {
        "id": guest["id"],
        "user_id": None,
        "title": guest.get("title"),
        "current_phase": guest.get("current_phase", "GKY"),
        "asked_q": guest.get("asked_q", "GKY.01"),
        "answered_count": guest.get("answered_count", 0),
        "business_context": deepcopy(guest.get("business_context") or {}),
    }


def _merge_gky_context(guest: dict[str, Any], content: str, tag: str) -> None:
    """Lightweight in-memory GKY context (mirrors patch_session_context_from_response)."""
    if not tag or not tag.startswith("GKY.") or not (content or "").strip():
        return
    lower = content.strip().lower()
    if lower in {"support", "draft", "scrapping", "accept", "modify", "proceed"}:
        return
    if lower.startswith("scrapping:") or lower.startswith("draft"):
        return

    ctx = guest.setdefault("business_context", {})
    if tag == "GKY.01":
        ctx["user_name"] = content.strip()
    elif tag == "GKY.02":
        ctx["has_business_experience"] = "yes" in lower
    elif tag == "GKY.03":
        ctx["business_type"] = content.strip()
    elif tag == "GKY.04":
        ctx["skills_assessment"] = content.strip()
    elif tag == "GKY.05":
        ctx["greatest_concern"] = content.strip()


async def start_guest_session(title: str = "Guest chat") -> dict[str, Any]:
    guest = create_guest_session(title=title)
    # Seed opening Angel turn (same empty-content pattern as authenticated chat)
    return await guest_chat(guest["guest_token"], guest["id"], content="")


async def guest_chat(guest_token: str, session_id: str, content: str) -> dict[str, Any]:
    guest = get_guest_session(guest_token, session_id)

    if guest.get("requires_auth_to_continue") or guest.get("awaiting_gky_proceed"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "GUEST_AUTH_REQUIRED",
                "message": "Sign up or log in to continue after Getting to Know You.",
                "requires_auth": True,
            },
        )

    phase = guest.get("current_phase", "GKY")
    if phase not in ("GKY",):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "GUEST_AUTH_REQUIRED",
                "message": "Guest chat is limited to Getting to Know You. Please log in to continue.",
                "requires_auth": True,
            },
        )

    text = (content or "").strip()
    is_user_turn = bool(text)

    if is_user_turn and guest.get("user_message_count", 0) >= GUEST_MESSAGE_LIMIT:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "GUEST_LIMIT",
                "message": "Guest chat is limited to 5 messages. Please log in or sign up to continue.",
                "requires_auth": True,
                "user_message_count": guest.get("user_message_count", 0),
                "message_limit": GUEST_MESSAGE_LIMIT,
            },
        )

    history = list(guest.get("history") or [])
    current_tag = guest.get("asked_q", "GKY.01")

    if is_user_turn:
        history.append({"role": "user", "content": text})
        guest["user_message_count"] = int(guest.get("user_message_count", 0)) + 1
        _merge_gky_context(guest, text, current_tag)

    angel_session = _session_for_angel(guest)
    # Merge business_context keys onto session for recap helpers
    for key, value in (guest.get("business_context") or {}).items():
        angel_session[key] = value

    pre_update_asked_q = angel_session.get("asked_q")

    angel_response = await get_angel_reply(
        {"role": "user", "content": text},
        history,
        angel_session,
        modify_intent=None,
    )

    if isinstance(angel_response, dict):
        assistant_reply = angel_response.get("reply", "")
        transition_phase = angel_response.get("transition_phase")
        session_update = angel_response.get("patch_session") or {}
        awaiting_gky_proceed = bool(angel_response.get("awaiting_gky_proceed"))
        web_search_status = angel_response.get(
            "web_search_status", {"is_searching": False, "query": None}
        )
        immediate_response = angel_response.get("immediate_response")
        show_accept_modify = angel_response.get("show_accept_modify", False)
    else:
        assistant_reply = str(angel_response)
        transition_phase = None
        session_update = {}
        awaiting_gky_proceed = False
        web_search_status = {"is_searching": False, "query": None}
        immediate_response = None
        show_accept_modify = False

    # Apply angel session mutations back onto guest
    guest["asked_q"] = angel_session.get("asked_q", guest.get("asked_q"))
    guest["answered_count"] = angel_session.get(
        "answered_count", guest.get("answered_count", 0)
    )
    guest["current_phase"] = angel_session.get(
        "current_phase", guest.get("current_phase", "GKY")
    )
    if session_update:
        guest.update({k: v for k, v in session_update.items() if k != "business_context"})
        if "business_context" in session_update and isinstance(
            session_update["business_context"], dict
        ):
            guest.setdefault("business_context", {}).update(
                session_update["business_context"]
            )

    # Progress bump for sequential GKY answers (mirrors authenticated router)
    if (
        is_user_turn
        and pre_update_asked_q
        and pre_update_asked_q.startswith("GKY.")
        and pre_update_asked_q != "GKY.05_ACK"
        and text.lower() not in ("", "accept", "modify", "support", "draft", "scrapping")
    ):
        # Only increment when angel advanced the tag or completed GKY
        new_tag = guest.get("asked_q")
        if transition_phase == "GKY_TO_BUSINESS_PLAN" or (
            new_tag and new_tag != pre_update_asked_q
        ):
            guest["answered_count"] = min(5, int(guest.get("answered_count", 0)) + 1)

    if transition_phase == "GKY_TO_BUSINESS_PLAN" or awaiting_gky_proceed:
        guest["current_phase"] = "BUSINESS_PLAN_INTRO"
        guest["asked_q"] = "GKY.05_ACK"
        guest["awaiting_gky_proceed"] = True
        guest["requires_auth_to_continue"] = True
        # Save transition reply into history so claim restores the same UX
        if assistant_reply:
            history.append({"role": "assistant", "content": assistant_reply})
    elif assistant_reply:
        history.append({"role": "assistant", "content": assistant_reply})

    guest["history"] = history
    save_guest_session(guest)

    answered = int(guest.get("answered_count", 0))
    progress = {
        "phase": "GKY",
        "answered": answered,
        "total": 5,
        "percent": int((answered / 5) * 100) if answered else 0,
        "asked_q": guest.get("asked_q"),
        "overall_progress": {
            "answered": answered,
            "total": 5,
            "percent": int((answered / 5) * 100) if answered else 0,
            "scope": "gky",
            "phase_breakdown": {
                "gky_completed": answered,
                "gky_total": 5,
                "bp_completed": 0,
                "bp_total": 45,
            },
        },
    }

    view = public_guest_view(guest)
    return {
        "reply": assistant_reply,
        "progress": progress,
        "session_id": guest["id"],
        "web_search_status": web_search_status,
        "immediate_response": immediate_response,
        "transition_phase": transition_phase,
        "awaiting_gky_proceed": bool(guest.get("awaiting_gky_proceed")),
        "requires_auth_to_continue": bool(guest.get("requires_auth_to_continue")),
        "show_accept_modify": show_accept_modify,
        "guest": view,
    }


async def claim_guest_session(
    user_id: str,
    guest_token: str | None = None,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Promote a guest chat into a real authenticated venture session and history.
    Prefer server guest store; fall back to client snapshot if store was lost.
    """
    guest: dict[str, Any] | None = None
    if guest_token:
        try:
            guest = get_guest_session(guest_token)
        except (KeyError, PermissionError):
            guest = None

    if guest is None and snapshot:
        guest = {
            "guest_token": snapshot.get("guest_token") or guest_token or str(uuid_fallback()),
            "id": snapshot.get("session_id") or snapshot.get("id"),
            "title": snapshot.get("title") or "Guest chat",
            "current_phase": snapshot.get("current_phase") or "BUSINESS_PLAN_INTRO",
            "asked_q": snapshot.get("asked_q") or "GKY.05_ACK",
            "answered_count": snapshot.get("answered_count", 5),
            "business_context": snapshot.get("business_context") or {},
            "history": snapshot.get("history") or [],
            "awaiting_gky_proceed": bool(snapshot.get("awaiting_gky_proceed", True)),
            "requires_auth_to_continue": True,
        }

    if not guest:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "GUEST_NOT_FOUND",
                "message": "Guest chat expired or was not found. Please start again.",
            },
        )

    title = guest.get("title") or "My venture"
    real = await create_session(user_id, title)
    real_id = real["id"]

    # Restore GKY completion state so user continues at Business Plan intro
    phase = guest.get("current_phase") or "GKY"
    asked_q = guest.get("asked_q") or "GKY.01"
    answered = int(guest.get("answered_count") or 0)
    if guest.get("awaiting_gky_proceed") or guest.get("requires_auth_to_continue"):
        phase = "BUSINESS_PLAN_INTRO"
        asked_q = "GKY.05_ACK"
        answered = max(answered, 5)

    updates: dict[str, Any] = {
        "current_phase": phase,
        "asked_q": asked_q,
        "answered_count": answered,
    }
    ctx = guest.get("business_context") or {}
    if ctx:
        updates["business_context"] = ctx

    await patch_session(real_id, user_id, updates)

    for msg in guest.get("history") or []:
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and content:
            await save_chat_message(real_id, user_id, role, content)

    token = guest.get("guest_token") or guest_token
    if token:
        mark_guest_claimed(token)

    # Re-fetch for response
    refreshed = (
        supabase.from_("chat_sessions")
        .select("*")
        .eq("id", real_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    session_row = refreshed.data if refreshed.data else {**real, **updates}

    return {
        "session_id": real_id,
        "session": session_row,
        "awaiting_gky_proceed": phase == "BUSINESS_PLAN_INTRO",
        "resume_path": f"/ventures/{real_id}",
    }


def uuid_fallback() -> str:
    import uuid

    return str(uuid.uuid4())
