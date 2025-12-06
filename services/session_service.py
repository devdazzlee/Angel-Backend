from db.supabase import supabase

async def create_session(user_id: str, title: str):
    response = supabase \
        .from_("chat_sessions") \
        .insert({
            "user_id": user_id, 
            "title": title,
            "current_phase": "KYC",
            "asked_q": "KYC.01",
            "answered_count": 0
        }) \
        .execute()

    if response.data:
        return response.data[0]
    else:
        raise Exception("Failed to create session")

async def list_sessions(user_id: str):
    response = supabase.from_("chat_sessions").select("*").eq("user_id", user_id).order("updated_at", desc=True).execute()
    return response.data

async def get_session(session_id: str, user_id: str):
    response = supabase.from_("chat_sessions").select("*").eq("id", session_id).eq("user_id", user_id).single().execute()
    
    if response.data:
        session = response.data
        # Ensure session has required fields with defaults
        session.setdefault("current_phase", "KYC")
        session.setdefault("asked_q", "KYC.01")
        session.setdefault("answered_count", 0)
        return session
    else:
        raise Exception("Session not found")

async def patch_session(session_id: str, user_id_or_updates, updates: dict = None):
    """
    Backwards compatible patch_session that accepts either:
    - patch_session(session_id, updates) - OLD signature
    - patch_session(session_id, user_id, updates) - NEW signature
    """
    if updates is None:
        # Old signature: patch_session(session_id, updates)
        updates = user_id_or_updates
        response = supabase.from_("chat_sessions").update(updates).eq("id", session_id).execute()
    else:
        # New signature: patch_session(session_id, user_id, updates)
        user_id = user_id_or_updates
        response = supabase.from_("chat_sessions").update(updates).eq("id", session_id).eq("user_id", user_id).execute()
    
    return response.data[0] if response.data else None