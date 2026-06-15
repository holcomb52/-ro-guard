#!/usr/bin/env python3
"""Send due scheduled Reporting PDF emails (GitHub Actions / cron entry point)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.supabase_config import load_local_env

load_local_env()

from core.scheduled_reports import (  # noqa: E402
    load_email_schedules,
    missing_report_smtp_env_vars,
    probe_email_schedules_table,
    record_automation_error_for_enabled_schedules,
    run_due_scheduled_reports,
    smtp_config_status,
)


def _create_supabase_client():
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        return None, (
            "Missing SUPABASE_URL or SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY) "
            "in GitHub Actions secrets."
        )
    from supabase import create_client

    return create_client(url, key), ""


def _fail(message: str, *, supabase=None) -> int:
    print(message, file=sys.stderr)
    if supabase is not None:
        record_automation_error_for_enabled_schedules(supabase, message)
    return 1


def main() -> int:
    missing_smtp = missing_report_smtp_env_vars()
    if missing_smtp:
        message = (
            "Report SMTP is not configured for GitHub Actions. Missing secrets: "
            + ", ".join(missing_smtp)
            + ". Add them under GitHub → Settings → Secrets and variables → Actions."
        )
        supabase, _ = _create_supabase_client()
        return _fail(message, supabase=supabase)

    smtp_ok, smtp_message = smtp_config_status()
    if not smtp_ok:
        supabase, _ = _create_supabase_client()
        return _fail(smtp_message, supabase=supabase)

    supabase, config_error = _create_supabase_client()
    if supabase is None:
        return _fail(config_error)

    table_ok, table_message = probe_email_schedules_table(supabase)
    if not table_ok:
        return _fail(table_message, supabase=supabase)
    print(table_message)
    print(smtp_message)

    schedules = load_email_schedules(supabase)
    enabled = [s for s in schedules if s.get("enabled")]
    print(f"Schedules on file: {len(schedules)} ({len(enabled)} enabled)")
    for row in enabled:
        print(
            f"  - {row.get('frequency')}: recipients={row.get('recipients') or '(none)'} "
            f"last_sent={row.get('last_sent_at') or 'never'}"
        )

    results = run_due_scheduled_reports(supabase)
    if not results:
        print("No due schedules.")
        return 0

    exit_code = 0
    for item in results:
        if item.get("status") == "sent":
            print(
                f"Sent {item.get('frequency')} report "
                f"({item.get('period_label')}, {item.get('review_count')} reviews) "
                f"to {', '.join(item.get('recipients') or [])}"
            )
        elif item.get("status") == "skipped":
            print(f"Skipped: {item.get('error')}")
        else:
            exit_code = 1
            print(
                f"Failed {item.get('frequency')}: {item.get('error')}",
                file=sys.stderr,
            )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
