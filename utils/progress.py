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
    "KYC": 19,  # Updated to 19 questions (removed privacy question)
    "BUSINESS_PLAN": 46,  # Restored to full 46 questions
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
    
    phase_order = ["KYC", "BUSINESS_PLAN", "ROADMAP", "ROADMAP_GENERATED", "ROADMAP_TO_IMPLEMENTATION_TRANSITION", "IMPLEMENTATION"]
    
    # Always use the current tag to determine the exact question number
    if current_tag and current_tag.startswith(current_phase + "."):
        try:
            question_num = int(current_tag.split(".")[1])
            current_step = question_num
            print(f"✅ Using tag-based calculation: tag={current_tag}, question_num={question_num}, current_step={current_step}")
        except (ValueError, IndexError):
            # Fallback to answered_count if tag parsing fails
            current_step = max(1, answered_count)
            print(f"❌ Tag parsing failed, using answered_count: {current_step}")
    else:
        # Fallback: Use answered_count if no valid tag
        current_step = max(1, answered_count)
        print(f"⚠️ No valid tag found, using answered_count: {current_step}")
    
    total_in_phase = TOTALS_BY_PHASE[current_phase]
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
    Calculate combined progress for KYC + Business Plan phases (65 total questions).
    This provides an overall progress view that combines both phases.
    """
    print(f"🔍 Combined Progress Calculation Debug:")
    print(f"  - current_phase: {current_phase}")
    print(f"  - answered_count: {answered_count}")
    print(f"  - current_tag: {current_tag}")
    
    # Define combined phase totals
    COMBINED_TOTALS = {
        "KYC": 19,
        "BUSINESS_PLAN": 46,
        "COMBINED_KYC_BP": 65,  # 19 + 46 = 65 total questions
        "ROADMAP": 1,
        "IMPLEMENTATION": 10
    }
    
    # Calculate current step based on phase and question number
    if current_tag and current_tag.startswith(current_phase + "."):
        try:
            question_num = int(current_tag.split(".")[1])
            
            if current_phase == "KYC":
                # For KYC, current step is just the question number
                current_step = question_num
            elif current_phase == "BUSINESS_PLAN":
                # For Business Plan, add KYC total (19) to current question number
                current_step = 19 + question_num
            else:
                # For other phases, use answered_count as fallback
                current_step = answered_count
                
            print(f"✅ Combined calculation: phase={current_phase}, question_num={question_num}, current_step={current_step}")
        except (ValueError, IndexError):
            # Fallback to answered_count if tag parsing fails
            current_step = answered_count
            print(f"❌ Tag parsing failed, using answered_count: {current_step}")
    else:
        # Fallback: Use answered_count if no valid tag
        current_step = answered_count
        print(f"⚠️ No valid tag found, using answered_count: {current_step}")
    
    # For KYC and Business Plan phases, use combined total (65)
    if current_phase in ["KYC", "BUSINESS_PLAN"]:
        total_combined = COMBINED_TOTALS["COMBINED_KYC_BP"]
        print(f"  - Using combined total: {total_combined}")
        
        # Ensure current_step doesn't exceed combined total
        current_step = min(current_step, total_combined)
        print(f"  - final current_step: {current_step}")
        
        # Calculate percentage based on combined total
        percent = max(1, min(100, round((current_step / total_combined) * 100)))
        print(f"  - calculated percent: {percent}")
        
        # Calculate phase-specific step for display
        if current_phase == "KYC":
            phase_specific_step = question_num if current_tag and current_tag.startswith("KYC.") else min(current_step, 19)
        elif current_phase == "BUSINESS_PLAN":
            phase_specific_step = question_num if current_tag and current_tag.startswith("BUSINESS_PLAN.") else max(0, current_step - 19)
        else:
            phase_specific_step = current_step
            
        result = {
            "phase": current_phase,
            "answered": current_step,  # Combined step (1-65)
            "phase_answered": phase_specific_step,  # Phase-specific step (1-19 for KYC, 1-46 for BP)
            "total": total_combined,
            "percent": percent,
            "combined": True,  # Flag to indicate this is combined progress
            "phase_breakdown": {
                "kyc_completed": min(current_step, 19),
                "kyc_total": 19,
                "bp_completed": max(0, current_step - 19),
                "bp_total": 46
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
