"""
Resolve affirmation vs constructive feedback intensities per Angel reply.

- Profile slider (`feedback_intensity`) maps to complementary affirmation/constructive
  balance unless the session is explicitly locked via response-config PATCH.
- Answer substance (deterministic heuristics) nudges tone one step when the user is
  clearly vague or clearly detailed — without extra LLM calls.
"""
from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from utils.constant import (
    DEFAULT_AFFIRMATION_INTENSITY,
    DEFAULT_CONSTRUCTIVE_FEEDBACK_INTENSITY,
)

TONE_SESSION_LOCKED_KEY = "response_tone_session_locked"

_HEDGE_PHRASES = frozenset({
    "maybe", "not sure", "i don't know", "i guess", "kind of", "sort of",
    "probably", "perhaps", "i think", "i'm not sure", "no idea", "unsure",
    "something like", "whatever",
})

_GENERIC_ANSWERS = frozenset({
    "yes", "no", "ok", "okay", "sure", "n/a", "none", "idk", "yep", "nope",
})


def assess_answer_substance(user_text: str) -> float:
    """
    Return 0..1: higher means more concrete / effortful text.
    Used only for a ±1 intensity nudge, not for blocking or scoring the user.
    """
    t = user_text.strip()
    if not t:
        return 0.0
    low = t.lower()
    if low in _GENERIC_ANSWERS:
        return 0.12
    words = re.findall(r"[A-Za-z']+", low)
    wc = len(words)
    if wc < 4:
        base = 0.18
    elif wc < 12:
        base = 0.35
    elif wc < 35:
        base = 0.55
    else:
        base = 0.72
    if len(re.findall(r"\d", t)) >= 2:
        base += 0.08
    if re.search(r"\b(usd|\$|€|£|percent|%)\b", low):
        base += 0.05
    hedge_hits = sum(1 for h in _HEDGE_PHRASES if h in low)
    base -= min(0.22, hedge_hits * 0.06)
    return max(0.0, min(1.0, round(base, 3)))


def _clamp_intensity(n: int) -> int:
    return max(0, min(10, int(n)))


def _coerce_intensity(value: Any, default: int) -> int:
    """None-safe / type-safe coercion to a 0-10 intensity.

    Stored prefs and `business_context` come from JSON columns that may legitimately
    contain `null` (key present, value None) or accidentally a non-numeric string.
    Falling through to `int(None)` would raise on the chat path, so anything we
    can't cleanly convert falls back to the documented default.
    """
    if value is None:
        return _clamp_intensity(default)
    try:
        return _clamp_intensity(int(value))
    except (TypeError, ValueError):
        return _clamp_intensity(default)


def apply_substance_tone_nudge(
    affirmation: int,
    constructive: int,
    substance: float,
) -> tuple[int, int]:
    """Bias toward constructive coaching for low-substance answers.

    - Very low substance: stronger constructive nudge (+2 / -2)
    - Low substance: light constructive nudge (+1 / -1)
    - High substance: ease back critique slightly (+1 affirmation / -1 constructive)
    """
    aff, cfb = affirmation, constructive
    if substance < 0.22:
        cfb = _clamp_intensity(cfb + 2)
        aff = _clamp_intensity(aff - 2)
    elif substance < 0.38:
        cfb = _clamp_intensity(cfb + 1)
        aff = _clamp_intensity(aff - 1)
    elif substance > 0.84:
        aff = _clamp_intensity(aff + 1)
        cfb = _clamp_intensity(cfb - 1)
    return aff, cfb


def compute_effective_tone_intensities(
    session_data: Optional[Mapping[str, Any]],
    user_prefs: Optional[Mapping[str, Any]],
    user_message: str,
    *,
    is_command_message: bool,
    tone_assessment_text: Optional[str] = None,
) -> tuple[int, int]:
    """
    Effective (affirmation, constructive) for this turn.

    Unlocked sessions: constructive = profile `feedback_intensity`,
    affirmation = 10 - constructive (balanced tradeoff).

    Locked sessions: use `business_context` affirmation_intensity and
    constructive_feedback_intensity from PATCH /response-config.
    """
    prefs = user_prefs or {}
    bc: dict[str, Any] = {}
    if session_data:
        raw = session_data.get("business_context")
        if isinstance(raw, dict):
            bc = raw

    fi = _coerce_intensity(prefs.get("feedback_intensity"), DEFAULT_CONSTRUCTIVE_FEEDBACK_INTENSITY)

    if bool(bc.get(TONE_SESSION_LOCKED_KEY)):
        aff = _coerce_intensity(bc.get("affirmation_intensity"), DEFAULT_AFFIRMATION_INTENSITY)
        cfb = _coerce_intensity(bc.get("constructive_feedback_intensity"), DEFAULT_CONSTRUCTIVE_FEEDBACK_INTENSITY)
    else:
        cfb = fi
        aff = _clamp_intensity(10 - fi)

    if is_command_message:
        return aff, cfb

    substance_source = (
        tone_assessment_text if tone_assessment_text is not None else user_message
    )
    substance = assess_answer_substance(substance_source)
    return apply_substance_tone_nudge(aff, cfb, substance)
