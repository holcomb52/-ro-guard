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
    key = os.getenv("SUPABASE_KEY", "").strip()
    if not url or not key:
        print("Missing SUPABASE_URL or SUPABASE_KEY.", file=sys.stderr)
        return 1

    smtp_ok, smtp_message = smtp_config_status()
    if not smtp_ok:
        print(smtp_message, file=sys.stderr)
        return 1

    from supabase import create_client

    supabase = create_client(url, key)
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
        else:
            exit_code = 1
            print(
                f"Failed {item.get('frequency')}: {item.get('error')}",
                file=sys.stderr,
            )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
