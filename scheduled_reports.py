"""Scheduled Reporting PDF emails — config storage, period logic, and SMTP delivery."""

from __future__ import annotations

import os
import smtplib
from datetime import date, datetime, timedelta, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd

from auth import is_valid_email, normalize_email
from pdf_reports import build_review_report_pdf, build_roi_report_pdf
from personnel_roles import parse_personnel_roles
from review_store import compute_roi_metrics, load_reviews, normalize_reviews_dataframe

SCHEDULE_FREQUENCIES = ("daily", "monthly", "yearly")
REPORT_TYPES = ("reporting", "roi")

REPORT_TYPE_LABELS = {
    "reporting": "Reporting summary PDF",
    "roi": "ROI dashboard PDF",
}

DEFAULT_ROI_REWORK_PCT = 0.40
DEFAULT_ROI_MINUTES_SAVED = 15.0
DEFAULT_ROI_HOURLY_RATE = 38.0

FREQUENCY_LABELS = {
    "daily": "Daily",
    "monthly": "Monthly",
    "yearly": "Yearly",
}

FREQUENCY_HELP = {
    "daily": "Sent every morning for the previous calendar day.",
    "monthly": "Sent on the 1st of each month for the prior calendar month.",
    "yearly": "Sent on January 1 for the prior calendar year.",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_timestamp(value) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_recipient_list(raw: str) -> list[str]:
    emails: list[str] = []
    seen: set[str] = set()
    for part in str(raw or "").replace(";", ",").split(","):
        email = normalize_email(part)
        if not email or email in seen:
            continue
        if not is_valid_email(email):
            continue
        seen.add(email)
        emails.append(email)
    return emails


def format_recipient_list(emails: list[str]) -> str:
    return ", ".join(parse_recipient_list(", ".join(emails)))


def _normalize_smtp_host(host: str) -> str:
    cleaned = str(host or "").strip().strip('"').strip("'")
    if ":" in cleaned:
        cleaned = cleaned.split(":", 1)[0].strip()
    return cleaned


def load_smtp_config() -> dict | None:
    def _get(name: str, default: str = "") -> str:
        value = os.getenv(name, default).strip()
        if value:
            return value
        try:
            import streamlit as st

            return str(st.secrets.get(name, default) or "").strip()
        except Exception:
            return default

    host = _normalize_smtp_host(_get("REPORT_SMTP_HOST"))
    user = _get("REPORT_SMTP_USER")
    password = _get("REPORT_SMTP_PASSWORD")
    if not host or not user or not password:
        return None
    port_raw = _get("REPORT_SMTP_PORT", "587")
    try:
        port = int(port_raw)
    except ValueError:
        port = 587
    use_tls = _get("REPORT_SMTP_USE_TLS", "true").lower() not in ("0", "false", "no")
    sender = _get("REPORT_SMTP_FROM") or user
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "use_tls": use_tls,
        "sender": sender,
    }


def smtp_config_status() -> tuple[bool, str]:
    config = load_smtp_config()
    if config:
        return True, f"SMTP ready ({config['sender']} via {config['host']})."
    return (
        False,
        "Report email is not configured. Add REPORT_SMTP_* secrets (see docs/SCHEDULED_REPORTS.md).",
    )


def load_email_schedules(supabase) -> list[dict]:
    if supabase is None:
        return []
    try:
        response = (
            supabase.table("email_schedules")
            .select("*")
            .order("frequency")
            .execute()
        )
        return list(response.data or [])
    except Exception:
        return []


def load_manager_emails(supabase) -> list[str]:
    if supabase is None:
        return []
    try:
        rows = supabase.table("personnel").select("email, roles, role, active").eq("active", True).execute().data or []
    except Exception:
        return []
    emails: list[str] = []
    seen: set[str] = set()
    for row in rows:
        roles = parse_personnel_roles(row)
        if "Manager" not in roles:
            continue
        email = normalize_email(row.get("email", ""))
        if email and is_valid_email(email) and email not in seen:
            seen.add(email)
            emails.append(email)
    return sorted(emails)


def schedule_report_flags(schedule: dict | None) -> tuple[bool, bool]:
    """Which PDFs to attach for this schedule row."""
    schedule = schedule or {}
    if "include_reporting" in schedule or "include_roi" in schedule:
        return bool(schedule.get("include_reporting")), bool(schedule.get("include_roi"))
    return True, False


def upsert_email_schedule(
    supabase,
    *,
    frequency: str,
    recipients: str,
    enabled: bool,
    include_reporting: bool = True,
    include_roi: bool = False,
    updated_by: str = "",
) -> None:
    if supabase is None:
        raise RuntimeError("Supabase is not configured.")
    frequency = str(frequency or "").strip().lower()
    if frequency not in SCHEDULE_FREQUENCIES:
        raise ValueError(f"Unsupported frequency: {frequency}")
    payload = {
        "frequency": frequency,
        "report_type": "reporting",
        "recipients": format_recipient_list(parse_recipient_list(recipients)),
        "enabled": bool(enabled),
        "include_reporting": bool(include_reporting),
        "include_roi": bool(include_roi),
        "updated_at": _utc_now_iso(),
        "updated_by": str(updated_by or "").strip() or None,
    }
    supabase.table("email_schedules").upsert(payload, on_conflict="frequency").execute()


def cancel_email_schedule(
    supabase,
    *,
    frequency: str,
    updated_by: str = "",
) -> bool:
    """Turn off automated sends for one frequency; keep recipient and report settings."""
    if supabase is None:
        raise RuntimeError("Supabase is not configured.")
    frequency = str(frequency or "").strip().lower()
    if frequency not in SCHEDULE_FREQUENCIES:
        raise ValueError(f"Unsupported frequency: {frequency}")

    existing = next(
        (row for row in load_email_schedules(supabase) if row.get("frequency") == frequency),
        None,
    )
    if not existing or not existing.get("enabled"):
        return False

    include_reporting, include_roi = schedule_report_flags(existing)
    upsert_email_schedule(
        supabase,
        frequency=frequency,
        recipients=str(existing.get("recipients") or ""),
        enabled=False,
        include_reporting=include_reporting,
        include_roi=include_roi,
        updated_by=updated_by,
    )
    return True


def report_period_for_frequency(frequency: str, reference: date | None = None) -> tuple[date, date, str]:
    ref = reference or date.today()
    frequency = str(frequency or "").strip().lower()
    if frequency == "daily":
        day = ref - timedelta(days=1)
        label = f"Daily report — {day.strftime('%B %d, %Y')}"
        return day, day, label
    if frequency == "monthly":
        first_of_month = ref.replace(day=1)
        end = first_of_month - timedelta(days=1)
        start = end.replace(day=1)
        label = f"Monthly report — {start.strftime('%B %Y')}"
        return start, end, label
    if frequency == "yearly":
        year = ref.year - 1
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        label = f"Yearly report — {year}"
        return start, end, label
    raise ValueError(f"Unsupported frequency: {frequency}")


def filter_reviews_for_period(df: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if df is None or df.empty or "created_at" not in df.columns:
        return pd.DataFrame()
    out = normalize_reviews_dataframe(df)
    mask = (out["created_at"].dt.date >= start) & (out["created_at"].dt.date <= end)
    return out.loc[mask].copy()


def is_schedule_due(schedule: dict, now: datetime | None = None) -> bool:
    if not schedule or not schedule.get("enabled"):
        return False
    frequency = str(schedule.get("frequency") or "").strip().lower()
    now = now or datetime.now(timezone.utc)
    today = now.date()
    last = _parse_timestamp(schedule.get("last_sent_at"))

    if frequency == "daily":
        if last is None:
            return True
        last_day = last.astimezone(timezone.utc).date() if last.tzinfo else last.date()
        return last_day < today

    if frequency == "monthly":
        if today.day != 1:
            return False
        if last is None:
            return True
        last_day = last.astimezone(timezone.utc).date() if last.tzinfo else last.date()
        return (last_day.year, last_day.month) < (today.year, today.month)

    if frequency == "yearly":
        if today.month != 1 or today.day != 1:
            return False
        if last is None:
            return True
        last_day = last.astimezone(timezone.utc).date() if last.tzinfo else last.date()
        return last_day.year < today.year

    return False


def build_reporting_pdf_for_schedule(
    supabase,
    frequency: str,
    *,
    reference: date | None = None,
) -> tuple[bytes, str, int, pd.DataFrame]:
    start, end, period_label = report_period_for_frequency(frequency, reference)
    df = normalize_reviews_dataframe(load_reviews(supabase))
    scoped = filter_reviews_for_period(df, start, end)
    pdf_bytes = build_review_report_pdf(scoped, period_label=period_label)
    return pdf_bytes, period_label, len(scoped), scoped


def build_roi_pdf_for_schedule(
    scoped: pd.DataFrame,
    *,
    period_label: str,
    rejection_rework_pct: float = DEFAULT_ROI_REWORK_PCT,
    minutes_saved: float = DEFAULT_ROI_MINUTES_SAVED,
    hourly_rate: float = DEFAULT_ROI_HOURLY_RATE,
) -> bytes:
    metrics = compute_roi_metrics(
        scoped,
        rejection_rework_pct=rejection_rework_pct,
        minutes_saved_per_review=minutes_saved,
        admin_hourly_rate=hourly_rate,
    )
    return build_roi_report_pdf(
        metrics,
        period_label=period_label,
        rejection_rework_pct=rejection_rework_pct,
        minutes_saved=minutes_saved,
        hourly_rate=hourly_rate,
    )


def format_smtp_send_error(exc: Exception, config: dict | None = None) -> str:
    message = str(exc)
    host = (config or {}).get("host") or "unknown"
    if "Name or service not known" in message or "Errno -2" in message:
        return (
            f"Cannot reach mail server `{host}`. In Streamlit Secrets, set "
            "`REPORT_SMTP_HOST = \"smtp.gmail.com\"` exactly (no port, no typos, no extra quotes)."
        )
    if "535" in message or "Authentication unsuccessful" in message:
        return (
            "SMTP login failed. For Gmail, use a 16-character **app password** "
            "(not your normal Gmail password) in `REPORT_SMTP_PASSWORD`."
        )
    return message


def send_report_email(
    *,
    recipients: list[str],
    subject: str,
    body_text: str,
    attachments: list[tuple[bytes, str]],
    smtp_config: dict | None = None,
) -> None:
    recipients = parse_recipient_list(", ".join(recipients))
    if not recipients:
        raise ValueError("No valid recipient email addresses.")
    if not attachments:
        raise ValueError("No report attachments to send.")
    config = smtp_config or load_smtp_config()
    if not config:
        raise RuntimeError("Report SMTP is not configured.")

    message = MIMEMultipart()
    message["Subject"] = subject
    message["From"] = config["sender"]
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(body_text, "plain"))

    for pdf_bytes, filename in attachments:
        attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
        attachment.add_header("Content-Disposition", "attachment", filename=filename)
        message.attach(attachment)

    if config["use_tls"]:
        with smtplib.SMTP(config["host"], config["port"], timeout=60) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(config["user"], config["password"])
            server.sendmail(config["sender"], recipients, message.as_string())
    else:
        with smtplib.SMTP_SSL(config["host"], config["port"], timeout=60) as server:
            server.login(config["user"], config["password"])
            server.sendmail(config["sender"], recipients, message.as_string())


def _safe_filename(label: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in label)
    cleaned = cleaned.strip("_") or "report"
    return f"RO_Shield_{cleaned}.pdf"


def build_schedule_attachments(
    supabase,
    frequency: str,
    *,
    include_reporting: bool,
    include_roi: bool,
    reference: date | None = None,
) -> tuple[list[tuple[bytes, str]], str, int]:
    if not include_reporting and not include_roi:
        raise ValueError("Select at least one report to email.")

    start, end, period_label = report_period_for_frequency(frequency, reference)
    df = normalize_reviews_dataframe(load_reviews(supabase))
    scoped = filter_reviews_for_period(df, start, end)
    review_count = len(scoped)
    period_slug = period_label.replace(" — ", "_").replace(" ", "_")
    attachments: list[tuple[bytes, str]] = []

    if include_reporting:
        reporting_pdf = build_review_report_pdf(scoped, period_label=period_label)
        attachments.append((reporting_pdf, _safe_filename(f"Review_{period_slug}")))

    if include_roi:
        roi_pdf = build_roi_pdf_for_schedule(scoped, period_label=period_label)
        attachments.append((roi_pdf, _safe_filename(f"ROI_{period_slug}")))

    return attachments, period_label, review_count


def send_schedule_report(
    supabase,
    schedule: dict,
    *,
    reference: date | None = None,
    record_send: bool = True,
) -> dict:
    frequency = str(schedule.get("frequency") or "").strip().lower()
    recipients = parse_recipient_list(schedule.get("recipients", ""))
    if not recipients:
        raise ValueError("Add at least one recipient email for this schedule.")

    include_reporting, include_roi = schedule_report_flags(schedule)
    attachments, period_label, review_count = build_schedule_attachments(
        supabase,
        frequency,
        include_reporting=include_reporting,
        include_roi=include_roi,
        reference=reference,
    )

    report_names = []
    if include_reporting:
        report_names.append("Reporting summary")
    if include_roi:
        report_names.append("ROI dashboard summary")

    subject = f"RO Shield — {period_label}"
    body = (
        f"{period_label}\n\n"
        f"Reviews in period: {review_count}\n"
        f"Attached PDFs:\n"
        + "".join(f"- {name}\n" for name in report_names)
        + "\n— RO Shield (automated report)\n"
    )
    send_report_email(
        recipients=recipients,
        subject=subject,
        body_text=body,
        attachments=attachments,
    )

    if record_send and supabase is not None:
        supabase.table("email_schedules").update(
            {
                "last_sent_at": _utc_now_iso(),
                "last_error": None,
                "updated_at": _utc_now_iso(),
            }
        ).eq("frequency", frequency).execute()

    return {
        "frequency": frequency,
        "period_label": period_label,
        "review_count": review_count,
        "recipients": recipients,
        "reports_sent": report_names,
    }


def record_schedule_error(supabase, frequency: str, error: str) -> None:
    if supabase is None:
        return
    supabase.table("email_schedules").update(
        {
            "last_error": str(error or "")[:500],
            "updated_at": _utc_now_iso(),
        }
    ).eq("frequency", frequency).execute()


def run_due_scheduled_reports(supabase, *, reference: date | None = None) -> list[dict]:
    results: list[dict] = []
    now = datetime.now(timezone.utc)
    for schedule in load_email_schedules(supabase):
        frequency = schedule.get("frequency")
        if not is_schedule_due(schedule, now):
            continue
        try:
            result = send_schedule_report(supabase, schedule, reference=reference, record_send=True)
            result["status"] = "sent"
            results.append(result)
        except Exception as exc:
            record_schedule_error(supabase, str(frequency), str(exc))
            results.append(
                {
                    "frequency": frequency,
                    "status": "error",
                    "error": str(exc),
                }
            )
    return results
