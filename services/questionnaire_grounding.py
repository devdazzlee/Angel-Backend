"""
Authoritative questionnaire context for Draft, Support, and main Angel turns.

Single assembly path: session + tagged history → venture facts the model must not contradict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.business_plan_registry import (
    get_question_meta,
    get_question_objective,
    normalize_business_plan_tag,
)
from utils.business_context import (
    TAGGED_QUESTION_FIELD_MAP,
    coerce_business_context,
    is_meaningful_context_value,
)

# Questionnaire tag → persisted identity field (for syncing prerequisite answers).
TAG_TO_IDENTITY_FIELD: dict[str, str] = {
    "BUSINESS_PLAN.01": "business_idea",
    "BUSINESS_PLAN.05": "business_name",
    "BUSINESS_PLAN.06": "industry",
    "BUSINESS_PLAN.14": "location",
}

FORBIDDEN_DRAFT_PLACEHOLDER_PHRASES = (
    "your business",
    "your industry",
    "your business type",
    "your location",
    "the business",
    "this industry",
    "this venture type",
)


@dataclass(frozen=True)
class QuestionnaireVentureContext:
    """Merged venture identity used to ground command assists and drafts."""

    business_idea: str
    business_name: str
    industry: str
    location: str
    business_type: str
    user_name: str
    prerequisite_answers: dict[str, str]

    def as_dict(self) -> dict[str, str]:
        return {
            "business_idea": self.business_idea,
            "business_name": self.business_name,
            "industry": self.industry,
            "location": self.location,
            "business_type": self.business_type,
            "user_name": self.user_name,
        }

    def has_anchor_idea(self) -> bool:
        return is_meaningful_context_value(self.business_idea)


def draft_output_has_placeholders(text: str) -> bool:
    lower = (text or "").lower()
    return any(phrase in lower for phrase in FORBIDDEN_DRAFT_PLACEHOLDER_PHRASES)


def _sync_prerequisite_answers_into_merged(
    merged: dict[str, Any],
    prerequisite_answers: dict[str, str],
) -> None:
    for tag, answer in prerequisite_answers.items():
        if not is_meaningful_context_value(answer):
            continue
        field = TAG_TO_IDENTITY_FIELD.get(normalize_business_plan_tag(tag))
        if field:
            merged[field] = answer


async def build_questionnaire_venture_context(
    session_data: dict | None,
    history: list | None,
    *,
    asked_q: str,
    get_answer_for_tag,
) -> QuestionnaireVentureContext:
    """Resolve venture facts from tagged answers (source of truth) merged with session."""
    from services.business_identity_extractor import (
        extract_authoritative_identity_from_history,
        get_tagged_user_answer,
    )
    from services.business_plan_registry import collect_draft_prerequisite_answers

    session_data = session_data or {}
    history = history or []
    ctx = coerce_business_context(session_data)
    stored_bc = session_data.get("business_context") or {}

    merged: dict[str, Any] = dict(ctx)
    for key in ("business_idea", "business_name", "industry", "location", "business_type"):
        stored_val = stored_bc.get(key)
        if is_meaningful_context_value(stored_val):
            merged[key] = stored_val

    tagged = await extract_authoritative_identity_from_history(history)
    for key, value in tagged.items():
        if key.endswith("_hash"):
            continue
        if is_meaningful_context_value(value):
            merged[key] = value

    for field in TAGGED_QUESTION_FIELD_MAP:
        tagged_answer = get_tagged_user_answer(history, field)
        if is_meaningful_context_value(tagged_answer):
            merged[field] = tagged_answer

    prerequisite_answers = collect_draft_prerequisite_answers(
        history,
        asked_q,
        get_answer_for_tag=get_answer_for_tag,
    )
    _sync_prerequisite_answers_into_merged(merged, prerequisite_answers)

    stored_bc = session_data.get("business_context") or {}
    user_name = (
        stored_bc.get("user_name")
        or session_data.get("user_name")
        or "the founder"
    )

    return QuestionnaireVentureContext(
        business_idea=str(merged.get("business_idea") or ""),
        business_name=str(merged.get("business_name") or ""),
        industry=str(merged.get("industry") or ""),
        location=str(merged.get("location") or ""),
        business_type=str(merged.get("business_type") or ""),
        user_name=str(user_name),
        prerequisite_answers=prerequisite_answers,
    )


def format_authoritative_context_block(
    venture: QuestionnaireVentureContext,
    *,
    asked_q: str,
) -> str:
    """System-prompt block: facts the model must treat as ground truth."""
    meta = get_question_meta(asked_q)
    lines: list[str] = [
        "AUTHORITATIVE VENTURE CONTEXT (from this founder's questionnaire — do not contradict):",
        "Never use placeholder phrases like 'your business' or 'your industry' in the draft.",
    ]

    if is_meaningful_context_value(venture.business_idea):
        lines.append(f'- Business idea (Q1): "{venture.business_idea}"')
    if is_meaningful_context_value(venture.business_name):
        lines.append(f'- Business name (Q5): "{venture.business_name}"')
    if is_meaningful_context_value(venture.industry):
        lines.append(f'- Industry (Q6): "{venture.industry}"')
    if is_meaningful_context_value(venture.location):
        lines.append(f'- Location: "{venture.location}"')
    if is_meaningful_context_value(venture.business_type):
        lines.append(f'- Venture type (GKY): "{venture.business_type}"')

    prior_lines: list[str] = []
    for tag, answer in venture.prerequisite_answers.items():
        norm = normalize_business_plan_tag(tag)
        if norm in TAG_TO_IDENTITY_FIELD and is_meaningful_context_value(
            getattr(venture, TAG_TO_IDENTITY_FIELD[norm], "")
        ):
            continue
        if not is_meaningful_context_value(answer):
            continue
        label = get_question_objective(tag) or tag
        prior_lines.append(f'  • Q{int(tag.split(".")[-1])} — {label}: "{answer}"')

    if prior_lines:
        lines.append("")
        lines.append("Prior questionnaire answers (grounding only — do not copy verbatim):")
        lines.extend(prior_lines)

    if meta:
        lines.extend(
            [
                "",
                f'You are drafting the answer to Question {meta.number} only:',
                f'  "{meta.prompt_text}"',
                "",
                "Rules:",
                "- Use ONLY facts above; never invent a different business model or industry.",
                "- Do NOT repeat prior answers verbatim — add NEW detail this question asks for.",
                "- Write in first person as the founder; paste-ready prose.",
            ]
        )
        if meta.is_business_name_question:
            lines.append(
                "- Output ONLY the business name (1–4 words) or exactly: Not decided yet"
            )
        elif meta.is_industry_question:
            lines.append(
                "- Write 2–4 sentences naming the primary industry and specific sub-sector(s) "
                "you target, grounded in the business idea and prior answers."
            )
        if meta.draft_grounding:
            lines.append(f"- {meta.draft_grounding}")

    return "\n".join(lines)
