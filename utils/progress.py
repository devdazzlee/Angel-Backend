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
    "GKY": 6,  # 6 sequential questions: GKY.01 through GKY.06
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
    Calculate progress within the current phase based on current question tag.
    This fixes the issue where progress was being calculated incorrectly.
    """
    print(f"🔍 Progress Calculation Debug:")
    print(f"  - current_phase: {current_phase}")
    print(f"  - answered_count: {answered_count}")
    print(f"  - current_tag: {current_tag}")
    
    # Handle transition phases - they don't have questions, just show 100% complete
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
    
    phase_order = ["GKY", "BUSINESS_PLAN", "ROADMAP", "ROADMAP_GENERATED", "ROADMAP_TO_IMPLEMENTATION_TRANSITION", "IMPLEMENTATION"]
    
    # Always use the current tag to determine the exact question number
    # CRITICAL: "current_step" means "the question the user is currently ON"
    # When the user sees Question 1, progress = 1 of 6 (not 0 of 6)
    if current_tag and current_tag.startswith(current_phase + "."):
        try:
            question_num = int(current_tag.split(".")[1])
            current_step = question_num
                
            print(f"✅ Using tag-based calculation: tag={current_tag}, question_num={question_num}, current_step={current_step}")
        except (ValueError, IndexError):
            current_step = answered_count
            print(f"❌ Tag parsing failed, using fallback: {current_step}")
    else:
        # Fallback: Use answered_count if no valid tag
        current_step = answered_count
        print(f"⚠️ No valid tag found, using fallback: {current_step}")
    
    # Get total for phase - handle missing phases gracefully
    total_in_phase = TOTALS_BY_PHASE.get(current_phase, 1)
    if current_phase not in TOTALS_BY_PHASE:
        print(f"⚠️ Phase '{current_phase}' not in TOTALS_BY_PHASE, using default total: 1")
    
    print(f"  - total_in_phase: {total_in_phase}")
    
    # Ensure current_step doesn't exceed total for this phase
    current_step = min(current_step, total_in_phase)
    print(f"  - final current_step: {current_step}")
    
    # Calculate percentage (1-100%)
    percent = max(1, min(100, round((current_step / total_in_phase) * 100)))
    print(f"  - calculated percent: {percent}")
    
    result = {
        "phase": current_phase,
        "answered": current_step,
        "total": total_in_phase,
        "percent": percent
    }
    
    print(f"📊 Final Progress Result: {result}")
    return result

def calculate_combined_progress(current_phase: str, answered_count: int, current_tag: str = None) -> dict:
    """
    Calculate combined progress for GKY + Business Plan phases (51 total questions).
    This provides an overall progress view that combines both phases.
    """
    print(f"🔍 Combined Progress Calculation Debug:")
    print(f"  - current_phase: {current_phase}")
    print(f"  - answered_count: {answered_count}")
    print(f"  - current_tag: {current_tag}")
    
    # Define combined phase totals
    COMBINED_TOTALS = {
        "GKY": 6,
        "BUSINESS_PLAN": 45,
        "COMBINED_GKY_BP": 51,  # 6 + 45 = 51 total questions
        "ROADMAP": 1,
        "IMPLEMENTATION": 10
    }
    
    # Calculate current step based on phase and question number
    # For GKY: current_step = question being viewed (1-based, inclusive)
    # For BP: current_step = total COMPLETED questions (GKY done + BP completed, exclusive of current)
    if current_tag and current_tag.startswith(current_phase + "."):
        try:
            question_num = int(current_tag.split(".")[1])
            
            if current_phase == "GKY":
                # GKY: question_num directly (Q1 = step 1, Q6 = step 6)
                current_step = question_num
            elif current_phase == "BUSINESS_PLAN":
                # For Business Plan: bp_completed = questions actually COMPLETED
                # When user is ON Q1, they haven't completed it yet → 0 BP completed
                # Combined step = all GKY (6) + BP questions completed (question_num - 1)
                current_step = 6 + (question_num - 1)
            else:
                # For other phases, use answered_count as fallback
                current_step = answered_count
                
            print(f"✅ Combined calculation: phase={current_phase}, question_num={question_num}, current_step={current_step}")
        except (ValueError, IndexError):
            current_step = answered_count
            print(f"❌ Tag parsing failed, using fallback: {current_step}")
    else:
        # Fallback: Use answered_count if no valid tag
        current_step = answered_count
        print(f"⚠️ No valid tag found, using fallback: {current_step}")
    
    # For GKY and Business Plan phases, use combined total (65)
    if current_phase in ["GKY", "BUSINESS_PLAN"]:
        total_combined = COMBINED_TOTALS["COMBINED_GKY_BP"]
        print(f"  - Using combined total: {total_combined}")
        
        # Ensure current_step doesn't exceed combined total
        current_step = min(current_step, total_combined)
        print(f"  - final current_step: {current_step}")
        
        # Calculate percentage based on combined total
        percent = max(1, min(100, round((current_step / total_combined) * 100)))
        print(f"  - calculated percent: {percent}")
        
        # Calculate phase-specific step for display
        if current_phase == "GKY":
            phase_specific_step = question_num if current_tag and current_tag.startswith("GKY.") else min(current_step, 6)
        elif current_phase == "BUSINESS_PLAN":
            phase_specific_step = question_num if current_tag and current_tag.startswith("BUSINESS_PLAN.") else max(0, current_step - 6)
        else:
            phase_specific_step = current_step
            
        result = {
            "phase": current_phase,
            "answered": current_step,  # Combined step (1-51)
            "phase_answered": phase_specific_step,  # Phase-specific step (1-6 for GKY, 1-45 for BP)
            "total": total_combined,
            "percent": percent,
            "combined": True,  # Flag to indicate this is combined progress
            "phase_breakdown": {
                "gky_completed": min(current_step, 6),
                "gky_total": 6,
                "bp_completed": max(0, current_step - 6),
                "bp_total": 45
            }
        }
    else:
        # For other phases, use regular phase calculation
        total_in_phase = TOTALS_BY_PHASE[current_phase]
        current_step = min(current_step, total_in_phase)
        percent = max(1, min(100, round((current_step / total_in_phase) * 100)))
        
        result = {
            "phase": current_phase,
            "answered": current_step,
            "total": total_in_phase,
            "percent": percent,
            "combined": False
        }
    
    print(f"📊 Combined Progress Result: {result}")
    return result
