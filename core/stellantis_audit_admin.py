"""Admin UI for uploaded Stellantis OEM audit guide documents."""

from __future__ import annotations

import streamlit as st

from core.auth import auth_user_email
from core.ro_ocr import ocr_runtime_ready
from core.stellantis_audit import render_stellantis_audit_reference
from core.stellantis_audit_store import (
    bind_stellantis_runtime_config,
    delete_stellantis_audit_document,
    get_stellantis_document_content,
    ingest_stellantis_audit_upload,
    list_stellantis_audit_documents,
    load_active_stellantis_config,
    set_active_stellantis_audit_document,
)


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
        if warnings:
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
            version_label = st.text_input(
                "Version label (optional)",
                placeholder="e.g. 2026 field audit guide",
                key="stellantis_upload_version",
            )
            make_active = st.checkbox(
                "Set as active guide after upload",
                value=True,
                key="stellantis_upload_set_active",
            )
            uploaded_files = st.file_uploader(
                "Upload Stellantis warranty audit guide (PDF or .txt)",
                type=["pdf", "txt"],
                accept_multiple_files=False,
                key="stellantis_audit_upload",
                help="Scanned PDFs are OCR'd automatically when Poppler + Tesseract are installed on the server.",
            )
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
                            result = ingest_stellantis_audit_upload(
                                supabase,
                                file_name=f"{paste_label.strip() or 'pasted-guide'}.txt",
                                file_bytes=b"",
                                uploaded_by=auth_user_email() or "unknown",
                                version_label=version_label,
                                set_active=make_active,
                                pasted_text=pasted_text,
                            )
                            if result.get("ok"):
                                st.success(result.get("message") or "Guide saved.")
                                bind_stellantis_runtime_config(supabase)
                                st.rerun()
                            else:
                                st.error(result.get("message") or "Save failed.")
                        except Exception as exc:
                            st.error(f"Could not save pasted guide: {exc}")

            if uploaded_files is not None:
                if st.button("Process and save guide", type="primary", key="stellantis_save_upload"):
                    try:
                        result = ingest_stellantis_audit_upload(
                            supabase,
                            file_name=uploaded_files.name,
                            file_bytes=uploaded_files.getvalue(),
                            uploaded_by=auth_user_email() or "unknown",
                            version_label=version_label,
                            set_active=make_active,
                        )
                        if result.get("ok"):
                            st.success(result.get("message") or "Guide saved.")
                            for warning in result.get("parse_warnings") or []:
                                st.warning(warning)
                            bind_stellantis_runtime_config(supabase)
                            st.rerun()
                        else:
                            st.error(result.get("message") or "Upload failed.")
                    except Exception as exc:
                        st.error(f"Could not save OEM audit guide: {exc}")
                        st.caption(
                            "Scanned PDFs need **Poppler** and **Tesseract** on the server. "
                            "After the next deploy, packages.txt installs these on Streamlit Cloud. "
                            "Until then, use **Paste guide text instead** or upload a `.txt` file."
                        )

            if not ocr_runtime_ready():
                st.caption(
                    "Scanned PDF OCR requires Poppler + Tesseract. "
                    "Streamlit Cloud installs them from packages.txt after redeploy. "
                    "Use paste/.txt upload if PDF processing is unavailable."
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
                            st.success("Active guide updated.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not activate guide: {exc}")
                    if c2.button("Delete", key=f"stellantis_delete_{doc_id}"):
                        try:
                            delete_stellantis_audit_document(supabase, doc_id)
                            bind_stellantis_runtime_config(supabase)
                            st.success("Guide deleted.")
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
