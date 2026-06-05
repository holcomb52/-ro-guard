#!/usr/bin/env python3
"""Send due scheduled Reporting PDF emails (GitHub Actions / cron entry point)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from core.scheduled_reports import run_due_scheduled_reports, smtp_config_status


def main() -> int:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
        or os.getenv("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        print(
            "Missing SUPABASE_URL or SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY).",
            file=sys.stderr,
        )
        return 1

    smtp_ok, smtp_message = smtp_config_status()
    if not smtp_ok:
        print(smtp_message, file=sys.stderr)
        return 1

    from supabase import create_client

    supabase = create_client(url, key)
    from core.scheduled_reports import load_email_schedules, probe_email_schedules_table

    table_ok, table_message = probe_email_schedules_table(supabase)
    if not table_ok:
        print(table_message, file=sys.stderr)
        return 1
    print(table_message)

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
