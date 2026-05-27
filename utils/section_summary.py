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


def is_section_summary_reply(
    reply: str | None,
    *,
    show_accept_modify: bool = False,
) -> bool:
    """True when the assistant message is a section-end summary awaiting Accept."""
    if not show_accept_modify or not reply:
        return False
    return any(marker in reply for marker in SECTION_SUMMARY_MARKERS)
