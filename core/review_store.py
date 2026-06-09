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
        "paid_after_rejection": _flag("paid_after_rejection"),
        "rejection_reason": str(payload.get("rejection_reason", "") or "").strip(),
        "jobs": jobs,
        "vin_recall_identified": _int("vin_recall_identified"),
        "vin_recall_count": _int("vin_recall_count"),
        "vin_recall_campaigns": str(payload.get("vin_recall_campaigns", "") or "").strip(),
        "vin_recall_acknowledged": _int("vin_recall_acknowledged"),
    }
    if "oem_paid_amount" in payload:
        raw_oem = payload.get("oem_paid_amount")
        record["oem_paid_amount"] = None if raw_oem is None else _num("oem_paid_amount")
    return record


def is_pending_outcome(first_pass_paid, rejected, paid_after_rejection=0) -> bool:
    try:
        fp = int(float(first_pass_paid or 0))
    except (TypeError, ValueError):
        fp = 0
    try:
        rej = int(float(rejected or 0))
    except (TypeError, ValueError):
        rej = 0
    try:
        par = int(float(paid_after_rejection or 0))
    except (TypeError, ValueError):
        par = 0
    return not fp and not rej and not par


def _parse_created_at(value) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def find_review_id_for_update(supabase, ro_number: str, vin: str = "") -> int | None:
    """Return an existing review id to update instead of inserting a duplicate."""
    ro_number = str(ro_number or "").strip()
    if not ro_number or supabase is None:
        return None

    rows = (
        supabase.table("reviews")
        .select("id, vin, first_pass_paid, rejected, paid_after_rejection, created_at")
        .eq("ro_number", ro_number)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    if not rows:
        return None

    vin_clean = str(vin or "").strip()
    today_utc = datetime.now(timezone.utc).date()

    def _vin_matches(row_vin: str) -> bool:
        row_vin = str(row_vin or "").strip()
        if not vin_clean or not row_vin:
            return True
        return row_vin == vin_clean

    for row in rows:
        if not _vin_matches(row.get("vin", "")):
            continue
        if is_pending_outcome(
            row.get("first_pass_paid"),
            row.get("rejected"),
            row.get("paid_after_rejection"),
        ):
            return int(row["id"])

    for row in rows:
        if not _vin_matches(row.get("vin", "")):
            continue
        created = _parse_created_at(row.get("created_at"))
        if created and created.astimezone(timezone.utc).date() == today_utc:
            return int(row["id"])

    return None


def save_or_update_review(supabase, data: dict, *, review_id: int | None = None) -> dict:
    """Insert a new review, or update an existing one when review_id / RO match applies."""
    if supabase is None:
        return {"ok": False, "review_id": None, "created": False}

    record = normalize_review_record(data)
    ro = record.get("ro_number", "")
    vin = record.get("vin", "")

    target_id = review_id or find_review_id_for_update(supabase, ro, vin)
    if target_id:
        patch = dict(record)
        patch.pop("created_at", None)
        supabase.table("reviews").update(patch).eq("id", int(target_id)).execute()
        return {"ok": True, "review_id": int(target_id), "created": False}

    resp = supabase.table("reviews").insert(record).execute()
    new_id = None
    if resp.data:
        new_id = int(resp.data[0]["id"])
    return {"ok": True, "review_id": new_id, "created": True}


def save_review(supabase, data: dict) -> bool:
    """Legacy insert-only save — prefer save_or_update_review for new code."""
    result = save_or_update_review(supabase, data)
    return bool(result.get("ok"))


def is_paid_outcome(first_pass_paid, rejected, paid_after_rejection=0) -> bool:
    fp = int(first_pass_paid or 0)
    rej = int(rejected or 0)
    par = int(paid_after_rejection or 0)
    return bool((fp or par) and not rej)


def normalize_oem_paid_amount(value, *, submitted: float) -> float | None:
    """Return stored OEM paid amount, or None when paid in full (blank or equals submitted)."""
    if value is None:
        return None
    if isinstance(value, str) and not str(value).strip():
        return None
    try:
        paid = float(value)
    except (TypeError, ValueError):
        raise ValueError("Enter a valid OEM paid amount.") from None
    if paid < 0:
        raise ValueError("OEM paid amount cannot be negative.")
    submitted_val = float(submitted or 0)
    if submitted_val > 0 and paid > submitted_val + 0.01:
        raise ValueError(
            f"OEM paid amount cannot exceed the audited claim value (${submitted_val:,.2f})."
        )
    if submitted_val > 0 and paid >= submitted_val - 0.01:
        return None
    return paid


def compute_short_pay(submitted: float, oem_paid_amount) -> float:
    submitted_val = float(submitted or 0)
    if submitted_val <= 0 or oem_paid_amount is None:
        return 0.0
    try:
        paid = float(oem_paid_amount)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, submitted_val - paid)


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


def update_review_outcome(
    supabase,
    review_id: int,
    *,
    first_pass_paid: bool,
    rejected: bool,
    paid_after_rejection: bool = False,
    rejection_reason: str = "",
    updated_by: str = "",
    oem_paid_amount: float | None = None,
    submitted_claim_value: float | None = None,
) -> None:
    if supabase is None:
        raise RuntimeError("Supabase is not configured.")
    selected = sum(bool(x) for x in (first_pass_paid, rejected, paid_after_rejection))
    if selected > 1:
        raise ValueError(
            "Choose only one outcome: first-pass paid, rejected, or paid after rejection."
        )
    if paid_after_rejection and not str(rejection_reason or "").strip():
        raise ValueError("Enter why the claim was initially declined.")
    stored_paid: float | None = None
    if is_paid_outcome(first_pass_paid, rejected, paid_after_rejection):
        submitted = float(
            submitted_claim_value if submitted_claim_value is not None else 0
        )
        stored_paid = normalize_oem_paid_amount(oem_paid_amount, submitted=submitted)
    payload = {
        "first_pass_paid": 1 if first_pass_paid else 0,
        "rejected": 1 if rejected else 0,
        "paid_after_rejection": 1 if paid_after_rejection else 0,
        "rejection_reason": (
            str(rejection_reason or "").strip()
            if rejected or paid_after_rejection
            else ""
        ),
        "oem_paid_amount": stored_paid,
        "outcome_updated_at": _utc_now_iso(),
        "outcome_updated_by": str(updated_by or "").strip(),
    }
    supabase.table("reviews").update(payload).eq("id", int(review_id)).execute()


def parse_review_jobs(review: dict | None) -> list[dict]:
    """Return job dicts from a review row."""
    if not review:
        return []
    jobs = review.get("jobs")
    if jobs is None:
        return []
    if isinstance(jobs, str):
        try:
            jobs = json.loads(jobs) if jobs.strip() else []
        except json.JSONDecodeError:
            return []
    return list(jobs) if isinstance(jobs, list) else []


def load_review_by_id(supabase, review_id: int) -> dict | None:
    if supabase is None or not review_id:
        return None
    try:
        response = (
            supabase.table("reviews")
            .select("*")
            .eq("id", int(review_id))
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None
    except Exception:
        return None


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
    "oil_leak": "Oil leak — Oil Leak and Oil Dye Billed must match",
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
    "other": "Other / uncategorized finding",
}

ADVISOR_COACHING_PHRASES = {
    "narrative_required": "missing concern, cause, or correction",
    "pencil_wrench_cause": "incomplete cause narrative (diagnostics or failure not clear)",
    "pencil_wrench_correction": "incomplete correction narrative (repair or verification not clear)",
    "oil_leak": "Oil Leak and Oil Dye Billed checkboxes do not match",
    "sublet": "sublet paperwork incomplete (VIN, mileage, or notes)",
    "rental": "rental days or manager sign-off missing",
    "rental_high_days": "long rental — supporting documentation may be missing",
    "warranty_add_on": "W+ add-on missing Service Manager sign-off",
    "tech_time": "tech flagged time vs. time allotted out of range",
    "battery_test_slip": "battery test slip/code missing",
    "ac_evac_slip": "A/C EVAC/recharge slip missing",
    "alignment_report": "alignment printout not attached to the RO",
    "parts_warranty_mopa": "parts warranty missing MOPAR/original RO support",
    "manual_guidance": "WAM/TSB guidance not confirmed",
    "other": "other audit documentation issue",
}


def format_coaching_issue(claim_count: int, rule_key: str) -> str:
    phrase = ADVISOR_COACHING_PHRASES.get(
        str(rule_key or "").strip(),
        audit_rule_label(rule_key).lower(),
    )
    noun = "claim" if claim_count == 1 else "claims"
    return f"{claim_count} {noun} with {phrase}"


def _coaching_examples_for_rule(
    findings: pd.DataFrame,
    *,
    advisor: str,
    rule_key: str,
) -> list[dict]:
    """Distinct RO examples for one advisor + audit rule (for coaching drill-down)."""
    subset = findings[
        (findings["advisor"] == advisor) & (findings["rule_key"] == rule_key)
    ].copy()
    if subset.empty:
        return []

    examples: list[dict] = []
    for ro_number, ro_group in subset.groupby("ro_number", sort=False):
        jobs = sorted(
            {
                str(job_no).strip()
                for job_no in ro_group["job_no"].tolist()
                if str(job_no).strip() not in {"", "nan", "None", "—"}
            }
        )
        messages: list[str] = []
        seen_messages: set[str] = set()
        for msg in ro_group["message"].tolist():
            text = str(msg or "").strip()
            if text and text not in seen_messages:
                seen_messages.add(text)
                messages.append(text)
        if not messages:
            continue

        severities = ro_group["severity"].astype(str).tolist()
        severity = "hard" if "hard" in severities else (severities[0] if severities else "warn")
        created = ro_group["created_at"].max()
        claim_value = float(pd.to_numeric(ro_group["claim_value"], errors="coerce").max() or 0)
        examples.append(
            {
                "ro_number": str(ro_number),
                "job_nos": jobs,
                "severity": severity,
                "messages": messages,
                "claim_value": claim_value,
                "created_at": created,
            }
        )

    examples.sort(
        key=lambda item: pd.to_datetime(item["created_at"], errors="coerce"),
        reverse=True,
    )
    return examples

def _valid_advisor_name(name: str) -> bool:
    cleaned = str(name or "").strip()
    return bool(cleaned) and cleaned not in {"—", "-", "Unknown", "unknown", "N/A", "n/a"}


def finding_message(item) -> str:
    if isinstance(item, dict):
        return str(item.get("message") or "").strip()
    return str(item or "").strip()


def finding_rule_key(item) -> str:
    if isinstance(item, dict):
        rule = str(item.get("rule") or "").strip()
        if rule:
            return rule
    return classify_finding_message(finding_message(item))


def classify_finding_message(message: str) -> str:
    """Map saved finding text to an audit rule bucket (legacy reviews without rule keys)."""
    msg = str(message or "").lower()
    if not msg:
        return "other"
    if msg.startswith("missing concern") or msg.startswith("missing cause") or msg.startswith("missing correction"):
        return "narrative_required"
    if "pencil wrench cause" in msg:
        return "pencil_wrench_cause"
    if "pencil wrench correction" in msg:
        return "pencil_wrench_correction"
    if "oil leak" in msg or "oil dye" in msg or "dye was used" in msg:
        return "oil_leak"
    if "sublet" in msg:
        return "sublet"
    if "rental days billed" in msg or ("manager sign-off" in msg and "rental" in msg):
        return "rental"
    if "rental days" in msg and "documentation" in msg:
        return "rental_high_days"
    if "add-on" in msg or "w+" in msg or "warranty add-on" in msg:
        return "warranty_add_on"
    if "tech flagged time" in msg or "time allotted" in msg:
        return "tech_time"
    if "battery" in msg and ("test slip" in msg or "test/code" in msg):
        return "battery_test_slip"
    if "a/c repair" in msg or "evac/recharge" in msg:
        return "ac_evac_slip"
    if "alignment" in msg:
        return "alignment_report"
    if "parts warranty" in msg or "mopar" in msg or "mopa" in msg:
        return "parts_warranty_mopa"
    if "manual guidance" in msg or "warranty manual" in msg:
        return "manual_guidance"
    return "other"


def audit_rule_label(rule_key: str) -> str:
    return AUDIT_RULE_LABELS.get(str(rule_key or "").strip(), AUDIT_RULE_LABELS["other"])


def _parse_jobs_cell(value) -> list:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _iter_review_findings(review_row: dict) -> list[dict]:
    """Flatten hard stops and warnings from a saved review into analytic rows."""
    jobs = _parse_jobs_cell(review_row.get("jobs"))
    advisor = str(review_row.get("advisor") or "").strip() or "—"
    technician = str(review_row.get("technician") or "").strip() or "—"
    ro_number = str(review_row.get("ro_number") or "").strip()
    created_at = review_row.get("created_at")
    rows = []

    for job in jobs:
        if not isinstance(job, dict):
            continue
        job_no = job.get("job_no", "")
        claim_value = float(job.get("claim_value") or 0)
        for severity, key in (("hard", "hard_stops"), ("warn", "warnings")):
            for item in job.get(key) or []:
                message = finding_message(item)
                if not message:
                    continue
                rule_key = finding_rule_key(item)
                rows.append(
                    {
                        "ro_number": ro_number,
                        "advisor": advisor,
                        "technician": technician,
                        "created_at": created_at,
                        "job_no": job_no,
                        "severity": severity,
                        "rule_key": rule_key,
                        "rule_label": audit_rule_label(rule_key),
                        "message": message,
                        "claim_value": claim_value,
                    }
                )
    return rows


def compute_hard_stop_breakdown(df: pd.DataFrame) -> dict:
    """Summarize audit findings by rule, advisor, and week for coaching dashboards."""
    empty = {
        "finding_count": 0,
        "hard_count": 0,
        "warn_count": 0,
        "reviews_with_findings": 0,
        "rule_summary": pd.DataFrame(),
        "rule_totals": pd.DataFrame(),
        "advisor_rule_summary": pd.DataFrame(),
        "weekly_rule_trend": pd.DataFrame(),
        "advisor_coaching": [],
    }
    if df is None or df.empty:
        return empty

    data = normalize_reviews_dataframe(df)
    all_rows: list[dict] = []
    reviews_with_findings: set[str] = set()

    for _, row in data.iterrows():
        review_rows = _iter_review_findings(row.to_dict())
        if review_rows:
            reviews_with_findings.add(str(row.get("ro_number") or row.name))
        all_rows.extend(review_rows)

    if not all_rows:
        return empty

    findings = pd.DataFrame(all_rows)
    hard_count = int((findings["severity"] == "hard").sum())
    warn_count = int((findings["severity"] == "warn").sum())
    total = len(findings)

    rule_summary = (
        findings.groupby(["rule_key", "rule_label", "severity"], as_index=False)
        .agg(count=("message", "count"))
        .sort_values(["count", "rule_label"], ascending=[False, True])
    )
    rule_summary["pct"] = (rule_summary["count"] / total * 100).round(1)

    rule_totals = (
        findings.groupby(["rule_key", "rule_label"], as_index=False)
        .agg(total_count=("message", "count"))
        .sort_values("total_count", ascending=False)
    )

    advisor_rule = (
        findings.groupby(["advisor", "rule_label"], as_index=False)
        .agg(count=("message", "count"))
        .sort_values(["count", "advisor"], ascending=[False, True])
    )

    weekly_rule_trend = pd.DataFrame()
    if "created_at" in findings.columns and findings["created_at"].notna().any():
        trend = findings.dropna(subset=["created_at"]).copy()
        trend["week"] = trend["created_at"].dt.to_period("W").astype(str)
        top_rules = rule_totals.head(5)["rule_label"].tolist()
        trend = trend[trend["rule_label"].isin(top_rules)]
        if not trend.empty:
            weekly_rule_trend = (
                trend.groupby(["week", "rule_label"], as_index=False)
                .agg(count=("message", "count"))
                .sort_values("week")
            )

    coaching_priorities = []
    for _, row in rule_totals.head(6).iterrows():
        coaching_priorities.append(
            {
                "rule_key": row["rule_key"],
                "rule_label": row["rule_label"],
                "count": int(row["total_count"]),
                "pct": round(float(row["total_count"]) / total * 100, 1),
            }
        )

    advisor_coaching = _compute_advisor_coaching_details(findings)

    return {
        "finding_count": total,
        "hard_count": hard_count,
        "warn_count": warn_count,
        "reviews_with_findings": len(reviews_with_findings),
        "rule_summary": rule_summary,
        "rule_totals": rule_totals,
        "advisor_rule_summary": advisor_rule,
        "weekly_rule_trend": weekly_rule_trend,
        "coaching_priorities": coaching_priorities,
        "advisor_coaching": advisor_coaching,
    }


def _compute_advisor_coaching_details(findings: pd.DataFrame) -> list[dict]:
    """Per-advisor coaching list: distinct RO counts by issue type."""
    if findings is None or findings.empty:
        return []

    scoped = findings.copy()
    scoped["advisor"] = scoped["advisor"].astype(str).str.strip()
    scoped = scoped[scoped["advisor"].map(_valid_advisor_name)]
    if scoped.empty:
        return []

    claim_counts = (
        scoped.groupby(["advisor", "rule_key"], as_index=False)
        .agg(claim_count=("ro_number", "nunique"))
        .sort_values(["advisor", "claim_count"], ascending=[True, False])
    )

    ros_with_issues = scoped.groupby("advisor")["ro_number"].nunique().to_dict()

    coaching: list[dict] = []
    for advisor, group in claim_counts.groupby("advisor", sort=False):
        issue_items: list[dict] = []
        for _, row in group.iterrows():
            claim_count = int(row["claim_count"])
            if claim_count <= 0:
                continue
            rule_key = str(row["rule_key"])
            issue_items.append(
                {
                    "label": format_coaching_issue(claim_count, rule_key),
                    "rule_key": rule_key,
                    "claim_count": claim_count,
                    "examples": _coaching_examples_for_rule(
                        scoped,
                        advisor=advisor,
                        rule_key=rule_key,
                    ),
                }
            )
        if not issue_items:
            continue
        coaching.append(
            {
                "advisor": advisor,
                "ros_with_issues": int(ros_with_issues.get(advisor, 0)),
                "issues": issue_items,
            }
        )

    coaching.sort(
        key=lambda item: (item["ros_with_issues"], len(item["issues"])),
        reverse=True,
    )
    return coaching


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

    if "oem_paid_amount" in out.columns:
        out["oem_paid_amount"] = pd.to_numeric(out["oem_paid_amount"], errors="coerce")

    for col in ("first_pass_paid", "rejected", "paid_after_rejection", "time_bypass"):
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)

    if "total_claim_value" in out.columns:
        submitted = pd.to_numeric(out["total_claim_value"], errors="coerce").fillna(0)
        paid_flag = pd.Series(False, index=out.index)
        if "first_pass_paid" in out.columns:
            paid_flag = paid_flag | (out["first_pass_paid"] == 1)
        if "paid_after_rejection" in out.columns:
            paid_flag = paid_flag | (out["paid_after_rejection"] == 1)
        if "oem_paid_amount" in out.columns:
            effective_paid = out["oem_paid_amount"].where(out["oem_paid_amount"].notna(), submitted)
        else:
            effective_paid = submitted
        short = (submitted - effective_paid).clip(lower=0)
        out["short_pay_amount"] = short.where(paid_flag, 0.0)
        out["is_partial_pay"] = paid_flag & (out["short_pay_amount"] > 0.01)

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
    """Summarize dealership value from saved RO Shield reviews."""
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
        "rejected_final_count": 0,
        "oem_rejection_total_count": 0,
        "partial_pay_count": 0,
        "short_pay_total": 0.0,
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
    oem_rejection_total_count = rejected_count + paid_after_rejection_count
    if "short_pay_amount" in data.columns:
        partial_pay_count = int(data.get("is_partial_pay", pd.Series([False])).sum())
        short_pay_total = float(data.get("short_pay_amount", pd.Series([0])).sum())
    else:
        partial_pay_count = 0
        short_pay_total = 0.0
    pending_outcome_count = int(
        (
            (data.get("first_pass_paid", pd.Series([0])) == 0)
            & (data.get("rejected", pd.Series([0])) == 0)
            & (data.get("paid_after_rejection", pd.Series([0])) == 0)
        ).sum()
        if "first_pass_paid" in data.columns and "rejected" in data.columns else 0
    )
    resolved_count = max(count - pending_outcome_count, 0)
    first_pass_pct = (first_pass_count / count * 100) if count else 0.0
    first_pass_pct_resolved = (first_pass_count / resolved_count * 100) if resolved_count else 0.0
    rejected_pct = (rejected_count / resolved_count * 100) if resolved_count else 0.0
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
        "rejected_final_count": rejected_count,
        "oem_rejection_total_count": oem_rejection_total_count,
        "partial_pay_count": partial_pay_count,
        "short_pay_total": short_pay_total,
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
