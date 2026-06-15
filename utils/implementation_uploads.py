import os
import tempfile
from pathlib import Path


def resolve_implementation_upload_dir() -> str:
    """
    Resolve a writable directory for implementation task documents.

    Cloud/serverless runtimes often mount the app directory read-only; using
    a relative ``uploads/`` folder fails with Errno 30. Prefer an explicit
    env override, otherwise use the OS temp directory.
    """
    configured = (os.getenv("IMPLEMENTATION_UPLOAD_DIR") or "").strip()
    if configured:
        base = Path(configured).expanduser().resolve()
    else:
        base = Path(tempfile.gettempdir()) / "founderport_implementation_uploads"

    base.mkdir(parents=True, exist_ok=True)
    return str(base)
