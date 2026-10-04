"""
Public guest Angel chat — additive parallel to authenticated /angel routes.

No JWT required except /claim.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from middlewares.auth import verify_auth_token
from services.guest_session_service import (
    claim_guest_session,
    guest_chat,
    start_guest_session,
)
from services.guest_session_store import get_guest_session, public_guest_view

router = APIRouter(tags=["Guest Angel"])


class GuestCreateSchema(BaseModel):
    title: Optional[str] = Field(default="Guest chat", max_length=120)


class GuestChatSchema(BaseModel):
    content: str = Field(default="", max_length=120_000)


class GuestClaimSchema(BaseModel):
    guest_token: Optional[str] = None
    snapshot: Optional[dict[str, Any]] = None


def _require_guest_token(
    x_guest_token: Optional[str] = Header(default=None, alias="X-Guest-Token"),
) -> str:
    if not x_guest_token or not x_guest_token.strip():
        raise HTTPException(
            status_code=401,
            detail={
                "code": "GUEST_TOKEN_REQUIRED",
                "message": "Missing X-Guest-Token header",
            },
        )
    return x_guest_token.strip()


@router.post("/sessions")
async def create_guest(payload: GuestCreateSchema):
    result = await start_guest_session(title=payload.title or "Guest chat")
    return {
        "success": True,
        "message": "Guest session started",
        "result": result,
    }


@router.get("/sessions/{session_id}")
async def get_guest(
    session_id: str,
    guest_token: str = Depends(_require_guest_token),
):
    try:
        session = get_guest_session(guest_token, session_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "GUEST_NOT_FOUND",
                "message": "Guest session not found or expired",
            },
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "GUEST_FORBIDDEN", "message": str(exc)},
        )

    return {
        "success": True,
        "message": "Guest session fetched",
        "result": public_guest_view(session),
    }


@router.get("/sessions/{session_id}/history")
async def guest_history(
    session_id: str,
    guest_token: str = Depends(_require_guest_token),
):
    try:
        session = get_guest_session(guest_token, session_id)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "GUEST_NOT_FOUND",
                "message": "Guest session not found or expired",
            },
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": "GUEST_FORBIDDEN", "message": str(exc)},
        )

    return {
        "success": True,
        "message": "Guest chat history fetched",
        "data": session.get("history") or [],
    }


@router.post("/sessions/{session_id}/chat")
async def post_guest_chat(
    session_id: str,
    payload: GuestChatSchema,
    guest_token: str = Depends(_require_guest_token),
):
    result = await guest_chat(guest_token, session_id, payload.content)
    return {
        "success": True,
        "message": "Guest chat reply",
        "result": result,
    }


@router.post("/sessions/claim", dependencies=[Depends(verify_auth_token)])
async def claim_guest(request: Request, payload: GuestClaimSchema):
    user_id = request.state.user["id"]
    if not payload.guest_token and not payload.snapshot:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "GUEST_CLAIM_INVALID",
                "message": "Provide guest_token and/or snapshot",
            },
        )

    result = await claim_guest_session(
        user_id=user_id,
        guest_token=payload.guest_token,
        snapshot=payload.snapshot,
    )
    return {
        "success": True,
        "message": "Guest session claimed",
        "result": result,
    }
