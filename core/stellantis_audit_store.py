"""Supabase storage for uploaded Stellantis OEM audit guide documents."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from core.stellantis_audit_parser import enrich_parsed_config, parse_stellantis_audit_guide
from core.ro_ocr import extract_audit_guide_text

_FLASH_KEY = "stellantis_upload_flash"
_LIBRARY_COLUMN = "stellantis_audit_library"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_library() -> dict:
    return {"active_id": "", "documents": {}}


def _normalize_library(raw) -> dict:
    if not isinstance(raw, dict):
        return _empty_library()
    documents = raw.get("documents") or {}
    if not isinstance(documents, dict):
        documents = {}
    cleaned: dict[str, dict] = {}
    for doc_id, entry in documents.items():
        if not isinstance(entry, dict):
            continue
        key = str(doc_id or entry.get("id") or "").strip()
        if not key:
            continue
        cleaned[key] = {**entry, "id": key}
    active_id = str(raw.get("active_id") or "").strip()
    if active_id and active_id not in cleaned:
        active_id = ""
    if not active_id:
        for doc_id, entry in cleaned.items():
            if entry.get("is_active"):
                active_id = doc_id
                break
    return {"active_id": active_id, "documents": cleaned}


def _load_library(supabase) -> dict:
    if supabase is None:
        return _empty_library()
    try:
        rows = (
            supabase.table("dealer_settings")
            .select(_LIBRARY_COLUMN)
            .eq("id", 1)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:
        return _empty_library()
    if not rows:
        return _empty_library()
    return _normalize_library(rows[0].get(_LIBRARY_COLUMN))


def _persist_library(supabase, library: dict) -> None:
    if supabase is None:
        raise RuntimeError("Supabase is not configured.")
    payload = _normalize_library(library)
    supabase.table("dealer_settings").update({_LIBRARY_COLUMN: payload}).eq("id", 1).execute()


def _new_document_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"doc_{stamp}"


def bump_stellantis_config_cache() -> None:
    st.session_state["stellantis_config_version"] = int(
        st.session_state.get("stellantis_config_version", 0)
    ) + 1


def _active_document(library: dict) -> dict | None:
    active_id = str(library.get("active_id") or "").strip()
    if not active_id:
        return None
    return (library.get("documents") or {}).get(active_id)


def _fetch_active_config_from_db(supabase) -> dict:
    if supabase is None:
        return {"_loaded": True}

    library = _load_library(supabase)
    row = _active_document(library)
    if not row:
        return {"_loaded": True}

    parsed = enrich_parsed_config(str(row.get("content") or ""), row.get("parsed_config") or {})
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
        "dealer_requirements": parsed.get("dealer_requirements") or {},
        "requirement_checks": parsed.get("requirement_checks") or [],
        "parse_warnings": parsed.get("parse_warnings") or [],
        "parsed_at": parsed.get("parsed_at"),
        "reason_code_count": parsed.get("reason_code_count") or len(parsed.get("reason_codes") or {}),
        "requirement_check_count": parsed.get("requirement_check_count") or len(parsed.get("requirement_checks") or []),
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

    library = _load_library(supabase)
    active_id = str(library.get("active_id") or "").strip()
    documents = library.get("documents") or {}
    display_rows = []
    for doc_id, row in sorted(
        documents.items(),
        key=lambda item: str(item[1].get("created_at") or ""),
        reverse=True,
    ):
        parsed = row.get("parsed_config") or {}
        content = str(row.get("content") or "")
        display_rows.append(
            {
                "id": doc_id,
                "created_at": row.get("created_at"),
                "source_file": row.get("source_file") or "",
                "version_label": row.get("version_label") or "",
                "uploaded_by": row.get("uploaded_by") or "",
                "ocr_used": bool(row.get("ocr_used")),
                "is_active": doc_id == active_id,
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

    library = _load_library(supabase)
    doc_id = _new_document_id()
    library.setdefault("documents", {})[doc_id] = {
        "id": doc_id,
        "created_at": _utc_now_iso(),
        "source_file": str(source_file or "").strip(),
        "version_label": str(version_label or "").strip(),
        "content": str(content or ""),
        "parsed_config": parsed_config,
        "uploaded_by": str(uploaded_by or "").strip(),
        "ocr_used": bool(ocr_used),
    }
    if set_active:
        library["active_id"] = doc_id
    _persist_library(supabase, library)
    bump_stellantis_config_cache()
    return {"ok": True, "id": doc_id}


def set_active_stellantis_audit_document(supabase, document_id: str | int) -> None:
    if supabase is None:
        raise RuntimeError("Supabase is not configured.")
    library = _load_library(supabase)
    doc_id = str(document_id or "").strip()
    if doc_id not in (library.get("documents") or {}):
        raise ValueError("Guide not found.")
    library["active_id"] = doc_id
    _persist_library(supabase, library)
    bump_stellantis_config_cache()


def delete_stellantis_audit_document(supabase, document_id: str | int) -> None:
    if supabase is None:
        raise RuntimeError("Supabase is not configured.")
    library = _load_library(supabase)
    doc_id = str(document_id or "").strip()
    documents = library.get("documents") or {}
    if doc_id not in documents:
        raise ValueError("Guide not found.")
    documents.pop(doc_id, None)
    if str(library.get("active_id") or "") == doc_id:
        library["active_id"] = next(iter(documents), "") if documents else ""
    library["documents"] = documents
    _persist_library(supabase, library)
    bump_stellantis_config_cache()


def ingest_stellantis_audit_upload(
    supabase,
    *,
    file_name: str,
    file_bytes: bytes,
    uploaded_by: str,
    version_label: str = "",
    set_active: bool = True,
    pasted_text: str = "",
    progress=None,
) -> dict:
    name = str(file_name or "").strip().lower()
    pasted = str(pasted_text or "").strip()
    if pasted:
        if progress:
            progress("Parsing pasted guide text…")
        text = pasted
        ocr_used = False
    elif name.endswith(".txt"):
        if progress:
            progress("Reading .txt guide file…")
        text = file_bytes.decode("utf-8", errors="replace")
        ocr_used = False
    else:
        text, ocr_used = extract_audit_guide_text(file_bytes, progress=progress)

    if progress:
        progress("Parsing Stellantis reason codes…")
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
            "message": (
                f"Saved {len(parsed.get('reason_codes') or {})} reason codes and "
                f"{parsed.get('requirement_check_count', 0)} dealer requirement checks from {file_name}."
            ),
            "reason_code_count": len(parsed.get("reason_codes") or {}),
            "requirement_check_count": parsed.get("requirement_check_count") or 0,
            "ocr_used": ocr_used,
            "parse_warnings": parsed.get("parse_warnings") or [],
        }
    )
    return result


def get_stellantis_document_content(supabase, document_id: str | int) -> dict | None:
    if supabase is None:
        return None
    library = _load_library(supabase)
    return (library.get("documents") or {}).get(str(document_id or "").strip())


def bundled_stellantis_guide_text() -> tuple[str, bool]:
    """Return repo-bundled OCR text for the default Stellantis audit guide, if present."""
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "docs" / "stellantis_audit_ocr.txt"
    if not path.is_file():
        return "", False
    return path.read_text(encoding="utf-8", errors="replace"), True


def pop_upload_flash() -> dict | None:
    return st.session_state.pop(_FLASH_KEY, None)


def set_upload_flash(*, kind: str, message: str) -> None:
    st.session_state[_FLASH_KEY] = {"kind": kind, "message": message}


def format_stellantis_save_error(exc: Exception) -> str:
    text = str(exc or "").strip()
    if "stellantis_audit_library" in text.lower() or "column" in text.lower():
        return (
            "Supabase is missing the OEM audit guide column. "
            "Run this once in SQL Editor: "
            "`ALTER TABLE dealer_settings ADD COLUMN IF NOT EXISTS stellantis_audit_library "
            "JSONB DEFAULT '{\"active_id\":\"\",\"documents\":{}}'::jsonb;`"
        )
    if "row-level security" in text.lower() or "42501" in text:
        return (
            "Supabase blocked the save on dealer_settings. "
            "Confirm dealer_settings write policies are enabled (same as Audit Rules / POPPS)."
        )
    return text or "Upload failed."
