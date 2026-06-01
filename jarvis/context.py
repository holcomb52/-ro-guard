"""Build a compact text context bundle for the local LLM."""

from __future__ import annotations

import pandas as pd

from jarvis.review_snapshot import review_outcome_label


def build_context(df: pd.DataFrame, metrics: dict) -> str:
    if df.empty or not metrics:
        return "No RO Guard review data is loaded."

    lines = [
        "RO GUARD DATA SNAPSHOT (aggregates + recent reviews)",
        "====================================================",
        f"Reviews in scope: {metrics.get('review_count', 0)}",
        f"Average audit score: {metrics.get('avg_score', 0):.1f}",
        f"Total claim value reviewed: ${metrics.get('total_claim_value', 0):,.2f}",
        f"Protected / hard-stop value flagged: ${metrics.get('protected_value', 0):,.2f}",
        f"Hard stops (job-level count sum): {metrics.get('hard_stop_count', 0)}",
        f"Warnings (job-level count sum): {metrics.get('warning_count', 0)}",
        "",
        "OEM OUTCOMES",
        f"- Pending outcome: {metrics.get('pending_outcome_count', 0)}",
        f"- First-pass paid: {metrics.get('first_pass_count', 0)} ({metrics.get('first_pass_pct_resolved', 0):.1f}% of resolved)",
        f"- Rejected / returned: {metrics.get('rejected_count', 0)}",
        f"- Paid after rejection: {metrics.get('paid_after_rejection_count', 0)}",
        f"- Rejected claim value: ${metrics.get('rejected_value', 0):,.2f}",
    ]

    advisor = metrics.get("advisor_summary")
    if isinstance(advisor, pd.DataFrame) and not advisor.empty:
        lines.extend(["", "TOP ADVISORS (by protected value flagged)"])
        for _, row in advisor.head(8).iterrows():
            lines.append(
                f"- {row.get('advisor', '—')}: {int(row.get('reviews', 0))} reviews, "
                f"avg score {float(row.get('avg_score', 0)):.0f}, "
                f"hard stops {int(row.get('hard_stops', 0))}, "
                f"protected ${float(row.get('protected_value', 0)):,.0f}"
            )

    rejections = metrics.get("rejection_reasons")
    if isinstance(rejections, pd.DataFrame) and not rejections.empty:
        lines.extend(["", "TOP REJECTION REASONS"])
        for _, row in rejections.head(8).iterrows():
            lines.append(
                f"- {row.get('rejection_reason', '—')}: {int(row.get('count', 0))} claims, "
                f"${float(row.get('total_value', 0)):,.0f}"
            )

    weekly = metrics.get("weekly")
    if isinstance(weekly, pd.DataFrame) and not weekly.empty:
        lines.extend(["", "RECENT WEEKS"])
        for _, row in weekly.tail(6).iterrows():
            lines.append(
                f"- {row.get('week', '—')}: {int(row.get('reviews', 0))} reviews, "
                f"avg score {float(row.get('avg_score', 0)):.0f}, "
                f"hard stops {int(row.get('hard_stops', 0))}"
            )

    lines.extend(["", "RECENT REVIEWS (newest first, capped at 25)"])
    recent = df.copy()
    if "created_at" in recent.columns:
        recent = recent.sort_values("created_at", ascending=False)
    for _, row in recent.head(25).iterrows():
        outcome = review_outcome_label(
            row.get("first_pass_paid"),
            row.get("rejected"),
            row.get("paid_after_rejection", 0),
        )
        lines.append(
            f"- RO {row.get('ro_number', '—')} | {row.get('advisor', '—')} | "
            f"score {row.get('score', '—')} | {row.get('status', '—')} | "
            f"claim ${float(row.get('total_claim_value') or 0):,.0f} | outcome {outcome}"
        )

    lines.extend([
        "",
        "NOTES FOR ASSISTANT",
        "- This is owner-only operational data from RO Guard.",
        "- Do not invent RO numbers or dollar amounts not listed above.",
        "- Do not write warranty narratives for Dealer Connect submission.",
        "- Prefer concise, actionable answers for a warranty manager.",
    ])
    return "\n".join(lines)
