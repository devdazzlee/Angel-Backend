from typing import Optional

def parse_tag(text: str) -> Optional[str]:
    import re
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

def calculate_phase_progress(current_phase: str, answered_count: int, current_tag: str = None) -> dict:
    """
    Progress = number of questions the user has ANSWERED, not the question
    they are currently viewing.  Q1 visible but unanswered → 0 / 5 = 0 %.
    """
    transition_phases = [
        "PLAN_TO_SUMMARY_TRANSITION",
        "PLAN_TO_BUDGET_TRANSITION",
        "PLAN_TO_ROADMAP_TRANSITION",
        "ROADMAP_TO_IMPLEMENTATION_TRANSITION",
        "ROADMAP_GENERATED"
    ]

    if current_phase in transition_phases:
        total_in_phase = TOTALS_BY_PHASE.get(current_phase, 1)
        return {
            "phase": current_phase,
            "answered": total_in_phase,
            "total": total_in_phase,
            "percent": 100
        }

    total_in_phase = TOTALS_BY_PHASE.get(current_phase, 1)

    answered = min(max(answered_count, 0), total_in_phase)

    percent = round((answered / total_in_phase) * 100) if total_in_phase > 0 else 0

    return {
        "phase": current_phase,
        "answered": answered,
        "total": total_in_phase,
        "percent": percent
    }

def calculate_combined_progress(current_phase: str, answered_count: int, current_tag: str = None) -> dict:
    """
    Overall progress across GKY (5) + Business Plan (45) = 50 total questions.
    Based strictly on answered_count — never on the tag of the question being viewed.
    """
    GKY_TOTAL = 5
    BP_TOTAL = 45
    COMBINED_TOTAL = GKY_TOTAL + BP_TOTAL

    if current_phase in ["GKY", "BUSINESS_PLAN"]:
        if current_phase == "GKY":
            gky_done = min(max(answered_count, 0), GKY_TOTAL)
            bp_done = 0
        else:
            gky_done = GKY_TOTAL
            bp_done = min(max(answered_count, 0), BP_TOTAL)

        overall_answered = gky_done + bp_done
        percent = round((overall_answered / COMBINED_TOTAL) * 100) if COMBINED_TOTAL > 0 else 0

        return {
            "phase": current_phase,
            "answered": overall_answered,
            "phase_answered": gky_done if current_phase == "GKY" else bp_done,
            "total": COMBINED_TOTAL,
            "percent": percent,
            "combined": True,
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
        "combined": False
    }
