"""
Business Plan section summaries — registry-driven context + bespoke considerations.

All content is generated from the founder's tagged answers and venture context.
No hardcoded business names or industry examples in prompts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from services.business_identity_extractor import get_tagged_answer_for_question_tag
from services.business_plan_registry import (
    SECTION_TOPIC_LABELS,
    get_question_meta,
    get_question_tags_for_section,
)
from services.questionnaire_grounding import (
    QuestionnaireVentureContext,
    build_questionnaire_venture_context,
)
from utils.business_context import is_meaningful_context_value

# Universal filler phrases — not business-specific; indicate template leakage.
UNIVERSAL_GENERIC_PHRASES = (
    "align with your brand values",
    "specific needs of your target market",
    "stay informed about industry regulations",
    "ensure your business operations comply with local laws",
)

SECTION_CONSIDERATION_FOCUS: dict[int, str] = {
    1: "MVP scope, differentiation, quality standards, feature prioritization",
    2: "Industry positioning, launch milestones, goal execution, brand strategy",
    3: "Customer acquisition, channels, competitive positioning, problem-solution fit",
    4: "Location/operations fit, staffing, facilities, supply chain",
    5: "Channel-specific marketing, sales process, pricing for the stated customer",
    6: "Industry-specific regulations, licenses, contracts, compliance",
    7: "Revenue model risks, unit economics, funding and cash-flow watchouts",
    8: "Scaling risks, hiring, partnerships, expansion constraints",
    9: "Contingency planning, key risks, mitigation for this venture's stage",
}


@dataclass(frozen=True)
class SectionAnswerRecord:
    tag: str
    number: int
    prompt_text: str
    answer: str


@dataclass
class SectionGroundingAnchors:
    """Concrete facts extracted from this session — the model must reference these."""

    business_name: str = ""
    industry: str = ""
    location: str = ""
    business_idea: str = ""
    numeric_facts: list[str] = field(default_factory=list)
    answer_snippets: list[str] = field(default_factory=list)

    def required_reference_tokens(self) -> list[str]:
        """Tokens a grounded bullet should match at least one of."""
        tokens: list[str] = []
        if self.business_name:
            tokens.append(self.business_name.lower())
        for fact in self.numeric_facts:
            tokens.append(fact.lower())
        for snippet in self.answer_snippets[:6]:
            for word in snippet.lower().split():
                if len(word) > 5 and word.isalpha():
                    tokens.append(word)
                    break
        if self.industry:
            for word in self.industry.lower().replace("/", " ").split():
                if len(word) > 4:
                    tokens.append(word)
        return tokens

    def prompt_block(self) -> str:
        lines = ["GROUNDING ANCHORS (each insight and consideration must cite at least one):"]
        if self.business_name:
            lines.append(f"- Business name: {self.business_name}")
        if self.business_idea:
            lines.append(f"- Business idea: {self.business_idea[:350]}")
        if self.industry:
            lines.append(f"- Industry: {self.industry}")
        if self.location:
            lines.append(f"- Location: {self.location}")
        if self.numeric_facts:
            lines.append("- Quantified goals/metrics from this section:")
            for fact in self.numeric_facts[:8]:
                lines.append(f"  • {fact}")
        if self.answer_snippets:
            lines.append("- Key facts from section answers:")
            for snippet in self.answer_snippets[:6]:
                lines.append(f"  • {snippet}")
        if len(lines) == 1:
            lines.append("- (Use exact details from section answers below.)")
        return "\n".join(lines)


def collect_section_answer_records(
    history: list | None,
    *,
    section_id: int,
) -> list[SectionAnswerRecord]:
    if not history:
        return []
    records: list[SectionAnswerRecord] = []
    for tag in get_question_tags_for_section(section_id):
        answer = get_tagged_answer_for_question_tag(history, tag)
        if not is_meaningful_context_value(answer):
            continue
        meta = get_question_meta(tag)
        if not meta:
            continue
        records.append(
            SectionAnswerRecord(
                tag=tag,
                number=meta.number,
                prompt_text=meta.prompt_text,
                answer=answer.strip(),
            )
        )
    return records


def build_grounding_anchors(
    venture: QuestionnaireVentureContext,
    records: list[SectionAnswerRecord],
) -> SectionGroundingAnchors:
    numeric_facts: list[str] = []
    snippets: list[str] = []

    for rec in records:
        compact = rec.answer.replace("\n", " ").strip()
        if compact:
            snippets.append(compact[:120])
        for match in re.finditer(
            r".{0,40}\b(\d[\d,./%]*\s*(?:%|students|tutors|users|customers|months|years|employees)?)\b.{0,20}",
            compact,
            re.IGNORECASE,
        ):
            fact = match.group(0).strip()
            if fact and fact not in numeric_facts:
                numeric_facts.append(fact[:100])

    return SectionGroundingAnchors(
        business_name=venture.business_name.strip(),
        industry=venture.industry.strip(),
        location=venture.location.strip(),
        business_idea=venture.business_idea.strip(),
        numeric_facts=numeric_facts,
        answer_snippets=snippets,
    )


def format_section_answers_block(records: list[SectionAnswerRecord]) -> str:
    if not records:
        return "(No tagged answers found for this section.)"
    lines: list[str] = []
    for rec in records:
        lines.append(f"Q{rec.number}: {rec.prompt_text}")
        lines.append(f"  → Answer: {rec.answer[:800]}")
        lines.append("")
    return "\n".join(lines).strip()


def build_summary_and_insights_instruction(
    *,
    section_name: str,
    section_id: int,
    records: list[SectionAnswerRecord],
    anchors: SectionGroundingAnchors,
) -> str:
    qa_block = format_section_answers_block(records)
    anchor_block = anchors.prompt_block()
    section_topic = SECTION_TOPIC_LABELS.get(section_id, "business planning")

    return f"""The founder completed the "{section_name}" section of their Business Plan.

{anchor_block}

SECTION ANSWERS (authoritative source — do not invent facts not present here):
{qa_block}

Return JSON only:
{{
  "summary": "One paragraph recapping every key fact from this section using exact names, numbers, and choices from the answers.",
  "insights": [
    "2-3 educational insights; each must cite at least one grounding anchor above"
  ]
}}

Rules:
- Ground every insight in the anchor facts and section answers for THIS founder only.
- Each insight must reference {section_topic} in the context of their stated business.
- Do not write advice that could apply unchanged to a different industry or business model.
- Do not include Critical Considerations (generated separately)."""


def build_critical_considerations_instruction(
    *,
    section_name: str,
    section_id: int,
    records: list[SectionAnswerRecord],
    anchors: SectionGroundingAnchors,
) -> str:
    qa_block = format_section_answers_block(records)
    anchor_block = anchors.prompt_block()
    focus = SECTION_CONSIDERATION_FOCUS.get(
        section_id,
        "Risks, compliance, and actions tied to this section's answers",
    )

    return f"""Write Critical Considerations for the "{section_name}" section.

{anchor_block}

SECTION ANSWERS:
{qa_block}

Section focus lenses (choose 2-3 distinct topics):
{focus}

Return JSON only:
{{
  "considerations": [
    {{"topic": "2-5 word topic label", "text": "1-2 sentences of actionable advice"}}
  ]
}}

Rules for each consideration:
1. "topic" is a short label (2-5 words) — never copy a sentence from the user's answers.
2. "text" must cite at least one grounding anchor (business name, metric, industry detail, or section fact).
3. Advice must be specific to this founder's industry and section answers — not interchangeable template text.
4. For compliance topics, name the regulation type relevant to their industry (not "stay informed about regulations").
5. Provide exactly 2-3 items."""


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _text_references_anchors(text: str, anchors: SectionGroundingAnchors) -> bool:
    lower = (text or "").lower()
    for token in anchors.required_reference_tokens():
        if token and token in lower:
            return True
    return False


def _topic_is_pasted_answer(topic: str, records: list[SectionAnswerRecord]) -> bool:
    topic_lower = topic.lower().strip()
    if len(topic_lower.split()) > 6:
        return True
    for rec in records:
        if topic_lower in rec.answer.lower():
            return True
    return False


def _consideration_fails_validation(
    topic: str,
    text: str,
    anchors: SectionGroundingAnchors,
    records: list[SectionAnswerRecord],
) -> bool:
    if not topic or not text:
        return True
    if len(topic.split()) > 6 or len(topic.split()) < 2:
        return True
    if len(text.split()) < 10:
        return True
    if _topic_is_pasted_answer(topic, records):
        return True
    combined = f"{topic} {text}".lower()
    if any(phrase in combined for phrase in UNIVERSAL_GENERIC_PHRASES):
        return True
    if not _text_references_anchors(text, anchors):
        return True
    return False


def _validate_considerations(
    items: list[dict[str, str]],
    anchors: SectionGroundingAnchors,
    records: list[SectionAnswerRecord],
) -> bool:
    """Return True when output is invalid and needs regeneration."""
    if not items or len(items) < 2:
        return True
    return any(
        _consideration_fails_validation(
            (item.get("topic") or "").strip(),
            (item.get("text") or "").strip(),
            anchors,
            records,
        )
        for item in items
    )


def _validate_insights(insights: list[str], anchors: SectionGroundingAnchors) -> bool:
    if len(insights) < 2:
        return True
    grounded = sum(1 for i in insights if _text_references_anchors(i, anchors))
    return grounded < 2


def _format_insights_block(insights: list[str]) -> str:
    lines = ["**Educational Insights:**"]
    for insight in insights[:3]:
        cleaned = insight.strip()
        if cleaned:
            lines.append(cleaned)
    return "\n".join(lines)


def _format_considerations_block(items: list[dict[str, str]]) -> str:
    lines = ["**Critical Considerations:**"]
    for item in items[:3]:
        topic = (item.get("topic") or "Consideration").strip()
        text = (item.get("text") or "").strip()
        lines.append(f"- **{topic}:** {text}")
    return "\n".join(lines)


def assemble_section_summary(
    *,
    section_name: str,
    summary_text: str,
    insights: list[str],
    considerations: list[dict[str, str]],
) -> str:
    parts = [
        f"🎯 **{section_name} Section Complete**",
        "",
        "**Summary of Your Information:**",
        summary_text.strip(),
        "",
        _format_insights_block(insights),
        "",
        _format_considerations_block(considerations),
        "",
        "**Ready to Continue?**",
        "Please confirm that this information is accurate before we move to the next section. "
        "You can either accept this summary and continue, or let me know what you'd like to modify.",
        "",
        "[[ACCEPT_MODIFY_BUTTONS]]",
    ]
    return "\n".join(parts)


def _build_retry_hint(anchors: SectionGroundingAnchors, *, block: str) -> str:
    return (
        f"Regenerate the {block}. Previous output was not grounded in the founder's answers. "
        f"Each item must cite at least one of: {anchors.prompt_block()}"
    )


async def _generate_summary_and_insights(
    openai_client,
    *,
    history: list,
    section_id: int,
    section_name: str,
    user_turn: str,
    angel_system_prompt: str,
    anchors: SectionGroundingAnchors,
    records: list[SectionAnswerRecord],
    retry_hint: str = "",
) -> tuple[str, list[str]]:
    instruction = build_summary_and_insights_instruction(
        section_name=section_name,
        section_id=section_id,
        records=records,
        anchors=anchors,
    )
    if retry_hint:
        instruction += f"\n\nREVISION: {retry_hint}"

    extended_history = history[-30:] if len(history) > 30 else history
    messages = [
        {"role": "system", "content": angel_system_prompt},
        *extended_history,
        {"role": "user", "content": user_turn},
        {"role": "system", "content": instruction},
    ]
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.4,
        max_tokens=900,
        response_format={"type": "json_object"},
        stream=False,
    )
    parsed = _parse_json_object(response.choices[0].message.content or "{}")
    summary = str(parsed.get("summary") or "").strip()
    insights = [str(i).strip() for i in (parsed.get("insights") or []) if str(i).strip()]
    return summary, insights[:3]


async def _generate_critical_considerations(
    openai_client,
    *,
    section_id: int,
    section_name: str,
    records: list[SectionAnswerRecord],
    anchors: SectionGroundingAnchors,
    retry_hint: str = "",
) -> list[dict[str, str]]:
    instruction = build_critical_considerations_instruction(
        section_name=section_name,
        section_id=section_id,
        records=records,
        anchors=anchors,
    )
    if retry_hint:
        instruction += f"\n\nREVISION: {retry_hint}"

    messages = [
        {"role": "system", "content": instruction},
        {"role": "user", "content": "Generate the JSON now."},
    ]
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.35,
        max_tokens=700,
        response_format={"type": "json_object"},
        stream=False,
    )
    parsed = _parse_json_object(response.choices[0].message.content or "{}")
    items: list[dict[str, str]] = []
    for entry in parsed.get("considerations") or []:
        if isinstance(entry, dict):
            items.append(
                {
                    "topic": str(entry.get("topic") or "").strip(),
                    "text": str(entry.get("text") or "").strip(),
                }
            )
    return items


async def generate_section_summary_text(
    openai_client,
    *,
    history: list,
    section_id: int,
    section_name: str,
    user_turn: str,
    angel_system_prompt: str,
    session_data: dict | None = None,
) -> str:
    """Generate a section summary grounded in this session's tagged answers."""
    venture = await build_questionnaire_venture_context(
        session_data,
        history,
        asked_q=(session_data or {}).get("asked_q", ""),
        get_answer_for_tag=get_tagged_answer_for_question_tag,
    )
    records = collect_section_answer_records(history, section_id=section_id)
    anchors = build_grounding_anchors(venture, records)

    summary_text, insights = await _generate_summary_and_insights(
        openai_client,
        history=history,
        section_id=section_id,
        section_name=section_name,
        user_turn=user_turn,
        angel_system_prompt=angel_system_prompt,
        anchors=anchors,
        records=records,
    )

    if not summary_text or _validate_insights(insights, anchors):
        summary_text, insights = await _generate_summary_and_insights(
            openai_client,
            history=history,
            section_id=section_id,
            section_name=section_name,
            user_turn=user_turn,
            angel_system_prompt=angel_system_prompt,
            anchors=anchors,
            records=records,
            retry_hint=_build_retry_hint(anchors, block="summary and insights"),
        )

    considerations = await _generate_critical_considerations(
        openai_client,
        section_id=section_id,
        section_name=section_name,
        records=records,
        anchors=anchors,
    )

    if _validate_considerations(considerations, anchors, records):
        considerations = await _generate_critical_considerations(
            openai_client,
            section_id=section_id,
            section_name=section_name,
            records=records,
            anchors=anchors,
            retry_hint=_build_retry_hint(anchors, block="Critical Considerations"),
        )

    reply_content = assemble_section_summary(
        section_name=section_name,
        summary_text=summary_text,
        insights=insights,
        considerations=considerations,
    )
    reply_content = re.sub(r"\[\[Q:[A-Z_]+\.\d+\]\]", "", reply_content)
    return reply_content.replace("[[ACCEPT_MODIFY_BUTTONS]]", "").strip()
