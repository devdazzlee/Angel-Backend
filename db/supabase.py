import os
from dotenv import load_dotenv
import httpx
from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

# 60s timeout - reset_password_for_email triggers Supabase to send email via SMTP
# (Office 365, etc.) which can take 15-30+ seconds on first connect; httpx default is 5s
SUPABASE_HTTP_TIMEOUT = 60.0


def create_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
    http_client = httpx.Client(timeout=SUPABASE_HTTP_TIMEOUT)
    options = ClientOptions(httpx_client=http_client)
    return create_client(SUPABASE_URL, SUPABASE_KEY, options)


supabase: Client = create_supabase_client()