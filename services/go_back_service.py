"""
Questionnaire go-back navigation — restore the prior question WITH its applied answer.

Previous deleted the user's answer and everything after the question, which left
Accept/Modify visible with no content. Go-back now keeps the answer row and only
removes later messages. Section-summary screens return to the last tagged question.
"""

from __future__ import annotations

import re
from typing import Any

from utils.section_summary import SECTION_SUMMARY_MARKERS

ACCEPT_TOKENS = frozenset({"accept", "yes"})


def is_section_summary_message(content: str | None) -> bool:
    if not content:
        return False
    return any(marker in content for marker in SECTION_SUMMARY_MARKERS)


def _tag_marker(tag: str) -> str:
    return f"[[Q:{tag}]]"


def find_last_assistant_index(
    records: list[dict[str, Any]],
    *,
    end_before: int | None = None,
    tag: str | None = None,
    require_tag: bool = False,
) -> int | None:
    end = end_before if end_before is not None else len(records)
    marker = _tag_marker(tag) if tag else None
    for idx in range(end - 1, -1, -1):
        record = records[idx]
        if record.get("role") != "assistant":
            continue
        content = record.get("content") or ""
        if require_tag and "[[Q:" not in content:
            continue
        if marker and marker not in content:
            continue
        return idx
    return None


def derive_review_answer_text(assistant_content: str, user_answer: str | None) -> str:
    """Text the user should see when reviewing a prior answer (Accept/Modify)."""
    answer = (user_answer or "").strip()
    if answer and answer.lower() not in ACCEPT_TOKENS:
        return answer

    body = assistant_content or ""
    body = re.sub(r"\[\[Q:[^\]]+\]\]", "", body, count=1)
    body = re.sub(r"\[\[ACCEPT_MODIFY_BUTTONS\]\]", "", body, flags=re.IGNORECASE)
    body = re.sub(r"^#+\s*", "", body.strip())
    return body.strip()


def resolve_go_back_plan(
    records: list[dict[str, Any]],
    *,
    current_tag: str,
    review_tag_override: str | None = None,
) -> dict[str, Any] | None:
    """
    Decide which question to restore and which chat_history rows to delete.

    Returns dict with:
      review_tag, assistant_index, ids_to_remove, user_answer, assistant_content
    """
    if not current_tag or "." not in current_tag:
        return None

    phase_prefix, num_str = current_tag.split(".", 1)
    current_q_num = int(num_str)

    latest_assistant_idx = find_last_assistant_index(records)
    latest_content = (
        records[latest_assistant_idx].get("content") or ""
        if latest_assistant_idx is not None
        else ""
    )

    # Section summary pause: asked_q stays on last section question (e.g. Q17).
    # Previous should return to that question + answer, not the prior question.
    if is_section_summary_message(latest_content):
        review_tag = current_tag
        assistant_index = find_last_assistant_index(
            records, tag=review_tag, require_tag=True
        )
        if assistant_index is None:
            return None
        ids_to_remove = [rec["id"] for rec in records[assistant_index + 1 :]]
        assistant_content = records[assistant_index].get("content") or ""
        user_answer = None
        if assistant_index + 1 < len(records):
            nxt = records[assistant_index + 1]
            if nxt.get("role") == "user":
                user_answer = nxt.get("content")
                ids_to_remove = [
                    rec["id"]
                    for rec in records[assistant_index + 2 :]
                ]
        return {
            "review_tag": review_tag,
            "assistant_index": assistant_index,
            "ids_to_remove": ids_to_remove,
            "user_answer": user_answer,
            "assistant_content": assistant_content,
            "from_section_summary": True,
        }

    if review_tag_override:
        review_tag = review_tag_override
    else:
        previous_q_num = current_q_num - 1
        if previous_q_num < 1:
            return None
        review_tag = f"{phase_prefix}.{previous_q_num:02d}"

    current_index = find_last_assistant_index(
        records, tag=current_tag, require_tag=True
    )
    search_end = current_index if current_index is not None else len(records)
    assistant_index = find_last_assistant_index(
        records, end_before=search_end, tag=review_tag, require_tag=True
    )
    if assistant_index is None:
        assistant_index = find_last_assistant_index(
            records, end_before=search_end, tag=review_tag
        )
    if assistant_index is None:
        assistant_index = find_last_assistant_index(records, tag=review_tag, require_tag=True)
    if assistant_index is None:
        return None

    assistant_content = records[assistant_index].get("content") or ""
    user_answer = None
    delete_from = assistant_index + 1
    if assistant_index + 1 < len(records):
        nxt = records[assistant_index + 1]
        if nxt.get("role") == "user":
            user_answer = nxt.get("content")
            delete_from = assistant_index + 2

    ids_to_remove = [rec["id"] for rec in records[delete_from:]]

    return {
        "review_tag": review_tag,
        "assistant_index": assistant_index,
        "ids_to_remove": ids_to_remove,
        "user_answer": user_answer,
        "assistant_content": assistant_content,
        "from_section_summary": False,
    }
