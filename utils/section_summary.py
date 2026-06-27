"""Section-summary detection for Business Plan phase boundaries.

A section summary is shown after the user answers the last question in a BP
section (Q4, Q7, Q13, …). It is not a questionnaire item — the UI must label it
"Section Summary", not "Question N".
"""

SECTION_SUMMARY_MARKERS = (
    "Section Complete",
    "Summary of Your Information",
    "Ready to Continue",
)


def get_last_assistant_content(history: list | None) -> str:
    if not history:
        return ""
    for message in reversed(history):
        if message.get("role") == "assistant":
            return (message.get("content") or "").strip()
    return ""


def section_summary_already_pending(history: list | None) -> bool:
    """True when the latest assistant turn is already a section-end summary awaiting Accept."""
    return is_section_summary_reply(get_last_assistant_content(history))


def is_section_summary_reply(
    reply: str | None,
    *,
    show_accept_modify: bool = False,
) -> bool:
    """True when the assistant message is a section-end summary awaiting Accept."""
    if not reply:
        return False
    return any(marker in reply for marker in SECTION_SUMMARY_MARKERS)
