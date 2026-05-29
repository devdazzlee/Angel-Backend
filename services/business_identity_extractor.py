"""
Structured extraction for BP.05 (business name) and BP.06 (industry).

Single pipeline: tagged questionnaire answer → LLM JSON schema → deterministic validator.
Never invents a name when the user has not decided. Never stores raw chat paragraphs as business_name.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from utils.business_context import (
    INVALID_CONTEXT_VALUES,
    _is_command_like_answer,
    clean_context_value,
    is_meaningful_context_value,
)

_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_MODEL = os.getenv("BUSINESS_IDENTITY_MODEL", "gpt-4o-mini")

# Sentence / narrative markers — valid brand names must not contain these.
_NAME_REJECT_RE = re.compile(
    r"\b(represents|representing|focused|specializ\w*|because|which|that|falls\s+under|"
    r"industry|sector|mission|values|comfort|quality|premium|brand\s+focused)\b",
    re.IGNORECASE,
)

_INDECISIVE_RE = re.compile(
    r"\b(not\s+decided|not\s+sure|don'?t\s+know|do\s+not\s+know|haven'?t\s+decided|"
    r"still\s+thinking|tbd|undecided|no\s+name\s+yet)\b",
    re.IGNORECASE,
)


class BusinessNameResult(BaseModel):
    decided: bool = Field(description="True only if the user provided a specific business/brand name.")
    business_name: str | None = Field(
        default=None,
        description="1–4 word brand name only when decided is true; otherwise null.",
    )


class IndustryResult(BaseModel):
    industry: str | None = Field(
        default=None,
        description="Short industry label (e.g. retail, home textiles), not a full sentence.",
    )


def is_valid_business_name(value: str) -> bool:
    """Deterministic gate — only names that pass are persisted or shown."""
    name = clean_context_value(value)
    if not name or not is_meaningful_context_value(name):
        return False
    if _INDECISIVE_RE.search(name):
        return False
    if _NAME_REJECT_RE.search(name):
        return False
    if len(name) > 60 or len(name) < 2:
        return False
    if name.count(".") > 0 or "?" in name or "!" in name:
        return False
    words = name.split()
    if len(words) > 6 or len(words) < 1:
        return False
    lower = name.lower()
    if lower in INVALID_CONTEXT_VALUES:
        return False
    return True


def is_valid_industry_label(value: str) -> bool:
    label = clean_context_value(value)
    if not label or not is_meaningful_context_value(label):
        return False
    if len(label) > 80 or len(label.split()) > 10:
        return False
    if _NAME_REJECT_RE.search(label) and "textile" not in label.lower():
        return False
    return True


def bp05_answer_hash(raw_answer: str) -> str:
    return hashlib.sha256(clean_context_value(raw_answer).encode("utf-8")).hexdigest()[:16]


async def extract_business_name_from_user_answer(user_answer: str) -> str:
    """
    Extract the business name from a BP.05 user message (any phrasing).
    Returns empty string if undecided, invalid, or command — never guesses.
    """
    text = clean_context_value(user_answer)
    if not text or _is_command_like_answer(text):
        return ""

    system = (
        "You extract the business/brand name from the user's answer to Business Plan question 5 "
        '("Business Name if decided"). Respond with JSON only.\n'
        "Rules:\n"
        "- decided=false when the user has not chosen a name (unsure, TBD, thinking, no name, skip).\n"
        "- When decided=true, business_name must be ONLY the name: 1–4 words (e.g. TowelNest, Blue Harbor Tea).\n"
        "- Strip labels like 'Business Name:' from the value.\n"
        "- Do NOT include taglines, explanations, or sentences ('it represents…').\n"
        "- Do NOT invent a name that the user did not provide."
    )
    user = f"User answer to Business Name (if decided):\n\n{text}"

    try:
        response = await _client.chat.completions.create(
            model=_MODEL,
            temperature=0,
            max_tokens=80,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        raw_json = response.choices[0].message.content or "{}"
        parsed = BusinessNameResult.model_validate(json.loads(raw_json))
    except Exception as exc:
        print(f"❌ business_name extraction failed: {exc}")
        return ""

    if not parsed.decided or not parsed.business_name:
        return ""

    name = clean_context_value(parsed.business_name)
    if not is_valid_business_name(name):
        print(f"⚠️ business_name rejected by validator: {name!r}")
        return ""

    return name


async def extract_industry_from_user_answer(user_answer: str) -> str:
    """Extract a short industry label from a BP.06 user message."""
    text = clean_context_value(user_answer)
    if not text or _is_command_like_answer(text):
        return ""

    system = (
        "You extract the primary industry label from the user's answer to Business Plan question 6 "
        '("What industry does your business fall into?"). JSON only.\n'
        "Return industry as a short phrase (2–6 words), e.g. 'retail and home textiles', 'food delivery', 'SaaS'.\n"
        "Do NOT return full sentences or repeat the business name as the industry."
    )
    user = f"User answer:\n\n{text}"

    try:
        response = await _client.chat.completions.create(
            model=_MODEL,
            temperature=0,
            max_tokens=100,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        raw_json = response.choices[0].message.content or "{}"
        parsed = IndustryResult.model_validate(json.loads(raw_json))
    except Exception as exc:
        print(f"❌ industry extraction failed: {exc}")
        return ""

    if not parsed.industry:
        return ""

    label = clean_context_value(parsed.industry)
    if not is_valid_industry_label(label):
        return ""
    return label


async def resolve_business_name_for_session(
    *,
    stored_name: str,
    bp05_raw_answer: str | None,
    bp05_hash: str | None,
) -> tuple[str, str | None]:
    """
    Resolve business_name for persistence.
    Returns (name, new_bp05_hash). Reuses stored name only if hash matches and name validates.
    """
    raw = clean_context_value(bp05_raw_answer or "")
    if raw and not _is_command_like_answer(raw):
        answer_hash = bp05_answer_hash(raw)
        if bp05_hash == answer_hash and is_valid_business_name(stored_name):
            return stored_name, answer_hash
        extracted = await extract_business_name_from_user_answer(raw)
        return extracted, answer_hash

    if is_valid_business_name(stored_name):
        return stored_name, bp05_hash

    return "", bp05_hash


def get_tagged_user_answer(history: list | None, field: str) -> str:
    """Return raw user answer for a tagged questionnaire field (sync)."""
    from utils.business_context import TAGGED_QUESTION_FIELD_MAP

    if not history:
        return ""
    tags = TAGGED_QUESTION_FIELD_MAP.get(field)
    if not tags:
        return ""

    question_index: int | None = None
    for index, message in enumerate(history):
        if message.get("role") != "assistant":
            continue
        content = message.get("content") or ""
        if any(tag in content for tag in tags):
            question_index = index
            break

    if question_index is None:
        return ""

    answer_index = question_index + 1
    if answer_index >= len(history):
        return ""
    answer_message = history[answer_index]
    if answer_message.get("role") != "user":
        return ""
    return clean_context_value(answer_message.get("content"))


async def extract_authoritative_identity_from_history(history: list | None) -> dict[str, str]:
    """
    Tagged BP/GKY answers → structured identity fields.
    business_name and industry use LLM extraction; business_idea uses raw answer.
    """
    from utils.business_context import TAGGED_QUESTION_FIELD_MAP, _is_command_like_answer

    if not history:
        return {}

    question_index_by_field: dict[str, int] = {}
    for index, message in enumerate(history):
        if message.get("role") != "assistant":
            continue
        content = message.get("content") or ""
        for field, tags in TAGGED_QUESTION_FIELD_MAP.items():
            if field in question_index_by_field:
                continue
            if any(tag in content for tag in tags):
                question_index_by_field[field] = index

    extracted: dict[str, str] = {}

    for field, question_index in question_index_by_field.items():
        answer_index = question_index + 1
        if answer_index >= len(history):
            continue
        answer_message = history[answer_index]
        if answer_message.get("role") != "user":
            continue
        raw = clean_context_value(answer_message.get("content"))
        if not raw or _is_command_like_answer(raw):
            continue

        if field == "business_name":
            name = await extract_business_name_from_user_answer(raw)
            if name:
                extracted["business_name"] = name
                extracted["bp05_raw_answer_hash"] = bp05_answer_hash(raw)
        elif field == "industry":
            industry = await extract_industry_from_user_answer(raw)
            if industry:
                extracted["industry"] = industry
        elif field == "business_idea":
            if is_meaningful_context_value(raw):
                extracted["business_idea"] = raw
        elif field == "business_type":
            if is_meaningful_context_value(raw):
                extracted["business_type"] = raw

    return extracted
