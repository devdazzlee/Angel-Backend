"""
Business Plan Scrapping command — refines founder notes using the same
authoritative questionnaire context path as Draft and Modify.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from services.business_plan_draft_service import prepare_draft_venture_context
from services.business_plan_registry import (
    get_question_meta,
    should_use_web_research_for_draft,
)
from services.questionnaire_grounding import (
    QuestionnaireVentureContext,
    format_authoritative_context_block,
)

SCRAPPING_COMMAND_SYSTEM = """You refine rough founder notes into polished Business Plan answer text.

Output ONLY the refined answer body — no preamble, no "Here's a refined version", no follow-up questions.
Stay within the word limit. Use first person ("I/we") when writing prose.
Never invent facts not present in AUTHORITATIVE VENTURE CONTEXT.
Never use placeholder phrases such as "your business", "your industry", or "your location".
Address ONLY the active questionnaire question — do not answer other plan sections."""


def _format_research_block(research_results: str | None) -> str:
    if not research_results:
        return (
            "NO-RESEARCH MODE: Polish the founder's notes using venture context only. "
            "Do not cite specific companies or unverified market statistics."
        )
    return (
        "RESEARCH DATA (incorporate only when relevant to this question; never fabricate beyond this):\n"
        f"{research_results}"
    )


def build_scrapping_messages(
    *,
    venture: QuestionnaireVentureContext,
    asked_q: str,
    user_notes: str,
    research_results: str | None,
    word_limit: int,
) -> list[dict[str, str]]:
    meta = get_question_meta(asked_q)
    context_block = format_authoritative_context_block(venture, asked_q=asked_q)
    research_block = _format_research_block(research_results)

    question_text = meta.prompt_text if meta else asked_q
    question_number = meta.number if meta else asked_q

    if user_notes.strip():
        user_body = (
            f"Refine the founder's rough notes for Question {question_number}.\n\n"
            f'Question: "{question_text}"\n\n'
            f"Founder's notes:\n{user_notes.strip()}\n\n"
            f"Maximum length: {word_limit} words.\n"
            "Return only the refined answer body."
        )
    else:
        user_body = (
            f"Question {question_number} has no notes in the input box. "
            f"Using venture context only, draft a concise polished starting answer.\n\n"
            f'Question: "{question_text}"\n\n'
            f"Maximum length: {word_limit} words.\n"
            "Return only the refined answer body."
        )

    return [
        {"role": "system", "content": SCRAPPING_COMMAND_SYSTEM},
        {"role": "system", "content": context_block},
        {"role": "system", "content": research_block},
        {"role": "user", "content": user_body},
    ]


def build_scrapping_research_query(
    venture: QuestionnaireVentureContext,
    asked_q: str,
) -> str:
    meta = get_question_meta(asked_q)
    parts = [
        venture.industry,
        venture.business_idea,
        meta.topic_label if meta else "",
        venture.location,
    ]
    return " ".join(p for p in parts if p and p.strip())


async def run_scrapping_refinement(
    *,
    session_data: dict | None,
    history: list | None,
    user_notes: str,
    asked_q: str,
    get_answer_for_tag: Callable[..., Any],
    conduct_web_search: Callable[..., Awaitable[str]],
    should_conduct_web_search: Callable[[], bool],
    openai_client: Any,
    word_limit: int,
) -> str:
    venture = await prepare_draft_venture_context(
        session_data,
        history,
        asked_q=asked_q,
        get_answer_for_tag=get_answer_for_tag,
    )

    research_results = None
    if should_use_web_research_for_draft(asked_q) and should_conduct_web_search():
        query = build_scrapping_research_query(venture, asked_q)
        if query.strip():
            research_results = await conduct_web_search(query)

    messages = build_scrapping_messages(
        venture=venture,
        asked_q=asked_q,
        user_notes=user_notes,
        research_results=research_results,
        word_limit=word_limit,
    )

    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.3,
        max_tokens=800,
    )
    return (response.choices[0].message.content or "").strip()
