#!/usr/bin/env python3
"""
Quick script to create a test session that skips to implementation phase
"""

import asyncio
from db.supabase import supabase

async def create_implementation_session():
    """Create a test session that starts in implementation phase"""
    
    test_user_id = "709cdc8a-ba39-4542-85b8-93edf51bc3d7"  # From your logs
    
    try:
        response = supabase.from_("chat_sessions").insert({
            "user_id": test_user_id,
            "title": "Test Implementation Session",
            "current_phase": "IMPLEMENTATION",
            "asked_q": "IMPLEMENTATION.01",
            "answered_count": 67,  # All previous questions completed
            "mode": "BUSINESS",
            "status": "OPEN"
        }).execute()
        
        if response.data:
            session = response.data[0]
            print(f"✅ Implementation test session created successfully!")
            print(f"Session ID: {session['id']}")
            print(f"Phase: {session['current_phase']}")
            print(f"URL: http://localhost:3000/venture/{session['id']}")
            return session['id']
        else:
            print("❌ Failed to create session")
            return None
            
    except Exception as e:
        print(f"❌ Error creating session: {e}")
        return None

if __name__ == "__main__":
    session_id = asyncio.run(create_implementation_session())
    if session_id:
        print(f"\n🚀 You can now test the implementation phase with session ID: {session_id}")
