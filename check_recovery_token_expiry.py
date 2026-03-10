"""
Script to check Supabase recovery token expiry setting.
This generates a recovery link and decodes the token to see its expiration time.
"""
import os
import sys
import base64
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env")
    sys.exit(1)

# Create Supabase client with service role key
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def decode_jwt(token: str):
    """Decode JWT token to get payload."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        # Decode payload (second part)
        payload = parts[1]
        # Add padding if needed
        padding = len(payload) % 4
        if padding:
            payload += '=' * (4 - padding)
        
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        print(f"Error decoding token: {e}")
        return None

def check_recovery_token_expiry(email: str):
    """Generate a recovery link and check token expiration."""
    print(f"\n{'='*60}")
    print(f"Checking Recovery Token Expiry for: {email}")
    print(f"{'='*60}\n")
    
    try:
        # Get frontend URL
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        frontend_url = frontend_url.rstrip('/')
        redirect_url = f"{frontend_url}/reset-password"
        
        print(f"Frontend URL: {frontend_url}")
        print(f"Redirect URL: {redirect_url}\n")
        
        # Generate recovery link using admin API
        print("Generating recovery link...")
        try:
            recovery_link_response = supabase.auth.admin.generate_link({
                "type": "recovery",
                "email": email,
                "options": {
                    "redirect_to": redirect_url
                }
            })
            
            # Extract recovery link
            recovery_link = None
            if hasattr(recovery_link_response, 'properties'):
                props = recovery_link_response.properties
                recovery_link = getattr(props, 'action_link', None) or getattr(props, 'recovery_link', None)
            elif hasattr(recovery_link_response, 'action_link'):
                recovery_link = recovery_link_response.action_link
            elif isinstance(recovery_link_response, dict):
                recovery_link = recovery_link_response.get('action_link') or recovery_link_response.get('properties', {}).get('action_link')
            
            if not recovery_link:
                print("ERROR: Could not extract recovery link from response")
                print(f"Response: {recovery_link_response}")
                return
            
            print(f"Recovery link generated: {recovery_link[:80]}...\n")
            
            # Extract token from link
            # Format: https://xxx.supabase.co/auth/v1/verify?token=xxx&type=recovery&redirect_to=xxx
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(recovery_link)
            params = parse_qs(parsed.query)
            token = params.get('token', [None])[0]
            
            if not token:
                print("ERROR: Could not extract token from recovery link")
                return
            
            print(f"Token extracted: {token[:50]}...\n")
            
            # Decode token
            print("Decoding token...")
            token_data = decode_jwt(token)
            
            if not token_data:
                print("ERROR: Could not decode token")
                return
            
            print(f"\n{'='*60}")
            print("TOKEN PAYLOAD:")
            print(f"{'='*60}")
            for key, value in token_data.items():
                if key == 'exp':
                    exp_timestamp = value
                    exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                    now = datetime.now(timezone.utc)
                    time_until_expiry = exp_datetime - now
                    time_until_expiry_seconds = time_until_expiry.total_seconds()
                    
                    print(f"  {key}: {value}")
                    print(f"    → Expires at: {exp_datetime.isoformat()}")
                    print(f"    → Current time: {now.isoformat()}")
                    print(f"    → Time until expiry: {time_until_expiry_seconds:.0f} seconds ({time_until_expiry_seconds/60:.1f} minutes)")
                    
                    if time_until_expiry_seconds < 60:
                        print(f"    ⚠️  WARNING: Token expires in less than 1 minute!")
                    elif time_until_expiry_seconds < 3600:
                        print(f"    ⚠️  WARNING: Token expires in less than 1 hour!")
                    else:
                        print(f"    ✅ Token expires in 1 hour or more")
                else:
                    print(f"  {key}: {value}")
            
            print(f"\n{'='*60}")
            print("SUMMARY:")
            print(f"{'='*60}")
            exp = token_data.get('exp')
            if exp:
                exp_datetime = datetime.fromtimestamp(exp, tz=timezone.utc)
                now = datetime.now(timezone.utc)
                time_until_expiry_seconds = (exp_datetime - now).total_seconds()
                
                print(f"Recovery Token Expiry: {time_until_expiry_seconds:.0f} seconds ({time_until_expiry_seconds/60:.1f} minutes)")
                print(f"Expected: 3600 seconds (60 minutes / 1 hour)")
                
                if abs(time_until_expiry_seconds - 3600) < 60:
                    print("✅ Token expiry matches expected 1 hour setting")
                else:
                    print(f"❌ Token expiry does NOT match expected 1 hour setting")
                    print(f"   Difference: {abs(time_until_expiry_seconds - 3600):.0f} seconds")
                    print(f"\n   ACTION REQUIRED:")
                    print(f"   Go to Supabase Dashboard → Authentication → URL Configuration")
                    print(f"   Set 'Recovery Token Expiry' to 3600 seconds (1 hour)")
            
        except AttributeError:
            print("ERROR: admin.generate_link not available in this Supabase client version")
            print("Falling back to standard method...")
            supabase.auth.reset_password_for_email(email, {"redirect_to": redirect_url})
            print("Password reset email sent via standard method.")
            print("Check your email and decode the token from the link to see expiry.")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python check_recovery_token_expiry.py <email>")
        print("\nExample:")
        print("  python check_recovery_token_expiry.py user@example.com")
        sys.exit(1)
    
    email = sys.argv[1]
    check_recovery_token_expiry(email)
