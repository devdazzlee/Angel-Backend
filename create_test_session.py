#!/usr/bin/env python3
"""
Quick script to create a test session that skips to roadmap phase
"""

import asyncio
import os
from db.supabase import supabase

async def create_test_session():
    """Create a test session that starts in roadmap phase"""
    
    # You can replace this with any user ID from your database
    test_user_id = "709cdc8a-ba39-4542-85b8-93edf51bc3d7"  # From your logs
    
    try:
        response = supabase.from_("chat_sessions").insert({
            "user_id": test_user_id,
            "title": "Test Roadmap Session",
            "current_phase": "ROADMAP",
            "asked_q": "ROADMAP.01",
            "answered_count": 66,  # Business plan questions (20 KYC + 46 Business Plan)
            "mode": "BUSINESS",
            "status": "OPEN"
        }).execute()
        
        if response.data:
            session = response.data[0]
            print(f"✅ Test session created successfully!")
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
    session_id = asyncio.run(create_test_session())
    if session_id:
        print(f"\n🎯 You can now test the roadmap phase with session ID: {session_id}")
