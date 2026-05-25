# api/index.py
#
# Vercel serverless entry point. The actual FastAPI app — routers, CORS,
# middleware, exception handlers — lives in `main.py`. This file used to
# re-declare the entire app, which silently drifted from main.py over time
# (e.g. business-context routes registered locally but missing in prod),
# producing 405 / 500 errors only in deployed environments.
#
# Single source of truth: import `app` from main.py. Do not add routes or
# middleware here — add them in main.py so every deployment target
# (Vercel / Azure / Heroku / local) sees the same surface.
from main import app  # noqa: F401  (re-exported as the Vercel handler)
