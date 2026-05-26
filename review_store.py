"""Supabase-backed review and bulletin storage."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_review_record(data: dict) -> dict:
    """Build a Supabase-ready review row with all reporting fields."""
    payload = dict(data or {})
    jobs = payload.pop("jobs", None)
    if jobs is None and "jobs_json" in payload:
        raw = payload.pop("jobs_json")
        jobs = json.loads(raw) if isinstance(raw, str) and raw.strip() else raw
    if jobs is None:
        jobs = []
    if isinstance(jobs, str):
        try:
            jobs = json.loads(jobs)
        except json.JSONDecodeError:
            jobs = []

    def _num(key, default=0):
        try:
            return float(payload.get(key, default) or default)
        except (TypeError, ValueError):
            return float(default)

    def _int(key, default=0):
        try:
            return int(float(payload.get(key, default) or default))
        except (TypeError, ValueError):
            return int(default)

    def _flag(key):
        """0/1 for Supabase — older reviews tables use INTEGER, not BOOLEAN."""
        val = payload.get(key, False)
        if isinstance(val, bool):
            return 1 if val else 0
        try:
            return 1 if int(val) else 0
        except (TypeError, ValueError):
            return 1 if val else 0

    record = {
        "created_at": payload.get("created_at") or _utc_now_iso(),
        "ro_number": str(payload.get("ro_number", "") or "").strip(),
        "vin": str(payload.get("vin", "") or "").strip(),
        "ro_invoiced": str(payload.get("ro_invoiced", "") or "") or None,
        "day_submitted": str(payload.get("day_submitted", "") or "") or None,
        "days_to_submit": _int("days_to_submit"),
        "advisor": str(payload.get("advisor", "") or "").strip(),
        "technician": str(payload.get("technician", "") or "").strip(),
        "warranty_admin": str(payload.get("warranty_admin", "") or "").strip(),
        "manager": str(payload.get("manager", "") or "").strip(),
        "entered_by": str(payload.get("entered_by", "") or "").strip(),
        "score": _int("score"),
        "status": str(payload.get("status", "") or "").strip(),
        "total_claim_value": _num("total_claim_value"),
        "hard_stop_value": _num("hard_stop_value"),
        "hard_stop_count": _int("hard_stop_count"),
        "warning_count": _int("warning_count"),
        "time_bypass": _flag("time_bypass"),
        "time_bypass_user": str(payload.get("time_bypass_user", "") or "").strip(),
        "first_pass_paid": _flag("first_pass_paid"),
        "rejected": _flag("rejected"),
        "rejection_reason": str(payload.get("rejection_reason", "") or "").strip(),
        "jobs": jobs,
        "vin_recall_identified": _int("vin_recall_identified"),
        "vin_recall_count": _int("vin_recall_count"),
        "vin_recall_campaigns": str(payload.get("vin_recall_campaigns", "") or "").strip(),
        "vin_recall_acknowledged": _int("vin_recall_acknowledged"),
    }
    return record


def save_review(supabase, data: dict) -> bool:
    if supabase is None:
        return False
    try:
        record = normalize_review_record(data)
        supabase.table("reviews").insert(record).execute()
        return True
    except Exception:
        raise


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
        for col in ("first_pass_paid", "rejected", "time_bypass"):
            if col in df.columns:
                df[col] = df[col].fillna(False).astype(int)
        return df
    except Exception:
        raise


def save_bulletin(
    supabase,
    title: str,
    keywords: str,
    notes: str,
    *,
    source_file: str = "",
    bulletin_number: str = "",
    content: str = "",
) -> bool:
    if supabase is None:
        return False
    payload = {
        "created_at": _utc_now_iso(),
        "title": title.strip(),
        "keywords": keywords.strip(),
        "notes": notes.strip()[:4000],
        "source_file": source_file.strip(),
        "bulletin_number": bulletin_number.strip(),
        "content": content.strip(),
    }
    supabase.table("bulletins").insert(payload).execute()
    return True


def load_bulletins(supabase) -> pd.DataFrame:
    if supabase is None:
        return pd.DataFrame()
    try:
        response = (
            supabase.table("bulletins")
            .select("*")
            .order("created_at", desc=True)
            .limit(1000)
            .execute()
        )
        return pd.DataFrame(response.data or [])
    except Exception:
        return pd.DataFrame()


def _bulletin_search_blob(row) -> str:
    parts = [
        row.get("bulletin_number", ""),
        row.get("title", ""),
        row.get("keywords", ""),
        row.get("notes", ""),
        row.get("content", ""),
        row.get("source_file", ""),
    ]
    return " ".join(str(part or "") for part in parts)


def filter_bulletins_df(
    df: pd.DataFrame,
    *,
    query: str = "",
    entry_type: str = "All",
) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    if "source_file" not in out.columns:
        out["source_file"] = ""

    if entry_type == "PDF upload":
        out = out[out["source_file"].fillna("").astype(str).str.strip() != ""]
    elif entry_type == "Manual entry":
        out = out[out["source_file"].fillna("").astype(str).str.strip() == ""]

    q = str(query or "").strip().lower()
    if q:
        q_compact = re.sub(r"[\s\-–]", "", q)

        def _matches(row) -> bool:
            blob = _bulletin_search_blob(row).lower()
            if q in blob:
                return True
            if q_compact:
                blob_compact = re.sub(r"[\s\-–]", "", blob)
                return q_compact in blob_compact
            return False

        out = out[out.apply(_matches, axis=1)]

    return out


def sort_bulletins_df(df: pd.DataFrame, sort_by: str = "Newest first") -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    if sort_by == "Oldest first":
        return out.sort_values("created_at", ascending=True, na_position="last")
    if sort_by == "TSB number":
        if "bulletin_number" not in out.columns:
            out["bulletin_number"] = ""
        return out.sort_values("bulletin_number", ascending=True, na_position="last")
    if sort_by == "Title":
        return out.sort_values("title", ascending=True, na_position="last")
    return out.sort_values("created_at", ascending=False, na_position="last")


SMART_WARRANTY_LEVELS = ("base", "plus", "premium")


def smart_warranty_punch_exempt(level: str) -> bool:
    return (level or "base").lower() in ("plus", "premium")


def load_smart_warranty_settings(supabase) -> dict:
    default = {
        "smart_warranty_level": "base",
        "updated_by": "",
        "updated_at": None,
    }
    if supabase is None:
        return default
    try:
        response = (
            supabase.table("dealer_settings")
            .select("smart_warranty_level, updated_by, updated_at")
            .eq("id", 1)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if rows:
            row = rows[0]
            level = str(row.get("smart_warranty_level", "base") or "base").lower()
            if level not in SMART_WARRANTY_LEVELS:
                level = "base"
            return {
                "smart_warranty_level": level,
                "updated_by": str(row.get("updated_by", "") or ""),
                "updated_at": row.get("updated_at"),
            }
    except Exception:
        pass
    return default


def save_smart_warranty_settings(supabase, level: str, updated_by: str) -> None:
    if supabase is None:
        raise RuntimeError("Supabase is not configured.")
    level = (level or "base").lower()
    if level not in SMART_WARRANTY_LEVELS:
        raise ValueError(f"Invalid Smart Warranty level: {level}")
    supabase.table("dealer_settings").upsert({
        "id": 1,
        "smart_warranty_level": level,
        "updated_by": (updated_by or "").strip(),
        "updated_at": _utc_now_iso(),
    }).execute()


DEFAULT_AUDIT_THRESHOLDS = {
    "tech_time_min_pct": 0.70,
    "tech_time_max_pct": 2.00,
    "rental_days_warn": 15,
    "rental_dollars_per_day": 0.0,
}

DEFAULT_AUDIT_RULES = {
    "narrative_required": {"enabled": True, "severity": "hard"},
    "pencil_wrench_cause": {"enabled": True, "severity": "warn"},
    "pencil_wrench_correction": {"enabled": True, "severity": "warn"},
    "oil_leak": {"enabled": True, "severity": "hard"},
    "sublet": {"enabled": True, "severity": "hard"},
    "rental": {"enabled": True, "severity": "hard"},
    "rental_high_days": {"enabled": True, "severity": "warn"},
    "warranty_add_on": {"enabled": True, "severity": "hard"},
    "tech_time": {"enabled": True, "severity": "hard"},
    "battery_test_slip": {"enabled": True, "severity": "hard"},
    "ac_evac_slip": {"enabled": True, "severity": "hard"},
    "alignment_report": {"enabled": True, "severity": "hard"},
    "parts_warranty_mopa": {"enabled": True, "severity": "hard"},
    "manual_guidance": {"enabled": True, "severity": "warn"},
}

AUDIT_RULE_LABELS = {
    "narrative_required": "Require concern, cause, and correction",
    "pencil_wrench_cause": "Pencil Wrench — cause quality checks",
    "pencil_wrench_correction": "Pencil Wrench — correction quality checks",
    "oil_leak": "Oil leak — dye billed and stated in narrative",
    "sublet": "Sublet — VIN, mileage, and detailed notes",
    "rental": "Rental — days billed and manager sign-off",
    "rental_high_days": "Rental — long-rental documentation warning",
    "warranty_add_on": "W+ add-on — Service Manager sign-off",
    "tech_time": "Tech flagged time vs time allotted",
    "battery_test_slip": "Battery replacement — failed test slip/code",
    "ac_evac_slip": "A/C repair — EVAC/recharge slip",
    "alignment_report": "Alignment — printout report attached to RO",
    "parts_warranty_mopa": "Parts warranty — MOPAR and original RO",
    "manual_guidance": "WAM / TSB guidance confirmation warning",
}


def normalize_audit_rules(raw: dict | None) -> dict:
    """Merge stored dealer audit settings with defaults."""
    raw = raw or {}
    thresholds = {**DEFAULT_AUDIT_THRESHOLDS}
    for key, default in DEFAULT_AUDIT_THRESHOLDS.items():
        val = raw.get("thresholds", {}).get(key, default)
        try:
            thresholds[key] = float(val)
        except (TypeError, ValueError):
            thresholds[key] = default

    thresholds["tech_time_min_pct"] = min(max(thresholds["tech_time_min_pct"], 0.0), 1.0)
    thresholds["tech_time_max_pct"] = max(thresholds["tech_time_max_pct"], 1.0)
    thresholds["rental_days_warn"] = max(int(thresholds["rental_days_warn"]), 1)
    thresholds["rental_dollars_per_day"] = max(float(thresholds.get("rental_dollars_per_day", 0.0)), 0.0)

    rules = {}
    stored_rules = raw.get("rules") or {}
    for key, default in DEFAULT_AUDIT_RULES.items():
        entry = stored_rules.get(key, {})
        enabled = bool(entry.get("enabled", default["enabled"]))
        severity = str(entry.get("severity", default["severity"]) or default["severity"]).lower()
        if severity not in ("hard", "warn"):
            severity = default["severity"]
        rules[key] = {"enabled": enabled, "severity": severity}

    return {
        "thresholds": thresholds,
        "rules": rules,
        "updated_by": str(raw.get("updated_by", "") or ""),
        "updated_at": raw.get("updated_at"),
    }


def load_audit_rules(supabase) -> dict:
    if supabase is None:
        return normalize_audit_rules({})
    try:
        response = (
            supabase.table("dealer_settings")
            .select("audit_rules")
            .eq("id", 1)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if rows and rows[0].get("audit_rules"):
            return normalize_audit_rules(rows[0]["audit_rules"])
    except Exception:
        pass
    return normalize_audit_rules({})


def save_audit_rules(supabase, rules: dict, updated_by: str) -> None:
    if supabase is None:
        raise RuntimeError("Supabase is not configured.")
    payload = normalize_audit_rules(rules)
    payload["updated_by"] = (updated_by or "").strip()
    payload["updated_at"] = _utc_now_iso()
    supabase.table("dealer_settings").update({
        "audit_rules": payload,
    }).eq("id", 1).execute()


DEFAULT_REJECTION_REASONS = [
    {"id": "narrative", "label": "Narrative insufficient (cause / correction)", "active": True},
    {"id": "diagnostic", "label": "Missing diagnostic documentation / DTC support", "active": True},
    {"id": "tech_time", "label": "Tech time / time punch issue", "active": True},
    {"id": "battery_slip", "label": "Missing battery test slip / code", "active": True},
    {"id": "ac_slip", "label": "Missing A/C EVAC / recharge documentation", "active": True},
    {"id": "sublet", "label": "Sublet documentation incomplete", "active": True},
    {"id": "rental", "label": "Rental documentation / manager approval", "active": True},
    {"id": "w_plus", "label": "W+ / add-on approval or pay type issue", "active": True},
    {"id": "parts_warranty", "label": "Parts warranty / MOPAR support missing", "active": True},
    {"id": "wam_policy", "label": "Stellantis policy / WAM non-compliance", "active": True},
    {"id": "recall_campaign", "label": "Campaign / recall related", "active": True},
    {"id": "duplicate_claim", "label": "Duplicate or prior claim issue", "active": True},
    {"id": "other", "label": "Other (specify in notes)", "active": True},
]


def _slug_rejection_reason_id(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (label or "").lower()).strip("_")
    return slug[:48] or "reason"


def normalize_rejection_reason_library(raw: dict | None) -> dict:
    raw = raw or {}
    stored = raw.get("reasons") or []
    by_id = {item["id"]: item for item in DEFAULT_REJECTION_REASONS}
    for entry in stored:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label", "") or "").strip()
        if not label:
            continue
        reason_id = str(entry.get("id") or _slug_rejection_reason_id(label)).strip()
        by_id[reason_id] = {
            "id": reason_id,
            "label": label,
            "active": bool(entry.get("active", True)),
        }

    reasons = list(by_id.values())
    reasons.sort(key=lambda r: (not r.get("active", True), r.get("label", "").lower()))
    return {
        "reasons": reasons,
        "updated_by": str(raw.get("updated_by", "") or ""),
        "updated_at": raw.get("updated_at"),
    }


def load_rejection_reason_library(supabase) -> dict:
    if supabase is None:
        return normalize_rejection_reason_library({})
    try:
        response = (
            supabase.table("dealer_settings")
            .select("rejection_reasons")
            .eq("id", 1)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if rows and rows[0].get("rejection_reasons"):
            return normalize_rejection_reason_library(rows[0]["rejection_reasons"])
    except Exception:
        pass
    return normalize_rejection_reason_library({})


def save_rejection_reason_library(supabase, reasons: list[dict], updated_by: str) -> None:
    if supabase is None:
        raise RuntimeError("Supabase is not configured.")
    cleaned = []
    seen_ids = set()
    for entry in reasons:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label", "") or "").strip()
        if not label:
            continue
        reason_id = str(entry.get("id") or _slug_rejection_reason_id(label)).strip()
        base_id = reason_id
        suffix = 2
        while reason_id in seen_ids:
            reason_id = f"{base_id}_{suffix}"
            suffix += 1
        seen_ids.add(reason_id)
        cleaned.append({
            "id": reason_id,
            "label": label,
            "active": bool(entry.get("active", True)),
        })
    payload = {
        "reasons": cleaned,
        "updated_by": (updated_by or "").strip(),
        "updated_at": _utc_now_iso(),
    }
    supabase.table("dealer_settings").update({
        "rejection_reasons": payload,
    }).eq("id", 1).execute()


def active_rejection_reason_labels(library: dict | None) -> list[str]:
    library = normalize_rejection_reason_library(library)
    return [
        str(item.get("label", "")).strip()
        for item in library.get("reasons", [])
        if item.get("active", True) and str(item.get("label", "")).strip()
    ]


def normalize_reviews_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare review rows for reporting and ROI dashboards."""
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if "created_at" in out.columns:
        out["created_at"] = pd.to_datetime(out["created_at"], errors="coerce")

    numeric_cols = [
        "score", "total_claim_value", "hard_stop_value", "hard_stop_count",
        "warning_count", "days_to_submit", "vin_recall_identified",
        "vin_recall_count", "vin_recall_acknowledged",
    ]
    for col in numeric_cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    for col in ("first_pass_paid", "rejected", "time_bypass"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)

    if "status" in out.columns:
        status = out["status"].astype(str)
        out["is_do_not_submit"] = status.str.contains("DO NOT", case=False, na=False).astype(int)
        out["is_needs_review"] = status.str.contains("NEEDS", case=False, na=False).astype(int)
        out["is_ready"] = status.str.contains("READY", case=False, na=False).astype(int)

    return out


def compute_roi_metrics(
    df: pd.DataFrame,
    *,
    rejection_rework_pct: float = 0.40,
    minutes_saved_per_review: float = 15.0,
    admin_hourly_rate: float = 38.0,
) -> dict:
    """Summarize dealership value from saved RO Shield reviews."""
    empty = {
        "review_count": 0,
        "protected_value": 0.0,
        "total_claim_value": 0.0,
        "avg_score": 0.0,
        "first_pass_pct": 0.0,
        "first_pass_count": 0,
        "rejected_pct": 0.0,
        "rejected_count": 0,
        "rejected_value": 0.0,
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
    first_pass_pct = (first_pass_count / count * 100) if count else 0.0
    rejected_pct = (rejected_count / count * 100) if count else 0.0
    rejected_value = float(
        data.loc[data.get("rejected", pd.Series([0])) == 1, "total_claim_value"].sum()
        if "rejected" in data.columns else 0.0
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
        reasons = data[data["rejection_reason"].astype(str).str.strip() != ""]
        if not reasons.empty:
            reasons = reasons.copy()
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
        "first_pass_count": first_pass_count,
        "rejected_pct": rejected_pct,
        "rejected_count": rejected_count,
        "rejected_value": rejected_value,
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


def _sqlite_review_to_record(row: dict) -> dict:
    jobs_raw = row.get("jobs_json") or row.get("jobs") or "[]"
    if isinstance(jobs_raw, str):
        try:
            jobs = json.loads(jobs_raw)
        except json.JSONDecodeError:
            jobs = []
    else:
        jobs = jobs_raw or []

    return normalize_review_record({
        "created_at": row.get("created_at"),
        "ro_number": row.get("ro_number"),
        "vin": row.get("vin"),
        "advisor": row.get("advisor"),
        "technician": row.get("technician"),
        "warranty_admin": row.get("warranty_admin"),
        "manager": row.get("manager"),
        "entered_by": row.get("entered_by"),
        "score": row.get("score"),
        "status": row.get("status"),
        "total_claim_value": row.get("total_claim_value"),
        "hard_stop_value": row.get("hard_stop_value"),
        "hard_stop_count": row.get("hard_stop_count"),
        "warning_count": row.get("warning_count"),
        "time_bypass": row.get("time_bypass"),
        "time_bypass_user": row.get("time_bypass_user"),
        "jobs": jobs,
    })


def migrate_sqlite_to_supabase(supabase, db_path: Path) -> tuple[int, int]:
    """Copy legacy local SQLite reviews into Supabase. Returns (migrated, skipped)."""
    if supabase is None or not db_path.exists():
        return 0, 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM reviews ORDER BY id").fetchall()
    except sqlite3.Error:
        return 0, 0
    finally:
        conn.close()

    migrated = 0
    skipped = 0
    for row in rows:
        record = _sqlite_review_to_record(dict(row))
        if not record.get("ro_number"):
            skipped += 1
            continue
        try:
            existing = (
                supabase.table("reviews")
                .select("id")
                .eq("ro_number", record["ro_number"])
                .eq("created_at", record["created_at"])
                .limit(1)
                .execute()
            )
            if existing.data:
                skipped += 1
                continue
            supabase.table("reviews").insert(record).execute()
            migrated += 1
        except Exception:
            skipped += 1
    return migrated, skipped
