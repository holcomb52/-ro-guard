"""Admin UI for scheduled Reporting PDF emails."""

from __future__ import annotations

import streamlit as st

from auth import auth_user_email
from scheduled_reports import (
    FREQUENCY_HELP,
    FREQUENCY_LABELS,
    REPORT_TYPE_LABELS,
    SCHEDULE_FREQUENCIES,
    format_recipient_list,
    format_smtp_send_error,
    load_email_schedules,
    load_manager_emails,
    load_smtp_config,
    parse_recipient_list,
    report_period_for_frequency,
    schedule_report_flags,
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


def _schedule_form_values(existing: dict, frequency: str) -> tuple[bool, bool]:
    include_reporting, include_roi = schedule_report_flags(existing)
    return (
        st.checkbox(
            REPORT_TYPE_LABELS["reporting"],
            value=include_reporting,
            key=f"schedule_reporting_{frequency}",
        ),
        st.checkbox(
            REPORT_TYPE_LABELS["roi"],
            value=include_roi,
            key=f"schedule_roi_{frequency}",
        ),
    )


def _validate_schedule_form(
    *,
    enabled: bool,
    recipients: str,
    include_reporting: bool,
    include_roi: bool,
    sending: bool,
) -> str | None:
    parsed = parse_recipient_list(recipients)
    if (enabled or sending) and not parsed:
        return "Add at least one valid recipient email."
    if (enabled or sending) and not include_reporting and not include_roi:
        return "Select at least one report to email."
    return None


def render_scheduled_reports_admin(supabase) -> None:
    st.header("Scheduled Reports")
    st.caption(
        "Choose recipients and which PDFs to email on a daily, monthly, or yearly schedule. "
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

            recipients = st.text_area(
                "Recipients (comma-separated)",
                value=str(existing.get("recipients") or ""),
                placeholder="manager@dealership.com, warranty@dealership.com",
                key=f"schedule_recipients_{frequency}",
            )

            st.markdown("**Reports to include**")
            include_reporting, include_roi = _schedule_form_values(existing, frequency)

            enabled = st.checkbox(
                f"Enable {label.lower()} emails",
                value=bool(existing.get("enabled")),
                key=f"schedule_enabled_{frequency}",
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
                    form_error = _validate_schedule_form(
                        enabled=enabled,
                        recipients=recipients,
                        include_reporting=include_reporting,
                        include_roi=include_roi,
                        sending=False,
                    )
                    if form_error:
                        st.error(form_error)
                    else:
                        try:
                            upsert_email_schedule(
                                supabase,
                                frequency=frequency,
                                recipients=recipients,
                                enabled=enabled,
                                include_reporting=include_reporting,
                                include_roi=include_roi,
                                updated_by=updated_by,
                            )
                            st.success(f"{label} schedule saved.")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not save schedule: {exc}")
            with action_cols[1]:
                send_label = f"Send {label.lower()} reports now"
                if st.button(send_label, key=f"schedule_test_{frequency}"):
                    if not smtp_ok:
                        st.error("Configure REPORT_SMTP_* secrets before sending.")
                    else:
                        form_error = _validate_schedule_form(
                            enabled=enabled,
                            recipients=recipients,
                            include_reporting=include_reporting,
                            include_roi=include_roi,
                            sending=True,
                        )
                        if form_error:
                            st.error(form_error)
                        else:
                            try:
                                upsert_email_schedule(
                                    supabase,
                                    frequency=frequency,
                                    recipients=recipients,
                                    enabled=enabled,
                                    include_reporting=include_reporting,
                                    include_roi=include_roi,
                                    updated_by=updated_by,
                                )
                                parsed = parse_recipient_list(recipients)
                                result = send_schedule_report(
                                    supabase,
                                    {
                                        "frequency": frequency,
                                        "recipients": format_recipient_list(parsed),
                                        "enabled": enabled,
                                        "include_reporting": include_reporting,
                                        "include_roi": include_roi,
                                    },
                                    record_send=False,
                                )
                                reports = ", ".join(result.get("reports_sent") or [])
                                st.success(
                                    f"Email sent to {', '.join(result['recipients'])} "
                                    f"with {reports} ({result['review_count']} review(s) in "
                                    f"{result['period_label']})."
                                )
                            except Exception as exc:
                                st.error(format_smtp_send_error(exc, load_smtp_config()))
