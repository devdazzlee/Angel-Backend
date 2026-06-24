"""
Modify revision — revise the full assistant snapshot in place (including auto-research).

Modify must not collapse long-form auto-injected research into a short summary.
"""

from __future__ import annotations

import re
from typing import Any

LONG_FORM_SNAPSHOT_MIN_CHARS = 800

_COMMAND_ASSIST_SNAPSHOT_MARKERS = (
    "here's a draft for you:",
    "here's a draft based on what you've shared:",
    "here's a refined version of your thoughts:",
    "here's some additional information to help you:",
)

MODIFY_REVISION_SYSTEM = """You are revising your prior assistant message in Founderport. The user chose **Modify** and is giving conversational feedback — this is NOT their answer to a questionnaire item.

Requirements:
• Output a complete replacement for the assistant message under "Assistant message to revise," fully applying their guidance.
• Preserve every [[Q:PHASE.NN]] tag exactly as in that snapshot when present; do not change the question number unless they explicitly ask to move on.
• Preserve [[ACCEPT_MODIFY_BUTTONS]] in the revised reply when the snapshot included it.
• Do not invent business facts the user did not supply unless they appear in the snapshot or their revision request.
• Keep useful structure (headings, bullets, competitor blocks, sections) unless they asked to change it.
• No apologies. Do not open with "Apologies", "Sorry", "My apologies", "I apologize", "I appreciate your patience", or similar."""

LONG_FORM_REVISION_RULES = """
LONG-FORM REVISION (the snapshot contains detailed auto-generated research or multi-section content):
• Revise the ENTIRE snapshot in place — every section, named competitor, trend, and bullet group.
• Keep comparable depth and length unless the user explicitly asked to shorten.
• Apply the user's guidance throughout (business name, geography, industry, offering) — do NOT replace with a brief generic summary.
• Preserve major headings and research structure from the snapshot; enrich them with the user's specifics.
• If the snapshot lists named competitors with strengths/weaknesses, keep that format for each competitor after revision."""

COMMAND_ASSIST_REVISION_RULES = """
COMMAND-ASSIST REVISION (Draft / Support / Scrapping snapshot):
• Revise the substantive answer body in place — apply the user's guidance to the actual draft/support content.
• Preserve the same wrapper format as the snapshot (e.g. "Here's a draft for you:" lead-in when present).
• Do NOT add a conversational preamble such as "Got it." or "Here's a revised draft focused on…".
• Do NOT repeat or nest wrapper lines (only one "Here's a draft for you:" lead-in in the entire output).
• Do NOT ask the next questionnaire question or add Accept/Modify UI text.
• Keep comparable length and structure unless the user asked to shorten."""

def format_modify_revision_user_turn(assistant_snapshot: str, user_guidance: str) -> str:
    return (
        "——— Assistant message to revise (revise this ENTIRE document in place) ———\n"
        f"{assistant_snapshot.strip()}\n\n"
        "——— User's revision request ———\n"
        f"{user_guidance.strip()}"
    )


def is_long_form_snapshot(text: str) -> bool:
    if not text:
        return False
    if len(text) >= LONG_FORM_SNAPSHOT_MIN_CHARS:
        return True
    markers = (
        "🔍 **",
        "Competitor Research",
        "Industry Trends Research",
        "Suggested Short-Term",
        "Competitive Position",
        "Direct Competitors",
    )
    return any(m in text for m in markers)


def is_command_assist_snapshot(text: str) -> bool:
    lower = (text or "").lower()
    return any(marker in lower for marker in _COMMAND_ASSIST_SNAPSHOT_MARKERS)


def resolve_modify_question_tag(assistant_snapshot: str, session_asked_q: str | None) -> str:
    tag_match = re.search(r"\[\[Q:([A-Z_]+\.\d{2})\]\]", assistant_snapshot, re.I)
    if tag_match:
        asked_q = tag_match.group(1).upper()
        if asked_q.startswith("BP."):
            return f"BUSINESS_PLAN.{asked_q[3:]}"
        return asked_q
    asked_q = (session_asked_q or "").strip().upper()
    if asked_q.startswith("BP."):
        return f"BUSINESS_PLAN.{asked_q[3:]}"
    return asked_q


def build_modify_formatting_instruction(
    *,
    user_name: str,
    intensity_guidance: str,
    long_form: bool,
    command_assist: bool,
) -> str:
    lines = [
        "FORMATTING FOR THIS TURN (revise-in-place):",
        f"• Address {user_name} naturally; use clear Markdown (headings, bullets) when it helps readability.",
        "• Do not add questionnaire flow instructions, option lists, or ask the next question unless the user explicitly asked to move on.",
        f"• Constructive tone calibration for this turn:",
        intensity_guidance.strip(),
    ]
    if command_assist:
        lines.append(COMMAND_ASSIST_REVISION_RULES.strip())
    elif long_form:
        lines.append(LONG_FORM_REVISION_RULES.strip())
    return "\n".join(lines)

def build_modify_revision_message_list(
    *,
    assistant_snapshot: str,
    user_guidance: str,
    grounding: str | None,
    venture_context_block: str | None,
    user_name: str,
    intensity_guidance: str,
    trimmed_history: list,
    tag_prompt: str,
    tone_directive: str,
) -> list[dict[str, str]]:
    long_form = is_long_form_snapshot(assistant_snapshot)
    command_assist = is_command_assist_snapshot(assistant_snapshot)

    msgs: list[dict[str, str]] = [
        {"role": "system", "content": MODIFY_REVISION_SYSTEM},
        {"role": "system", "content": tag_prompt},
        {
            "role": "system",
            "content": build_modify_formatting_instruction(
                user_name=user_name,
                intensity_guidance=intensity_guidance,
                long_form=long_form,
                command_assist=command_assist,
            ),
        },
    ]
    if grounding:
        msgs.append({"role": "system", "content": grounding})
    if venture_context_block:
        msgs.append({"role": "system", "content": venture_context_block})
    msgs.append({"role": "system", "content": tone_directive})
    msgs.extend(trimmed_history)
    msgs.append(
        {
            "role": "user",
            "content": format_modify_revision_user_turn(assistant_snapshot, user_guidance),
        }
    )
    return msgs


_COMMAND_ASSIST_LEAD_IN_PATTERNS = (
    r"^Got it\.?\s*",
    r"^Updated\.?\s*",
    r"^Here'?s a revised draft(?:\s+for you)?:\s*",
    r"^Here'?s a refined draft(?:\s+for you)?:\s*",
    r"^Here'?s a (?:research-backed )?draft for you:\s*",
    r"^Here'?s a draft based on what you'?ve shared:\s*",
    r"^Here'?s a refined version of your thoughts:\s*",
    r"^Here'?s some additional information to help you:\s*",
)

# Standalone lead-in lines the model sometimes emits on their own paragraph.
_COMMAND_ASSIST_LEAD_IN_LINE = re.compile(
    r"^Here'?s a (?:(?:research-backed )?draft|revised draft|refined draft)"
    r"(?:\s+for you)?:\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def _canonical_wrapper_for_snapshot(snapshot_lower: str) -> str | None:
    if "here's a draft for you:" in snapshot_lower:
        return "Here's a draft for you:"
    if "here's a draft based on what you've shared:" in snapshot_lower:
        return "Here's a draft based on what you've shared:"
    if "here's a refined version of your thoughts:" in snapshot_lower:
        return "Here's a refined version of your thoughts:"
    if "here's some additional information to help you:" in snapshot_lower:
        return "Here's some additional information to help you:"
    return None


def _strip_all_command_assist_lead_ins(text: str) -> str:
    """Remove every command-assist preamble line — models often nest wrappers."""
    body = (text or "").strip()
    for _ in range(12):
        previous = body
        for pattern in _COMMAND_ASSIST_LEAD_IN_PATTERNS:
            body = re.sub(pattern, "", body, flags=re.IGNORECASE | re.MULTILINE).strip()
        body = _COMMAND_ASSIST_LEAD_IN_LINE.sub("", body).strip()
        body = re.sub(r"\n{3,}", "\n\n", body)
        if body == previous:
            break
    return body


def normalize_command_assist_modify_reply(
    assistant_snapshot: str,
    reply_content: str,
) -> str:
    """Restore a single canonical Draft/Support/Scrapping wrapper after LLM modify."""
    if not is_command_assist_snapshot(assistant_snapshot):
        return (reply_content or "").strip()

    snapshot_lower = assistant_snapshot.lower()
    wrapper = _canonical_wrapper_for_snapshot(snapshot_lower)
    body = _strip_all_command_assist_lead_ins(reply_content)

    if not wrapper:
        return body

    if body.lower().startswith(wrapper.lower()):
        return f"{wrapper}\n\n{body[len(wrapper):].strip()}\n\n"

    return f"{wrapper}\n\n{body}\n\n"


def choose_modify_max_tokens(assistant_snapshot: str) -> int:
    """Scale output budget with snapshot size so revisions can match long-form research."""
    length = len(assistant_snapshot or "")
    if length >= 4000:
        return 6000
    if length >= 2000:
        return 5000
    if is_long_form_snapshot(assistant_snapshot):
        return 4500
    return 4096
