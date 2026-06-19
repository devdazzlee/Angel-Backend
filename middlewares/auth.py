from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db.supabase import supabase_auth
import logging

logger = logging.getLogger(__name__)
oauth_scheme = HTTPBearer()

async def verify_auth_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(oauth_scheme)
):
    token = credentials.credentials
    print(f"🔐 Verifying token for path: {request.url.path}")
    
    try:
        # Use Supabase's built-in token verification
        user_response = supabase_auth.auth.get_user(token)
        
        if not user_response or not user_response.user:
            print("❌ Invalid user from token")
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = user_response.user
        print(f"✅ Token validated successfully for user: {user.email}")
        
        request.state.user = {
            "id": user.id, 
            "email": user.email
        }
        
    except Exception as e:
        print(f"❌ Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

