"""Read-only review snapshot logic for JARVIS — self-contained, not imported by RO Guard."""

from __future__ import annotations

import pandas as pd


def review_outcome_label(first_pass_paid, rejected, paid_after_rejection=0) -> str:
    fp = int(first_pass_paid or 0)
    rej = int(rejected or 0)
    par = int(paid_after_rejection or 0)
    if par and not fp and not rej:
        return "Paid After Rejection"
    if fp and not rej and not par:
        return "First-Pass Paid"
    if rej and not fp and not par:
        return "Rejected / Returned"
    if fp and rej:
        return "Needs correction"
    return "Pending"


def load_reviews(supabase, limit: int = 5000) -> pd.DataFrame:
    if supabase is None:
        return pd.DataFrame()
    try:
        response = (
            supabase.table("reviews")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        for col in ("first_pass_paid", "rejected", "paid_after_rejection", "time_bypass"):
            if col in df.columns:
                df[col] = df[col].fillna(False).astype(int)
        return df
    except Exception:
        return pd.DataFrame()


def normalize_reviews_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if "created_at" in out.columns:
        out["created_at"] = pd.to_datetime(out["created_at"], errors="coerce")

    numeric_cols = [
        "score",
        "total_claim_value",
        "hard_stop_value",
        "hard_stop_count",
        "warning_count",
        "days_to_submit",
        "vin_recall_identified",
        "vin_recall_count",
        "vin_recall_acknowledged",
    ]
    for col in numeric_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    for col in ("first_pass_paid", "rejected", "paid_after_rejection", "time_bypass"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)

    if "status" in out.columns:
        status = out["status"].astype(str)
        out["is_do_not_submit"] = status.str.contains("DO NOT", case=False, na=False).astype(int)
        out["is_needs_review"] = status.str.contains("NEEDS", case=False, na=False).astype(int)
        out["is_ready"] = status.str.contains("READY", case=False, na=False).astype(int)

    if "first_pass_paid" in out.columns and "rejected" in out.columns:
        par_series = out.get("paid_after_rejection", pd.Series([0] * len(out)))
        out["outcome_status"] = [
            review_outcome_label(fp, rej, par)
            for fp, rej, par in zip(out["first_pass_paid"], out["rejected"], par_series)
        ]

    return out


def compute_roi_metrics(
    df: pd.DataFrame,
    *,
    rejection_rework_pct: float = 0.40,
    minutes_saved_per_review: float = 15.0,
    admin_hourly_rate: float = 38.0,
) -> dict:
    empty = {
        "review_count": 0,
        "protected_value": 0.0,
        "total_claim_value": 0.0,
        "avg_score": 0.0,
        "first_pass_pct": 0.0,
        "first_pass_pct_resolved": 0.0,
        "first_pass_count": 0,
        "paid_after_rejection_count": 0,
        "rejected_pct": 0.0,
        "rejected_count": 0,
        "rejected_value": 0.0,
        "pending_outcome_count": 0,
        "hard_stop_count": 0,
        "warning_count": 0,
        "do_not_submit_count": 0,
        "needs_review_count": 0,
        "ready_count": 0,
        "rework_savings": 0.0,
        "time_savings": 0.0,
        "total_estimated_value": 0.0,
        "weekly_trend": pd.DataFrame(),
        "rejection_reasons": pd.DataFrame(),
        "advisor_summary": pd.DataFrame(),
    }
    if df is None or df.empty:
        return empty

    data = normalize_reviews_dataframe(df)
    count = len(data)
    protected = float(data.get("hard_stop_value", pd.Series([0])).sum())
    total_claim = float(data.get("total_claim_value", pd.Series([0])).sum())
    avg_score = float(data.get("score", pd.Series([0])).mean())
    hard_stops = int(data.get("hard_stop_count", pd.Series([0])).sum())
    warnings = int(data.get("warning_count", pd.Series([0])).sum())

    first_pass_count = int(data.get("first_pass_paid", pd.Series([0])).sum())
    rejected_count = int(data.get("rejected", pd.Series([0])).sum())
    paid_after_rejection_count = int(data.get("paid_after_rejection", pd.Series([0])).sum())
    pending_outcome_count = int(
        (
            (data.get("first_pass_paid", pd.Series([0])) == 0)
            & (data.get("rejected", pd.Series([0])) == 0)
            & (data.get("paid_after_rejection", pd.Series([0])) == 0)
        ).sum()
        if "first_pass_paid" in data.columns and "rejected" in data.columns
        else 0
    )
    resolved_count = max(count - pending_outcome_count, 0)
    first_pass_pct = (first_pass_count / count * 100) if count else 0.0
    first_pass_pct_resolved = (first_pass_count / resolved_count * 100) if resolved_count else 0.0
    rejected_pct = (rejected_count / resolved_count * 100) if resolved_count else 0.0
    rejected_value = float(
        data.loc[data.get("rejected", pd.Series([0])) == 1, "total_claim_value"].sum()
        if "rejected" in data.columns
        else 0.0
    )

    do_not_submit = int(data.get("is_do_not_submit", pd.Series([0])).sum())
    needs_review = int(data.get("is_needs_review", pd.Series([0])).sum())
    ready = int(data.get("is_ready", pd.Series([0])).sum())

    rework_savings = protected * max(0.0, min(rejection_rework_pct, 1.0))
    time_savings = count * max(minutes_saved_per_review, 0) / 60.0 * max(admin_hourly_rate, 0)
    total_value = rework_savings + time_savings

    weekly = pd.DataFrame()
    if "created_at" in data.columns and data["created_at"].notna().any():
        trend = data.dropna(subset=["created_at"]).copy()
        trend["week"] = trend["created_at"].dt.to_period("W").astype(str)
        weekly = trend.groupby("week", as_index=False).agg(
            reviews=("ro_number", "count"),
            protected_value=("hard_stop_value", "sum"),
            avg_score=("score", "mean"),
            hard_stops=("hard_stop_count", "sum"),
        ).sort_values("week")

    rejection_reasons = pd.DataFrame()
    if "rejection_reason" in data.columns:
        declined_mask = (
            (pd.to_numeric(data.get("rejected", 0), errors="coerce").fillna(0).astype(int) == 1)
            | (
                pd.to_numeric(data.get("paid_after_rejection", 0), errors="coerce").fillna(0).astype(int)
                == 1
            )
        )
        reasons = data[declined_mask & data["rejection_reason"].astype(str).str.strip().astype(bool)].copy()
        if not reasons.empty:
            reasons["rejection_reason_primary"] = (
                reasons["rejection_reason"].astype(str).str.split(" — ").str[0].str.strip()
            )
            rejection_reasons = reasons.groupby("rejection_reason_primary", as_index=False).agg(
                count=("ro_number", "count"),
                total_value=("total_claim_value", "sum"),
            ).sort_values(["count", "total_value"], ascending=[False, False])
            rejection_reasons = rejection_reasons.rename(
                columns={"rejection_reason_primary": "rejection_reason"}
            )

    advisor_summary = pd.DataFrame()
    if "advisor" in data.columns and data["advisor"].astype(str).str.strip().any():
        advisor_summary = data.groupby("advisor", as_index=False).agg(
            reviews=("ro_number", "count"),
            avg_score=("score", "mean"),
            hard_stops=("hard_stop_count", "sum"),
            protected_value=("hard_stop_value", "sum"),
            rejected=("rejected", "sum"),
        ).sort_values(["protected_value", "hard_stops"], ascending=[False, False])

    return {
        "review_count": count,
        "protected_value": protected,
        "total_claim_value": total_claim,
        "avg_score": avg_score,
        "first_pass_pct": first_pass_pct,
        "first_pass_pct_resolved": first_pass_pct_resolved,
        "first_pass_count": first_pass_count,
        "paid_after_rejection_count": paid_after_rejection_count,
        "rejected_pct": rejected_pct,
        "rejected_count": rejected_count,
        "rejected_value": rejected_value,
        "pending_outcome_count": pending_outcome_count,
        "hard_stop_count": hard_stops,
        "warning_count": warnings,
        "do_not_submit_count": do_not_submit,
        "needs_review_count": needs_review,
        "ready_count": ready,
        "rework_savings": rework_savings,
        "time_savings": time_savings,
        "total_estimated_value": total_value,
        "weekly_trend": weekly,
        "rejection_reasons": rejection_reasons,
        "advisor_summary": advisor_summary,
    }
