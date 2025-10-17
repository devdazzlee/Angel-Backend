#!/usr/bin/env python3
"""
Script to update existing session to skip to roadmap phase
"""

import asyncio
from db.supabase import supabase

async def update_session_to_roadmap(session_id: str):
    """Update existing session to roadmap phase"""
    
    try:
        response = supabase.from_("chat_sessions").update({
            "current_phase": "ROADMAP",
            "asked_q": "ROADMAP.01",
            "answered_count": 66,  # KYC (20) + Business Plan (46)
            "updated_at": "now()"
        }).eq("id", session_id).execute()
        
        if response.data:
            session = response.data[0]
            print(f"✅ Session updated successfully!")
            print(f"Session ID: {session['id']}")
            print(f"New Phase: {session['current_phase']}")
            print(f"URL: http://localhost:3000/venture/{session['id']}")
            return True
        else:
            print("❌ Failed to update session")
            return False
            
    except Exception as e:
        print(f"❌ Error updating session: {e}")
        return False

if __name__ == "__main__":
    # Replace with your actual session ID
    session_id = "c6a2718c-c2d8-4f01-aaae-42ac9e408423"  # From your logs
    success = asyncio.run(update_session_to_roadmap(session_id))
    if success:
        print(f"\n🎯 Your existing session has been updated to roadmap phase!")
