import re
from typing import Optional


def parse_question_number_from_tag(tag: str | None) -> Optional[int]:
    """Parse ``BUSINESS_PLAN.42`` / ``GKY.03`` / ``GKY.05_ACK`` → question number."""
    if not tag or "." not in tag:
        return None
    normalized = tag.replace("KYC.", "GKY.")
    match = re.search(r"\.(\d+)", normalized)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def tag_phase_name(tag: str | None) -> Optional[str]:
    if not tag or "." not in tag:
        return None
    return tag.split(".", 1)[0].replace("KYC", "GKY")


def derive_phase_answered_from_tag(
    phase: str,
    asked_q: str | None,
    *,
    section_summary_pause: bool = False,
) -> int:
    """
    Progress is derived from ``asked_q``, not a separate increment counter.

    - Viewing question N (about to answer): N−1 completed.
    - Section-summary pause at QN (just finished the section): N completed.
    """
    num = parse_question_number_from_tag(asked_q)
    if num is None:
        return 0

    tag_phase = tag_phase_name(asked_q)
    phase_norm = (phase or "").replace("KYC", "GKY")
    if tag_phase and tag_phase != phase_norm:
        return 0

    total = TOTALS_BY_PHASE.get(phase_norm, num)
    if section_summary_pause:
        completed = num
    else:
        completed = max(0, num - 1)
    return min(completed, total)


def parse_tag(text: str) -> Optional[str]:
    match = re.search(r"\[\[Q:([A-Z_]+\.\d{2})]]", text)
    return match.group(1) if match else None


def is_answer_valid(q_tag: str, answer: str) -> bool:
    return answer.strip() and len(answer.strip()) > 3

def smart_trim_history(history_list, max_lines=150):
    # Flatten the list of dicts to a single string (assuming each item is a dict with 'role' and 'content')
    joined = "\n".join(
        f"{msg['role'].upper()}: {msg['content']}" for msg in history_list if 'content' in msg
    )
    lines = joined.splitlines()
    trimmed = "\n".join(lines[-max_lines:])
    return trimmed

TOTALS_BY_PHASE = {
    "GKY": 5,  # 5 sequential questions: GKY.01 through GKY.05
    "BUSINESS_PLAN": 45,  # Updated to 45 questions (9 sections restructured)
    "PLAN_TO_SUMMARY_TRANSITION": 1,  # Transition phase - show summary first
    "PLAN_TO_BUDGET_TRANSITION": 1,  # Transition phase - no questions, just waiting for user action
    "PLAN_TO_ROADMAP_TRANSITION": 1,  # Restored to normal flow
    "ROADMAP": 1,
    "ROADMAP_GENERATED": 1,
    "ROADMAP_TO_IMPLEMENTATION_TRANSITION": 1,
    "IMPLEMENTATION": 10
}

def calculate_phase_progress(
    current_phase: str,
    answered_count: int,
    current_tag: str = None,
    *,
    section_summary_pause: bool = False,
) -> dict:
    """
    Phase progress is derived from ``asked_q`` (session position), not a
    separate counter that can drift from the active question number.

    `asked_q` is also passed through so the frontend can render the question
    header on command turns where no new tag is parsed.
    """
    transition_phases = [
        "PLAN_TO_SUMMARY_TRANSITION",
        "PLAN_TO_BUDGET_TRANSITION",
        "PLAN_TO_ROADMAP_TRANSITION",
        "ROADMAP_TO_IMPLEMENTATION_TRANSITION",
        "ROADMAP_GENERATED",
    ]

    if current_phase in transition_phases:
        total_in_phase = TOTALS_BY_PHASE.get(current_phase, 1)
        return {
            "phase": current_phase,
            "answered": total_in_phase,
            "total": total_in_phase,
            "percent": 100,
            "asked_q": current_tag,
        }

    total_in_phase = TOTALS_BY_PHASE.get(current_phase, 1)

    if current_phase in ("GKY", "BUSINESS_PLAN") and current_tag:
        answered = derive_phase_answered_from_tag(
            current_phase,
            current_tag,
            section_summary_pause=section_summary_pause,
        )
    else:
        answered = min(max(answered_count, 0), total_in_phase)

    percent = round((answered / total_in_phase) * 100) if total_in_phase > 0 else 0

    return {
        "phase": current_phase,
        "answered": answered,
        "total": total_in_phase,
        "percent": percent,
        "asked_q": current_tag,
    }

def build_phase_scoped_overall_progress(
    current_phase: str,
    current_tag: str | None,
    *,
    section_summary_pause: bool = False,
) -> dict:
    """
    UI progress for the active phase only (GKY → X/5, Business Plan → X/45).
    Never mixes GKY counts into the Business Plan progress bar or header.
    """
    GKY_TOTAL = 5
    BP_TOTAL = 45

    if current_phase == "GKY":
        gky_done = derive_phase_answered_from_tag(
            "GKY", current_tag, section_summary_pause=section_summary_pause
        )
        return {
            "answered": gky_done,
            "total": GKY_TOTAL,
            "percent": round((gky_done / GKY_TOTAL) * 100) if GKY_TOTAL else 0,
            "scope": "gky",
            "phase_breakdown": {
                "gky_completed": gky_done,
                "gky_total": GKY_TOTAL,
                "bp_completed": 0,
                "bp_total": BP_TOTAL,
            },
        }

    if current_phase == "BUSINESS_PLAN":
        bp_done = derive_phase_answered_from_tag(
            "BUSINESS_PLAN", current_tag, section_summary_pause=section_summary_pause
        )
        return {
            "answered": bp_done,
            "total": BP_TOTAL,
            "percent": round((bp_done / BP_TOTAL) * 100) if BP_TOTAL else 0,
            "scope": "business_plan",
            "phase_breakdown": {
                "gky_completed": GKY_TOTAL,
                "gky_total": GKY_TOTAL,
                "bp_completed": bp_done,
                "bp_total": BP_TOTAL,
            },
        }

    return {}


def calculate_combined_progress(
    current_phase: str,
    answered_count: int,
    current_tag: str = None,
    *,
    section_summary_pause: bool = False,
) -> dict:
    """
    Full journey progress (GKY + Business Plan = 50) for internal/analytics.
    The chat UI uses ``build_phase_scoped_overall_progress`` instead so BP
    never shows GKY numbers in its progress bar.
    """
    GKY_TOTAL = 5
    BP_TOTAL = 45
    COMBINED_TOTAL = GKY_TOTAL + BP_TOTAL

    if current_phase in ["GKY", "BUSINESS_PLAN"]:
        if current_phase == "GKY":
            gky_done = derive_phase_answered_from_tag(
                "GKY", current_tag, section_summary_pause=section_summary_pause
            )
            bp_done = 0
        else:
            gky_done = GKY_TOTAL
            bp_done = derive_phase_answered_from_tag(
                "BUSINESS_PLAN", current_tag, section_summary_pause=section_summary_pause
            )

        overall_answered = gky_done + bp_done
        percent = round((overall_answered / COMBINED_TOTAL) * 100) if COMBINED_TOTAL > 0 else 0

        return {
            "phase": current_phase,
            "answered": overall_answered,
            "phase_answered": gky_done if current_phase == "GKY" else bp_done,
            "total": COMBINED_TOTAL,
            "percent": percent,
            "combined": True,
            "asked_q": current_tag,
            "phase_breakdown": {
                "gky_completed": gky_done,
                "gky_total": GKY_TOTAL,
                "bp_completed": bp_done,
                "bp_total": BP_TOTAL
            }
        }

    total_in_phase = TOTALS_BY_PHASE.get(current_phase, 1)
    answered = min(max(answered_count, 0), total_in_phase)
    percent = round((answered / total_in_phase) * 100) if total_in_phase > 0 else 0

    return {
        "phase": current_phase,
        "answered": answered,
        "total": total_in_phase,
        "percent": percent,
        "combined": False,
        "asked_q": current_tag,
    }
