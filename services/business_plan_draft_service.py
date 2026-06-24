"""
Business Plan Draft command — uses the same authoritative context path as Modify/main chat.
"""

from __future__ import annotations

from typing import Any, Literal

from services.business_plan_registry import get_question_meta
from services.questionnaire_grounding import (
    QuestionnaireVentureContext,
    build_questionnaire_venture_context,
    draft_output_has_placeholders,
    format_authoritative_context_block,
)

DraftMode = Literal["prose", "business_name", "industry_label"]

DRAFT_COMMAND_SYSTEM = """You draft Business Plan questionnaire answers for founders.

Output ONLY the draft answer text — no preamble, no "Here's a draft", no follow-up questions.
Stay within the word limit. Use first person ("I/we") when writing prose.
Never invent facts not present in AUTHORITATIVE VENTURE CONTEXT.
Never use placeholder phrases such as "your business", "your industry", "your business type", or "your location".
Never substitute a generic SaaS, consulting, or retail business unless the founder's Q1 idea says so."""


def resolve_draft_mode(asked_q: str) -> DraftMode:
    meta = get_question_meta(asked_q)
    if not meta:
        return "prose"
    if meta.is_business_name_question:
        return "business_name"
    if meta.is_industry_question:
        return "industry_label"
    return "prose"


def _format_thought_starter_hints(starters: list[str] | None) -> str:
    if not starters:
        return ""
    bullets = "\n".join(f"  • {s}" for s in starters[:3])
    return (
        "Angles to cover (add detail beyond prior answers — do not repeat Q1):\n"
        f"{bullets}"
    )


def _format_research_block(research_results: str | None) -> str:
    if not research_results:
        return (
            "NO-RESEARCH MODE: Do not cite specific companies or unverified market statistics. "
            "Use only user-provided context."
        )
    return (
        "RESEARCH DATA (incorporate when relevant; never fabricate beyond this):\n"
        f"{research_results}"
    )


def build_draft_messages(
    *,
    venture: QuestionnaireVentureContext,
    asked_q: str,
    research_results: str | None,
    thought_starters: list[str] | None,
    word_limit: int,
    mode: DraftMode | None = None,
    expand_existing: bool = False,
) -> list[dict[str, str]]:
    meta = get_question_meta(asked_q)
    draft_mode = mode or resolve_draft_mode(asked_q)
    context_block = format_authoritative_context_block(venture, asked_q=asked_q)
    starter_block = _format_thought_starter_hints(thought_starters)
    research_block = _format_research_block(research_results)

    user_parts = [
        f"Draft the answer for Question {meta.number if meta else asked_q}.",
        f'Question: "{meta.prompt_text if meta else asked_q}"',
    ]
    if expand_existing:
        user_parts.append(
            "Provide additional depth on THIS question only — do not repeat prior answers verbatim."
        )
    if starter_block and draft_mode == "prose":
        user_parts.append(starter_block)

    if draft_mode == "business_name":
        user_parts.append("Return only the business name (1–4 words) or: Not decided yet")
        max_words = 6
    elif draft_mode == "industry_label":
        user_parts.append(
            "Return only a short industry label (2–6 words) derived from the business idea above."
        )
        max_words = 12
    else:
        user_parts.append(f"Maximum length: {word_limit} words.")
    user_parts.append("Return only the draft answer body.")

    system_extra = ""
    if draft_mode == "industry_label":
        system_extra = (
            "\nIndustry drafts must be a concise label, not a paragraph. "
            "Derive the label from Q1 and prior answers only."
        )
    elif draft_mode == "business_name":
        system_extra = (
            "\nPropose a name that fits the business idea in context. "
            "If the idea does not support a confident name, output: Not decided yet"
        )

    return [
        {"role": "system", "content": DRAFT_COMMAND_SYSTEM + system_extra},
        {"role": "system", "content": context_block},
        {"role": "system", "content": research_block},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


def validate_draft_output(text: str, *, asked_q: str) -> str | None:
    """Return an error message if output is unusable; None if OK."""
    if not (text or "").strip():
        return "Draft generation returned empty content."
    if draft_output_has_placeholders(text):
        return (
            "Draft could not be grounded in your questionnaire answers. "
            "Please answer or accept Question 1 (your business idea), then try Draft again."
        )
    meta = get_question_meta(asked_q)
    if meta and meta.is_industry_question and len(text.split()) > 15:
        return (
            "Industry answer must be a short label (a few words), not a paragraph. "
            "Try Draft again or type your industry directly."
        )
    return None


async def prepare_draft_venture_context(
    session_data: dict | None,
    history: list | None,
    *,
    asked_q: str,
    get_answer_for_tag: Any,
) -> QuestionnaireVentureContext:
    return await build_questionnaire_venture_context(
        session_data,
        history,
        asked_q=asked_q,
        get_answer_for_tag=get_answer_for_tag,
    )
