"""Admin UI for uploaded Stellantis OEM audit guide documents."""

from __future__ import annotations

import streamlit as st

from core.auth import auth_user_email
from core.ro_ocr import ocr_runtime_ready
from core.stellantis_audit import render_stellantis_audit_reference
from core.stellantis_audit_store import (
    bind_stellantis_runtime_config,
    bundled_stellantis_guide_text,
    delete_stellantis_audit_document,
    get_stellantis_document_content,
    ingest_stellantis_audit_upload,
    list_stellantis_audit_documents,
    load_active_stellantis_config,
    pop_upload_flash,
    set_active_stellantis_audit_document,
    set_upload_flash,
)


def _format_supabase_error(exc: Exception) -> str:
    text = str(exc or "").strip()
    if "row-level security" in text.lower() or "42501" in text:
        return (
            "Supabase blocked the save (row-level security). "
            "In Supabase → SQL Editor, run the file `docs/FIX_STELLANTIS_AUDIT_RLS.sql`, "
            "then try again."
        )
    return text or "Upload failed."


def _run_guide_ingest(
    supabase,
    *,
    file_name: str,
    file_bytes: bytes,
    version_label: str,
    make_active: bool,
    pasted_text: str = "",
) -> None:
    with st.status("Processing OEM audit guide…", expanded=True) as status:

        def _progress(message: str) -> None:
            status.write(message)

        result = ingest_stellantis_audit_upload(
            supabase,
            file_name=file_name,
            file_bytes=file_bytes,
            uploaded_by=auth_user_email() or "unknown",
            version_label=version_label,
            set_active=make_active,
            pasted_text=pasted_text,
            progress=_progress,
        )

    if result.get("ok"):
        status.update(label="Guide saved", state="complete")
        msg = result.get("message") or "Guide saved."
        warnings = result.get("parse_warnings") or []
        if warnings:
            msg = f"{msg} ({'; '.join(warnings)})"
        set_upload_flash(kind="success", message=msg)
        bind_stellantis_runtime_config(supabase)
        st.rerun()
    else:
        status.update(label="Could not save guide", state="error")
        set_upload_flash(kind="error", message=result.get("message") or "Upload failed.")
        st.rerun()


def render_stellantis_audit_guide_tab(
    supabase,
    *,
    can_upload: bool,
    render_role_gate_message,
    content_admin_roles: tuple[str, ...],
) -> None:
    st.header("OEM Audit Guide")
    st.caption(
        "Upload the Stellantis **Warranty Audit — Reason Code Application Guide** PDF. "
        "RO Guard extracts reason codes and keyword checks from the document and applies them "
        "as hard stops on Review. When Stellantis publishes an updated guide, upload the new PDF "
        "and set it active — no code deploy required."
    )

    flash = pop_upload_flash()
    if flash:
        if flash.get("kind") == "success":
            st.success(flash.get("message") or "Guide saved.")
        else:
            st.error(flash.get("message") or "Upload failed.")

    bind_stellantis_runtime_config(supabase)
    active = load_active_stellantis_config(supabase)

    if active.get("document_id"):
        label_bits = [active.get("source_file") or "Uploaded guide"]
        if active.get("version_label"):
            label_bits.append(f"({active['version_label']})")
        ocr_note = " · OCR used" if active.get("ocr_used") else ""
        st.success(
            f"**Active guide:** {' '.join(label_bits)} — "
            f"{int(active.get('reason_code_count') or 0)} reason codes parsed{ocr_note}. "
            f"Uploaded by {active.get('uploaded_by') or '—'}."
        )
        warnings = active.get("parse_warnings") or []
        for warning in warnings:
            st.warning(warning)
    else:
        st.info(
            "No uploaded guide is active yet. Built-in default Stellantis rules still apply. "
            "Upload the dealer audit PDF below to replace the reference text and B-code keyword checks."
        )

    upload_tab, library_tab, reference_tab = st.tabs(
        ["Upload guide", "Saved guides", "Reason code reference"]
    )

    with upload_tab:
        if not can_upload:
            render_role_gate_message(content_admin_roles, "upload OEM audit guides")
            st.info("Upload is available to Manager and Warranty Admin only.")
        else:
            bundled_text, has_bundled = bundled_stellantis_guide_text()
            if has_bundled:
                st.caption(
                    "Fastest option: load the Stellantis guide text already included with RO Guard "
                    "(same content as your scanned PDF)."
                )
                if st.button(
                    "Load built-in Stellantis audit guide",
                    type="secondary",
                    key="stellantis_load_bundled",
                ):
                    try:
                        _run_guide_ingest(
                            supabase,
                            file_name="WARRANTY AUDIT (built-in).txt",
                            file_bytes=b"",
                            version_label="Built-in RO Guard guide",
                            make_active=True,
                            pasted_text=bundled_text,
                        )
                except Exception as exc:
                    set_upload_flash(kind="error", message=_format_supabase_error(exc))
                    st.rerun()

            with st.form("stellantis_upload_form", clear_on_submit=False):
                version_label = st.text_input(
                    "Version label (optional)",
                    placeholder="e.g. 2026 field audit guide",
                )
                make_active = st.checkbox(
                    "Set as active guide after upload",
                    value=True,
                )
                uploaded_files = st.file_uploader(
                    "Upload Stellantis warranty audit guide (PDF or .txt)",
                    type=["pdf", "txt"],
                    accept_multiple_files=False,
                    help="Scanned PDFs are OCR'd page-by-page. Large scans can take several minutes — keep this tab open.",
                )
                submitted = st.form_submit_button(
                    "Process and save guide",
                    type="primary",
                    use_container_width=True,
                )

            if uploaded_files is not None:
                size_mb = len(uploaded_files.getvalue()) / (1024 * 1024)
                st.caption(f"Selected: **{uploaded_files.name}** ({size_mb:.1f} MB)")

            if submitted:
                if uploaded_files is None:
                    set_upload_flash(kind="error", message="Choose a PDF or .txt file first.")
                    st.rerun()
                try:
                    _run_guide_ingest(
                        supabase,
                        file_name=uploaded_files.name,
                        file_bytes=uploaded_files.getvalue(),
                        version_label=version_label,
                        make_active=make_active,
                    )
                except Exception as exc:
                    set_upload_flash(kind="error", message=_format_supabase_error(exc))
                    st.rerun()

            with st.expander("Paste guide text instead (if PDF upload fails)", expanded=False):
                pasted_text = st.text_area(
                    "Extracted guide text",
                    height=200,
                    placeholder="Paste OCR or copied text from the Stellantis audit guide…",
                    key="stellantis_pasted_text",
                )
                paste_label = st.text_input(
                    "Label for pasted upload",
                    value="Pasted audit guide text",
                    key="stellantis_paste_label",
                )
                if st.button("Save pasted text", key="stellantis_save_pasted"):
                    if not pasted_text.strip():
                        st.error("Paste the guide text first.")
                    else:
                        try:
                            _run_guide_ingest(
                                supabase,
                                file_name=f"{paste_label.strip() or 'pasted-guide'}.txt",
                                file_bytes=b"",
                                version_label=version_label,
                                make_active=make_active,
                                pasted_text=pasted_text,
                            )
                        except Exception as exc:
                            set_upload_flash(kind="error", message=_format_supabase_error(exc))
                            st.rerun()

            if not ocr_runtime_ready():
                st.caption(
                    "Scanned PDF OCR requires Poppler + Tesseract. "
                    "Streamlit Cloud installs them from packages.txt after redeploy. "
                    "Until then, use **Load built-in Stellantis audit guide** or paste/.txt upload."
                )
            elif uploaded_files is not None and str(uploaded_files.name or "").lower().endswith(".pdf"):
                st.caption(
                    "Scanned PDF selected — after you click **Process and save guide**, "
                    "a progress panel appears below. Do not switch tabs until it finishes."
                )

    with library_tab:
        docs = list_stellantis_audit_documents(supabase)
        if docs.empty:
            st.info("No OEM audit guides uploaded yet.")
        else:
            st.dataframe(
                docs.drop(columns=["id"], errors="ignore"),
                use_container_width=True,
                hide_index=True,
            )

            doc_ids = docs["id"].astype(int).tolist()
            labels = [
                f"{'★ ' if row['is_active'] else ''}{row['source_file']} ({row['created_at']})"
                for _, row in docs.iterrows()
            ]
            id_by_label = dict(zip(labels, doc_ids))

            if can_upload:
                pick = st.selectbox("Manage saved guide", options=[""] + labels, key="stellantis_manage_pick")
                if pick:
                    doc_id = id_by_label[pick]
                    c1, c2, c3 = st.columns(3)
                    if c1.button("Set active", key=f"stellantis_activate_{doc_id}"):
                        try:
                            set_active_stellantis_audit_document(supabase, doc_id)
                            bind_stellantis_runtime_config(supabase)
                            set_upload_flash(kind="success", message="Active guide updated.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not activate guide: {exc}")
                    if c2.button("Delete", key=f"stellantis_delete_{doc_id}"):
                        try:
                            delete_stellantis_audit_document(supabase, doc_id)
                            bind_stellantis_runtime_config(supabase)
                            set_upload_flash(kind="success", message="Guide deleted.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not delete guide: {exc}")
                    if c3.button("Preview extracted text", key=f"stellantis_preview_{doc_id}"):
                        st.session_state["stellantis_preview_id"] = doc_id

            preview_id = st.session_state.get("stellantis_preview_id")
            if preview_id:
                doc = get_stellantis_document_content(supabase, int(preview_id))
                if doc:
                    st.markdown(f"### Preview — {doc.get('source_file') or 'Guide'}")
                    parsed = doc.get("parsed_config") or {}
                    st.caption(
                        f"{len(parsed.get('reason_codes') or {})} reason codes · "
                        f"{len(str(doc.get('content') or '')):,} characters extracted"
                    )
                    with st.expander("Parsed reason codes", expanded=True):
                        for letter in sorted((parsed.get("reason_codes") or {}).keys()):
                            meta = parsed["reason_codes"][letter]
                            st.markdown(f"**{letter}** — {meta.get('title') or ''}")
                            for sub in meta.get("subcodes") or []:
                                st.markdown(f"- {sub}")
                    with st.expander("Extracted text (first 8,000 characters)", expanded=False):
                        st.text(str(doc.get("content") or "")[:8000])

    with reference_tab:
        render_stellantis_audit_reference()
