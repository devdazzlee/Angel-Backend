from __future__ import annotations

import os
import re
import uuid
from typing import Any

from db.supabase import supabase

DEFAULT_BUCKET = "Founderport Docuemnts"
SIGNED_URL_TTL_SECONDS = 60 * 60  # 1 hour


def get_implementation_storage_bucket() -> str:
    return (os.getenv("SUPABASE_IMPLEMENTATION_BUCKET") or DEFAULT_BUCKET).strip()


def is_implementation_bucket_public() -> bool:
    raw = (os.getenv("SUPABASE_IMPLEMENTATION_BUCKET_PUBLIC") or "true").strip().lower()
    return raw in ("1", "true", "yes", "on")


def build_implementation_storage_path(
    user_id: str,
    session_id: str,
    task_id: str,
    file_extension: str,
) -> tuple[str, str]:
    """Return (file_id, storage_path) for a new upload."""
    safe_task = re.sub(r"[^a-zA-Z0-9_-]", "_", task_id)[:80]
    file_id = f"{session_id}_{safe_task}_{uuid.uuid4().hex}"
    filename = f"{file_id}.{file_extension}"
    storage_path = f"{user_id}/{session_id}/{safe_task}/{filename}"
    return file_id, storage_path


def upload_implementation_document_bytes(
    *,
    storage_path: str,
    content: bytes,
    content_type: str,
) -> str:
    bucket = get_implementation_storage_bucket()
    supabase.storage.from_(bucket).upload(
        storage_path,
        content,
        file_options={
            "content-type": content_type,
            "upsert": "false",
            "cache-control": "3600",
        },
    )
    return bucket


def create_implementation_document_view_url(
    storage_path: str,
    *,
    bucket: str | None = None,
    expires_in: int = SIGNED_URL_TTL_SECONDS,
) -> str:
    bucket_name = bucket or get_implementation_storage_bucket()

    if is_implementation_bucket_public():
        result = supabase.storage.from_(bucket_name).get_public_url(storage_path)
        if isinstance(result, dict):
            public_url = result.get("publicUrl") or result.get("publicURL")
            if public_url:
                return str(public_url)
        if isinstance(result, str):
            return result

    result = supabase.storage.from_(bucket_name).create_signed_url(
        storage_path,
        expires_in,
    )
    if isinstance(result, dict):
        signed = result.get("signedURL") or result.get("signedUrl")
        if signed:
            return str(signed)
    raise RuntimeError("Could not create view URL for uploaded document")


def create_implementation_document_signed_url(
    storage_path: str,
    *,
    bucket: str | None = None,
    expires_in: int = SIGNED_URL_TTL_SECONDS,
) -> str:
    return create_implementation_document_view_url(
        storage_path,
        bucket=bucket,
        expires_in=expires_in,
    )


def document_record_with_view_url(
    row: dict[str, Any],
    *,
    expires_in: int = SIGNED_URL_TTL_SECONDS,
) -> dict[str, Any]:
    storage_path = row.get("storage_path")
    bucket = row.get("storage_bucket") or get_implementation_storage_bucket()
    view_url = None
    if storage_path:
        try:
            view_url = create_implementation_document_view_url(
                storage_path,
                bucket=bucket,
                expires_in=expires_in,
            )
        except Exception:
            view_url = None

    return {
        "id": row.get("id"),
        "file_id": row.get("file_id"),
        "original_filename": row.get("original_filename"),
        "content_type": row.get("content_type"),
        "size_bytes": row.get("size_bytes"),
        "storage_bucket": bucket,
        "storage_path": storage_path,
        "uploaded_at": row.get("created_at"),
        "view_url": view_url,
    }
