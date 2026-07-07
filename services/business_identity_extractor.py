"""
Structured extraction for BP.05 (business name), BP.06 (industry), and BP.14 (location).

Single pipeline: tagged questionnaire answer → LLM JSON schema → deterministic structural validator.
Never persists raw chat paragraphs as identity fields.
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


class LocationResult(BaseModel):
    is_operating_location: bool = Field(
        description=(
            "True only when the user describes where the business operates "
            "(geography, region, or channel such as online/mobile/physical)."
        ),
    )
    location: str | None = Field(
        default=None,
        description="Short label (max ~12 words) when is_operating_location is true; otherwise null.",
    )


def tagged_answer_hash(raw_answer: str) -> str:
    return hashlib.sha256(clean_context_value(raw_answer).encode("utf-8")).hexdigest()[:16]


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


def is_valid_location_label(value: str) -> bool:
    """Structural gate for a short location label — same role as is_valid_industry_label."""
    label = clean_context_value(value)
    if not label or not is_meaningful_context_value(label):
        return False
    if len(label) > 80 or len(label.split()) > 12:
        return False
    return True


def bp05_answer_hash(raw_answer: str) -> str:
    return tagged_answer_hash(raw_answer)


def try_parse_business_name_literal(text: str) -> str:
    """
    When BP.05 answer is already a short literal name, use it directly.
    Structural parsing only — no content keyword blocklists.
    """
    line = clean_context_value(text).split("\n")[0].strip()
    if not line:
        return ""

    line = re.sub(
        r"^(?:business\s+name|brand\s+name|company\s+name|name)\s*:\s*",
        "",
        line,
        flags=re.IGNORECASE,
    ).strip()
    line = re.sub(
        r"^(?:it'?s|we(?:'re| are)|i(?:'m| am)|called|named)\s+",
        "",
        line,
        flags=re.IGNORECASE,
    ).strip()

    quoted = re.match(r'^["\'“”‘’]([^"\']+)["\'“”‘’]', line)
    if quoted:
        candidate = quoted.group(1).strip()
        if is_valid_business_name(candidate):
            return candidate

    if ". " in line:
        first_sentence = line.split(". ", 1)[0].strip()
        if is_valid_business_name(first_sentence):
            return first_sentence

    if is_valid_business_name(line):
        return line

    return ""


async def extract_business_name_from_user_answer(user_answer: str) -> str:
    """
    Extract the business name from a BP.05 user message (any phrasing).
    Returns empty string if undecided, invalid, or command — never guesses.
    """
    text = clean_context_value(user_answer)
    if not text or _is_command_like_answer(text):
        return ""

    literal = try_parse_business_name_literal(text)

    system = (
        "You extract the business/brand name from the user's answer to Business Plan question 5 "
        '("Business Name if decided"). Respond with JSON only.\n'
        "Rules:\n"
        "- decided=true when the user gives ANY specific brand or business name, including inside a sentence "
        "(e.g. 'IdeaLink', 'We chose the name AutoFix Pro', 'Business name: Harbor Tea Co.').\n"
        "- decided=false ONLY when they clearly have not chosen a name (unsure, TBD, no name yet, skip).\n"
        "- When decided=true, business_name must be ONLY the name: 1–6 words.\n"
        "- Strip labels like 'Business Name:' from the value.\n"
        "- Do NOT include taglines, explanations, or full sentences.\n"
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
        return literal

    if parsed.decided and parsed.business_name:
        name = clean_context_value(parsed.business_name)
        if is_valid_business_name(name):
            return name

    return literal


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


async def extract_location_from_user_answer(user_answer: str) -> str:
    """Extract a short location label from a BP.14 user message."""
    text = clean_context_value(user_answer)
    if not text or _is_command_like_answer(text):
        return ""

    system = (
        "You extract WHERE the business operates from the user's answer to Business Plan question 14 "
        '("Where will your business be located?"). Respond with JSON only.\n'
        "Set is_operating_location=true only when the answer describes geography or operating channel "
        "(city/region, online, mobile route, physical address, etc.).\n"
        "Set is_operating_location=false when the answer is about future vision, scaling plans, "
        "goals, mission, or other non-location content.\n"
        "When is_operating_location=true, location must be a SHORT label (max ~12 words), "
        "e.g. 'San Diego County, CA', 'Online only', 'Mobile — Los Angeles metro'.\n"
        "Distill long answers into that label; never return the full paragraph."
    )
    user = f"User answer:\n\n{text}"

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
        parsed = LocationResult.model_validate(json.loads(raw_json))
    except Exception as exc:
        print(f"❌ location extraction failed: {exc}")
        return ""

    if not parsed.is_operating_location or not parsed.location:
        return ""

    label = clean_context_value(parsed.location)
    if not is_valid_location_label(label):
        print(f"⚠️ location rejected by validator: {label!r}")
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
        if extracted:
            return extracted, answer_hash
        if is_valid_business_name(stored_name):
            return stored_name, answer_hash
        return "", answer_hash

    if is_valid_business_name(stored_name):
        return stored_name, bp05_hash

    return "", bp05_hash


async def resolve_location_for_session(
    *,
    stored_location: str,
    bp14_raw_answer: str | None,
    bp14_hash: str | None,
) -> tuple[str, str | None]:
    """
    Resolve location for persistence from BP.14 tagged answer.
    Reuses stored value only when hash matches and label validates.
    """
    raw = clean_context_value(bp14_raw_answer or "")
    if raw and not _is_command_like_answer(raw):
        answer_hash = tagged_answer_hash(raw)
        if bp14_hash == answer_hash and is_valid_location_label(stored_location):
            return stored_location, answer_hash
        extracted = await extract_location_from_user_answer(raw)
        return extracted, answer_hash

    if is_valid_location_label(stored_location):
        return stored_location, bp14_hash

    return "", bp14_hash


def get_tagged_user_answer(history: list | None, field: str) -> str:
    """Return raw user answer for the most recent tagged questionnaire prompt."""
    from utils.business_context import TAGGED_QUESTION_FIELD_MAP

    if not history:
        return ""
    tags = TAGGED_QUESTION_FIELD_MAP.get(field)
    if not tags:
        return ""

    question_tags = list(tags)
    return _scan_substantive_answer_after_tagged_question(history, question_tags)


_QUESTION_TAG_PATTERN = re.compile(
    r"\[\[Q:(?P<phase>BUSINESS_PLAN|BP|GKY)\.(?P<num>\d{2})\]\]",
    re.IGNORECASE,
)


def get_tagged_answer_for_question_tag(history: list | None, question_tag: str) -> str:
    """Return the substantive user answer for a specific questionnaire tag (e.g. BUSINESS_PLAN.01)."""
    if not history or not question_tag:
        return ""
    alt = (
        question_tag.replace("BUSINESS_PLAN.", "BP.")
        if question_tag.startswith("BUSINESS_PLAN.")
        else question_tag.replace("BP.", "BUSINESS_PLAN.")
    )
    search_tags = {f"[[Q:{question_tag}]]", f"[[Q:{alt}]]"}
    return _scan_substantive_answer_after_tagged_question(history, list(search_tags))


def _scan_substantive_answer_after_tagged_question(
    history: list,
    search_tags: list[str],
) -> str:
    """
    Find the latest assistant message containing one of search_tags, then return the
    first substantive user reply before a different questionnaire tag is asked.
    Skips command tokens (draft, accept, support, etc.).
    """
    from utils.business_context import _is_command_like_answer

    question_index: int | None = None
    for index, message in enumerate(history):
        if message.get("role") != "assistant":
            continue
        content = message.get("content") or ""
        if any(tag in content for tag in search_tags):
            question_index = index

    if question_index is None:
        return ""

    for idx in range(question_index + 1, len(history)):
        msg = history[idx]
        if msg.get("role") == "assistant":
            content = msg.get("content") or ""
            if "[[Q:" in content and not any(tag in content for tag in search_tags):
                if _QUESTION_TAG_PATTERN.search(content):
                    break
            continue
        if msg.get("role") != "user":
            continue
        raw = clean_context_value(msg.get("content"))
        if not raw or _is_command_like_answer(raw):
            continue
        # Return the FIRST substantive reply — it's the direct answer to the
        # question just asked. Anything the user sends afterward but before the
        # next tagged question (a clarifying follow-up, an aside, a comment on
        # Angel's coaching remarks) is not a redefinition of that answer and must
        # not silently overwrite it. Legitimate revisions go through "go back",
        # which deletes the stale history rows before the new answer is added, so
        # there is never more than one real answer to scan here for that case.
        return raw

    return ""


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
            if any(tag in content for tag in tags):
                question_index_by_field[field] = index

    extracted: dict[str, str] = {}

    for field, tags in TAGGED_QUESTION_FIELD_MAP.items():
        raw = _scan_substantive_answer_after_tagged_question(history, list(tags))
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
        elif field == "location":
            location = await extract_location_from_user_answer(raw)
            if location:
                extracted["location"] = location
                extracted["bp14_raw_answer_hash"] = tagged_answer_hash(raw)
        elif field == "business_idea":
            if is_meaningful_context_value(raw):
                extracted["business_idea"] = raw
        elif field == "business_type":
            if is_meaningful_context_value(raw):
                extracted["business_type"] = raw

    return extracted
