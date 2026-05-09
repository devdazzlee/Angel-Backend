# test development 
from pydantic import BaseModel, Field, model_validator
from typing import Optional

class CreateSessionSchema(BaseModel):
    title: Optional[str] = Field(default="Untitled", max_length=120)


class ModifyIntentSchema(BaseModel):
    """Structured Modify: user guidance + snapshot of the assistant message being revised."""

    assistant_snapshot: str = Field(..., min_length=1, max_length=100_000)
    user_guidance: str = Field(..., min_length=1, max_length=8_000)


class ChatRequestSchema(BaseModel):
    content: str = Field(
        default="",
        max_length=120_000,
        description="User-visible chat text; if modify is set and content is empty, guidance is copied from modify.user_guidance",
    )
    context: Optional[str] = Field(default=None, description="Chat context: 'budget_chat' allows chat during budget transitions")
    modify: Optional[ModifyIntentSchema] = Field(
        default=None,
        description="When set, Angel reworks assistant_snapshot using user_guidance (conversational iteration)",
    )

    @model_validator(mode="after")
    def normalize_content_and_modify(self):
        if self.modify is not None:
            if not (self.content or "").strip():
                object.__setattr__(self, "content", self.modify.user_guidance)
            return self
        # Allow empty content for startup/system-driven turns (e.g., initial question fetch).
        # Interactive user turns still provide non-empty content via the frontend input guard.
        object.__setattr__(self, "content", (self.content or "").strip())
        return self

class RefreshTokenSchema(BaseModel):
    refresh_token: str


class SyncProgressSchema(BaseModel):
    phase: str
    answered_count: int = Field(ge=0)
    asked_q: Optional[str] = None