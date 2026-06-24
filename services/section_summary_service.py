"""
Business Plan section summaries — registry-driven context + bespoke considerations.

Section summaries are NOT questionnaire items. All three blocks (Summary, Educational
Insights, Critical Considerations) must ground in tagged answers for that section.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.business_plan_registry import (
    get_question_meta,
    get_question_tags_for_section,
)
from services.business_identity_extractor import get_tagged_answer_for_question_tag
from utils.business_context import is_meaningful_context_value

GENERIC_CONSIDERATION_PATTERNS = (
    "stay informed about industry regulations",
    "ensure you have a clear understanding of contract terms",
    "consider how your advertising will align with your brand values",
    "ensure your business operations comply with local laws",
    "things to consider based on",
    "important watchouts",
)


@dataclass(frozen=True)
class SectionAnswerRecord:
    tag: str
    number: int
    prompt_text: str
    answer: str


def collect_section_answer_records(
    history: list | None,
    *,
    section_id: int,
) -> list[SectionAnswerRecord]:
    """Tagged answers for every question in the section (source of truth)."""
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


def format_section_answers_block(records: list[SectionAnswerRecord]) -> str:
    if not records:
        return "(No tagged answers found for this section — use conversation history.)"
    lines: list[str] = []
    for rec in records:
        lines.append(f"Q{rec.number}: {rec.prompt_text}")
        lines.append(f"  → Answer: {rec.answer[:800]}")
        lines.append("")
    return "\n".join(lines).strip()


def _format_anchor_facts(records: list[SectionAnswerRecord]) -> str:
    if not records:
        return "- (No anchor facts — do not invent generic considerations.)"
    bullets: list[str] = []
    for rec in records:
        snippet = rec.answer[:220].replace("\n", " ")
        bullets.append(f"- Q{rec.number} ({rec.prompt_text[:60]}…): \"{snippet}\"")
    return "\n".join(bullets)


def build_section_summary_instruction(
    *,
    section_name: str,
    records: list[SectionAnswerRecord],
) -> str:
    """Single prompt contract for all section summary generation paths."""
    qa_block = format_section_answers_block(records)
    anchor_facts = _format_anchor_facts(records)

    return f"""IMPORTANT: The founder just completed the "{section_name}" section of the Business Plan.
You MUST produce a section summary grounded ONLY in the answers below — not generic templates.

SECTION ANSWERS (AUTHORITATIVE — every section of your reply must reflect these):
{qa_block}

Provide the summary in this EXACT format:

🎯 **{section_name} Section Complete**

**Summary of Your Information:**
Recap ALL key information the founder provided across EVERY question in this section.
Use their exact names, numbers, goals, locations, and choices — no placeholders.

**Educational Insights:**
Provide 2-3 insights specific to their answers and industry context in this section.
Each insight must reference at least one concrete detail from the answers above.

**Critical Considerations:**
Provide exactly 2-3 bullets. EACH bullet MUST follow this pattern:
**[Specific fact from their answers]:** [Risk, compliance point, or action tailored ONLY to that fact]

ANCHOR FACTS (use at least one distinct fact per bullet — do not repeat the same fact):
{anchor_facts}

FORBIDDEN in Critical Considerations:
- Generic advice that could apply to any business without naming their specifics
- Placeholders like "your business", "your industry", "your target market"
- Vague bullets such as "stay informed about regulations" or "align advertising with brand values" WITHOUT citing their business name, contract goal, location, or other section-specific detail
- Repeating the Educational Insights in different words

If a bullet would still make sense for a unrelated business, rewrite it until it is clearly about THIS founder's section answers.

**Ready to Continue?**
Please confirm that this information is accurate before we move to the next section. You can either accept this summary and continue, or let me know what you'd like to modify.

[[ACCEPT_MODIFY_BUTTONS]]

CRITICAL:
- End with [[ACCEPT_MODIFY_BUTTONS]]
- Do NOT ask the next questionnaire question
- Do NOT include [[Q:BUSINESS_PLAN.XX]] tags
- Do NOT include Thought Starters or follow-up questions
- Use exactly ONE blank line between major sections
"""


def build_section_summary_messages(
    *,
    history: list,
    section_id: int,
    section_name: str,
    user_turn: str,
    angel_system_prompt: str,
) -> list[dict[str, str]]:
    records = collect_section_answer_records(history, section_id=section_id)
    instruction = build_section_summary_instruction(
        section_name=section_name,
        records=records,
    )
    extended_history = history[-30:] if len(history) > 30 else history
    return [
        {"role": "system", "content": angel_system_prompt},
        *extended_history,
        {"role": "user", "content": user_turn},
        {"role": "system", "content": instruction},
    ]


def section_summary_has_generic_considerations(reply: str) -> bool:
    """Heuristic: True if Critical Considerations block looks like generic filler."""
    lower = (reply or "").lower()
    start = lower.find("critical considerations")
    if start == -1:
        return False
    end = lower.find("ready to continue", start)
    block = lower[start:end] if end != -1 else lower[start:]
    return any(pattern in block for pattern in GENERIC_CONSIDERATION_PATTERNS)


async def generate_section_summary_text(
    openai_client,
    *,
    history: list,
    section_id: int,
    section_name: str,
    user_turn: str,
    angel_system_prompt: str,
) -> str:
    """Generate a section summary with registry-grounded Critical Considerations."""
    import re

    messages = build_section_summary_messages(
        history=history,
        section_id=section_id,
        section_name=section_name,
        user_turn=user_turn,
        angel_system_prompt=angel_system_prompt,
    )
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.5,
        max_tokens=1200,
        stream=False,
    )
    reply_content = response.choices[0].message.content or ""

    if section_summary_has_generic_considerations(reply_content):
        stricter = (
            "REVISION REQUIRED: Your Critical Considerations were too generic. "
            "Rewrite ONLY the **Critical Considerations** block. Each bullet must name "
            "a specific fact from the founder's section answers (business name, contract, "
            "location, competitor, price, etc.) and a tailored watchout. "
            "Return the full summary again with the corrected block."
        )
        retry_messages = messages + [
            {"role": "assistant", "content": reply_content},
            {"role": "user", "content": stricter},
        ]
        retry = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=retry_messages,
            temperature=0.4,
            max_tokens=1200,
            stream=False,
        )
        reply_content = retry.choices[0].message.content or reply_content

    reply_content = re.sub(r"\[\[Q:[A-Z_]+\.\d+\]\]", "", reply_content)
    return reply_content.replace("[[ACCEPT_MODIFY_BUTTONS]]", "").strip()
