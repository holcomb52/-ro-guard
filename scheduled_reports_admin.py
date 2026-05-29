"""Admin UI for scheduled Reporting PDF emails."""

from __future__ import annotations

import streamlit as st

from auth import auth_user_email
from scheduled_reports import (
    FREQUENCY_HELP,
    FREQUENCY_LABELS,
    SCHEDULE_FREQUENCIES,
    format_recipient_list,
    format_smtp_send_error,
    load_email_schedules,
    load_manager_emails,
    load_smtp_config,
    parse_recipient_list,
    report_period_for_frequency,
    send_schedule_report,
    smtp_config_status,
    upsert_email_schedule,
)

ADMIN_WRITE_ROLES = ("Manager", "Warranty Admin", "Admin")


def _current_person_roles() -> list[str]:
    roles = st.session_state.get("current_person_roles") or []
    if roles:
        return [str(r) for r in roles]
    legacy = str(st.session_state.get("current_person_role") or "").strip()
    if not legacy:
        return []
    if " · " in legacy:
        return [part.strip() for part in legacy.split(" · ") if part.strip()]
    return [legacy]


def _can_configure_schedules() -> bool:
    return bool(set(_current_person_roles()) & set(ADMIN_WRITE_ROLES))


def _current_person_name() -> str:
    return str(st.session_state.get("current_person_name") or "").strip()


def render_scheduled_reports_admin(supabase) -> None:
    st.header("Scheduled Reports")
    st.caption(
        "Emails the **Reporting** and **ROI** summary PDFs on a daily, monthly, or yearly schedule. "
        "Requires REPORT_SMTP_* secrets and the GitHub Actions workflow (see docs/SCHEDULED_REPORTS.md)."
    )

    if not _can_configure_schedules():
        st.warning(
            "Your account needs a linked **Manager**, **Warranty Admin**, or **Admin** "
            "personnel record to configure scheduled reports."
        )
        return

    smtp_ok, smtp_message = smtp_config_status()
    if smtp_ok:
        st.success(smtp_message)
    else:
        st.warning(smtp_message)

    manager_emails = load_manager_emails(supabase)
    if manager_emails:
        st.caption(f"Manager emails on file: {', '.join(manager_emails)}")
    else:
        st.caption("No Manager emails found in Personnel — add emails under Admin → Personnel.")

    schedules = {row.get("frequency"): row for row in load_email_schedules(supabase)}
    updated_by = _current_person_name() or auth_user_email()

    for frequency in SCHEDULE_FREQUENCIES:
        existing = schedules.get(frequency) or {}
        label = FREQUENCY_LABELS[frequency]
        with st.expander(f"{label} report", expanded=frequency == "daily"):
            st.caption(FREQUENCY_HELP[frequency])
            start, end, preview_label = report_period_for_frequency(frequency)
            st.caption(f"Next automated run covers: **{preview_label}** ({start} → {end}).")

            enabled = st.checkbox(
                f"Enable {label.lower()} emails",
                value=bool(existing.get("enabled")),
                key=f"schedule_enabled_{frequency}",
            )
            recipients = st.text_area(
                "Recipients (comma-separated)",
                value=str(existing.get("recipients") or ""),
                placeholder="manager@dealership.com, warranty@dealership.com",
                key=f"schedule_recipients_{frequency}",
            )
            cols = st.columns(2)
            with cols[0]:
                if st.button("Use manager emails", key=f"schedule_mgr_{frequency}"):
                    if manager_emails:
                        st.session_state[f"schedule_recipients_{frequency}"] = format_recipient_list(manager_emails)
                        st.rerun()
                    else:
                        st.warning("No manager emails in Personnel.")
            with cols[1]:
                parsed = parse_recipient_list(recipients)
                st.caption(f"{len(parsed)} valid recipient(s)")

            last_sent = str(existing.get("last_sent_at") or "").strip()
            last_error = str(existing.get("last_error") or "").strip()
            if last_sent:
                st.caption(f"Last sent: {last_sent[:19].replace('T', ' ')} UTC")
            if last_error:
                st.error(f"Last error: {last_error}")

            action_cols = st.columns(2)
            with action_cols[0]:
                if st.button(f"Save {label.lower()} schedule", key=f"schedule_save_{frequency}"):
                    parsed = parse_recipient_list(recipients)
                    if enabled and not parsed:
                        st.error("Add at least one valid recipient email, or disable this schedule.")
                    else:
                        try:
                            upsert_email_schedule(
                                supabase,
                                frequency=frequency,
                                recipients=recipients,
                                enabled=enabled,
                                updated_by=updated_by,
                            )
                            st.success(f"{label} schedule saved.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not save schedule: {exc}")
            with action_cols[1]:
                if st.button(f"Send test now", key=f"schedule_test_{frequency}"):
                    if not smtp_ok:
                        st.error("Configure REPORT_SMTP_* secrets before sending.")
                    else:
                        parsed = parse_recipient_list(recipients)
                        if not parsed:
                            st.error("Add at least one valid recipient email.")
                        else:
                            try:
                                upsert_email_schedule(
                                    supabase,
                                    frequency=frequency,
                                    recipients=recipients,
                                    enabled=enabled,
                                    updated_by=updated_by,
                                )
                                result = send_schedule_report(
                                    supabase,
                                    {
                                        "frequency": frequency,
                                        "recipients": format_recipient_list(parsed),
                                        "enabled": enabled,
                                    },
                                    record_send=False,
                                )
                                st.success(
                                    f"Test email sent to {', '.join(result['recipients'])} "
                                    f"with Reporting + ROI PDFs ({result['review_count']} review(s) in "
                                    f"{result['period_label']})."
                                )
                            except Exception as exc:
                                st.error(format_smtp_send_error(exc, load_smtp_config()))
