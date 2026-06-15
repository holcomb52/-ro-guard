"""Supabase storage for uploaded Stellantis OEM audit guide documents."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from core.stellantis_audit_parser import parse_stellantis_audit_guide

_TABLE = "stellantis_audit_documents"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def bump_stellantis_config_cache() -> None:
    st.session_state["stellantis_config_version"] = int(
        st.session_state.get("stellantis_config_version", 0)
    ) + 1


def _fetch_active_config_from_db(supabase) -> dict:
    if supabase is None:
        return {"_loaded": True}
    try:
        rows = (
            supabase.table(_TABLE)
            .select("id, source_file, version_label, parsed_config, uploaded_by, created_at, ocr_used")
            .eq("is_active", True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:
        return {"_loaded": True}

    if not rows:
        return {"_loaded": True}

    row = rows[0]
    parsed = row.get("parsed_config") or {}
    return {
        "_loaded": True,
        "document_id": row.get("id"),
        "source_file": row.get("source_file") or "",
        "version_label": row.get("version_label") or "",
        "uploaded_by": row.get("uploaded_by") or "",
        "created_at": row.get("created_at"),
        "ocr_used": bool(row.get("ocr_used")),
        "reason_codes": parsed.get("reason_codes") or {},
        "non_warranty_patterns": parsed.get("non_warranty_patterns") or [],
        "parse_warnings": parsed.get("parse_warnings") or [],
        "parsed_at": parsed.get("parsed_at"),
        "reason_code_count": parsed.get("reason_code_count") or 0,
    }


def load_active_stellantis_config(supabase) -> dict:
    """Return parsed config from the active uploaded guide, or empty dict."""
    version = int(st.session_state.get("stellantis_config_version", 0))
    cache_key = f"_stellantis_active_config_v{version}"
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    payload = _fetch_active_config_from_db(supabase)
    st.session_state[cache_key] = payload
    return payload


def bind_stellantis_runtime_config(supabase) -> dict:
    """Load active guide config for the current app run."""
    config = load_active_stellantis_config(supabase)
    st.session_state["_stellantis_runtime_config"] = config
    return config


def get_bound_stellantis_config() -> dict:
    return dict(st.session_state.get("_stellantis_runtime_config") or {})


def list_stellantis_audit_documents(supabase) -> pd.DataFrame:
    if supabase is None:
        return pd.DataFrame()
    try:
        rows = (
            supabase.table(_TABLE)
            .select(
                "id, created_at, source_file, version_label, uploaded_by, ocr_used, is_active, "
                "parsed_config, content"
            )
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
    except Exception:
        return pd.DataFrame()

    display_rows = []
    for row in rows:
        parsed = row.get("parsed_config") or {}
        content = str(row.get("content") or "")
        display_rows.append(
            {
                "id": row.get("id"),
                "created_at": row.get("created_at"),
                "source_file": row.get("source_file") or "",
                "version_label": row.get("version_label") or "",
                "uploaded_by": row.get("uploaded_by") or "",
                "ocr_used": bool(row.get("ocr_used")),
                "is_active": bool(row.get("is_active")),
                "reason_codes": int(parsed.get("reason_code_count") or len(parsed.get("reason_codes") or {})),
                "text_chars": len(content),
                "parse_warnings": "; ".join(parsed.get("parse_warnings") or []),
            }
        )
    return pd.DataFrame(display_rows)


def save_stellantis_audit_document(
    supabase,
    *,
    source_file: str,
    content: str,
    parsed_config: dict,
    uploaded_by: str,
    ocr_used: bool,
    version_label: str = "",
    set_active: bool = True,
) -> dict:
    if supabase is None:
        raise RuntimeError("Supabase is not configured.")

    if set_active:
        supabase.table(_TABLE).update({"is_active": False}).eq("is_active", True).execute()

    payload = {
        "created_at": _utc_now_iso(),
        "source_file": str(source_file or "").strip(),
        "version_label": str(version_label or "").strip(),
        "content": str(content or ""),
        "parsed_config": parsed_config,
        "uploaded_by": str(uploaded_by or "").strip(),
        "ocr_used": bool(ocr_used),
        "is_active": bool(set_active),
    }
    resp = supabase.table(_TABLE).insert(payload).execute()
    doc_id = None
    if resp.data:
        doc_id = resp.data[0].get("id")
    bump_stellantis_config_cache()
    return {"ok": True, "id": doc_id}


def set_active_stellantis_audit_document(supabase, document_id: int) -> None:
    if supabase is None:
        raise RuntimeError("Supabase is not configured.")
    supabase.table(_TABLE).update({"is_active": False}).eq("is_active", True).execute()
    supabase.table(_TABLE).update({"is_active": True}).eq("id", int(document_id)).execute()
    bump_stellantis_config_cache()


def delete_stellantis_audit_document(supabase, document_id: int) -> None:
    if supabase is None:
        raise RuntimeError("Supabase is not configured.")
    supabase.table(_TABLE).delete().eq("id", int(document_id)).execute()
    bump_stellantis_config_cache()


def ingest_stellantis_audit_upload(
    supabase,
    *,
    file_name: str,
    file_bytes: bytes,
    uploaded_by: str,
    version_label: str = "",
    set_active: bool = True,
) -> dict:
    from core.ro_ocr import extract_ro_text, ocr_available

    text, ocr_used = extract_ro_text(file_bytes, force_ocr=ocr_available())
    parsed = parse_stellantis_audit_guide(text)
    if not parsed.get("reason_codes"):
        return {
            "ok": False,
            "message": "Could not parse reason codes from this PDF. Try a clearer scan or re-export the file.",
            "text_len": len(text.strip()),
            "ocr_used": ocr_used,
        }

    result = save_stellantis_audit_document(
        supabase,
        source_file=file_name,
        content=text,
        parsed_config=parsed,
        uploaded_by=uploaded_by,
        ocr_used=ocr_used,
        version_label=version_label,
        set_active=set_active,
    )
    result.update(
        {
            "ok": True,
            "message": f"Saved {len(parsed.get('reason_codes') or {})} reason codes from {file_name}.",
            "reason_code_count": len(parsed.get("reason_codes") or {}),
            "ocr_used": ocr_used,
            "parse_warnings": parsed.get("parse_warnings") or [],
        }
    )
    return result


def get_stellantis_document_content(supabase, document_id: int) -> dict | None:
    if supabase is None:
        return None
    rows = (
        supabase.table(_TABLE)
        .select("id, source_file, version_label, content, parsed_config, is_active, created_at")
        .eq("id", int(document_id))
        .limit(1)
        .execute()
        .data
        or []
    )
    return rows[0] if rows else None
