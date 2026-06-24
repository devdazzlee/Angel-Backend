"""Shared detection and parsing for questionnaire quick-action commands."""

from __future__ import annotations

import re

_EXACT_COMMANDS = frozenset(
    {
        "draft",
        "support",
        "scrapping",
        "scraping",
        "draft more",
        "draft answer",
        "accept",
        "modify",
    }
)

_PREFIX_COMMANDS = ("scrapping:", "scraping:", "support:", "draft:")

_SCRAPPING_PREFIX = re.compile(r"^\s*scrapp?ing\s*:\s*", re.IGNORECASE)


def is_questionnaire_command(text: str) -> bool:
    """True when the user turn is Draft/Support/Scrapping/etc., not a questionnaire answer."""
    lowered = (text or "").strip().lower()
    if not lowered:
        return False
    if lowered in _EXACT_COMMANDS:
        return True
    return any(lowered.startswith(prefix) for prefix in _PREFIX_COMMANDS)


def parse_scrapping_notes(text: str) -> str:
    """Extract founder notes from `Scrapping: …` regardless of capitalization."""
    return _SCRAPPING_PREFIX.sub("", (text or "").strip()).strip()
