from __future__ import annotations

import html
import json
import os
import re
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from core.ro_charts import (
    advisor_hard_stops_chart,
    hard_stop_rules_chart,
    audit_outcomes_pie,
    first_pass_pie,
    issue_breakdown_pie,
    review_status_pie,
    score_distribution_chart,
    weekly_activity_chart,
)
from core.pdf_reports import (
    build_audit_report_pdf,
    build_decline_reasons_pdf,
    build_review_report_pdf,
    build_roi_report_pdf,
    build_short_pay_report_pdf,
)
from core.report_export_ui import (
    period_label_from_df,
    render_branded_pdf_download,
    render_branded_report_table,
)
from core.auth import (
    apply_session_to_client,
    auth_user_email,
    capture_recovery_from_query,
    get_stored_session,
    inject_auth_hash_bridge,
    is_authenticated,
    is_password_recovery_mode,
    is_valid_email,
    normalize_email,
    render_authenticated_sidebar,
    render_login_page,
    render_password_reset_page,
    render_sidebar_brand,
    restore_client_session,
    request_soft_refresh,
    run_soft_refresh_if_requested,
    sync_personnel_identity,
)
from core.review_store import (
    AUDIT_RULE_LABELS,
    DEFAULT_AUDIT_RULES,
    active_rejection_reason_labels,
    compute_hard_stop_breakdown,
    compute_roi_metrics,
    finding_message,
    load_audit_rules,
    filter_bulletins_df,
    load_bulletins,
    load_rejection_reason_library,
    sort_bulletins_df,
    load_reviews as fetch_reviews,
    load_smart_warranty_settings,
    migrate_sqlite_to_supabase,
    normalize_audit_rules,
    normalize_rejection_reason_library,
    normalize_reviews_dataframe,
    normalize_oem_paid_amount,
    compute_short_pay,
    is_paid_outcome,
    build_short_pay_report_dataframe,
    validate_short_pay_reason,
    review_outcome_label,
    save_audit_rules,
    save_bulletin as persist_bulletin,
    save_rejection_reason_library,
    find_review_id_for_update,
    save_or_update_review as persist_save_or_update_review,
    save_smart_warranty_settings,
    smart_warranty_punch_exempt,
    update_review_outcome,
)
from core.theme_styles import (
    BRAND_TEXT,
    THEME_CSS,
    audit_result_panel_css,
    brand_color_lock_css,
    claim_learning_css,
    expander_css,
    metric_display_css,
    multiselect_css,
    pricing_page_css,
    dealer_connect_panel_css,
    narrative_copy_button_css,
    review_collapsible_css,
    review_open_claims_strip_css,
    script_embed_collapse_css,
    main_scroll_fix_css,
    streamlit_primary_override_css,
    vin_recall_alert_css,
)
from core.personnel_roles import (
    ALL_PERSONNEL_ROLES,
    DEALERSHIP_ROLES,
    PLATFORM_ADMIN_ROLES,
    format_roles_display,
    normalize_roles_list,
    parse_personnel_roles,
    person_has_any_role,
    primary_personnel_role,
)
from core.sales_pricing import render_pricing_roi_page
from core.deployment_admin import render_deployment_secrets_admin, user_can_view_deployment
from core.scheduled_reports_admin import render_scheduled_reports_admin
from core.display_prefs import build_user_display_css, render_display_settings_sidebar, request_display_widget_resync
from core.popps_report import render_popps_report
from core.html_embed import embed_html, embed_script, ensure_sidebar_expanded
from core.ro_ocr import extract_ro_text, merge_form_imports, ocr_available, parsed_to_form_import, scan_repair_order_pdf
from core import vin_recalls
from core.vin_recalls import apply_job_relevance, lookup_vin_recalls, normalize_vin

MAX_DISPLAY_RECALLS = getattr(vin_recalls, "MAX_DISPLAY_RECALLS", 5)


def filter_actionable_recalls(
    recalls: list[dict],
    *,
    min_score: int = getattr(vin_recalls, "RELATED_RECALL_MIN_SCORE", 12),
) -> list[dict]:
    """Use vin_recalls filter when available; keep a local fallback for older deploys."""
    module_fn = getattr(vin_recalls, "filter_actionable_recalls", None)
    if module_fn is not None:
        return module_fn(recalls, min_score=min_score)

    actionable: list[dict] = []
    for recall in recalls:
        score = int(recall.get("relevance_score") or 0)
        critical = bool(recall.get("park_it") or recall.get("park_outside"))
        if score >= min_score or critical:
            actionable.append(recall)
    actionable.sort(
        key=lambda r: (
            0 if (r.get("park_it") or r.get("park_outside")) else 1,
            -int(r.get("relevance_score") or 0),
            r.get("report_date") or "",
        ),
    )
    return actionable

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

try:
    from supabase import create_client
except Exception:
    create_client = None


def _load_supabase_credentials():
    """Local .env first; Streamlit Cloud uses app Secrets (st.secrets)."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    try:
        if not url:
            url = str(st.secrets.get("SUPABASE_URL", "")).strip()
        if not key:
            key = str(st.secrets.get("SUPABASE_KEY", "")).strip()
    except Exception:
        pass
    return url, key


SUPABASE_URL, SUPABASE_KEY = _load_supabase_credentials()

if create_client and SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    supabase = None

st.set_page_config(page_title="RO Shield", layout="wide", initial_sidebar_state="expanded")


def _ensure_review_form_session() -> None:
    if "form_version" not in st.session_state:
        st.session_state.form_version = 0
    if "job_count" not in st.session_state:
        st.session_state.job_count = 1


_ensure_review_form_session()

DB_PATH = Path("ro_shield_final.db")


# =========================
# DATABASE (Supabase = source of truth for reviews, claims, personnel, WAM)
# =========================
def _active_review_id_key(form_version: int) -> str:
    return f"active_review_id_{form_version}"


def _active_review_ro_key(form_version: int) -> str:
    return f"active_review_ro_{form_version}"


def _active_review_vin_key(form_version: int) -> str:
    return f"active_review_vin_{form_version}"


def _resolve_session_review_id(form_version: int, ro_number: str, vin: str) -> int | None:
    review_id = st.session_state.get(_active_review_id_key(form_version))
    if not review_id:
        return None
    tracked_ro = str(st.session_state.get(_active_review_ro_key(form_version), "") or "").strip()
    tracked_vin = str(st.session_state.get(_active_review_vin_key(form_version), "") or "").strip()
    if tracked_ro != str(ro_number or "").strip() or tracked_vin != str(vin or "").strip():
        for key in (
            _active_review_id_key(form_version),
            _active_review_ro_key(form_version),
            _active_review_vin_key(form_version),
        ):
            st.session_state.pop(key, None)
        return None
    return int(review_id)


def _parse_review_jobs(review: dict | None) -> list[dict]:
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


def _load_review_by_id(review_id: int) -> dict | None:
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


def _review_will_update(form_version: int, ro_number: str, vin: str) -> bool:
    if _resolve_session_review_id(form_version, ro_number, vin):
        return True
    if not str(ro_number or "").strip():
        return False
    return find_review_id_for_update(supabase, ro_number, vin) is not None


def save_review(data, *, review_id: int | None = None):
    try:
        return persist_save_or_update_review(supabase, data, review_id=review_id)
    except Exception as e:
        st.error(f"Review save failed: {e}")
        st.caption("If this is your first deploy, run docs/SUPABASE_SCHEMA.sql in Supabase SQL Editor.")
        return {"ok": False, "review_id": None, "created": False}


def invalidate_reviews_cache() -> None:
    st.session_state["_reviews_cache_gen"] = int(st.session_state.get("_reviews_cache_gen", 0)) + 1


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_reviews_cached(cache_generation: int) -> tuple[pd.DataFrame, str | None]:
    del cache_generation
    try:
        return fetch_reviews(supabase), None
    except Exception as e:
        return pd.DataFrame(), str(e)


def load_reviews(*, bust_cache: bool = False) -> pd.DataFrame:
    if bust_cache:
        invalidate_reviews_cache()
    generation = int(st.session_state.get("_reviews_cache_gen", 0))
    df, err = _fetch_reviews_cached(generation)
    if err:
        st.warning(f"Review load failed: {err}")
    return df


def clear_all_reviews() -> dict:
    """Remove every saved review from Reporting."""
    stats = {"removed": 0, "errors": 0, "method": ""}
    if supabase is None:
        return stats

    try:
        resp = supabase.rpc("clear_all_reviews", {}).execute()
        if resp.data is not None:
            stats["removed"] = int(resp.data)
            stats["method"] = "rpc"
            return stats
    except Exception:
        pass

    try:
        rows = supabase.table("reviews").select("id").execute().data or []
        for row in rows:
            try:
                deleted = supabase.table("reviews").delete().eq("id", row["id"]).execute().data
                if deleted:
                    stats["removed"] += len(deleted)
            except Exception:
                stats["errors"] += 1
        stats["method"] = "row_delete"
    except Exception:
        stats["errors"] += 1

    return stats


def save_bulletin(title, keywords, notes, **kwargs):
    try:
        persist_bulletin(supabase, title, keywords, notes, **kwargs)
    except Exception as e:
        st.warning(f"Bulletin save failed: {e}")
        st.caption("Run docs/SUPABASE_SCHEMA.sql in Supabase if the bulletins table is missing columns.")


def init_db():
    """Legacy local DB — kept only for one-time SQLite → Supabase migration."""
    pass

def save_shared_claims(file_name, claims):
    for idx, claim in enumerate(claims, start=1):
        data = {
            "ro_number": file_name,
            "vin": "",
            "concern": "",
            "cause": "",
            "correction": "",
            "tech": "",
            "advisor": "",
            "story": claim
        }
        try:
            existing = supabase.table("claims").select("id").eq("ro_number", file_name).eq("story", claim).execute()

            if not existing.data:
                supabase.table("claims").insert(data).execute()
        except Exception as e:
            st.warning(f"Save failed: {e}")

def load_shared_claims():
    try:
        response = supabase.table("claims").select("*").order("created_at", desc=True).limit(10000).execute()
        rows = response.data or []
        return pd.DataFrame(rows)

    except Exception as e:
        st.warning(f"Load failed: {e}")
        return pd.DataFrame()

def load_personnel():
    try:
        response = supabase.table("personnel").select("*").eq("active", True).execute()
        rows = response.data or []
        return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"Personnel load failed: {e}")
        return pd.DataFrame(columns=["name", "role", "email"])


def add_person_shared(name, roles, employee_number, email=""):
    role_list = normalize_roles_list(roles)
    if not role_list:
        st.warning("Select at least one role.")
        return
    try:
        email_clean = normalize_email(email)
        if email_clean:
            existing = (
                supabase.table("personnel")
                .select("id")
                .eq("email", email_clean)
                .execute()
            )
            if existing.data:
                st.warning("Someone with this email is already on file — edit that person to add roles.")
                return

        payload = {
            "name": name,
            "employee_number": employee_number,
            "roles": role_list,
            "role": primary_personnel_role(role_list),
            "active": True,
        }
        if email_clean:
            payload["email"] = email_clean
        supabase.table("personnel").insert(payload).execute()

    except Exception as e:
        st.warning(f"Personnel save failed: {e}")

def deactivate_person(pid):
    try:
        supabase.table("personnel").update({"active": False}).eq("id", int(pid)).execute()
    except Exception as e:
        st.warning(f"Personnel deactivate failed: {e}")


ADMIN_WRITE_ROLES = ("Manager", "Warranty Admin", "Admin")
PERSONNEL_ADMIN_ROLES = ("Manager", "Admin")
CONTENT_ADMIN_ROLES = ("Manager", "Warranty Admin", "Admin")


def admin_write_names() -> list[str]:
    df = load_personnel()
    if df.empty:
        return []
    mask = df.apply(lambda row: person_has_any_role(row, *ADMIN_WRITE_ROLES), axis=1)
    return df.loc[mask, "name"].astype(str).tolist()


def current_person_name() -> str:
    return str(st.session_state.get("current_person_name") or "").strip()


def current_person_roles() -> list[str]:
    roles = st.session_state.get("current_person_roles")
    if isinstance(roles, list) and roles:
        return normalize_roles_list(roles)
    legacy = str(st.session_state.get("current_person_role") or "").strip()
    if " · " in legacy:
        return normalize_roles_list([p.strip() for p in legacy.split(" · ")])
    return normalize_roles_list(legacy)


def current_person_role() -> str:
    roles = current_person_roles()
    if roles:
        return format_roles_display(roles)
    return str(st.session_state.get("current_person_role") or "").strip()


def is_signed_in() -> bool:
    return is_authenticated()


def user_has_role(*roles: str) -> bool:
    mine = set(current_person_roles())
    return bool(mine.intersection(roles))


def user_is_platform_admin() -> bool:
    return user_has_role(*PLATFORM_ADMIN_ROLES)


def user_can_admin_write() -> bool:
    return user_has_role(*ADMIN_WRITE_ROLES)


def user_can_manage_personnel() -> bool:
    return user_has_role(*PERSONNEL_ADMIN_ROLES)


def user_can_upload_library() -> bool:
    return user_has_role(*CONTENT_ADMIN_ROLES)


def user_can_see_pricing() -> bool:
    return user_is_platform_admin()


def assignable_personnel_roles() -> list[str]:
    """Roles the current user may assign when adding or editing personnel."""
    roles = list(DEALERSHIP_ROLES)
    if user_is_platform_admin():
        roles.append("Admin")
    return roles


def _pick_personnel_roles(
    options: list[str],
    default: list[str],
    *,
    key_prefix: str,
    disabled: bool = False,
) -> list[str]:
    """Checkbox-based role picker — avoids broken multiselect tag styling."""
    st.markdown("**Roles (select all that apply)**")
    if disabled:
        locked = normalize_roles_list(default)
        if locked:
            st.caption(format_roles_display(locked))
        return locked

    defaults = set(normalize_roles_list(default))
    picked: list[str] = []
    columns = st.columns(2 if len(options) > 1 else 1)
    for idx, role in enumerate(options):
        with columns[idx % len(columns)]:
            if st.checkbox(
                role,
                value=role in defaults,
                key=f"{key_prefix}_{role}",
            ):
                picked.append(role)
    return normalize_roles_list(picked)


def render_role_gate_message(required_roles: tuple[str, ...], action_label: str = "make changes"):
    roles_text = " or ".join(required_roles)
    who = current_person_name() or "—"
    role = current_person_role() or "no linked role"
    st.warning(
        f"Your account needs a linked **{roles_text}** personnel record to {action_label}. "
        f"Signed in as **{who}** ({role})."
    )


def resolve_admin_author(authorized_names: list[str]) -> str:
    name = current_person_name()
    if name and user_can_admin_write() and name in authorized_names:
        return name
    return ""


def render_admin_author_field(authorized_names: list[str], *, key: str) -> str:
    locked = resolve_admin_author(authorized_names)
    if locked:
        st.text_input(
            "Authorized by (Manager / Warranty Admin)",
            value=locked,
            disabled=True,
            key=f"{key}_locked",
        )
        return locked
    if not user_can_admin_write():
        st.caption("Admin save requires a linked Manager or Warranty Admin account.")
        return ""
    return st.selectbox(
        "Authorized by (Manager / Warranty Admin)",
        options=[""] + authorized_names,
        disabled=not authorized_names,
        key=key,
    )


_GENERIC_PERSONNEL_NAMES = frozenset({"service manager", "manager", "platform admin"})


def personnel_display_name(name: str, email: str = "") -> str:
    """Show a real name in dropdowns — not placeholder text like 'Service Manager'."""
    cleaned = str(name or "").strip()
    if cleaned and cleaned.lower() not in _GENERIC_PERSONNEL_NAMES:
        return cleaned
    email = str(email or "").strip().lower()
    if email and "@" in email:
        local = email.split("@", 1)[0]
        parts = re.split(r"[._+-]+", local)
        derived = " ".join(p.capitalize() for p in parts if p)
        if derived:
            return derived
    return cleaned or "Manager"


def _personnel_display_names(df) -> list[str]:
    if df is None or df.empty:
        return []
    names = [
        personnel_display_name(row.get("name", ""), row.get("email", ""))
        for _, row in df.iterrows()
    ]
    return sorted({n for n in names if n})


def role_options(role, *, include_managers: bool = True):
    df = load_personnel()
    if df.empty:
        return [""]
    allowed = {role}
    if include_managers and role in ("Advisor", "Technician", "Warranty Admin"):
        allowed.add("Manager")
    mask = df["active"].astype(bool) & df.apply(
        lambda row: bool(set(parse_personnel_roles(row)) & allowed),
        axis=1,
    )
    return [""] + _personnel_display_names(df.loc[mask])


def review_personnel_names(primary_role: str) -> list[str]:
    """Names for Review tab dropdowns; Managers may fill any service role."""
    df = load_personnel()
    if df.empty:
        return []
    allowed = {primary_role, "Manager"}
    mask = df["active"].astype(bool) & df.apply(
        lambda row: bool(set(parse_personnel_roles(row)) & allowed),
        axis=1,
    )
    return _personnel_display_names(df.loc[mask])


def service_manager_names() -> list[str]:
    df = load_personnel()
    if df.empty:
        return []
    mask = df["active"].astype(bool) & df.apply(
        lambda row: "Manager" in parse_personnel_roles(row),
        axis=1,
    )
    return _personnel_display_names(df.loc[mask])


def service_manager_selectbox_label() -> str:
    """Dropdown title above the service manager field — the person's name when one manager."""
    names = service_manager_names()
    if len(names) == 1:
        return names[0]
    return "Manager"


def service_manager_action_label(action: str) -> str:
    return f"Service Manager {action}"


def service_manager_signoff_phrase() -> str:
    return "Service Manager"


def extract_claim_fields(claim_text):
    import re

    text = str(claim_text or "")
    text = re.sub(r"\s+", " ", text).strip()

    # Start at the real story, not acknowledgement/payment header
    start_patterns = [
    r"claim narrative[:\s]+customer states",
    r"customer states",
    r"verified the customer'?s concern",
    r"verified customer'?s concern",
    r"check engine light",
    r"performed scan",
    r"performed inspection"
]
    

    lower = text.lower()
    starts = []

    for pat in start_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            starts.append(m.end())

    if starts:
        text = text[min(starts):]

    # Remove payment / acknowledgement junk after narrative
    stop_patterns = [
        r"net amount",
        r"tax amount",
        r"total part",
        r"total labor",
        r"repair sub total",
        r"deductible amount",
        r"dealer ad",
        r"warranty contact center",
        r"thank you from"
    ]

    stops = []
    for pat in stop_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            stops.append(m.start())

    if stops:
        text = text[:min(stops)]

    # Remove remaining header junk
    junk_patterns = [
        r"date received:.*?claim narrative:",
        r"authorization number:.*?claim narrative:",
        r"date completed:.*?claim narrative:",
        r"owner's name:.*?claim narrative:",
        r"vehicle description:.*?claim narrative:",
        r"technician identification:.*?claim narrative:",
        r"line item number:.*?claim narrative:",
        r"part number description.*?claim narrative:",
    ]

    for pat in junk_patterns:
        text = re.sub(pat, "Claim Narrative:", text, flags=re.IGNORECASE)
        if text.lower().startswith("claim narrative:"):
            text = text[len("claim narrative:"):].strip()

    bad_start_phrases = [
        "date received:",
        "authorization number:",
        "date completed:",
        "owner's name:"
    ]

    if any(text.lower().startswith(x) for x in bad_start_phrases):
        return {
            "concern": "",
            "cause": "",
            "correction": "",
            "parts": "",
            "wam_reference": ""
        }
    if text.lower().startswith("claim narrative:"):
        text = text.replace("Claim Narrative:", "").replace("claim narrative:", "").strip()
        
    text = text.strip()

    if len(text.strip()) < 40:
        return {
            "concern": "",
            "cause": "",
            "correction": "",
            "labor_ops": "",
            "parts": "",
            "wam_reference": "",
            "story": "",
        }

    if not any(x in text.lower() for x in [
        "customer",
        "verified",
        "found",
        "performed",
        "replaced",
        "states",
    ]):
        return {
            "concern": "",
            "cause": "",
            "correction": "",
            "labor_ops": "",
            "parts": "",
            "wam_reference": "",
            "story": "",
        }

    def slice_after(labels, max_len=700):
        lower = text.lower()
        for label in labels:
            idx = lower.find(label.lower())
            if idx != -1:
                start = idx + len(label)
                return text[start:start + max_len].strip(" :-\n\r\t")
        return ""

    concern = slice_after([
        "customer states",
        "customer concern",
        "concern:",
        "condition:",
    ])
    if not concern:
        m = re.search(
            r"customer states\s+(.*?)(?=verified|found|accessed|removed|replaced|performed|cause:)",
            text,
            re.I,
        )
        if m:
            concern = m.group(1).strip()[:500]

    cause = slice_after(["cause:", "cause "])
    if not cause:
        m = re.search(
            r"(?:verified|found)\s+(.*?)(?=accessed|removed|replaced|performed|correction:|labor operations)",
            text,
            re.I,
        )
        if m:
            cause = m.group(1).strip()[:700]

    correction = slice_after(["correction:", "repair performed"])
    if not correction:
        for verb in ["accessed", "removed and replaced", "replaced", "performed", "repaired", "installed"]:
            idx = text.lower().find(verb)
            if idx != -1:
                correction = text[idx: idx + 1200].strip()
                break

    if not concern:
        concern = text[:500]

    labor_ops = extract_labor_ops_detail(text)
    parts = extract_parts_detail(text)

    wam_reference = extract_wam_reference(text)

    return {
        "concern": concern,
        "cause": cause,
        "correction": correction,
        "labor_ops": labor_ops,
        "parts": parts,
        "wam_reference": wam_reference,
        "story": text[:5000],
    }


def claim_source_text(*chunks):
    return " ".join(str(c or "") for c in chunks).strip()


LEARNED_CLAIM_NARRATIVE_TERMS = (
    "customer states",
    "customer concern",
    "verified the customer",
    "verified customer",
    "verified concern",
    "found that",
    "found the",
    "performed",
    "replaced",
    "repaired",
    "installed",
    "removed and replaced",
    "accessed and",
    "diagnosed",
    "per tsb",
    "per bulletin",
    "correction:",
    "cause:",
)

LEARNED_CLAIM_NON_WARRANTY_PATTERNS = (
    r"\boil change\b",
    r"\boil/filter\b",
    r"\blube\b",
    r"\bmaintenance only\b",
    r"\bscheduled maintenance\b",
    r"\brecall\b",
    r"\bnhtsa\b",
    r"\bcampaign\b",
    r"\bloaner vehicle\b",
    r"\bloaner car\b",
    r"\bcustomer rental\b",
    r"\brental agreement\b",
    r"\brental day\b",
    r"\bmessage level\b",
    r"\bmessage code\b",
    r"\bline message\b",
    r"\bsr7\b",
    r"\bclaim mc4\b",
    r"\bno repair performed\b",
    r"\bdeclined service\b",
    r"\bgoodwill only\b",
    r"\bdeductible amount\b",
    r"\bnet amount\b",
    r"\btotal labor\b",
    r"\btotal part\b",
)


LEARNED_CLAIM_MAINTENANCE_PATTERNS = (
    r"\boil change\b",
    r"\boil/filter\b",
    r"\blube\b",
    r"\bscheduled maintenance\b",
    r"\bmaintenance only\b",
    r"\btire rotation\b",
    r"\balignment only\b",
)

LEARNED_CLAIM_REPAIR_CONTEXT_TERMS = (
    "check engine",
    "mil ",
    " dtc",
    "no start",
    "hard start",
    "misfire",
    "leak",
    "noise",
    "vibration",
    "inop",
    "inoperative",
    "stall",
    "transmission concern",
    "engine concern",
    " tsb",
    "bulletin",
    "sensor",
    "module",
    "pump",
    "gasket",
    "harness",
    "switch",
    "calibration",
)


def _learned_claim_is_maintenance_only(text: str) -> bool:
    lower = str(text or "").lower()
    if not any(re.search(pat, lower, re.I) for pat in LEARNED_CLAIM_MAINTENANCE_PATTERNS):
        return False
    return not any(term in lower for term in LEARNED_CLAIM_REPAIR_CONTEXT_TERMS)


def _learned_claim_has_warranty_narrative(text: str) -> bool:
    lower = str(text or "").lower()
    return any(term in lower for term in LEARNED_CLAIM_NARRATIVE_TERMS)


def _learned_claim_is_non_warranty_only(text: str) -> bool:
    lower = str(text or "").lower()
    if not any(re.search(pat, lower, re.I) for pat in LEARNED_CLAIM_NON_WARRANTY_PATTERNS):
        return False
    return not _learned_claim_has_warranty_narrative(lower)


def learned_claim_narrative_text(record) -> str:
    if not isinstance(record, dict):
        return ""
    return claim_source_text(
        record.get("concern"),
        record.get("cause"),
        record.get("correction"),
        record.get("story"),
        record.get("content"),
    )


def learned_claim_has_visible_narrative(record) -> bool:
    concern = str(record.get("concern") or "").strip()
    correction = str(record.get("correction") or "").strip()
    return len(concern) >= 15 or len(correction) >= 15


def learned_claim_is_useful(record) -> bool:
    concern = str(record.get("concern") or "").strip()
    cause = str(record.get("cause") or "").strip()
    correction = str(record.get("correction") or "").strip()
    story = str(record.get("story") or record.get("content") or "").strip()

    if not learned_claim_has_visible_narrative(record):
        return False

    structured = claim_source_text(concern, cause, correction)
    full_text = claim_source_text(concern, cause, correction, story)
    lower = full_text.lower()

    if len(structured) < 20:
        return False

    compact = lower.replace(" ", "")
    if not compact or set(compact) <= {"_", "-", "."}:
        return False
    if "____" in lower or lower.count("_") > max(20, len(lower) // 3):
        return False

    junk_markers = (
        "acknowledgementservlet",
        "privacy policy",
        "authorization number:",
        "date received:",
        "technician identification:",
        "line item number:",
        "vehicle description:",
        "thank you from the warranty contact center",
    )
    if any(marker in lower for marker in junk_markers) and not _learned_claim_has_warranty_narrative(lower):
        return False

    if _learned_claim_is_non_warranty_only(lower):
        return False

    if _learned_claim_is_maintenance_only(lower):
        return False

    primary_narrative = concern if len(concern) >= 20 else correction
    if not _learned_claim_has_warranty_narrative(primary_narrative):
        return False

    if _learned_claim_is_non_warranty_only(primary_narrative):
        return False

    # Admin/loaner lines sometimes land in concern with no cause or correction.
    if len(correction) < 15 and len(cause) < 15:
        admin_only = (
            "message level",
            "message code",
            "loaner",
            "rental",
            "sr7",
            "line message",
            "condition-1",
        )
        concern_lower = concern.lower()
        if any(token in concern_lower for token in admin_only):
            return False

    return True


def filter_useful_learned_claims(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    mask = df.apply(lambda row: learned_claim_is_useful(row.to_dict()), axis=1)
    return df.loc[mask].copy()


def extract_labor_ops_detail(text):
    """Pull labor op numbers and hours from paid-claim narrative text."""
    text = str(text or "")
    if not text.strip():
        return ""

    pairs = []
    patterns = [
        r"labor\s+operation(?:\s+number)?(?:\s*&\s*time)?[^0-9]{0,60}(\d{7,8})[^0-9]{0,40}labor\s+time(?:\s+as)?\s*(\d*\.\d+|\d+)",
        r"operation\s+(\d{7,8})[^0-9]{0,40}time\s*[=:]\s*(\d*\.\d+|\d+)",
        r"(\d{7,8})\s*[-:]\s*(\d*\.\d+|\d+)\s*(?:hr|hour|h\b)",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            pairs.append((m.group(1), m.group(2)))

    formatted = []
    seen = set()
    for op, hrs in pairs:
        if op in seen:
            continue
        seen.add(op)
        hrs_clean = hrs.strip()
        if hrs_clean.startswith("."):
            hrs_clean = f"0{hrs_clean}"
        elif re.fullmatch(r"\d{1,2}", hrs_clean) and float(hrs_clean) <= 9:
            hrs_clean = f"0.{hrs_clean}"
        formatted.append(f"{op} ({hrs_clean}h)" if hrs_clean else op)

    if not formatted:
        for op in sorted(set(re.findall(r"\b\d{7,8}\b", text))):
            if op not in seen:
                seen.add(op)
                formatted.append(op)

    return ", ".join(formatted[:10])


def extract_parts_detail(text):
    """Pull part numbers and descriptions from paid-claim packet text."""
    text = str(text or "")
    if not text.strip():
        return ""

    found = []

    for section_pat in [
        r"part\s+number\s+description(.*?)(?:quantity|extended\s+price|net\s+amount|total\s+part|repair\s+sub)",
        r"parts?\s+replaced(.*?)(?:labor\s+operation|documented|total\s+part|net\s+amount)",
    ]:
        m = re.search(section_pat, text, re.I | re.S)
        if not m:
            continue
        for line in re.split(r"[\n\r]+", m.group(1)):
            line = re.sub(r"\s+", " ", line).strip()
            if len(line) < 6:
                continue
            low = line.lower()
            if any(x in low for x in ["quantity", "extended", "total", "____", "amount"]):
                continue
            pm = re.match(r"^([A-Z0-9]{2,6}\d{4,12}[A-Z]{0,4})\s+(.+)$", line.upper())
            if pm:
                found.append(f"{pm.group(1)} — {pm.group(2).title()[:50]}")
            elif re.search(r"\d", line) and re.search(r"[A-Z]{3,}", line.upper()):
                found.append(line[:90])

    for m in re.finditer(
        r"\b([A-Z0-9]{2,6}\d{4,10}[A-Z]{0,4})\s+([A-Z][A-Z0-9\s\-\/]{4,55})",
        text.upper(),
    ):
        pn = m.group(1)
        if re.fullmatch(r"0\d{7}", pn) or re.fullmatch(r"\d{7,8}", pn):
            continue
        desc = m.group(2).strip()
        if any(w in desc for w in ["OPERATION", "DOCUMENTED", "LABOR TIME", "CUSTOMER STATES", "VERIFIED"]):
            continue
        found.append(f"{pn} — {desc[:50].title()}")

    for m in re.finditer(
        r"(?:replaced|installed)\s+(?:the\s+)?([A-Z][A-Z0-9\s\-]{10,55}?)(?:\s+WITH|\s+AND\s+ALL|\s+AND\s+OTHER|\.|,|$)",
        text.upper(),
    ):
        phrase = re.sub(r"\s+", " ", m.group(1)).strip()
        if len(phrase) > 12 and "LABOR" not in phrase:
            found.append(phrase.title())

    deduped = []
    seen = set()
    for item in found:
        key = item[:35].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return "; ".join(deduped[:10])


def _clean_stored_field(value):
    val = str(value or "").strip()
    if not val:
        return ""
    low = val.lower()
    if any(
        phrase in low
        for phrase in (
            "review similar claim packet",
            "no labor operations parsed",
            "no parts list parsed",
            "no wam reference found",
        )
    ):
        return ""
    return val


def extract_wam_reference(text):
    """Find explicit WAM / bulletin references inside paid-claim text."""
    text = str(text or "")
    if not text.strip():
        return ""

    patterns = [
        r"\bWAM\s*[#:\-]?\s*([A-Z0-9][A-Z0-9\-/]{2,24})",
        r"\bWAM\s+REFERENCE\s*[#:\-]?\s*([A-Z0-9][A-Z0-9\-/]{2,24})",
        r"\b(WAM\d+[A-Z0-9\-/]*)\b",
        r"warranty\s+action\s+(?:memo|manual|bulletin)?\s*(?:number|no\.?|#)?\s*[:.]?\s*([A-Z0-9][A-Z0-9\-/]{2,24})",
        r"(?:policy|bulletin)\s*(?:number|no\.?|#)?\s*[:.]?\s*([A-Z0-9][A-Z0-9\-/]{3,24})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            ref = m.group(1).strip().upper()
            if ref and ref not in {"REFERENCE", "MANUAL", "MEMO"}:
                return ref if ref.startswith("WAM") else f"WAM {ref}"
    return ""


def lookup_wam_for_claim_text(text):
    """WAM from claim text plus keyword hits in uploaded WAM documents."""
    text = str(text or "")
    refs = []

    explicit = extract_wam_reference(text)
    if explicit:
        refs.append(explicit)

    if supabase is None:
        return " | ".join(refs)

    try:
        rows = supabase.table("wam_documents").select("*").execute().data or []
        text_low = text.lower()
        for row in rows:
            keywords = str(row.get("keywords", "")).lower()
            hits = [
                k.strip()
                for k in keywords.split(",")
                if k.strip() and k.strip() in text_low
            ]
            if hits:
                refs.append(
                    f"{row.get('section', 'WAM')} — {row.get('source_file', 'manual')} "
                    f"({', '.join(hits[:3])})"
                )
    except Exception:
        pass

    deduped = []
    seen = set()
    for ref in refs:
        key = ref.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(ref)
    return " | ".join(deduped[:3])


def _normalize_wam_ref(wam_ref: str) -> str:
    return re.sub(r"^WAM\s*", "", str(wam_ref or "").strip(), flags=re.I).upper()


def extract_warranty_coverage_code(text: str) -> str:
    """Pull Stellantis Warranty Coverage Code from servlet / inquiry PDFs."""
    match = re.search(r"Warranty Coverage\s*Code:\s*(\d+)", str(text or ""), re.I)
    if match:
        return f"Coverage Code {match.group(1).strip()}"
    return ""


def extract_declined_wam_reference(claim_text: str, *, document_text: str = "") -> str:
    """Find the WAM tied to a declined claim — usually near Message Code Information."""
    combined = "\n".join(part for part in (claim_text, document_text) if str(part or "").strip())
    if not combined.strip():
        return ""

    coverage = extract_warranty_coverage_code(combined)
    if coverage:
        return coverage

    flat = re.sub(r"\s+", " ", combined).strip()
    msg_match = re.search(r"message code information", flat, re.I)
    if msg_match:
        window = flat[max(0, msg_match.start() - 700) : msg_match.start() + 120]
        ref = extract_wam_reference(window)
        if ref:
            return ref

    return extract_wam_reference(combined)


@st.cache_data(ttl=600, show_spinner=False)
def _load_wam_document_rows() -> list[dict]:
    if supabase is None:
        return []
    try:
        return supabase.table("wam_documents").select("*").limit(1000).execute().data or []
    except Exception:
        return []


def summarize_wam_reference(wam_ref: str, *, max_len: int = 240) -> str:
    """Return a short plain-language summary from uploaded WAM documents."""
    ref_key = _normalize_wam_ref(wam_ref)
    if not ref_key:
        return ""

    best = ""
    for row in _load_wam_document_rows():
        section = str(row.get("section") or "")
        source = str(row.get("source_file") or "")
        content = re.sub(r"\s+", " ", str(row.get("content") or "")).strip()
        blob = f"{section} {source} {content}".upper()
        if ref_key not in blob and f"WAM{ref_key}" not in blob:
            continue

        idx = blob.find(ref_key)
        if idx < 0:
            idx = blob.find(f"WAM{ref_key}")
        if content and idx >= 0:
            snippet = content[max(0, idx - 50) : idx + max_len]
        elif content:
            snippet = content[:max_len]
        else:
            snippet = section or source

        snippet = snippet.strip()
        if len(snippet) > len(best):
            best = snippet

    if len(best) > max_len:
        best = best[: max_len - 3].rsplit(" ", 1)[0] + "..."
    return best


def _declined_wam_reference(row) -> str:
    if isinstance(row, dict):
        return str(row.get("wam_reference") or extract_wam_reference(row.get("story") or "") or "").strip()
    return str(getattr(row, "wam_reference", None) or "").strip()


def _declined_wam_summary(row) -> str:
    if isinstance(row, dict):
        stored = str(row.get("wam") or "").strip()
        if stored:
            return stored
        wam_ref = _declined_wam_reference(row)
    else:
        stored = str(getattr(row, "wam", None) or "").strip()
        if stored:
            return stored
        wam_ref = _declined_wam_reference(row)

    if not wam_ref:
        return ""
    return summarize_wam_reference(wam_ref)


def _declined_issue_summary(row) -> str:
    """Short issue text for tables — prefer WAM summary, else first message code."""
    wam_summary = _declined_wam_summary(row)
    if wam_summary:
        return wam_summary

    reason = _decline_reason_value(row)
    if not reason:
        return ""

    first = reason.split(" | ")[0].strip()
    first = re.sub(r"^\[[^\]]+\]\s*", "", first)
    first = re.sub(r"^[A-Z]{2,4}\d{1,2}\s*(?:L-\d+\s*)?—\s*", "", first)
    return first[:240]


def format_recommendation_list(value, empty_label):
    val = str(value or "").strip()
    if not val:
        return empty_label
    if ";" in val:
        items = [x.strip() for x in val.split(";") if x.strip()]
    elif "," in val and "(" in val:
        items = [x.strip() for x in val.split(",") if x.strip()]
    else:
        items = [val]
    if len(items) == 1:
        return items[0]
    return "\n".join(f"• {item}" for item in items)


def _parse_labor_op_entries(labor_ops: str) -> list[tuple[str, str]]:
    """Return (op_code, time_str) pairs from a stored labor_ops field."""
    raw = str(labor_ops or "").strip()
    if not raw:
        return []

    chunks = re.split(r"[;\n]+", raw)
    if len(chunks) == 1:
        chunks = re.split(r",(?=\s*\d{7,8})", raw)

    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        matched = re.match(
            r"(\d{7,8}[A-Z]{0,2})\s*(?:\(([\d.]+)\s*h?\))?",
            chunk,
            re.I,
        )
        if matched:
            op = matched.group(1).upper()
            time_str = (matched.group(2) or "").strip()
        else:
            fallback = re.search(r"\b(\d{7,8}[A-Z]{0,2})\b", chunk, re.I)
            if not fallback:
                continue
            op = fallback.group(1).upper()
            time_str = ""
        if op in seen:
            continue
        seen.add(op)
        entries.append((op, time_str))
    return entries


def _common_labor_time(times: list[str]) -> str:
    cleaned = [t.strip() for t in times if str(t or "").strip()]
    if not cleaned:
        return ""
    return max(set(cleaned), key=cleaned.count)


def _collect_paid_labor_op_suggestions(
    job: dict,
    *,
    limit_matches: int = 5,
    max_ops: int = 10,
) -> tuple[list[dict], list[dict]]:
    """Rank labor ops from similar paid claims for a review job."""
    similar = find_similar_paid_claims(job, limit=limit_matches)
    if not similar:
        return [], []

    op_stats: dict[str, dict] = {}
    for match in similar:
        labor = str(enrich_paid_claim_match(match).get("labor_ops") or "").strip()
        if not labor:
            continue
        score = int(match.get("score") or 0)
        ro_number = str(match.get("ro_number") or "").strip()
        for op_code, time_str in _parse_labor_op_entries(labor):
            key = op_code.upper()
            if key not in op_stats:
                op_stats[key] = {
                    "op_code": op_code,
                    "count": 0,
                    "best_score": 0,
                    "best_ro": "",
                    "times": [],
                }
            entry = op_stats[key]
            entry["count"] += 1
            if time_str:
                entry["times"].append(time_str)
            if score >= entry["best_score"]:
                entry["best_score"] = score
                entry["best_ro"] = ro_number

    ranked = sorted(
        op_stats.values(),
        key=lambda row: (-int(row["count"]), -int(row["best_score"]), row["op_code"]),
    )
    return ranked[:max_ops], similar


def _dc_note_info(message: str) -> None:
    st.markdown(f'<div class="dc-note-info">{message}</div>', unsafe_allow_html=True)


def _dc_note_warn(message: str) -> None:
    st.markdown(f'<div class="dc-note-warn">{message}</div>', unsafe_allow_html=True)


def _collapsible_section_label(title: str, applicable_hint: str | None = None) -> str:
    """Expander title; append a dot hint when the section has claim-relevant content."""
    if applicable_hint:
        return f"{title} · ● {applicable_hint}"
    return title


@contextmanager
def _collapsible_section(
    title: str,
    applicable_hint: str | None = None,
    *,
    marker_class: str = "review-collapsible",
    anchor_class: str = "",
    expanded: bool = False,
):
    """Collapsible review / Dealer Connect block with optional applicable-content marker."""
    label = _collapsible_section_label(title, applicable_hint)
    anchor_classes = ["dc-expander-anchor"]
    for token in str(marker_class or "").split():
        if token and token not in anchor_classes:
            anchor_classes.append(token)
    if anchor_class and anchor_class not in anchor_classes:
        anchor_classes.append(anchor_class)
    st.markdown(
        f'<div class="{" ".join(anchor_classes)}" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    with st.expander(label, expanded=expanded):
        yield


def _job_narrative_length(job: dict) -> int:
    return len(
        claim_source_text(
            job.get("concern"),
            job.get("cause"),
            job.get("correction"),
        ).strip()
    )


def _paid_labor_op_section_visible(jobs: list[dict]) -> bool:
    """Show labor-op helper only when narrative exists and paid-claim context may help."""
    eligible = [job for job in jobs if _job_narrative_length(job) >= 20]
    if not eligible:
        return False
    if _paid_labor_op_applicable_hint(jobs):
        return True
    for job in eligible:
        _suggestions, similar = _collect_paid_labor_op_suggestions(job)
        if similar:
            return True
    return False


def _paid_labor_op_applicable_hint(jobs: list[dict]) -> str | None:
    """Short hint for labor-op expander when paid-claim ops are available to copy."""
    total_ops = 0
    for job in jobs:
        narrative = claim_source_text(
            job.get("concern"),
            job.get("cause"),
            job.get("correction"),
        )
        if len(narrative.strip()) < 20:
            continue
        suggestions, _similar = _collect_paid_labor_op_suggestions(job)
        total_ops += len(suggestions)
    if not total_ops:
        return None
    noun = "ops" if total_ops != 1 else "op"
    return f"{total_ops} labor {noun} to copy"


def _dealer_connect_has_copy_sections(
    jobs: list[dict],
    *,
    ro_number: str,
    vin: str,
) -> bool:
    """True when at least one Dealer Connect collapsible may appear."""
    if _paid_labor_op_section_visible(jobs):
        return True
    if str(ro_number or "").strip() or str(vin or "").strip():
        return True
    for job in jobs:
        if (
            str(job.get("operation_code") or "").strip()
            or float(job.get("tech_flagged_time") or 0) > 0
            or float(job.get("time_allotted") or 0) > 0
            or float(job.get("claim_value") or 0) > 0
        ):
            return True
    return False


def _render_paid_labor_op_body(jobs: list[dict]) -> None:
    """Labor ops from similar paid claims — inner body for collapsible Dealer Connect panel."""
    eligible_jobs: list[dict] = []
    for job in jobs:
        narrative = claim_source_text(
            job.get("concern"),
            job.get("cause"),
            job.get("correction"),
        )
        if len(narrative.strip()) >= 20:
            eligible_jobs.append(job)

    st.caption(
        "Labor operations from similar **paid claims** in your library. "
        "Use **Copy** below each op to paste into Dealer Connect."
    )
    if not eligible_jobs:
        _dc_note_info(
            "Enter concern, cause, or correction above to suggest labor ops from paid claims."
        )
        return

    multi = len(eligible_jobs) > 1
    found_any = False
    for job in eligible_jobs:
        job_no = int(job.get("job_no") or 1)
        suggestions, similar = _collect_paid_labor_op_suggestions(job)

        if multi:
            st.markdown(f"**Job {job_no}**")

        if not similar:
            _dc_note_info(
                "No similar paid claims yet. Upload paid warranty PDFs on **Claim Learning** "
                "to build your labor op library."
            )
            continue

        if not suggestions:
            best = enrich_paid_claim_match(similar[0])
            _dc_note_warn(
                f"Similar paid claim **{best.get('ro_number', 'on file')}** "
                f"({similar[0].get('score', 0)}% match) has no labor ops parsed. "
                "Re-upload paid Dealer Connect PDFs that include labor operation lines."
            )
            continue

        found_any = True
        best = enrich_paid_claim_match(similar[0])
        st.caption(
            f"Best match: **{best.get('ro_number', 'Paid claim')}** · "
            f"**{similar[0].get('score', 0)}%** similar repair"
        )

        for idx, suggestion in enumerate(suggestions):
            op_code = str(suggestion["op_code"])
            time_hint = _common_labor_time(suggestion.get("times") or [])
            detail_parts: list[str] = []
            if time_hint:
                detail_parts.append(f"**{time_hint}h** paid time")
            count = int(suggestion.get("count") or 0)
            if count > 1:
                detail_parts.append(f"on **{count}** similar paid claims")
            elif suggestion.get("best_ro"):
                detail_parts.append(f"paid RO **{suggestion['best_ro']}**")

            st.markdown(
                f"**{op_code}**"
                + (f" · {' · '.join(detail_parts)}" if detail_parts else "")
            )
            safe_op = re.sub(r"[^a-zA-Z0-9_-]", "_", op_code)
            _render_field_copy_button(
                op_code,
                label=f"Labor op {op_code}",
                element_id=f"copy_labor_op_j{job_no}_{idx}_{safe_op}",
                show_value_box=True,
            )

        if len(similar) > 1:
            others = len(similar) - 1
            st.caption(f"+ {others} more similar paid claim(s) checked for labor ops.")

    if not found_any and len(eligible_jobs) == 1:
        pass


def _render_paid_labor_op_helper(jobs: list[dict], *, expand_all: bool = False) -> None:
    """Surface labor ops from similar paid claims for Dealer Connect entry."""
    if not _paid_labor_op_section_visible(jobs):
        return
    hint = _paid_labor_op_applicable_hint(jobs)
    with _collapsible_section(
        "Labor ops that paid — copy into Dealer Connect",
        hint,
        marker_class="dealer-connect-collapsible labor-ops-panel",
        anchor_class="dc-anchor-labor-ops",
        expanded=expand_all,
    ):
        _render_paid_labor_op_body(jobs)


def enrich_paid_claim_match(match):
    """Fill labor_ops, parts, and WAM from full claim text when DB fields are empty."""
    source = claim_source_text(
        match.get("story"),
        match.get("content"),
        match.get("correction"),
        match.get("cause"),
        match.get("concern"),
    )
    labor = _clean_stored_field(match.get("labor_ops"))
    parts = _clean_stored_field(match.get("parts"))
    wam = _clean_stored_field(
        match.get("wam_reference") or match.get("wam") or match.get("reference")
    )

    if not labor:
        labor = extract_labor_ops_detail(source)
    if not parts:
        parts = extract_parts_detail(source)
    if not wam:
        wam = lookup_wam_for_claim_text(source)

    out = dict(match)
    out["labor_ops"] = labor
    out["parts"] = parts
    out["wam_reference"] = wam
    return out


def _paid_claim_reference_text(match: dict) -> str:
    return claim_source_text(
        match.get("story"),
        match.get("content"),
        match.get("correction"),
        match.get("cause"),
        match.get("concern"),
        match.get("labor_ops"),
        match.get("parts"),
    )


def analyze_narrative_gaps(current_job: dict, paid_match: dict) -> dict:
    """Compare current job narrative to a matched paid claim and list documentation gaps."""
    concern = str(current_job.get("concern") or "").lower()
    cause = str(current_job.get("cause") or "").lower()
    correction = str(current_job.get("correction") or "").lower()
    current_all = f"{concern} {cause} {correction}".strip()

    paid = enrich_paid_claim_match(paid_match)
    paid_ref = _paid_claim_reference_text(paid).lower()
    paid_cause = str(paid.get("cause") or "").lower()
    paid_correction = str(paid.get("correction") or "").lower()
    paid_blob = paid_ref or f"{paid.get('concern', '')} {paid_cause} {paid_correction}".lower()

    gaps = []

    def _add_gap(category, message):
        gaps.append({"category": category, "message": message})

    def _paid_has_phrases(phrases, text):
        return [p for p in phrases if p in text]

    def _current_missing(paid_hits, current_text):
        return paid_hits and not any(p in current_text for p in paid_hits)

    cause_blob = f"{paid_cause} {paid_blob}"
    diagnostic = _paid_has_phrases(
        ["found", "tested", "verified", "diagnosed", "inspected", "scanned"],
        cause_blob,
    )
    if _current_missing(diagnostic, cause):
        _add_gap(
            "Cause",
            "Paid claims documented diagnostic steps (tested, scanned, verified, etc.) — "
            "your cause does not.",
        )

    evidence = _paid_has_phrases(
        ["dtc", "code", "inspection", "measured", "scan", "test", "voltage", "pressure", "leak test"],
        cause_blob,
    )
    if _current_missing(evidence, cause):
        _add_gap(
            "Cause",
            "Paid claims included supporting evidence (DTC, test result, measurement, etc.) — "
            "your cause does not.",
        )

    failure = _paid_has_phrases(
        [
            "failed", "failure", "inoperative", "not working", "leak", "leaking",
            "shorted", "open circuit", "broken", "faulty", "damaged", "internal failure",
        ],
        cause_blob,
    )
    if _current_missing(failure, cause):
        _add_gap(
            "Cause",
            "Paid claims clearly identified the failure — your cause may not state what failed.",
        )

    correction_blob = f"{paid_correction} {paid_blob}"
    repair = _paid_has_phrases(
        ["replaced", "repaired", "installed", "removed", "programmed", "performed", "flashed"],
        correction_blob,
    )
    if _current_missing(repair, correction):
        _add_gap(
            "Correction",
            "Paid claims clearly state the repair action — your correction may be missing it.",
        )

    justification = _paid_has_phrases(
        [
            "due to", "because", "failed", "failure", "leaking", "shorted", "open",
            "damaged", "removed and replaced", "reprogrammed", "updated",
        ],
        correction_blob,
    )
    if _current_missing(justification, correction):
        _add_gap(
            "Correction",
            "Paid claims tied the repair to the failure — your correction may need a 'due to / because' link.",
        )

    verification = _paid_has_phrases(
        [
            "verified", "operates", "operating", "designed", "working",
            "proper operation", "test drove", "road test", "no further issues",
            "operating as designed", "as designed",
        ],
        correction_blob,
    )
    if verification and not _correction_verifies_proper_operation(correction):
        _add_gap(
            "Correction",
            "Paid claims verified proper operation or test drove — your correction does not.",
        )

    paid_dtcs = set(re.findall(r"\b[A-Z][0-9A-Z]{4}(?:-[0-9A-Z]{2})?\b", paid_blob.upper()))
    current_dtcs = set(re.findall(r"\b[A-Z][0-9A-Z]{4}(?:-[0-9A-Z]{2})?\b", current_all.upper()))
    missing_dtcs = sorted(paid_dtcs - current_dtcs)
    if missing_dtcs:
        _add_gap(
            "Cause",
            f"Paid claim cited DTC(s): {', '.join(missing_dtcs[:4])} — include applicable codes in your cause.",
        )

    paid_lops = set(re.findall(r"\b\d{7,8}\b", paid_blob))
    current_lops = set(re.findall(r"\b\d{7,8}\b", current_all))
    missing_lops = sorted(paid_lops - current_lops)
    if missing_lops:
        _add_gap(
            "Labor",
            f"Paid claim used labor op(s): {', '.join(missing_lops[:4])} — confirm your narrative/claim matches.",
        )

    wam_ref = str(paid.get("wam_reference") or "").strip()
    if wam_ref and wam_ref.lower() not in current_all:
        _add_gap("WAM", f"Paid claim referenced **{wam_ref}** — verify if WAM applies to this job.")

    parts_text = str(paid.get("parts") or "")
    if parts_text.strip():
        part_tokens = re.findall(r"\b[A-Z0-9]{2,}(?:[-\s][A-Z0-9]{2,})+\b", parts_text.upper())
        part_tokens += re.findall(r"\b\d{5,}\w*\b", parts_text)
        missing_parts = []
        for token in part_tokens:
            token_clean = token.strip().lower().replace(" ", "")
            if len(token_clean) >= 5 and token_clean not in current_all.replace(" ", ""):
                missing_parts.append(token)
            if len(missing_parts) >= 3:
                break
        if missing_parts:
            _add_gap(
                "Parts",
                f"Paid claim listed part(s) not mentioned in your narrative: {', '.join(missing_parts[:3])}.",
            )

    for component in paid.get("match_reasons") or []:
        if component and component not in current_all:
            _add_gap(
                "Component",
                f"Matched paid claim documented **{component}** — confirm your narrative mentions it.",
            )

    strengths = []
    if not gaps:
        strengths.append("Your narrative matches key documentation patterns from the paid claim.")
    elif len(gaps) <= 2:
        strengths.append("Core component match is good — tighten the remaining narrative gaps above.")

    return {
        "gaps": gaps,
        "strengths": strengths,
        "gap_count": len(gaps),
    }


def _narrative_gap_coach_hint(current_job: dict, similar_claims: list) -> str | None:
    """Short expander hint when gap coach has claim-relevant output."""
    text_len = len(
        f"{current_job.get('concern', '')} {current_job.get('cause', '')} {current_job.get('correction', '')}".strip()
    )
    if text_len < 20 or not similar_claims:
        return None
    best_match = enrich_paid_claim_match(similar_claims[0])
    analysis = analyze_narrative_gaps(current_job, best_match)
    if analysis["gap_count"] > 0:
        noun = "gaps" if analysis["gap_count"] != 1 else "gap"
        return f"{analysis['gap_count']} narrative {noun} vs paid claim"
    return f"{best_match.get('score', 0)}% paid claim match"


def _render_narrative_gap_coach_body(current_job: dict, similar_claims: list, job_no: int) -> None:
    st.caption(
        "Compares this job's concern, cause, and correction to similar **paid claims** "
        "in your Claim Learning library."
    )

    text_len = len(
        f"{current_job.get('concern', '')} {current_job.get('cause', '')} {current_job.get('correction', '')}".strip()
    )
    if text_len < 20:
        st.info("Enter more narrative text to activate the gap coach.")
        return

    if not similar_claims:
        st.info(
            "No similar paid claims found yet. Upload paid warranty claims on the **Claim Learning** tab "
            "to build your library."
        )
        return

    best_match = enrich_paid_claim_match(similar_claims[0])
    analysis = analyze_narrative_gaps(current_job, best_match)

    st.success(
        f"Similar paid claim match: **{best_match.get('score', 0)}%** · "
        f"{best_match.get('ro_number', 'Paid claim')}"
    )

    if analysis["gaps"]:
        st.warning(
            f"**{analysis['gap_count']} narrative gap(s) vs paid claim** — consider addressing before submit:"
        )
        for gap in analysis["gaps"][:10]:
            st.markdown(f"- **{gap['category']}:** {gap['message']}")
    else:
        st.success("No major narrative gaps detected vs the matched paid claim.")

    for note in analysis.get("strengths") or []:
        st.caption(note)

    reference = (
        best_match.get("correction", "")
        or best_match.get("cause", "")
        or best_match.get("concern", "")
        or str(best_match.get("story", ""))[:600]
    )
    labor_list = format_recommendation_list(
        best_match.get("labor_ops"),
        "No labor operations found in this paid claim.",
    )
    parts_list = format_recommendation_list(
        best_match.get("parts"),
        "No parts list found in this paid claim.",
    )
    wam_display = (best_match.get("wam_reference") or "").strip() or "No WAM reference in paid claim."

    with st.expander("Paid claim reference (what passed)", expanded=analysis["gap_count"] > 0):
        st.markdown("**Suggested narrative source**")
        st.write(reference)
        st.markdown("**Labor ops**")
        st.markdown(labor_list)
        st.markdown("**Parts**")
        st.markdown(parts_list)
        st.markdown(f"**WAM reference:** {wam_display}")

    if len(similar_claims) > 1:
        with st.expander(f"Other similar paid claims ({len(similar_claims) - 1} more)"):
            for raw_match in similar_claims[1:]:
                match = enrich_paid_claim_match(raw_match)
                st.markdown(f"**{match.get('score', 0)}%** · {match.get('ro_number', '')}")
                if match.get("match_reasons"):
                    st.caption(f"Components: {', '.join(match['match_reasons'][:5])}")
                preview = (
                    match.get("correction")
                    or match.get("cause")
                    or match.get("concern")
                    or str(match.get("story", ""))[:300]
                )
                st.write(preview)
                st.markdown("---")


def render_narrative_gap_coach(current_job: dict, similar_claims: list, job_no: int):
    text_len = len(
        f"{current_job.get('concern', '')} {current_job.get('cause', '')} {current_job.get('correction', '')}".strip()
    )
    if text_len < 20 or not similar_claims:
        return
    hint = _narrative_gap_coach_hint(current_job, similar_claims)
    with _collapsible_section(
        "Narrative Gap Coach",
        hint,
        marker_class="review-collapsible gap-coach-panel",
        anchor_class="dc-anchor-gap-coach",
    ):
        _render_narrative_gap_coach_body(current_job, similar_claims, job_no)


def _declined_claim_hint(current_job: dict, similar_declined: list) -> str | None:
    text_len = len(
        f"{current_job.get('concern', '')} {current_job.get('cause', '')} {current_job.get('correction', '')}".strip()
    )
    if text_len < 20 or not similar_declined:
        return None
    best = similar_declined[0]
    return f"{best.get('score', 0)}% declined match"


def _render_declined_claim_alert_body(current_job: dict, similar_declined: list) -> None:
    st.caption(
        "This job looks similar to a declined claim from Dealer Connect — review before submit."
    )

    best = similar_declined[0]
    reason = _decline_reason_value(best).strip()
    wam_ref = _declined_wam_reference(best)
    wam_summary = _declined_wam_summary(best)
    issue_bits = []
    if wam_ref:
        issue_bits.append(f"**WAM {wam_ref.lstrip('WAM ').strip()}**")
    if wam_summary:
        issue_bits.append(wam_summary)
    elif reason:
        issue_bits.append(_declined_issue_summary(best))

    st.warning(
        f"**{best.get('score', 0)}% match** to a declined claim"
        + (f" — {' · '.join(issue_bits)}" if issue_bits else ". Review the reference below before submit.")
    )

    with st.expander("Declined claim reference", expanded=True):
        if wam_ref:
            st.markdown(f"**WAM reference:** {wam_ref}")
        if wam_summary:
            st.markdown(f"**WAM issue:** {wam_summary}")
        elif wam_ref:
            st.caption(
                "Upload this WAM on the **WAM** tab to see a fuller summary here. "
                "Message codes from the declined claim are shown below."
            )
        if reason:
            st.markdown(f"**Message codes:** {reason}")
        st.markdown("**Concern / cause / correction from declined claim**")
        st.write(
            claim_source_text(
                best.get("concern"),
                best.get("cause"),
                best.get("correction"),
                best.get("story"),
            )[:2500]
        )
        if best.get("labor_ops"):
            st.caption(f"Labor ops: {best.get('labor_ops')}")

    if len(similar_declined) > 1:
        with st.expander(f"Other similar declined claims ({len(similar_declined) - 1} more)"):
            for match in similar_declined[1:]:
                label = (_decline_reason_value(match) or match.get("ro_number") or "Declined claim").strip()
                st.markdown(f"**{match.get('score', 0)}%** · {label[:120]}")


def render_declined_claim_alert(current_job: dict, similar_declined: list) -> None:
    hint = _declined_claim_hint(current_job, similar_declined)
    if not hint:
        return
    with _collapsible_section(
        "Declined Claim Alert",
        hint,
        marker_class="review-collapsible declined-alert-panel",
        anchor_class="dc-anchor-declined-alert",
    ):
        _render_declined_claim_alert_body(current_job, similar_declined)


def _sync_declined_upload_metadata(file_name: str, claims: list[str]) -> int:
    """Refresh decline/WAM fields on declined rows from the same upload file."""
    if supabase is None or not file_name or not claims:
        return 0

    updated = 0

    def _apply_patch(row_id: str, claim: str) -> bool:
        nonlocal updated
        claim_num = extract_claim_ro_number(claim)
        decline_reason = extract_decline_reason(claim)
        wam_ref = extract_declined_wam_reference(claim)
        wam_summary = summarize_wam_reference(wam_ref) if wam_ref else ""
        patch: dict = {}
        if decline_reason:
            patch["reference"] = decline_reason
            patch["content"] = decline_reason
        if wam_ref:
            patch["wam_reference"] = wam_ref
        if wam_summary:
            patch["wam"] = wam_summary
        if claim_num:
            patch["vin"] = claim_num
        if not patch:
            return False
        try:
            supabase.table("claims").update(patch).eq("id", row_id).execute()
            updated += 1
            return True
        except Exception:
            return False

    try:
        existing_rows = (
            supabase.table("claims")
            .select("id, vin, reference, wam_reference, story")
            .eq("ro_number", file_name)
            .eq("claim_status", "declined")
            .execute()
            .data
            or []
        )
    except Exception:
        return 0

    by_vin: dict[str, dict] = {}
    stale_rows: list[dict] = []
    for row in existing_rows:
        vin = str(row.get("vin") or "").strip()
        if vin:
            by_vin[vin] = row
        elif not str(row.get("reference") or "").strip():
            stale_rows.append(row)

    matched_ids: set[str] = set()
    for claim in claims:
        claim_num = extract_claim_ro_number(claim)
        if claim_num and claim_num in by_vin:
            row = by_vin[claim_num]
            if _apply_patch(str(row["id"]), claim):
                matched_ids.add(str(row["id"]))

    remaining_claims = [c for c in claims if extract_claim_ro_number(c) not in by_vin]
    remaining_stale = [r for r in stale_rows if str(r["id"]) not in matched_ids]
    if remaining_stale and remaining_claims:
        remaining_stale.sort(key=lambda r: str(r.get("id")))
        remaining_claims.sort(key=lambda c: extract_claim_ro_number(c) or c[:40])
        for row, claim in zip(remaining_stale, remaining_claims):
            _apply_patch(str(row["id"]), claim)

    return updated


def clear_all_declined_claims() -> dict:
    """Remove every declined row from the claims library."""
    stats = {"removed": 0, "errors": 0, "method": ""}
    if supabase is None:
        return stats

    try:
        resp = supabase.rpc("clear_declined_claims", {}).execute()
        if resp.data is not None:
            stats["removed"] = int(resp.data)
            stats["method"] = "rpc"
            return stats
    except Exception:
        pass

    try:
        rows = (
            supabase.table("claims")
            .select("id")
            .eq("claim_status", "declined")
            .execute()
            .data
            or []
        )
        for row in rows:
            try:
                deleted = supabase.table("claims").delete().eq("id", row["id"]).execute().data
                if deleted:
                    stats["removed"] += len(deleted)
            except Exception:
                stats["errors"] += 1
        stats["method"] = "row_delete"
    except Exception:
        stats["errors"] += 1

    return stats


def save_learned_claims(file_name, claims, *, outcome: str = "paid", document_text: str = "") -> dict:
    stats = {"parsed": len(claims), "saved": 0, "duplicate": 0, "skipped": 0, "errors": 0, "updated": 0}
    outcome = str(outcome or "paid").strip().lower()
    if outcome not in ("paid", "declined"):
        outcome = "paid"
    doc_meta = (
        _document_decline_metadata(document_text)
        if outcome == "declined" and str(document_text or "").strip()
        else {"decline_reason": "", "wam_reference": "", "wam_summary": ""}
    )
    required_terms = [
        "customer states",
        "verified",
        "found",
        "performed",
        "replaced",
        "customer",
        "states",
    ]

    for idx, claim in enumerate(claims, start=1):
        fields = extract_claim_fields(claim)
        if not fields:
            stats["skipped"] += 1
            continue

        claim_body = (
            fields.get("story")
            or claim_source_text(
                fields.get("concern"),
                fields.get("cause"),
                fields.get("correction"),
            )
            or claim
        ).strip().lower()

        decline_reason = ""
        wam_ref = fields.get("wam_reference", "")
        wam_summary = ""
        if outcome == "declined":
            decline_reason = extract_decline_reason(claim)
            if not decline_reason and len(claims) == 1:
                decline_reason = doc_meta.get("decline_reason", "")
            wam_ref = (
                extract_declined_wam_reference(claim)
                or extract_warranty_coverage_code(claim)
                or wam_ref
            )
            if not wam_ref and len(claims) == 1:
                wam_ref = doc_meta.get("wam_reference", "") or wam_ref
            wam_summary = summarize_wam_reference(wam_ref) if wam_ref else ""
            if not wam_summary and len(claims) == 1:
                wam_summary = doc_meta.get("wam_summary", "")
        claim_ro = extract_claim_ro_number(claim)

        if (
            len(claim_body) < 40
            or set(claim_body) <= {"_"}
            or "____" in claim_body
            or not any(term in claim_body for term in required_terms)
        ):
            if not (outcome == "declined" and decline_reason and len(claim_body) >= 20):
                stats["skipped"] += 1
                continue

        data = {
            "ro_number": file_name,
            "vin": claim_ro if outcome == "declined" and claim_ro else "",
            "concern": fields.get("concern", ""),
            "cause": fields.get("cause", ""),
            "correction": fields.get("correction", ""),
            "tech": "",
            "advisor": "",
            "story": fields.get("story", "") or claim_body[:5000],
            "labor_ops": fields.get("labor_ops", ""),
            "parts": fields.get("parts", ""),
            "wam_reference": wam_ref,
            "wam": wam_summary if outcome == "declined" else "",
            "content": decline_reason if outcome == "declined" and decline_reason else "",
            "claim_status": outcome,
            "reference": decline_reason if outcome == "declined" else "",
        }

        if not learned_claim_is_useful(data):
            if not (outcome == "declined" and (decline_reason or doc_meta.get("decline_reason"))):
                stats["skipped"] += 1
                continue

        try:
            existing_query = (
                supabase.table("claims")
                .select("id, reference, wam_reference")
                .eq("ro_number", file_name)
                .eq("claim_status", outcome)
            )
            if outcome == "declined" and data.get("vin"):
                existing_query = existing_query.eq("vin", data["vin"])
            else:
                existing_query = existing_query.eq("story", data["story"])
            existing = existing_query.execute()
            if existing.data:
                stats["duplicate"] += 1
                if outcome == "declined" and decline_reason:
                    row = existing.data[0]
                    patch = {}
                    if not str(row.get("reference") or "").strip():
                        patch["reference"] = decline_reason
                        patch["content"] = decline_reason
                    if wam_ref and not str(row.get("wam_reference") or "").strip():
                        patch["wam_reference"] = wam_ref
                        patch["wam"] = wam_summary
                    if patch:
                        supabase.table("claims").update(patch).eq("id", row["id"]).execute()
                        stats["updated"] += 1
                continue
            supabase.table("claims").insert(data).execute()
            stats["saved"] += 1
        except Exception as e:
            stats["errors"] += 1
            st.warning(f"Could not save learned claim {idx}: {e}")

    if outcome == "declined":
        stats["updated"] += _sync_declined_upload_metadata(file_name, claims)
        if len(claims) == 1:
            stats["updated"] += _backfill_declined_file_metadata(file_name, document_text, doc_meta)

    return stats


def extract_message_code_reasons(claim_text: str) -> list[str]:
    """Parse Dealer Connect *Message Code Information* tables from PDF text."""
    raw = str(claim_text or "")
    if not raw.strip():
        return []

    flat = re.sub(r"\s+", " ", raw).strip()
    match = re.search(r"message code information", flat, re.I)
    if not match:
        match = re.search(r"dealer correctable message codes", flat, re.I)
    if not match:
        return _extract_message_codes_loose(flat)

    section = flat[match.start():]
    stop = re.search(
        r"\b(claim narrative|date received|authorization number|vehicle description|"
        r"owner'?s name|technician identification|net amount|repair sub total)\b",
        section[40:],
        re.I,
    )
    if stop:
        section = section[: 40 + stop.start()]

    categories = [
        ("Dealer Correctable", r"dealer correctable message codes"),
        ("Authorization Required", r"authorization required message codes"),
        ("Informational", r"informational message codes"),
    ]

    reasons: list[str] = []
    seen: set[str] = set()

    def _add_reason(code: str, description: str, line: str = "", category: str = "") -> None:
        code = code.strip().upper()
        description = re.sub(r"\s+", " ", description or "").strip(" .:-_")
        description = re.sub(r"\s+Condition-\d+\s*$", "", description, flags=re.I)
        description = re.sub(
            r"\s+(?:Dealer Correctable|Authorization Required|Informational Message).*$",
            "",
            description,
            flags=re.I,
        )
        if len(code) < 2 or len(description) < 8:
            return
        if description.lower() in {
            "message code description",
            "message level line message code",
            "message code",
        }:
            return
        prefix = f"[{category}] " if category else ""
        line_part = f"{line} " if line else ""
        entry = f"{prefix}{code} {line_part}— {description}".strip()
        key = f"{code}|{line}|{description.lower()}"
        if key in seen:
            return
        seen.add(key)
        reasons.append(entry)

    for category_label, category_pat in categories:
        cat_match = re.search(category_pat, section, re.I)
        if not cat_match:
            continue
        next_starts = [
            m.start()
            for _, pat in categories
            if pat != category_pat
            for m in [re.search(pat, section[cat_match.end() :], re.I)]
            if m
        ]
        cat_end = cat_match.end() + min(next_starts) if next_starts else len(section)
        cat_section = section[cat_match.end() : cat_end]
        cat_before = len(reasons)

        row_pattern = re.compile(
            r"Condition-\d+\s+(?:L-(\d+)\s*)?([A-Z]{2,4}\d{0,2})\s+(.{10,240}?)"
            r"(?=\s*Condition-\d+|\s*Claim\s+[A-Z0-9]{2,4}\s+|\s*(?:Dealer Correctable|Authorization Required|Informational Message)|\s*$)",
            re.I,
        )
        for row in row_pattern.finditer(cat_section):
            _add_reason(row.group(2), row.group(3), line=f"L-{row.group(1)}" if row.group(1) else "", category=category_label)

        claim_row_pattern = re.compile(
            r"Claim\s+([A-Z0-9]{2,4})\s+(.{10,240}?)"
            r"(?=\s*Claim\s+[A-Z0-9]{2,4}\s+|\s*Condition-\d+|\s*(?:Dealer Correctable|Authorization Required|Informational Message)|\s*$)",
            re.I,
        )
        for row in claim_row_pattern.finditer(cat_section):
            _add_reason(row.group(1), row.group(2), category=category_label)

        if len(reasons) == cat_before:
            loose_pattern = re.compile(
                r"(?:(?:L-(\d+))\s*)?([A-Z]{2,4}\d{0,2})\s+(.{10,240}?)"
                r"(?=\s*(?:(?:L-\d+\s*)?[A-Z]{2,4}\d{0,2}\s+)|\s*(?:Dealer Correctable|Authorization Required|Informational Message)|\s*$)",
                re.I,
            )
            for row in loose_pattern.finditer(cat_section):
                _add_reason(row.group(2), row.group(3), line=f"L-{row.group(1)}" if row.group(1) else "", category=category_label)

    if reasons:
        return reasons

    # Last resort: any message-code-shaped token followed by descriptive text.
    fallback = re.compile(
        r"\b([A-Z]{2,4}\d{0,2})\s+(.{12,220}?)(?=\s+[A-Z]{2,4}\d{0,2}\s+|\s*$)",
        re.I,
    )
    for row in fallback.finditer(section):
        _add_reason(row.group(1), row.group(2))

    return reasons


def _extract_message_codes_loose(flat: str) -> list[str]:
    """Find Stellantis message codes when PDF text lacks the full section header."""
    if not flat.strip():
        return []

    reasons: list[str] = []
    seen: set[str] = set()

    def _add(code: str, desc: str) -> None:
        code = code.strip().upper()
        desc = re.sub(r"\s+", " ", desc or "").strip(" .:-_")
        desc = re.sub(r"\s+Condition-\d+\s*$", "", desc, flags=re.I)
        if len(code) < 3 or len(desc) < 12:
            return
        junk_desc = {
            "message code description",
            "message level line message code",
            "dealer correctable message codes",
            "authorization required message codes",
        }
        if desc.lower() in junk_desc:
            return
        key = f"{code}|{desc.lower()}"
        if key in seen:
            return
        seen.add(key)
        reasons.append(f"{code} — {desc}")

    row_pattern = re.compile(
        r"Condition-\d+\s+(?:L-(\d+)\s*)?([A-Z]{2,4}\d{0,2})\s+(.{12,220}?)"
        r"(?=\s*Condition-\d+|\s*Claim\s+[A-Z0-9]{2,4}\s+|\s*(?:Dealer Correctable|Authorization Required|Informational Message)|\s*$)",
        re.I,
    )
    for row in row_pattern.finditer(flat):
        line = f"L-{row.group(1)}" if row.group(1) else ""
        desc = row.group(3)
        if line:
            desc = f"{line}: {desc}"
        _add(row.group(2), desc)

    claim_pattern = re.compile(
        r"Claim\s+([A-Z0-9]{2,4})\s+(.{12,220}?)"
        r"(?=\s*Claim\s+[A-Z0-9]{2,4}\s+|\s*Condition-\d+|\s*(?:Dealer Correctable|Authorization Required|Informational Message)|\s*$)",
        re.I,
    )
    for row in claim_pattern.finditer(flat):
        _add(row.group(1), row.group(2))

    if not reasons:
        fallback = re.compile(
            r"\b([A-Z]{2,4}\d{0,2})\s+((?:Only |LOP |Missing |Incomplete |Invalid |Contract |Claim ).{10,220}?)(?=\s+[A-Z]{2,4}\d{0,2}\s+|\s*$)",
            re.I,
        )
        for row in fallback.finditer(flat):
            _add(row.group(1), row.group(2))

    return reasons


def _document_decline_metadata(document_text: str) -> dict:
    doc = str(document_text or "").strip()
    if not doc:
        return {"decline_reason": "", "wam_reference": "", "wam_summary": ""}
    decline_reason = extract_decline_reason("", document_text=doc)
    wam_ref = extract_declined_wam_reference("", document_text=doc)
    wam_summary = summarize_wam_reference(wam_ref) if wam_ref else ""
    return {
        "decline_reason": decline_reason,
        "wam_reference": wam_ref,
        "wam_summary": wam_summary,
    }


def _backfill_declined_file_metadata(file_name: str, document_text: str, doc_meta: dict | None = None) -> int:
    """Apply PDF-level decline/WAM data to every declined row from the same upload file."""
    if supabase is None or not file_name:
        return 0
    meta = doc_meta or _document_decline_metadata(document_text)
    decline_reason = str(meta.get("decline_reason") or "").strip()
    wam_ref = str(meta.get("wam_reference") or "").strip()
    wam_summary = str(meta.get("wam_summary") or "").strip()
    if not decline_reason and not wam_ref:
        return 0

    try:
        rows = (
            supabase.table("claims")
            .select("id, reference, wam_reference, wam")
            .eq("ro_number", file_name)
            .eq("claim_status", "declined")
            .execute()
            .data
            or []
        )
    except Exception:
        return 0

    updated = 0
    for row in rows:
        patch = {}
        if decline_reason and not str(row.get("reference") or "").strip():
            patch["reference"] = decline_reason
            patch["content"] = decline_reason
        if wam_ref and not str(row.get("wam_reference") or "").strip():
            patch["wam_reference"] = wam_ref
        if wam_summary and not str(row.get("wam") or "").strip():
            patch["wam"] = wam_summary
        if not patch:
            continue
        try:
            supabase.table("claims").update(patch).eq("id", row["id"]).execute()
            updated += 1
        except Exception:
            pass
    return updated


def extract_decline_reason(claim_text: str, *, document_text: str = "") -> str:
    """Pull OEM decline/return reason text from a Dealer Connect claim PDF segment."""
    combined = "\n".join(part for part in (claim_text, document_text) if str(part or "").strip())
    message_codes = extract_message_code_reasons(combined)
    if message_codes:
        return " | ".join(message_codes)[:2000]

    text = re.sub(r"\s+", " ", str(claim_text or "")).strip()
    if not text:
        return ""

    patterns = [
        r"(?:decline|declined|return|returned|reject(?:ed|ion)?)\s+reason[:\s-]+(.{8,400}?)(?:\s+claim narrative|\s+date received|\s+authorization|\s+line item|$)",
        r"reason\s+for\s+(?:decline|return|reject(?:ion)?)[:\s-]+(.{8,400}?)(?:\s+claim narrative|\s+date received|$)",
        r"claim\s+(?:was\s+)?(?:declined|returned|rejected)[:\s-]+(.{8,300}?)(?:\s+claim narrative|\s+date received|$)",
        r"comments[:\s-]+(.{8,400}?)(?:\s+claim narrative|\s+date received|$)",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.I)
        if not match:
            continue
        reason = match.group(1).strip(" .:-_")
        if len(reason) >= 8 and reason.lower() not in {"n/a", "none", "see below"}:
            return reason[:500]
    return ""


def _claim_status_value(row) -> str:
    if isinstance(row, dict):
        raw = row.get("claim_status") or row.get("claim_outcome") or "paid"
    else:
        raw = getattr(row, "claim_status", None) or getattr(row, "claim_outcome", None) or "paid"
    status = str(raw or "paid").strip().lower()
    return status if status in ("paid", "declined") else "paid"


def _decline_reason_value(row) -> str:
    if isinstance(row, dict):
        reason = str(row.get("decline_reason") or "").strip()
        if not reason and _claim_status_value(row) == "declined":
            reason = str(row.get("reference") or "").strip()
        if not reason and _claim_status_value(row) == "declined":
            reason = str(row.get("content") or "").strip()
        return reason
    reason = str(getattr(row, "decline_reason", None) or "").strip()
    if not reason and _claim_status_value(row) == "declined":
        reason = str(getattr(row, "reference", None) or "").strip()
    if not reason and _claim_status_value(row) == "declined":
        reason = str(getattr(row, "content", None) or "").strip()
    return reason


def _claims_for_outcome(df: pd.DataFrame, outcome: str) -> pd.DataFrame:
    if df.empty:
        return df
    outcome = str(outcome or "paid").strip().lower()
    if "claim_status" not in df.columns and "claim_outcome" not in df.columns:
        return df if outcome == "paid" else df.iloc[0:0].copy()
    status_col = "claim_status" if "claim_status" in df.columns else "claim_outcome"
    normalized = df[status_col].fillna("paid").astype(str).str.lower()
    if outcome == "paid":
        return df[normalized.isin(["paid", ""]) | normalized.isna()].copy()
    return df[normalized == outcome].copy()


# =========================
# STYLE
# =========================
STREAMLIT_CHROME_HIDE_CSS = """
[data-testid="stHeaderActionElements"],
[data-testid="stToolbar"],
[data-testid="stToolbarActions"],
.stAppDeployButton,
.stDeployButton,
[data-testid="stBottomBlock"],
footer {
    display: none !important;
}
"""


def _owner_emails() -> set[str]:
    raw = os.getenv("RO_SHIELD_OWNER_EMAIL", "").strip()
    if not raw:
        try:
            raw = str(st.secrets.get("RO_SHIELD_OWNER_EMAIL", "")).strip()
        except Exception:
            raw = ""
    return {normalize_email(part) for part in raw.replace(";", ",").split(",") if part.strip()}


def streamlit_cloud_chrome_allowed() -> bool:
    """Streamlit Share / Manage app chrome only for RO_SHIELD_OWNER_EMAIL login(s)."""
    owners = _owner_emails()
    if not owners:
        return True
    if not is_authenticated():
        return False
    email = normalize_email(auth_user_email())
    return bool(email and email in owners)


def configure_streamlit_toolbar() -> None:
    """Developer toolbar for app owner; viewer mode for dealership users."""
    try:
        if streamlit_cloud_chrome_allowed():
            st.set_option("client.toolbarMode", "developer")
        else:
            st.set_option("client.toolbarMode", "viewer")
    except Exception:
        pass


def _inject_streamlit_cloud_chrome_restore() -> None:
    """Keep Share / Manage app visible for the app owner."""
    embed_script(
        """
        <script>
        (function () {
          function chromeRoots(doc) {
            return [
              doc.querySelector('[data-testid="stHeader"]'),
              doc.querySelector('[data-testid="stBottomBlock"]'),
              doc.querySelector("footer")
            ].filter(Boolean);
          }
          function restoreChrome(doc) {
            if (!doc || !doc.body) return;
            var selectors = [
              '[data-testid="stHeaderActionElements"]',
              '[data-testid="stToolbar"]',
              '[data-testid="stToolbarActions"]',
              '[data-testid="stBottomBlock"]',
              '.stAppDeployButton',
              '.stDeployButton',
              'footer'
            ];
            selectors.forEach(function (sel) {
              doc.querySelectorAll(sel).forEach(function (el) {
                el.style.removeProperty("display");
                el.style.removeProperty("visibility");
                el.style.removeProperty("opacity");
              });
            });
            chromeRoots(doc).forEach(function (root) {
              root.querySelectorAll("a, button, span, p, div, label").forEach(function (el) {
                var text = (el.textContent || "").trim();
                if (text === "Share" || text === "Manage app" || text === "Manage App") {
                  var target = el.closest("a, button, [role='button']") || el;
                  target.style.removeProperty("display");
                  target.style.removeProperty("visibility");
                }
              });
            });
          }
          function sweep() {
            try { restoreChrome(document); } catch (e) {}
            try { restoreChrome(window.parent.document); } catch (e) {}
          }
          sweep();
          [250, 1000, 2500, 5000].forEach(function (delay) {
            setTimeout(sweep, delay);
          });
          try {
            var target = window.parent.document.body || document.body;
            if (target && window.parent.MutationObserver) {
              new window.parent.MutationObserver(sweep).observe(target, { childList: true, subtree: true });
            }
          } catch (e) {}
        })();
        </script>
        """,
    )


def _inject_streamlit_cloud_chrome_hide() -> None:
    """Hide Manage app / Share for dealership logins (Streamlit may still inject them)."""
    embed_script(
        """
        <script>
        (function () {
          function chromeRoots(doc) {
            return [
              doc.querySelector('[data-testid="stHeader"]'),
              doc.querySelector('[data-testid="stBottomBlock"]'),
              doc.querySelector("footer")
            ].filter(Boolean);
          }
          function hideChrome(doc) {
            if (!doc || !doc.body) return;
            chromeRoots(doc).forEach(function (root) {
              root.querySelectorAll("a, button, span, p, div, label").forEach(function (el) {
                var text = (el.textContent || "").trim();
                if (text === "Share" || text === "Manage app" || text === "Manage App") {
                  var target = el.closest("a, button, [role='button']") || el;
                  if (target.closest('section[data-testid="stSidebar"]')) return;
                  target.style.setProperty("display", "none", "important");
                }
              });
            });
          }
          function sweep() {
            try { hideChrome(document); } catch (e) {}
            try { hideChrome(window.parent.document); } catch (e) {}
          }
          sweep();
          [250, 1000, 2500].forEach(function (delay) { setTimeout(sweep, delay); });
          try {
            var target = window.parent.document.body || document.body;
            if (target && window.parent.MutationObserver) {
              new window.parent.MutationObserver(sweep).observe(target, { childList: true, subtree: true });
            }
          } catch (e) {}
        })();
        </script>
        """,
    )


def _inject_dealer_connect_expander_header_fix(theme: str = "Dark") -> None:
    """Late CSS so Dealer Connect expander headers stay dark before hover on Streamlit Cloud."""
    is_light = str(theme).lower() == "light"
    bg = "var(--rg-surface-card, #f4f8fc)" if is_light else "rgba(7, 19, 34, .92)"
    text = "#0f172a" if is_light else "#f8fbff"
    st.markdown(
        f"""
        <style>
        .stApp:has(.dealer-connect-workspace-marker) details[data-testid="stExpander"] > summary,
        .stApp:has(.dealer-connect-workspace-marker) details[data-testid="stExpander"][open] > summary,
        .stApp:has(.dealer-connect-workspace-marker) details[data-testid="stExpander"] > summary:not(:hover) {{
            background: {bg} !important;
            background-color: {bg} !important;
            background-image: none !important;
            color: {text} !important;
            -webkit-text-fill-color: {text} !important;
        }}
        .stApp:has(.dealer-connect-workspace-marker) details[data-testid="stExpander"] > summary *,
        .stApp:has(.dealer-connect-workspace-marker) details[data-testid="stExpander"] > summary div[data-testid="stMarkdownContainer"],
        .stApp:has(.dealer-connect-workspace-marker) details[data-testid="stExpander"] > summary div[data-testid="stMarkdownContainer"] p {{
            color: {text} !important;
            -webkit-text-fill-color: {text} !important;
            background: transparent !important;
            background-color: transparent !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def apply_style(theme="Dark", display_prefs: dict | None = None):
    css = THEME_CSS.get(theme, THEME_CSS["Dark"])
    if display_prefs:
        css += build_user_display_css(display_prefs, theme=theme)
    css += brand_color_lock_css(theme)
    css += metric_display_css()
    css += claim_learning_css(theme)
    css += pricing_page_css(theme)
    css += multiselect_css(theme)
    css += audit_result_panel_css(theme)
    css += review_open_claims_strip_css(theme)
    css += expander_css(theme)
    css += vin_recall_alert_css(theme)
    css += dealer_connect_panel_css(theme)
    css += narrative_copy_button_css(theme)
    css += review_collapsible_css(theme)
    css += streamlit_primary_override_css(theme)
    css += main_scroll_fix_css()
    css += script_embed_collapse_css()
    from core.ui_polish import workspace_polish_css

    css += workspace_polish_css(theme)
    if streamlit_cloud_chrome_allowed():
        _inject_streamlit_cloud_chrome_restore()
    else:
        css = STREAMLIT_CHROME_HIDE_CSS + css
        _inject_streamlit_cloud_chrome_hide()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


# =========================
# CLAIM LEARNING
# =========================
def extract_claim_ro_number(text: str) -> str:
    """Pull repair order number from Dealer Connect claim PDF text."""
    for pat in (
        r"repair order(?:\s+number)?\s*[#:\-]?\s*(\d{5,10})",
        r"\bro(?:\s+number)?\s*[#:\-]?\s*(\d{5,10})",
        r"claim(?:\s+number)?\s*[#:\-]?\s*(\d{5,10})",
    ):
        match = re.search(pat, str(text or ""), re.I)
        if match:
            return match.group(1).strip()
    return ""


def extract_pages(file):
    if PdfReader is None:
        return []
    reader = PdfReader(file)
    pages = []
    for p in reader.pages:
        try:
            txt = p.extract_text() or ""
            if len(txt.strip()) > 80:
                pages.append(txt)
        except Exception:
            pass
    return pages


def extract_pdf_document_text(file) -> tuple[list[str], str]:
    """Return page list and full text from a claim PDF upload."""
    import io

    pdf_bytes = file.getvalue() if hasattr(file, "getvalue") else file.read()
    if hasattr(file, "seek"):
        file.seek(0)

    pages: list[str] = []
    if PdfReader is not None:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
                if txt.strip():
                    pages.append(txt)
            except Exception:
                pass

    return pages, "\n\n".join(pages)


def is_acknowledgement_servlet_export(document_text: str) -> bool:
    return bool(re.search(r"global claim acknowledgement", str(document_text or ""), re.I))


def split_acknowledgement_servlet_claims(pages: list[str]) -> list[str]:
    """Group servlet export pages by claim number; attach code-only continuation pages."""
    groups: list[dict] = []
    current: dict = {"claim_number": "", "pages": []}

    def _flush() -> None:
        nonlocal current
        if not current["pages"]:
            return
        text = "\n\n".join(current["pages"]).strip()
        if len(text) >= 80:
            groups.append({"claim_number": current["claim_number"], "text": text})
        current = {"claim_number": "", "pages": []}

    for page in pages:
        text = str(page or "").strip()
        if not text:
            continue

        claim_match = re.search(r"Claim Number:\s*(\d+)", text, re.I)
        claim_num = claim_match.group(1).strip() if claim_match else ""

        if claim_num:
            if current["pages"] and claim_num != current["claim_number"]:
                _flush()
            current["claim_number"] = claim_num
            current["pages"].append(text)
            continue

        if current["pages"]:
            current["pages"].append(text)
            continue

        if extract_message_code_reasons(text) and groups:
            groups[-1]["text"] = f"{groups[-1]['text']}\n\n{text}".strip()
        elif len(text) >= 80:
            current["pages"].append(text)

    _flush()
    return [g["text"] for g in groups if g.get("text")]


def split_claims_from_pages(pages):
    claims = []
    for page in pages:
        parts = re.split(
            r"(?=advisor:\s*process date:|process date:|claim type:|submission type:|date received:)",
            page,
            flags=re.I,
        )
        parts = [p.strip() for p in parts if len(p.strip()) > 180]
        claims.extend(parts if len(parts) > 1 else [page])
    return [c for c in claims if len(c.strip()) > 180]


def split_declined_claims_from_pages(pages):
    """Keep message-code pages paired with the narrative on the same or next segment."""
    claims: list[str] = []
    pending_codes = ""

    for page in pages:
        text = str(page or "").strip()
        if not text:
            continue

        page_codes = extract_decline_reason(text) or ""
        if page_codes:
            pending_codes = page_codes

        has_narrative = bool(re.search(r"customer states|verified the customer", text, re.I))
        if has_narrative:
            blob = text
            if pending_codes and pending_codes not in blob:
                blob = f"Message Code Information\n{pending_codes}\n\n{blob}"
            claims.append(blob)
            pending_codes = ""
            continue

        parts = re.split(
            r"(?=advisor:\s*process date:|process date:|claim type:|submission type:|date received:)",
            text,
            flags=re.I,
        )
        parts = [p.strip() for p in parts if len(p.strip()) > 120]
        if parts:
            for part in parts:
                if pending_codes and pending_codes not in part:
                    part = f"{pending_codes}\n{part}"
                if re.search(r"customer states|verified", part, re.I):
                    claims.append(part)
            pending_codes = ""
        elif page_codes and len(text) > 80:
            claims.append(text)

    if claims:
        return [c for c in claims if len(c.strip()) > 80]
    return split_claims_from_pages(pages)


def prepare_declined_pdf_claims(file) -> tuple[list[str], str, dict]:
    """Extract declined PDF text; OCR when message codes are missing from the text layer."""
    import io

    pdf_bytes = file.getvalue() if hasattr(file, "getvalue") else file.read()
    if hasattr(file, "seek"):
        file.seek(0)

    pages: list[str] = []
    if PdfReader is not None:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
                if txt.strip():
                    pages.append(txt)
            except Exception:
                pass

    document_text = "\n\n".join(pages)
    ocr_used = False
    has_codes = bool(extract_decline_reason("", document_text=document_text))

    if not has_codes:
        try:
            ocr_text, ocr_used = extract_ro_text(io.BytesIO(pdf_bytes), force_ocr=ocr_available())
            if ocr_text.strip():
                document_text = ocr_text
                if not pages:
                    pages = [ocr_text]
                has_codes = bool(extract_decline_reason("", document_text=document_text))
        except Exception:
            pass

    claims = split_declined_claims_from_pages(pages if pages else ([document_text] if document_text else []))
    if is_acknowledgement_servlet_export(document_text):
        servlet_claims = split_acknowledgement_servlet_claims(pages if pages else [document_text])
        if servlet_claims:
            claims = servlet_claims
    if not claims and document_text:
        claims = split_claims_from_pages([document_text])

    return claims, document_text, {
        "has_message_codes": has_codes,
        "ocr_used": ocr_used,
        "page_count": len(pages),
        "claim_segments": len(claims),
        "servlet_export": is_acknowledgement_servlet_export(document_text),
    }


def words(text):
    stop = set("the and or to of in on for with a an is was were customer states vehicle claim type date advisor".split())
    text = re.sub(r"[^a-zA-Z0-9\s]", " ", (text or "").lower())
    return [w for w in text.split() if len(w) > 2 and w not in stop]


def score_match(query, claim_text):
    q = words(query)
    c = set(words(claim_text))
    score = sum(2 for w in q if w in c)
    phrases = ["oil leak", "coolant leak", "no start", "hard start", "backup camera", "camera inop",
               "a/c not cold", "ac not cold", "misfire", "check engine", "battery", "rental", "sublet"]
    ql = query.lower()
    cl = claim_text.lower()
    for p in phrases:
        if p in ql and p in cl:
            score += 12
    return score


def suggested_lops(claim_text):
    lops = re.findall(r"\b[A-Z]{2,6}[0-9]{2,6}\b", claim_text.upper())
    bad = {"TOTAL", "PARTS", "LABOR", "AMOUNT"}
    return sorted({x for x in lops if x not in bad})[:8]


def extract_sentence(claim_text, kind):
    lines = [x.strip() for x in claim_text.splitlines() if len(x.strip()) > 12 and "____" not in x]
    bad = ["part number", "quantity", "extended", "price", "invoice", "amount"]
    lines = [x for x in lines if not any(b in x.lower() for b in bad)]
    if kind == "concern":
        keys = ["customer", "complaint", "concern", "inop", "leak", "noise", "no start"]
    elif kind == "cause":
        keys = [
    "found", "verified", "tested", "failed", "diagnosed", "inspection", "dtc",
    "short to ground", "short to voltage", "open circuit", "internal failure",
    "delamination", "manufacturing defect", "poor workmanship", "identified",
    "pin fit issue", "terminal spread", "high resistance", "corrosion",
    "broken wire", "failed internally", "leaking", "binding", "seized",
    "out of specification", "not communicating", "intermittent failure",
    "connector issue", "water intrusion", "damaged", "contaminated",
    "cracked", "misaligned", "excessive play", "faulty", "defective"
        ]
    else:
        keys = ["replaced", "repaired", "installed", "performed", "completed", "programmed"]
    for line in lines:
        if any(k in line.lower() for k in keys):
            return line[:700]
    return ""


# =========================
# AUDIT ENGINE
# =========================
MANUAL_STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "was", "were", "are",
    "has", "have", "had", "customer", "states", "vehicle", "performed", "removed",
    "replaced", "checked", "found", "verified", "repair", "concern", "cause",
    "correction", "warranty", "claim", "technician", "advisor",
    # Generic pencil-wrench / narrative words — too broad to match WAM sections.
    "inspection", "operating", "accessed", "visual", "examination", "designed",
    "system", "internal", "malfunction", "binding", "jammed", "switch", "button",
    "further", "concern", "complaint", "diagnostic", "proper", "working",
    "operates", "designed", "start", "stop", "replaced", "removed",
}

JOB_MANUAL_TRIGGERS = {
    "battery_replacement": ["battery test", "battery replacement", "test slip", "failed battery", "aux battery"],
    "ac_repair": ["a/c repair", "evac", "recharge", "refrigerant", "compressor"],
    "oil_leak": ["oil leak", "oil leakage", "oil dye", "leak detection", "engine oil"],
    "sublet_repair": ["sublet", "sublet invoice", "outside repair"],
    "rental_involved": ["rental", "loaner", "rental days"],
    "warranty_add_on": ["add-on", "add on", "manager approval", "authorization"],
    "parts_warranty": ["parts warranty", "mopar", "mopa", "original ro"],
    "alignment_involved": ["alignment", "wheel alignment", "align vehicle", "four wheel alignment"],
}

# Section must contain one of these when the matching checkbox is checked.
TOPIC_STRONG_PHRASES = {
    "battery_replacement": ["battery test", "battery replacement", "test slip", "failed battery", "battery code"],
    "ac_repair": ["a/c", "evac", "recharge", "refrigerant", "air conditioning"],
    "oil_leak": ["oil leak", "oil leakage", "oil dye", "leak detection", "engine oil"],
    "sublet_repair": ["sublet", "outside repair", "sublet invoice"],
    "rental_involved": ["rental", "loaner", "rental vehicle"],
    "warranty_add_on": ["add-on", "add on", "manager approval", "authorization"],
    "parts_warranty": ["parts warranty", "mopar", "mopa", "original ro"],
    "alignment_involved": ["alignment", "wheel alignment", "align vehicle", "four wheel alignment"],
}


def _active_checkbox_topics(job):
    return [topic for topic in JOB_MANUAL_TRIGGERS if job.get(topic)]


def _topic_anchor_phrases(job):
    """Strong phrases used to locate the right excerpt — not loose narrative words."""
    anchors = []
    for topic in _active_checkbox_topics(job):
        anchors.extend(TOPIC_STRONG_PHRASES.get(topic, JOB_MANUAL_TRIGGERS[topic]))
    explicit = extract_wam_reference(_job_narrative_text(job))
    if explicit:
        anchors.append(explicit.lower())
    return list(dict.fromkeys(a.lower() for a in anchors if a))


def _content_matches_any_phrase(content_low, phrases):
    return any(phrase.lower() in content_low for phrase in phrases if phrase)


def _section_matches_job_topics(job, content_low):
    active = _active_checkbox_topics(job)
    if not active:
        return False
    for topic in active:
        topic_phrases = TOPIC_STRONG_PHRASES.get(topic, JOB_MANUAL_TRIGGERS[topic])
        if _content_matches_any_phrase(content_low, topic_phrases):
            return True
    return False


def _job_narrative_text(job):
    return " ".join([
        str(job.get("concern", "")),
        str(job.get("cause", "")),
        str(job.get("correction", "")),
    ]).lower()


def _significant_terms(text):
    return {
        w.strip(".,:;()[]\"'").lower()
        for w in str(text or "").split()
        if len(w.strip(".,:;()[]\"'")) > 4
        and w.strip(".,:;()[]\"'").lower() not in MANUAL_STOP_WORDS
    }


def _job_manual_search_terms(job):
    text = _job_narrative_text(job)
    terms = set(_significant_terms(text))
    for topic in _active_checkbox_topics(job):
        terms.update(JOB_MANUAL_TRIGGERS[topic])
    explicit = extract_wam_reference(text)
    if explicit:
        terms.add(explicit.lower())
    return text, terms


TOPIC_EXCLUDE_PHRASES = {
    "oil_leak": ["sheet metal", "transportation damage", "carrier delivery", "drop-ship", "cummins diesel"],
    "battery_replacement": ["sheet metal", "transportation damage", "oil leak", "a/c"],
    "ac_repair": ["sheet metal", "transportation damage", "battery test", "oil leak"],
}


def _trim_snippet_at_unrelated_topic(snippet, active_topics):
    if not snippet or not active_topics:
        return snippet
    low = snippet.lower()
    cut_at = len(snippet)
    for topic in active_topics:
        for bad in TOPIC_EXCLUDE_PHRASES.get(topic, []):
            idx = low.find(bad.lower())
            if idx > 80:
                cut_at = min(cut_at, idx)
    if cut_at < len(snippet):
        snippet = snippet[:cut_at].rstrip(" ,.;:-") + "…"
    return snippet


def _find_snippet_start(raw, anchor_idx, lookback=520):
    """Walk backward to a natural section/table row start — not mid-word."""
    region_start = max(0, anchor_idx - lookback)
    region = raw[region_start:anchor_idx]

    break_points = [0]
    patterns = [
        r"(?i)\btype of reimbursement\b",
        r"(?i)\bsupporting documents\b",
        r"(?i)(?:^|[\n\r]|(?:\s{2,}))(?:battery|diagnostic|oil leakage|oil leak|sublet|rental)\b",
        r"(?m)^\s*\d+\.\d+(?:\.\d+)?(?:\.\d+)?\s+[A-Z]",
        r"•\s*",
        r"\.\s+(?=[A-Z0-9•\-])",
        r";\s+",
        r":\s+(?=[A-Z])",
    ]
    for pat in patterns:
        for match in re.finditer(pat, region):
            break_points.append(match.start())

    start_rel = max(break_points)
    start = region_start + start_rel

    while start < anchor_idx and raw[start:start + 1] in " \t\n\r|":
        start += 1

    if start > 0 and start < len(raw) and raw[start - 1].isalnum() and raw[start].isalnum():
        space_idx = raw.rfind(" ", region_start, start)
        if space_idx != -1:
            start = space_idx + 1

    return start


def _extract_manual_snippet(content, anchor_phrases, max_len=480):
    """Return a readable excerpt centered on a topic phrase — not mid-sentence."""
    raw = str(content or "")
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{2,}", "\n", raw).strip()
    if not raw or not anchor_phrases:
        return ""

    low = raw.lower()
    best_idx = -1
    best_phrase = ""
    for phrase in sorted(anchor_phrases, key=len, reverse=True):
        p = phrase.lower().strip()
        if len(p) < 4:
            continue
        idx = low.find(p)
        if idx != -1 and (best_idx == -1 or len(p) > len(best_phrase)):
            best_idx = idx
            best_phrase = p

    if best_idx == -1:
        return ""

    start = _find_snippet_start(raw, best_idx)
    end = min(len(raw), best_idx + len(best_phrase) + max_len)
    snippet = raw[start:end].strip()

    if start > 0:
        snippet = "…" + snippet
    if end < len(raw):
        snippet = snippet + "…"

    return snippet


def _guess_wam_keywords(text):
    """Auto-tag uploaded manual chunks so Review can match without manual keyword entry."""
    text_low = str(text or "").lower()
    candidates = [
        "battery", "test slip", "oil leak", "oil dye", "sublet", "rental", "loaner",
        "a/c", "evac", "recharge", "refrigerant", "mopar", "parts warranty",
        "manager approval", "add-on", "warranty claim", "narrative", "documentation",
        "hard stop", "required", "must", "shall",
    ]
    return ", ".join(c for c in candidates if c in text_low)


def _extract_tsb_number(text):
    patterns = [
        r"(?:TSB|Technical Service Bulletin)\s*(?:Number|No\.?|#)?\s*[:\-\s]*(\d{1,3}[-–]\d{2,4}\w?)",
        r"Bulletin\s*(?:Number|No\.?)\s*[:\-\s]*(\d{1,3}[-–]\d{2,4}\w?)",
        r"\b(\d{2}[-–]\d{3,4})\b",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.I)
        if match:
            return match.group(1).replace("–", "-").strip()
    return ""


def _guess_tsb_keywords(text):
    """Auto-tag uploaded TSB text from components and common bulletin terms."""
    text_low = str(text or "").lower()
    hits = _components_in_claim_text(text_low)
    extra = [
        term for term in (
            "recall", "reprogram", "software update", "flash", "module",
            "technical service bulletin", "warranty", "campaign",
        )
        if term in text_low
    ]
    return ", ".join(dict.fromkeys(hits + extra))


def _bulletin_preview_label(row) -> str:
    num = str(row.get("bulletin_number") or "").strip()
    title = str(row.get("title") or "").strip()
    if num and title:
        return f"{num} — {title}"
    return num or title or "Untitled bulletin"


def _extract_tsb_metadata(text, filename):
    bulletin_number = _extract_tsb_number(text)
    title = ""
    for pat in (
        r"(?:SUBJECT|TOPIC|TITLE|REASON FOR BULLETIN)\s*[:\-\s]+(.{8,140})",
    ):
        match = re.search(pat, text, re.I)
        if match:
            title = re.sub(r"\s+", " ", match.group(1)).strip()
            break
    if not title:
        title = f"TSB {bulletin_number}" if bulletin_number else Path(filename).stem
    return bulletin_number, title[:200], _guess_tsb_keywords(text)


def find_applicable_tsb_bulletins(job, limit=3):
    """Match uploaded TSB / bulletin content to this job's repair narrative."""
    text = _job_narrative_text(job).lower()
    if not text.strip():
        return []

    try:
        bulletin_df = load_bulletins(supabase)
    except Exception:
        return []

    if bulletin_df.empty:
        return []

    job_components = set(_components_in_claim_text(text))
    scored = []

    for _, row in bulletin_df.iterrows():
        title = str(row.get("title", "") or "").strip()
        content = str(row.get("content") or row.get("notes") or "").strip()
        if len(content) < 40:
            continue

        content_low = content.lower()
        bulletin_num = str(row.get("bulletin_number", "") or "").strip()
        keyword_hits = [
            k.strip()
            for k in str(row.get("keywords", "") or "").split(",")
            if k.strip() and k.strip().lower() in text
        ]
        shared_components = sorted(
            job_components & set(_components_in_claim_text(content_low))
        )
        num_hit = bool(
            bulletin_num
            and bulletin_num.lower().replace(" ", "") in text.replace(" ", "")
        )

        topic_phrases = shared_components + keyword_hits
        if bulletin_num:
            topic_phrases.append(bulletin_num)
        snippet = _extract_manual_snippet(
            content,
            topic_phrases or list(job_components)[:5],
            max_len=280,
        )
        if not snippet:
            continue

        score = len(keyword_hits) * 15 + len(shared_components) * 28 + (30 if num_hit else 0)
        if score < 25 and not num_hit:
            continue

        source_file = str(row.get("source_file", "") or "").strip()
        matched_on = ", ".join(
            dict.fromkeys(
                ([bulletin_num] if num_hit else [])
                + keyword_hits
                + shared_components
            )
        )[:120] or title

        scored.append({
            "score": score,
            "section": title or (f"TSB {bulletin_num}" if bulletin_num else "Service Bulletin"),
            "source": source_file or "TSB Library",
            "source_type": "TSB",
            "matched_on": matched_on,
            "snippet": snippet,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    seen = set()
    results = []
    for item in scored:
        key = (item["section"].lower(), item["snippet"][:80].lower())
        if key in seen:
            continue
        seen.add(key)
        results.append(item)
        if len(results) >= limit:
            break
    return results


def find_applicable_manual_sections(job, limit=3):
    """Return WAM and TSB excerpts that match this specific job."""
    text, terms = _job_manual_search_terms(job)
    active_topics = _active_checkbox_topics(job)
    anchor_phrases = _topic_anchor_phrases(job)
    explicit_wam = extract_wam_reference(_job_narrative_text(job))

    scored = []

    if (active_topics or explicit_wam) and (anchor_phrases or terms):
        try:
            wam_rows = supabase.table("wam_documents").select("*").execute().data or []
        except Exception:
            wam_rows = []

        for row in wam_rows:
            content = str(row.get("content", "") or "")
            if not content.strip():
                continue

            content_low = content.lower()
            if not _section_matches_job_topics(job, content_low):
                continue

            section = str(row.get("section", "Warranty Manual") or "Warranty Manual")
            source = str(row.get("source_file", "manual") or "manual")

            topic_phrases = anchor_phrases or list(terms)
            snippet = _extract_manual_snippet(content, topic_phrases)
            if not snippet:
                continue
            snippet = _trim_snippet_at_unrelated_topic(snippet, active_topics)

            snippet_low = snippet.lower()
            if active_topics and not _content_matches_any_phrase(snippet_low, topic_phrases):
                continue

            keyword_hits = [
                k.strip()
                for k in str(row.get("keywords", "") or "").split(",")
                if k.strip() and k.strip().lower() in text
            ]

            trigger_hits = []
            for topic in active_topics:
                hits = [
                    p for p in TOPIC_STRONG_PHRASES.get(topic, [])
                    if p in content_low
                ]
                trigger_hits.extend(hits[:2])

            score = len(keyword_hits) * 18 + len(trigger_hits) * 30
            if active_topics:
                score += 25
            if score < 25:
                continue

            matched_on = ", ".join(
                dict.fromkeys(keyword_hits + trigger_hits)
            )[:120] or (active_topics[0].replace("_", " ") if active_topics else explicit_wam)

            scored.append({
                "score": score,
                "section": section,
                "source": source,
                "source_type": "WAM",
                "matched_on": matched_on,
                "snippet": snippet,
            })

    scored.extend(find_applicable_tsb_bulletins(job, limit=limit))

    scored.sort(key=lambda x: x["score"], reverse=True)
    seen = set()
    results = []
    for item in scored:
        key = (item["section"].lower(), item["snippet"][:80].lower())
        if key in seen:
            continue
        seen.add(key)
        results.append(item)
        if len(results) >= limit:
            break
    return results


def find_wam_matches(job):
    """Backward-compatible wrapper."""
    return find_applicable_manual_sections(job)


def _render_applicable_manual_sections_body(sections) -> None:
    st.caption(
        "WAM excerpts require a checked warranty flag or explicit WAM reference. "
        "TSB / bulletins match automatically when the repair narrative applies."
    )

    for idx, sec in enumerate(sections):
        label = sec.get("section", "Warranty Manual")
        source = sec.get("source", "manual")
        matched = sec.get("matched_on", "")
        st.markdown(f"**{label}**")
        st.caption(f"Source: {source} · Matched on: {matched}")
        st.info(sec.get("snippet", ""))
        if idx < len(sections) - 1:
            st.markdown("")


def render_applicable_manual_sections(sections, key_prefix="manual"):
    if not sections:
        return

    count = len(sections)
    noun = "matches" if count != 1 else "match"
    hint = f"{count} manual / TSB {noun}"
    with _collapsible_section(
        "Applicable Manual & TSB Guidance",
        hint,
        marker_class="review-collapsible manual-tsb-panel",
        anchor_class="dc-anchor-manual-tsb",
    ):
        _render_applicable_manual_sections_body(sections)
CLAIM_COMPONENT_TERMS = [
    "lower control arm", "control arm", "upper control arm", "bushing",
    "ball joint", "tie rod", "sway bar", "strut", "wheel bearing",
    "squeak", "squeaking", "clunk", "rattle", "alignment",
    "spark plug", "misfire", "camshaft", "lifter",
    "water pump", "coolant leak", "thermostat", "radiator",
    "evap", "purge", "canister", "fuel pump", "injector",
    "compressor", "evaporator", "blend door", "blower motor",
    "battery", "alternator", "starter motor", "backup camera",
    "axle shaft", "cv axle", "transmission", "torque converter",
    "brake", "rotor", "caliper", "short to ground", "open circuit",
    "start/stop switch", "start stop switch", "stop switch", "start button",
    "push start", "push button", "ignition switch", "steering column",
    "oil filter adapter", "engine front cover", "oil leak",
]

CLAIM_MATCH_STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "was", "were",
    "are", "has", "have", "had", "customer", "states", "vehicle",
    "performed", "removed", "replaced", "checked", "found", "warranty",
    "claim", "number", "date", "line", "part", "parts", "verified",
    "inspection", "operating", "accessed", "visual", "examination",
    "designed", "system", "internal", "malfunction", "binding", "jammed",
    "switch", "button", "further", "concern", "complaint", "diagnostic",
    "proper", "working", "operates", "start", "stop", "repair", "technician",
    "cause", "correction", "road", "test", "drove", "tested",
}


def _components_in_claim_text(text, terms=None):
    text = str(text or "").lower()
    terms = terms or CLAIM_COMPONENT_TERMS
    return [term for term in terms if term in text]


def find_similar_learned_claims(current_job, *, outcome: str = "paid", limit: int = 5):
    try:
        outcome = str(outcome or "paid").strip().lower()
        current_text = " ".join([
            str(current_job.get("concern", "")),
            str(current_job.get("cause", "")),
            str(current_job.get("correction", "")),
        ]).lower().strip()

        if len(current_text) < 20:
            return []

        rows = supabase.table("claims").select("*").limit(10000).execute().data or []
        matches = []

        dtcs = re.findall(r"\b[A-Z][0-9A-Z]{4}(?:-[0-9A-Z]{2})?\b", current_text.upper())

        component_terms = CLAIM_COMPONENT_TERMS

        bad_terms = [
            "acknowledgement", "servlet", "policy", "privacy", "terms",
            "authorization", "disclosure",
        ]

        junk_phrases = [
            "warranty pays for parts",
            "thank you from the warranty contact center",
            "authorization number",
            "date completed",
            "date received",
            "technician identification",
            "line item number",
            "vehicle description",
        ]

        stop_words = CLAIM_MATCH_STOP_WORDS

        current_components = _components_in_claim_text(current_text, component_terms)

        current_words = {
            w.strip(".,:;()[]").lower()
            for w in current_text.split()
            if len(w.strip(".,:;()[]")) > 4 and w.strip(".,:;()[]").lower() not in stop_words
        }

        current_lops = set(re.findall(r"\b\d{7,8}\b", current_text))

        if not current_words:
            return []

        for row in rows:
            if _claim_status_value(row) != outcome:
                continue
            if not learned_claim_is_useful(row):
                if outcome != "declined" or not _decline_reason_value(row):
                    continue

            ro_name = str(row.get("ro_number", "")).lower()
            if any(term in ro_name for term in bad_terms):
                continue

            claim_text = " ".join([
                str(row.get("concern") or ""),
                str(row.get("cause") or ""),
                str(row.get("correction") or ""),
                str(row.get("story") or ""),
                str(row.get("content") or ""),
                str(row.get("labor_ops") or ""),
                str(row.get("parts") or ""),
            ]).lower()

            for phrase in junk_phrases:
                claim_text = claim_text.replace(phrase, "")

            if len(claim_text.strip()) < 40:
                if outcome != "declined" or not _decline_reason_value(row):
                    continue

            claim_words = {
                w.strip(".,:;()[]").lower()
                for w in claim_text.split()
                if len(w.strip(".,:;()[]")) > 4 and w.strip(".,:;()[]").lower() not in stop_words
            }

            claim_components = _components_in_claim_text(claim_text, component_terms)

            if current_components or claim_components:
                shared_components = set(current_components) & set(claim_components)
                if not shared_components:
                    continue
            elif len(current_words.intersection(claim_words)) < 3:
                continue

            overlap = current_words.intersection(claim_words)
            score = int((len(overlap) / max(len(current_words), 1)) * 50)

            matched_components = sorted(set(current_components) & set(claim_components))
            if matched_components:
                score += min(35, 12 * len(matched_components[:3]))

            claim_lops = set(re.findall(r"\b\d{7,8}\b", claim_text))
            if current_lops and claim_lops:
                lop_overlap = current_lops.intersection(claim_lops)
                if lop_overlap:
                    score += min(15, 5 * len(lop_overlap))

            dtc_match = any(dtc.lower() in claim_text for dtc in dtcs)
            if dtcs:
                if dtc_match:
                    score += 10
                else:
                    score = int(score * 0.5)

            if current_text in claim_text:
                score += 10

            score = min(score, 100)

            if score < 40:
                continue

            matches.append(enrich_paid_claim_match({
                "score": score,
                "ro_number": row.get("ro_number", ""),
                "concern": row.get("concern", ""),
                "cause": row.get("cause", ""),
                "correction": row.get("correction", ""),
                "labor_ops": row.get("labor_ops", ""),
                "parts": row.get("parts", ""),
                "story": row.get("story", ""),
                "content": row.get("content", ""),
                "wam": row.get("wam", ""),
                "wam_reference": row.get("wam_reference", ""),
                "reference": row.get("reference", ""),
                "decline_reason": _decline_reason_value(row),
                "wam_issue": _declined_issue_summary(row),
                "match_reasons": matched_components,
                "matching_codes": ", ".join(sorted(current_lops.intersection(claim_lops))) if current_lops else "",
            }))

        matches = sorted(matches, key=lambda x: x["score"], reverse=True)
        return matches[:limit]

    except Exception as e:
        st.warning(f"Claim Intelligence could not load: {e}")
        return []


def find_similar_paid_claims(current_job, limit=5):
    return find_similar_learned_claims(current_job, outcome="paid", limit=limit)


def find_similar_declined_claims(current_job, limit=5):
    return find_similar_learned_claims(current_job, outcome="declined", limit=limit)


def _audit_rule_severity(audit_rules, rule_key):
    rule = audit_rules.get("rules", {}).get(rule_key, {})
    if not rule.get("enabled", True):
        return None
    severity = str(rule.get("severity", "hard") or "hard").lower()
    return severity if severity in ("hard", "warn") else "hard"


def _add_audit_finding(hard, warn, audit_rules, rule_key, message):
    severity = _audit_rule_severity(audit_rules, rule_key)
    if severity is None:
        return
    finding = {"rule": rule_key, "message": message}
    if severity == "warn":
        warn.append(finding)
    else:
        hard.append(finding)


def _correction_verifies_proper_operation(correction_text: str) -> bool:
    """True when correction documents post-repair verification."""
    text = str(correction_text or "").lower()
    if not text.strip():
        return False
    if "operating" in text or "designed" in text:
        return True
    return any(
        phrase in text
        for phrase in (
            "verified",
            "operates",
            "working",
            "proper operation",
            "no further issues",
            "test drove",
            "road tested",
        )
    )


def audit_job(job, time_bypass, *, smart_warranty_time_exempt=False, audit_rules=None):
    audit_rules = normalize_audit_rules(audit_rules)
    thresholds = audit_rules["thresholds"]
    tech_min = float(thresholds.get("tech_time_min_pct", 0.70))
    tech_max = float(thresholds.get("tech_time_max_pct", 2.00))
    rental_warn_days = int(thresholds.get("rental_days_warn", 15))

    hard = []
    warn = []
    text = f"{job['concern']} {job['cause']} {job['correction']}".lower()

    if not job["concern"].strip():
        _add_audit_finding(hard, warn, audit_rules, "narrative_required", "Missing concern.")
    if not job["cause"].strip():
        _add_audit_finding(hard, warn, audit_rules, "narrative_required", "Missing cause.")
    if not job["correction"].strip():
        _add_audit_finding(hard, warn, audit_rules, "narrative_required", "Missing correction.")

    cause_text = job["cause"].lower()
    if job["cause"].strip():
        if not any(x in cause_text for x in ["found", "tested", "verified", "diagnosed", "inspected", "scanned"]):
            _add_audit_finding(
                hard, warn, audit_rules, "pencil_wrench_cause",
                "Pencil Wrench Cause: missing diagnostic steps used to get to the failure.",
            )
        if not any(x in cause_text for x in ["dtc", "code", "inspection", "measured", "scan", "test", "voltage", "pressure", "leak test"]):
            _add_audit_finding(
                hard, warn, audit_rules, "pencil_wrench_cause",
                "Pencil Wrench Cause: missing supporting evidence such as DTC, test result, inspection, or measurement.",
            )
        if not any(x in cause_text for x in [
            "failed", "failure", "internal failure", "inoperative",
            "not working", "leak", "leaking internally",
            "shorted", "short to ground", "open", "open circuit",
            "intermittent open circuit", "broken", "faulty",
            "collapsed lifter", "damaged camshaft lobe",
            "damaged cam shaft lobe", "warped",
            "mechanical failure", "electrical failure",
        ]):
            _add_audit_finding(
                hard, warn, audit_rules, "pencil_wrench_cause",
                "Pencil Wrench Cause: failure is not clearly identified.",
            )

    correction_text = job["correction"].lower()
    if job["correction"].strip():
        if not any(x in correction_text for x in ["replaced", "repaired", "installed", "removed", "programmed", "performed"]):
            _add_audit_finding(
                hard, warn, audit_rules, "pencil_wrench_correction",
                "Pencil Wrench Correction: repair action is not clearly identified.",
            )
        if not any(x in correction_text for x in [
            "due to", "because", "failed", "failure",
            "leaking", "shorted", "open", "damaged",
            "replaced", "removed and replaced",
            "repaired", "reprogrammed", "updated",
            "sealed", "resealed", "adjusted",
            "verified proper operation",
            "test drove", "road tested",
        ]):
            _add_audit_finding(
                hard, warn, audit_rules, "pencil_wrench_correction",
                "Pencil Wrench Correction: parts replaced are not clearly justified.",
            )
        if not _correction_verifies_proper_operation(job["correction"]):
            _add_audit_finding(
                hard, warn, audit_rules, "pencil_wrench_correction",
                "Pencil Wrench Correction: proper operation was not verified after repair.",
            )

    oil_leak = bool(job.get("oil_leak"))
    oil_dye_billed = bool(job.get("oil_dye_billed"))
    if oil_leak and not oil_dye_billed:
        _add_audit_finding(
            hard, warn, audit_rules, "oil_leak",
            "Oil leak repair requires oil dye billed.",
        )
    elif oil_dye_billed and not oil_leak:
        _add_audit_finding(
            hard, warn, audit_rules, "oil_leak",
            "Oil dye billed but Oil Leak is not selected.",
        )

    if job.get("sublet_repair"):
        _add_audit_finding(
            hard, warn, audit_rules, "sublet",
            "Sublet selected: invoice must include VIN, mileage, and detailed repair notes.",
        )
        if not job.get("sublet_vin"):
            _add_audit_finding(hard, warn, audit_rules, "sublet", "Sublet invoice must show VIN.")
        if not job.get("sublet_mileage"):
            _add_audit_finding(hard, warn, audit_rules, "sublet", "Sublet invoice must show mileage.")
        if not job.get("sublet_notes"):
            _add_audit_finding(hard, warn, audit_rules, "sublet", "Sublet invoice must include detailed repair notes.")

    if job.get("rental_involved"):
        if job.get("rental_days", 0) <= 0:
            _add_audit_finding(hard, warn, audit_rules, "rental", "Rental involved but rental days are not billed.")
        if not job.get("manager_signed_rental"):
            _add_audit_finding(hard, warn, audit_rules, "rental", "Rental involved but manager sign-off is missing.")
        if job.get("rental_days", 0) >= rental_warn_days:
            _add_audit_finding(
                hard, warn, audit_rules, "rental_high_days",
                f"{rental_warn_days} or more rental days billed: make sure all documentation to support "
                "rental days is submitted to Stellantis with the claim.",
            )

    if job.get("warranty_add_on") and not job.get("manager_approval"):
        manager_name = service_manager_signoff_phrase()
        _add_audit_finding(
            hard, warn, audit_rules, "warranty_add_on",
            f"Warranty add-on (W+) requires {manager_name} sign-off.",
        )

    tech_flagged_time = float(job.get("tech_flagged_time") or 0)
    time_allotted = float(job.get("time_allotted") or 0)

    if smart_warranty_time_exempt:
        pass
    elif time_bypass:
        _add_audit_finding(
            hard, warn, audit_rules, "tech_time",
            "Tech Flagged Time / Time Allotted validation was bypassed for this review.",
        )
    elif _audit_rule_severity(audit_rules, "tech_time") is not None:
        if time_allotted > 0 and tech_flagged_time > 0:
            pct = tech_flagged_time / time_allotted
            if pct < tech_min:
                _add_audit_finding(
                    hard, warn, audit_rules, "tech_time",
                    f"Tech Flagged Time is below {tech_min:.0%} of Time Allotted ({pct:.0%}).",
                )
            if pct > tech_max:
                _add_audit_finding(
                    hard, warn, audit_rules, "tech_time",
                    f"Tech Flagged Time exceeds {tech_max:.0%} of Time Allotted ({pct:.0%}).",
                )
        elif time_allotted > 0 and tech_flagged_time <= 0:
            _add_audit_finding(hard, warn, audit_rules, "tech_time", "Tech Flagged Time is missing.")
        elif tech_flagged_time > 0 and time_allotted <= 0:
            _add_audit_finding(hard, warn, audit_rules, "tech_time", "Time Allotted for the job is missing.")

    if job.get("battery_replacement") and not job.get("battery_test_slip"):
        _add_audit_finding(
            hard, warn, audit_rules, "battery_test_slip",
            "Battery replacement requires failed battery test slip/code.",
        )
    if job.get("ac_repair") and not job.get("ac_evac_slip"):
        _add_audit_finding(
            hard, warn, audit_rules, "ac_evac_slip",
            "A/C repair requires EVAC/recharge slip.",
        )
    if job.get("alignment_involved") and not job.get("alignment_report_attached"):
        _add_audit_finding(
            hard, warn, audit_rules, "alignment_report",
            "Alignment requires printout report attached to the repair order.",
        )
    if job.get("parts_warranty") and not job.get("mopa_original_ro"):
        _add_audit_finding(
            hard, warn, audit_rules, "parts_warranty_mopa",
            "Parts warranty requires MOPAR and original RO support.",
        )

    manual_sections = find_applicable_manual_sections(job)
    job["manual_sections"] = manual_sections

    if manual_sections:
        _add_audit_finding(
            hard, warn, audit_rules, "manual_guidance",
            "Applicable warranty manual guidance is shown below — confirm compliance before submission.",
        )

    score = max(0, 100 - len(hard) * 15 - len(warn) * 5)
    return hard, warn, score

def result_banner(status):
    if "DO NOT" in status:
        cls = "status-stop"
    elif "NEEDS" in status:
        cls = "status-review"
    else:
        cls = "status-ready"
    st.markdown(f'<div class="{cls}"><h2>{status}</h2></div>', unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_vin_recall_lookup(vin: str) -> dict:
    return lookup_vin_recalls(vin)


def _vin_recall_ack_key(form_version: int, vin_clean: str) -> str:
    return f"vin_recall_ack_{form_version}_{vin_clean}"


def _is_vin_recall_acknowledged(form_version: int, vin_clean: str) -> bool:
    ack = st.session_state.get(_vin_recall_ack_key(form_version, vin_clean))
    if not isinstance(ack, dict):
        return False
    return bool(ack.get("acknowledged"))


def _vin_recall_skip_fetch_key(form_version: int) -> str:
    return f"vin_recall_skip_fetch_{form_version}"


def _restore_saved_recall_state(review: dict, form_version: int) -> None:
    """Reuse recall results from a saved review — no new NHTSA lookup on re-open."""
    fv = int(form_version)
    vin_clean = normalize_vin(str(review.get("vin") or ""))
    if len(vin_clean) < 11:
        return

    recall_key = f"vin_recall_result_{fv}"
    count = int(review.get("vin_recall_count") or 0)
    campaigns = [
        c.strip() for c in str(review.get("vin_recall_campaigns") or "").split(",") if c.strip()
    ]
    recalls = [{"campaign": c, "component": ""} for c in campaigns]
    if count > len(recalls):
        recalls.extend({"campaign": "Campaign", "component": ""} for _ in range(count - len(recalls)))

    st.session_state[f"vin_recall_tracked_vin_{fv}"] = vin_clean
    st.session_state[_vin_recall_skip_fetch_key(fv)] = True
    st.session_state[recall_key] = {
        "ok": True,
        "vin": vin_clean,
        "recall_count": count,
        "recalls": recalls[:count] if count else [],
        "vehicle": {},
        "from_saved_review": True,
    }
    if _truthy_flag(review.get("vin_recall_acknowledged")):
        st.session_state[_vin_recall_ack_key(fv, vin_clean)] = {
            "acknowledged": True,
            "acknowledged_at": "",
        }


def _ensure_vin_recall_lookup(vin: str, form_version: int) -> dict | None:
    """Auto-fetch NHTSA recalls when the VIN is long enough (initial entry only)."""
    vin_clean = normalize_vin(vin)
    recall_key = f"vin_recall_result_{form_version}"
    tracked_vin_key = f"vin_recall_tracked_vin_{form_version}"
    skip_key = _vin_recall_skip_fetch_key(form_version)

    if len(vin_clean) < 11:
        return None

    if st.session_state.get(skip_key):
        tracked = st.session_state.get(tracked_vin_key)
        if tracked == vin_clean:
            return st.session_state.get(recall_key)
        st.session_state.pop(skip_key, None)

    if st.session_state.get(tracked_vin_key) != vin_clean:
        st.session_state[recall_key] = _cached_vin_recall_lookup(vin_clean)
        st.session_state[tracked_vin_key] = vin_clean

    result = st.session_state.get(recall_key)
    if result and result.get("vin") != vin_clean:
        st.session_state[recall_key] = _cached_vin_recall_lookup(vin_clean)
        st.session_state[tracked_vin_key] = vin_clean
        result = st.session_state.get(recall_key)

    return result


def _actionable_vin_recalls(
    form_version: int,
    job_count: int,
    result: dict | None = None,
) -> list[dict]:
    payload = result if result is not None else st.session_state.get(f"vin_recall_result_{form_version}") or {}
    if not payload.get("ok"):
        return []
    job_text = _review_job_text_from_session(form_version, job_count)
    recalls = apply_job_relevance(list(payload.get("recalls") or []), job_text)
    return filter_actionable_recalls(recalls)


def _vin_recall_save_fields(form_version: int, vin: str, job_count: int = 1) -> dict:
    vin_clean = normalize_vin(vin)
    actionable = _actionable_vin_recalls(form_version, job_count)
    count = len(actionable)
    campaigns = [
        str(item.get("campaign", "")).strip()
        for item in actionable
        if item.get("campaign")
    ]
    return {
        "vin_recall_identified": 1 if count > 0 else 0,
        "vin_recall_count": count,
        "vin_recall_campaigns": ", ".join(campaigns),
        "vin_recall_acknowledged": 1 if _is_vin_recall_acknowledged(form_version, vin_clean) else 0,
    }


def _review_job_text_from_session(form_version: int, job_count: int) -> str:
    parts = []
    for job_no in range(1, int(job_count) + 1):
        for field in ("concern", "cause", "correction"):
            parts.append(str(st.session_state.get(f"{field}_{job_no}_{form_version}", "") or ""))
    return " ".join(parts)


def _render_recall_details_body(
    result: dict,
    *,
    form_version: int,
    job_count: int,
    vin_clean: str,
    actionable: list[dict],
) -> None:
    vehicle = result.get("vehicle") or {}
    all_on_file = int(result.get("all_recall_count") or len(result.get("recalls") or []))

    vehicle_label = " ".join(
        p for p in (
            vehicle.get("model_year"),
            vehicle.get("make"),
            vehicle.get("model"),
            vehicle.get("trim"),
        )
        if p
    )
    if vehicle_label:
        st.markdown(
            f"**{vehicle_label}** · {len(actionable)} recall(s) may apply to this repair"
        )
    elif result.get("from_saved_review"):
        st.caption("Recall data from the saved review — verify current status in OASIS / wiTECH.")

    st.caption(
        "Only recalls related to this job (or flagged Park It / Park Outside) are shown. "
        "Confirm open/completed status in **OASIS / wiTECH / DealerCONNECT** before submit."
    )
    if all_on_file > len(actionable):
        st.caption(
            f"{all_on_file - len(actionable)} other campaign(s) exist for this vehicle configuration "
            "but do not match this repair — hidden to reduce noise."
        )
    if result.get("disclaimer"):
        st.caption(result.get("disclaimer"))

    critical = [r for r in actionable if r.get("park_it") or r.get("park_outside")]
    if critical:
        st.markdown(
            f'<div class="vin-recall-critical-note">'
            f"{len(critical)} campaign(s) flagged "
            f"<strong>Park It / Park Outside</strong> — verify immediately."
            f"</div>",
            unsafe_allow_html=True,
        )

    related = [
        r for r in actionable
        if int(r.get("relevance_score") or 0) >= 12 and not (r.get("park_it") or r.get("park_outside"))
    ]
    if related:
        st.markdown(
            f'<div class="vin-recall-match-note">{len(related)} recall(s) match the job narrative.</div>',
            unsafe_allow_html=True,
        )

    for recall in actionable[:MAX_DISPLAY_RECALLS]:
        campaign = recall.get("campaign") or "Campaign"
        component = recall.get("component") or "Component not listed"
        flags = []
        if recall.get("park_it"):
            flags.append("Park It")
        if recall.get("park_outside"):
            flags.append("Park Outside")
        if recall.get("ota"):
            flags.append("OTA")
        flag_text = f" · {' / '.join(flags)}" if flags else ""
        st.markdown(f"**{campaign}** — {component}{flag_text}")
        if recall.get("summary"):
            st.caption(recall.get("summary")[:320])

    remaining = len(actionable) - min(len(actionable), MAX_DISPLAY_RECALLS)
    if remaining > 0:
        st.caption(f"+ {remaining} more matching recall(s) — verify all in OASIS / wiTECH.")

    if not _is_vin_recall_acknowledged(form_version, vin_clean):
        if st.button(
            "I acknowledge — continue with this claim",
            type="primary",
            use_container_width=True,
            key=f"vin_recall_ack_btn_{form_version}_{vin_clean}",
        ):
            st.session_state[_vin_recall_ack_key(form_version, vin_clean)] = {
                "acknowledged": True,
                "acknowledged_at": datetime.now().isoformat(timespec="seconds"),
            }
            st.rerun()
    else:
        st.caption("Recall notice acknowledged for this claim.")


def _vin_recall_details_open_key(form_version: int, vin_clean: str) -> str:
    return f"recall_details_open_{form_version}_{vin_clean}"


def render_vin_recall_panel(vin: str, form_version: int, job_count: int):
    vin_clean = normalize_vin(vin)
    if len(vin_clean) < 11:
        return

    tracked_vin_key = f"vin_recall_tracked_vin_{form_version}"
    needs_fetch = (
        not st.session_state.get(_vin_recall_skip_fetch_key(form_version))
        and st.session_state.get(tracked_vin_key) != vin_clean
    )
    if needs_fetch:
        with st.spinner("Checking NHTSA recalls…"):
            result = _ensure_vin_recall_lookup(vin, form_version)
    else:
        result = _ensure_vin_recall_lookup(vin, form_version)

    if not result or not result.get("ok"):
        return

    actionable = _actionable_vin_recalls(form_version, job_count, result)
    if not actionable:
        return

    if _is_vin_recall_acknowledged(form_version, vin_clean):
        return

    details_key = _vin_recall_details_open_key(form_version, vin_clean)
    st.markdown('<div class="vin-recall-alert-wrap"></div>', unsafe_allow_html=True)
    recall_label = (
        f"{len(actionable)} open recall{'s' if len(actionable) != 1 else ''} may apply"
        f" — click for details"
    )
    if st.button(
        recall_label,
        key=f"vin_recall_toggle_{form_version}_{vin_clean}",
        use_container_width=True,
    ):
        st.session_state[details_key] = not st.session_state.get(details_key, False)
        st.rerun()

    if st.session_state.get(details_key):
        with st.container(border=True):
            st.markdown('<div class="vin-recall-details-panel"></div>', unsafe_allow_html=True)
            _render_recall_details_body(
                result,
                form_version=form_version,
                job_count=job_count,
                vin_clean=vin_clean,
                actionable=actionable,
            )


def _vin_recall_blocks_audit(form_version: int, vin: str, job_count: int = 1) -> bool:
    vin_clean = normalize_vin(vin)
    result = st.session_state.get(f"vin_recall_result_{form_version}") or {}
    if not result.get("ok"):
        return False
    if not _actionable_vin_recalls(form_version, job_count, result):
        return False
    return not _is_vin_recall_acknowledged(form_version, vin_clean)


def _build_job_from_session(form_version: int, job_no: int) -> dict:
    fv = form_version
    j = job_no
    return {
        "job_no": str(j),
        "concern": str(st.session_state.get(f"concern_{j}_{fv}", "") or ""),
        "cause": str(st.session_state.get(f"cause_{j}_{fv}", "") or ""),
        "correction": str(st.session_state.get(f"correction_{j}_{fv}", "") or ""),
        "operation_code": str(st.session_state.get(f"operation_code_{j}", "") or "").strip(),
        "tech_flagged_time": float(st.session_state.get(f"tech_time_{j}", 0) or 0),
        "time_allotted": float(st.session_state.get(f"allotted_{j}", 0) or 0),
        "claim_value": float(st.session_state.get(f"claim_value_{j}", 0) or 0),
        "oil_leak": bool(st.session_state.get(f"oil_leak_{j}", False)),
        "oil_dye_billed": bool(st.session_state.get(f"oil_dye_{j}", False)),
        "battery_replacement": bool(st.session_state.get(f"battery_{j}", False)),
        "battery_test_slip": bool(st.session_state.get(f"battery_slip_{j}", False)),
        "sublet_repair": bool(st.session_state.get(f"sublet_{j}", False)),
        "sublet_vin": bool(st.session_state.get(f"sublet_vin_{j}", False)),
        "sublet_mileage": bool(st.session_state.get(f"sublet_mileage_{j}", False)),
        "sublet_notes": bool(st.session_state.get(f"sublet_notes_{j}", False)),
        "rental_involved": bool(st.session_state.get(f"rental_{j}", False)),
        "rental_days": int(st.session_state.get(f"rental_days_{j}", 0) or 0),
        "manager_signed_rental": bool(st.session_state.get(f"rental_signed_{j}", False)),
        "warranty_add_on": bool(st.session_state.get(f"addon_{j}", False)),
        "manager_approval": bool(st.session_state.get(f"manager_approval_{j}", False)),
        "ac_repair": bool(st.session_state.get(f"ac_{j}", False)),
        "ac_evac_slip": bool(st.session_state.get(f"ac_slip_{j}", False)),
        "parts_warranty": bool(st.session_state.get(f"parts_warranty_{j}", False)),
        "mopa_original_ro": bool(st.session_state.get(f"mopa_{j}", False)),
        "alignment_involved": bool(st.session_state.get(f"alignment_{j}", False)),
        "alignment_report_attached": bool(st.session_state.get(f"alignment_report_{j}", False)),
    }


def _format_dc_copy_number(value: float | int | str) -> str:
    """Format hours or dollars for Dealer Connect copy fields."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value or "").strip()
    if abs(number - round(number)) < 0.001:
        return str(int(round(number))) if number == int(number) else f"{number:.2f}".rstrip("0").rstrip(".")
    return f"{number:.2f}".rstrip("0").rstrip(".")


def _format_dc_copy_date(value) -> str:
    """Format dates the way Dealer Connect entry screens usually show them."""
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y/%m/%d")
    return str(value).strip()


def _render_input_copy_slot(
    *,
    label: str,
    element_id: str,
    text: str,
    align: str = "left",
) -> None:
    payload = str(text or "").strip()
    align_class = " field-copy-align-right" if align == "right" else ""
    st.markdown(
        f'<div class="field-copy-slot{align_class}" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    if payload:
        _render_field_copy_button(
            payload,
            label=label,
            element_id=element_id,
            iframe_width=108,
        )
    else:
        _render_field_copy_button(
            "",
            label=label,
            element_id=element_id,
            iframe_width=108,
            disabled=True,
        )


def _render_field_with_copy_column(
    label: str,
    *,
    copy_id: str,
    render_field,
    format_copy=lambda value: str(value or ""),
    show_label: bool = True,
    copy_align: str = "left",
):
    """Label, full-width input, then Copy tucked underneath."""
    if show_label and label:
        st.markdown(f"**{label}**")
    value = render_field()
    _render_input_copy_slot(
        label=label,
        element_id=copy_id,
        text=format_copy(value),
        align=copy_align,
    )
    return value


def _render_paired_fields_with_copy(
    left_label: str,
    left_copy_id: str,
    left_render_field,
    right_label: str,
    right_copy_id: str,
    right_render_field,
    *,
    left_format_copy=lambda value: str(value or ""),
    right_format_copy=lambda value: str(value or ""),
):
    """Two fields side by side — each with Copy directly under its input."""
    left_col, right_col = st.columns(2, gap="medium")
    with left_col:
        st.markdown(f"**{left_label}**")
        left_value = left_render_field()
        _render_input_copy_slot(
            label=left_label,
            element_id=left_copy_id,
            text=left_format_copy(left_value),
        )
    with right_col:
        st.markdown(f"**{right_label}**")
        right_value = right_render_field()
        _render_input_copy_slot(
            label=right_label,
            element_id=right_copy_id,
            text=right_format_copy(right_value),
        )
    return left_value, right_value


def _render_text_input_with_copy(
    label: str,
    key: str,
    *,
    copy_id: str | None = None,
    help: str | None = None,
) -> str:
    copy_id = copy_id or f"copy_{key}"
    value = _render_field_with_copy_column(
        label,
        copy_id=copy_id,
        render_field=lambda: st.text_input(
            label,
            key=key,
            label_visibility="collapsed",
            help=help,
        ),
        format_copy=lambda value: str(value or ""),
    )
    return str(value or "")


def _render_number_input_with_copy(
    label: str,
    key: str,
    *,
    copy_id: str | None = None,
    min_value: float = 0.0,
    max_value: float | None = None,
    step: float = 0.1,
) -> float:
    copy_id = copy_id or f"copy_{key}"

    def render_field():
        kwargs: dict = {
            "min_value": min_value,
            "step": step,
            "key": key,
            "label_visibility": "collapsed",
        }
        if max_value is not None:
            kwargs["max_value"] = max_value
        return st.number_input(label, **kwargs)

    value = _render_field_with_copy_column(
        label,
        copy_id=copy_id,
        render_field=render_field,
        format_copy=_format_dc_copy_number,
    )
    return float(value)


def _render_date_input_with_copy(
    label: str,
    key: str,
    *,
    copy_id: str | None = None,
):
    copy_id = copy_id or f"copy_{key}"
    value = _render_field_with_copy_column(
        label,
        copy_id=copy_id,
        render_field=lambda: st.date_input(label, key=key, label_visibility="collapsed"),
        format_copy=_format_dc_copy_date,
    )
    return value


def _render_field_copy_button(
    text: str,
    *,
    label: str,
    element_id: str,
    show_value_box: bool = False,
    iframe_width: int = 100,
    disabled: bool = False,
) -> None:
    """Copy control for narrative / Dealer Connect fields (iframe — clipboard needs JS)."""
    payload_text = str(text or "").strip()
    if not payload_text and not disabled:
        return
    payload = json.dumps(payload_text)
    safe_label = html.escape(label)
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", element_id)
    safe_display = html.escape(payload_text)
    disabled_attr = " disabled" if disabled or not payload_text else ""
    button_label = "Copy" if not disabled else "Copy"
    value_box = ""
    if show_value_box:
        value_box = f"""
        <div class="copy-value-box" id="{safe_id}_box" title="Click to copy {safe_label}">
          {safe_display}
        </div>
        """
    iframe_height = 34
    if show_value_box:
        line_count = max(1, payload_text.count("\n") + 1, (len(payload_text) // 48) + 1)
        iframe_height = min(220, 78 + (line_count * 22))

    embed_html(
        f"""
        <style>
          html, body {{
            margin: 0;
            padding: 0;
            background: transparent !important;
            overflow: hidden;
            font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
          }}
          .copy-value-box {{
            margin: 0 0 8px 0;
            padding: 10px 12px;
            border-radius: 10px;
            background: rgba(7, 19, 34, .92);
            border: 1px solid rgba(62, 150, 255, .28);
            color: #f8fbff;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.92rem;
            line-height: 1.45;
            white-space: pre-wrap;
            word-break: break-word;
            cursor: pointer;
          }}
          .copy-value-box:hover {{
            border-color: rgba(96, 165, 250, .55);
            background: rgba(13, 30, 55, .95);
          }}
          button {{
            width: 100%;
            min-width: 6.5rem;
            padding: 5px 12px;
            border-radius: 8px;
            border: 1px solid rgba(62, 150, 255, .35);
            background: rgba(7, 19, 34, .75);
            color: #f8fbff;
            font-size: 0.78rem;
            font-weight: 600;
            white-space: nowrap;
            cursor: pointer;
          }}
          button:hover {{
            background: rgba(13, 30, 55, .95);
          }}
          button:disabled {{
            opacity: 0.45;
            cursor: not-allowed;
          }}
        </style>
        {value_box}
        <button id="{safe_id}" type="button" title="Copy {safe_label}"{disabled_attr}>{button_label}</button>
        <script>
        (function() {{
          const btn = document.getElementById("{safe_id}");
          const box = document.getElementById("{safe_id}_box");
          if (!btn) return;
          if (btn.disabled) return;
          const text = {payload};
          const reset = () => {{ btn.textContent = "Copy"; }};
          const copied = () => {{
            btn.textContent = "Copied!";
            if (box) {{
              box.style.borderColor = "rgba(74, 222, 128, .65)";
            }}
            setTimeout(() => {{
              reset();
              if (box) {{
                box.style.borderColor = "rgba(62, 150, 255, .28)";
              }}
            }}, 1200);
          }};
          const fallback = () => {{
            const ta = document.createElement("textarea");
            ta.value = text;
            ta.setAttribute("readonly", "");
            ta.style.position = "fixed";
            ta.style.left = "-9999px";
            document.body.appendChild(ta);
            ta.select();
            try {{
              document.execCommand("copy");
              copied();
            }} catch (e) {{
              btn.textContent = "Select text";
              setTimeout(reset, 1600);
            }}
            document.body.removeChild(ta);
          }};
          const copyText = () => {{
            if (navigator.clipboard && navigator.clipboard.writeText) {{
              navigator.clipboard.writeText(text).then(copied).catch(fallback);
            }} else {{
              fallback();
            }}
          }};
          btn.addEventListener("click", copyText);
          if (box) {{
            box.addEventListener("click", copyText);
          }}
        }})();
        </script>
        """,
        height=iframe_height,
        width=iframe_width if not show_value_box else None,
    )


def _render_narrative_field(
    label: str,
    session_key: str,
    *,
    copy_id: str,
    height: int = 72,
) -> str:
    """Narrative text area with Copy under the box for Dealer Connect paste."""
    value = _render_field_with_copy_column(
        label,
        copy_id=copy_id,
        show_label=True,
        copy_align="right",
        render_field=lambda: st.text_area(
            label,
            key=session_key,
            height=height,
            label_visibility="collapsed",
        ),
        format_copy=lambda value: str(value or ""),
    )
    return str(value or "")


def _render_dealer_connect_copy_field(*, label: str, value: str, copy_id: str) -> None:
    """Label + clickable value block with Copy button for Dealer Connect paste."""
    text = str(value or "").strip()
    if not text:
        return
    st.markdown(f"**{label}**")
    _render_field_copy_button(
        text,
        label=label,
        element_id=copy_id,
        show_value_box=True,
    )


def _render_dealer_connect_job_lines_body(
    *,
    line_jobs: list[dict],
    ro_clean: str,
    vin_clean: str,
    form_version: int,
) -> None:
    st.caption(
        "Labor operation, times, and claim value from the scanned invoice / RO. "
        "Use **Copy** below each field to paste into Dealer Connect."
    )
    fv = int(form_version)
    if ro_clean or vin_clean:
        header_cols = st.columns(2, gap="medium")
        with header_cols[0]:
            if ro_clean:
                _render_dealer_connect_copy_field(
                    label="RO",
                    value=ro_clean,
                    copy_id=f"copy_dc_ro_{fv}",
                )
        with header_cols[1]:
            if vin_clean:
                _render_dealer_connect_copy_field(
                    label="VIN",
                    value=vin_clean,
                    copy_id=f"copy_dc_vin_{fv}",
                )

    if not line_jobs:
        _dc_note_info(
            "No labor operation or times imported yet. Upload the **Final Invoice** on the scan panel "
            "and click **Scan & Fill Form**."
        )
        return

    multi = len(line_jobs) > 1
    for job in line_jobs:
        job_no = job["job_no"]
        with st.container(border=True):
            st.markdown(
                '<div class="dealer-connect-job-line"></div>',
                unsafe_allow_html=True,
            )
            if multi:
                st.markdown(f"**Job {job_no}**")

            if job.get("operation_code"):
                _render_dealer_connect_copy_field(
                    label="Labor operation",
                    value=str(job["operation_code"]),
                    copy_id=f"copy_dc_op_j{job_no}_{fv}",
                )
            if float(job.get("tech_flagged_time") or 0) > 0:
                _render_dealer_connect_copy_field(
                    label="Tech flagged time",
                    value=_format_dc_copy_number(job["tech_flagged_time"]),
                    copy_id=f"copy_dc_tech_time_j{job_no}_{fv}",
                )
            if float(job.get("time_allotted") or 0) > 0:
                _render_dealer_connect_copy_field(
                    label="Time allotted",
                    value=_format_dc_copy_number(job["time_allotted"]),
                    copy_id=f"copy_dc_allotted_j{job_no}_{fv}",
                )
            if float(job.get("claim_value") or 0) > 0:
                _render_dealer_connect_copy_field(
                    label="Claim value",
                    value=_format_dc_copy_number(job["claim_value"]),
                    copy_id=f"copy_dc_value_j{job_no}_{fv}",
                )


def _render_dealer_connect_job_lines_export(
    jobs: list[dict],
    *,
    ro_number: str,
    vin: str,
    expand_all: bool = False,
) -> None:
    """Per-job labor op, times, and claim value from invoice / RO scan."""
    ro_clean = str(ro_number or "").strip()
    vin_clean = str(vin or "").strip()

    line_jobs: list[dict] = []
    for job in jobs:
        job_no = int(job.get("job_no") or len(line_jobs) + 1)
        operation_code = str(job.get("operation_code") or "").strip()
        tech_time = float(job.get("tech_flagged_time") or 0)
        allotted = float(job.get("time_allotted") or 0)
        claim_value = float(job.get("claim_value") or 0)
        if operation_code or tech_time or allotted or claim_value:
            line_jobs.append(
                {
                    "job_no": job_no,
                    "operation_code": operation_code,
                    "tech_flagged_time": tech_time,
                    "time_allotted": allotted,
                    "claim_value": claim_value,
                }
            )

    if not line_jobs and not ro_clean and not vin_clean:
        st.caption(
            "Scan the **Final Invoice** above to auto-fill labor operation codes and times for Dealer Connect."
        )
        return

    if line_jobs:
        noun = "lines" if len(line_jobs) != 1 else "line"
        hint = f"{len(line_jobs)} job {noun} ready"
    elif ro_clean or vin_clean:
        hint = "RO / VIN ready"
    else:
        hint = None

    with _collapsible_section(
        "Job line details — copy into Dealer Connect",
        hint,
        marker_class="dealer-connect-collapsible job-lines-panel",
        anchor_class="dc-anchor-job-lines",
        expanded=expand_all,
    ):
        _render_dealer_connect_job_lines_body(
            line_jobs=line_jobs,
            ro_clean=ro_clean,
            vin_clean=vin_clean,
            form_version=st.session_state.form_version,
        )


def compute_live_audit_summary(
    form_version: int,
    job_count: int,
    vin: str,
    *,
    smart_warranty_time_exempt: bool,
    audit_rules: dict,
) -> dict:
    time_bypass = bool(st.session_state.get("time_bypass", False))
    all_hard = []
    all_warn = []
    scores = []
    total_value = 0.0
    hard_value = 0.0

    for i in range(1, int(job_count) + 1):
        job = _build_job_from_session(form_version, i)
        hard, warn, score = audit_job(
            job,
            time_bypass,
            smart_warranty_time_exempt=smart_warranty_time_exempt,
            audit_rules=audit_rules,
        )
        claim_val = float(job.get("claim_value") or 0)
        total_value += claim_val
        if hard:
            hard_value += claim_val
        all_hard.extend(hard)
        all_warn.extend(warn)
        scores.append(score)

    recall_block = _vin_recall_blocks_audit(form_version, vin, job_count)

    if recall_block:
        status = "🔴 DO NOT SUBMIT"
        status_reason = "Open recall(s) must be acknowledged before submission."
    elif all_hard:
        status = "🔴 DO NOT SUBMIT"
        status_reason = f"{len(all_hard)} hard stop(s) across {int(job_count)} job(s)."
    elif all_warn:
        status = "🟡 NEEDS REVIEW"
        status_reason = f"{len(all_warn)} warning(s) — review before submitting."
    else:
        status = "🟢 READY"
        status_reason = "No hard stops or warnings detected."

    final_score = int(sum(scores) / len(scores)) if scores else 100

    return {
        "status": status,
        "status_reason": status_reason,
        "score": final_score,
        "total_value": total_value,
        "hard_value": hard_value,
        "hard_stop_count": len(all_hard),
        "warning_count": len(all_warn),
        "recall_block": recall_block,
        "job_count": int(job_count),
    }


def render_live_submit_status_bar(summary: dict):
    status = summary["status"]
    if "DO NOT" in status:
        cls = "status-stop"
    elif "NEEDS" in status:
        cls = "status-review"
    else:
        cls = "status-ready"

    recall_note = ""
    if summary.get("recall_block"):
        recall_note = (
            '<div class="live-submit-note">'
            "⚠️ Open VIN recall — acknowledge before Run Audit + Save."
            "</div>"
        )

    st.markdown(
        f"""
        <div class="live-submit-bar {cls}">
            <div class="live-submit-main">
                <span class="live-submit-status">{html.escape(status)}</span>
                <span class="live-submit-reason">{html.escape(summary.get("status_reason", ""))}</span>
            </div>
            <div class="live-submit-metrics">
                <span><strong>Score</strong> {summary["score"]}</span>
                <span><strong>Total claim</strong> ${summary["total_value"]:,.2f}</span>
                <span><strong>Hard-stop value</strong> ${summary["hard_value"]:,.2f}</span>
                <span><strong>Hard stops</strong> {summary["hard_stop_count"]}</span>
            </div>
            {recall_note}
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================
# RO OCR
# =========================
def _match_personnel_name(name: str, options: list) -> str:
    if not name or not options:
        return None
    target = name.strip().upper()
    for opt in options:
        if opt.strip().upper() == target:
            return opt
    for opt in options:
        opt_u = opt.strip().upper()
        if target in opt_u or opt_u in target:
            return opt
    last = target.split()[-1]
    for opt in options:
        if last and last in opt.upper():
            return opt
    return None


def _truthy_flag(value) -> bool:
    if isinstance(value, bool):
        return value
    try:
        return int(float(value or 0)) != 0
    except (TypeError, ValueError):
        return bool(value)


def _coerce_form_date(value) -> date:
    if isinstance(value, date):
        return value
    if value is None or str(value).strip() in ("", "NaT", "None"):
        return date.today()
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return date.today()


_JOB_CHECKBOX_FIELDS = (
    ("oil_leak", "oil_leak"),
    ("oil_dye_billed", "oil_dye"),
    ("battery_replacement", "battery"),
    ("battery_test_slip", "battery_slip"),
    ("alignment_involved", "alignment"),
    ("alignment_report_attached", "alignment_report"),
    ("sublet_repair", "sublet"),
    ("sublet_vin", "sublet_vin"),
    ("sublet_mileage", "sublet_mileage"),
    ("sublet_notes", "sublet_notes"),
    ("rental_involved", "rental"),
    ("manager_signed_rental", "rental_signed"),
    ("warranty_add_on", "addon"),
    ("manager_approval", "manager_approval"),
    ("ac_repair", "ac"),
    ("ac_evac_slip", "ac_slip"),
    ("parts_warranty", "parts_warranty"),
    ("mopa_original_ro", "mopa"),
)


def _apply_saved_review_to_form(review: dict, form_version: int) -> None:
    """Hydrate the Review form from a saved Supabase review row."""
    fv = int(form_version)
    jobs = _parse_review_jobs(review)
    st.session_state.job_count = max(len(jobs), 1)

    st.session_state[f"ro_number_{fv}"] = str(review.get("ro_number") or "").strip()
    st.session_state[f"vin_{fv}"] = str(review.get("vin") or "").strip()
    st.session_state[f"ro_invoiced_{fv}"] = _coerce_form_date(review.get("ro_invoiced"))
    st.session_state[f"day_submitted_{fv}"] = _coerce_form_date(review.get("day_submitted"))

    for field, stash_key in (
        ("advisor", "_loaded_review_advisor"),
        ("technician", "_loaded_review_technician"),
        ("warranty_admin", "_loaded_review_warranty_admin"),
        ("manager", "_loaded_review_service_manager"),
    ):
        value = str(review.get(field) or "").strip()
        if value:
            st.session_state[stash_key] = value

    st.session_state[f"first_pass_paid_{fv}"] = _truthy_flag(review.get("first_pass_paid"))
    st.session_state[f"rejected_{fv}"] = _truthy_flag(review.get("rejected"))
    st.session_state[f"paid_after_rejection_{fv}"] = _truthy_flag(review.get("paid_after_rejection"))
    oem_paid = review.get("oem_paid_amount")
    try:
        st.session_state[f"loaded_oem_paid_{fv}"] = (
            float(oem_paid) if oem_paid is not None and str(oem_paid).strip() else None
        )
    except (TypeError, ValueError):
        st.session_state[f"loaded_oem_paid_{fv}"] = None
    st.session_state[f"loaded_short_pay_reason_{fv}"] = str(review.get("short_pay_reason") or "").strip()

    rejection_reason = str(review.get("rejection_reason") or "").strip()
    if _truthy_flag(review.get("paid_after_rejection")):
        st.session_state[f"initial_decline_reason_{fv}"] = rejection_reason
    else:
        st.session_state[f"initial_decline_reason_{fv}"] = ""
    if rejection_reason and not _truthy_flag(review.get("paid_after_rejection")):
        primary, _, notes = rejection_reason.partition(" — ")
        st.session_state[f"rejection_reason_select_{fv}"] = primary.strip()
        if notes.strip():
            st.session_state[f"rejection_reason_notes_{fv}"] = notes.strip()
    else:
        st.session_state[f"rejection_reason_select_{fv}"] = ""
        st.session_state[f"rejection_reason_notes_{fv}"] = ""

    st.session_state["time_bypass"] = _truthy_flag(review.get("time_bypass"))

    for job_no in range(1, 11):
        for _, dest in _JOB_CHECKBOX_FIELDS:
            st.session_state[f"{dest}_{job_no}"] = False
        st.session_state[f"tech_time_{job_no}"] = 0.0
        st.session_state[f"allotted_{job_no}"] = 0.0
        st.session_state[f"claim_value_{job_no}"] = 0.0
        st.session_state[f"operation_code_{job_no}"] = ""
        st.session_state[f"rental_days_{job_no}"] = 0
        st.session_state[f"concern_{job_no}_{fv}"] = ""
        st.session_state[f"cause_{job_no}_{fv}"] = ""
        st.session_state[f"correction_{job_no}_{fv}"] = ""

    for idx, job in enumerate(jobs, start=1):
        st.session_state[f"concern_{idx}_{fv}"] = str(job.get("concern") or "")
        st.session_state[f"cause_{idx}_{fv}"] = str(job.get("cause") or "")
        st.session_state[f"correction_{idx}_{fv}"] = str(job.get("correction") or "")
        st.session_state[f"tech_time_{idx}"] = float(job.get("tech_flagged_time") or 0)
        st.session_state[f"allotted_{idx}"] = float(job.get("time_allotted") or 0)
        st.session_state[f"claim_value_{idx}"] = float(job.get("claim_value") or 0)
        st.session_state[f"operation_code_{idx}"] = str(job.get("operation_code") or "").strip()
        st.session_state[f"rental_days_{idx}"] = int(float(job.get("rental_days") or 0))
        for src, dest in _JOB_CHECKBOX_FIELDS:
            st.session_state[f"{dest}_{idx}"] = _truthy_flag(job.get(src))

    _restore_saved_recall_state(review, fv)


def _open_review_for_editing(review_id: int) -> bool:
    review = _load_review_by_id(int(review_id))
    if not review:
        return False

    st.session_state.form_version += 1
    fv = st.session_state.form_version
    st.session_state.pop(f"vin_recall_result_{fv}", None)
    st.session_state.pop(f"vin_recall_tracked_vin_{fv}", None)
    st.session_state.pop(_vin_recall_skip_fetch_key(fv), None)
    st.session_state.pop("ro_scan_summary", None)

    # Apply on the next run at the top of render_review — before job_count widgets exist.
    st.session_state["_pending_review_load"] = review
    st.session_state[_active_review_id_key(fv)] = int(review_id)
    st.session_state[_active_review_ro_key(fv)] = str(review.get("ro_number") or "").strip()
    st.session_state[_active_review_vin_key(fv)] = str(review.get("vin") or "").strip()
    st.session_state["loaded_review_ro"] = str(review.get("ro_number") or "").strip()
    st.session_state["loaded_review_id"] = int(review_id)
    return True


def _pending_claims_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work["first_pass_paid"] = pd.to_numeric(work.get("first_pass_paid", 0), errors="coerce").fillna(0).astype(int)
    work["rejected"] = pd.to_numeric(work.get("rejected", 0), errors="coerce").fillna(0).astype(int)
    work["paid_after_rejection"] = pd.to_numeric(
        work.get("paid_after_rejection", 0), errors="coerce"
    ).fillna(0).astype(int)
    pending = work[
        (work["first_pass_paid"] == 0)
        & (work["rejected"] == 0)
        & (work["paid_after_rejection"] == 0)
    ].copy()
    if pending.empty:
        return pending

    status_rank = {"🔴 DO NOT SUBMIT": 0, "🟡 NEEDS REVIEW": 1}
    pending["status_rank"] = pending.get("status", "").astype(str).map(status_rank).fillna(2)
    sort_cols = ["status_rank"]
    if "created_at" in pending.columns:
        pending["created_at"] = pd.to_datetime(pending["created_at"], errors="coerce")
        sort_cols.append("created_at")
    pending = pending.sort_values(sort_cols, ascending=[True, False][: len(sort_cols)])
    return pending.drop(columns=["status_rank"], errors="ignore")


def _next_pending_review_row(pending: pd.DataFrame) -> dict | None:
    if pending.empty or "id" not in pending.columns:
        return None
    loaded_id = st.session_state.get("loaded_review_id")
    for _, row in pending.iterrows():
        row_id = int(row["id"])
        if loaded_id is not None and row_id == int(loaded_id):
            continue
        return row.to_dict()
    return pending.iloc[0].to_dict()


def _pending_claim_counts(pending: pd.DataFrame) -> tuple[int, int, int]:
    if pending.empty:
        return 0, 0, 0
    status = pending.get("status", pd.Series(dtype=str)).astype(str)
    total = len(pending)
    hard_stop = int(status.str.contains("DO NOT SUBMIT", na=False).sum())
    needs_review = int(status.str.contains("NEEDS REVIEW", na=False).sum())
    return total, hard_stop, needs_review


def _render_review_open_claims_strip() -> None:
    """Queue summary at the top of Review — open claims without switching tabs."""
    df = load_reviews()
    pending = _pending_claims_dataframe(df)
    loaded_ro = str(st.session_state.get("loaded_review_ro") or "").strip()
    total, hard_stop, needs_review = _pending_claim_counts(pending)

    strip_col, btn_col = st.columns([4.6, 1.1], vertical_alignment="center")

    with strip_col:
        if pending.empty:
            st.markdown(
                """
<div class="review-open-claims-strip review-open-claims-strip--clear">
<div class="review-open-claims-strip__title">Open claims queue</div>
<div class="review-open-claims-strip__clear">All saved reviews have a recorded OEM outcome.</div>
</div>
                """,
                unsafe_allow_html=True,
            )
        else:
            parts = [f"<strong>{total}</strong> open claim{'s' if total != 1 else ''}"]
            if hard_stop:
                parts.append(
                    f'<span class="review-open-claims-strip__stop">{hard_stop} DO NOT SUBMIT</span>'
                )
            if needs_review:
                parts.append(
                    f'<span class="review-open-claims-strip__warn">{needs_review} NEEDS REVIEW</span>'
                )
            meta = " · ".join(parts)
            edit_line = ""
            if loaded_ro:
                others = max(0, total - 1)
                if others:
                    edit_line = (
                        f'<div class="review-open-claims-strip__meta">'
                        f'Editing <span class="review-open-claims-strip__edit">RO {html.escape(loaded_ro)}</span>'
                        f" · {others} other open claim{'s' if others != 1 else ''} waiting"
                        f"</div>"
                    )
                else:
                    edit_line = (
                        f'<div class="review-open-claims-strip__meta">'
                        f'Editing <span class="review-open-claims-strip__edit">RO {html.escape(loaded_ro)}</span>'
                        f" · last open claim in queue"
                        f"</div>"
                    )
            st.markdown(
                f"""
<div class="review-open-claims-strip">
<div class="review-open-claims-strip__title">Open claims queue</div>
<div class="review-open-claims-strip__meta">{meta}</div>
{edit_line}
</div>
                """,
                unsafe_allow_html=True,
            )

    with btn_col:
        st.markdown('<div class="review-open-claims-strip-btn-slot"></div>', unsafe_allow_html=True)
        if not pending.empty:
            next_row = _next_pending_review_row(pending)
            next_ro = str((next_row or {}).get("ro_number") or "").strip()
            loaded_id = st.session_state.get("loaded_review_id")
            next_id = int((next_row or {}).get("id") or 0)
            same_ro = loaded_id is not None and next_id == int(loaded_id)
            label = "Reload RO" if same_ro else "Open next"
            help_text = (
                f"Reload RO {next_ro} in this form"
                if same_ro
                else f"Open RO {next_ro} for editing"
            )
            if st.button(
                label,
                key="review_open_claims_strip_btn",
                use_container_width=True,
                help=help_text,
            ):
                if next_row and _open_review_for_editing(int(next_row["id"])):
                    st.rerun()


def _apply_ro_scan_to_form(import_data: dict):
    fv = st.session_state.form_version
    jobs = import_data.get("jobs") or []

    if jobs:
        st.session_state.job_count = len(jobs)

    if import_data.get("ro_number"):
        st.session_state[f"ro_number_{fv}"] = import_data["ro_number"]
    if import_data.get("vin"):
        st.session_state[f"vin_{fv}"] = import_data["vin"]
    if import_data.get("ro_invoiced"):
        st.session_state[f"ro_invoiced_{fv}"] = import_data["ro_invoiced"]
    if import_data.get("day_submitted"):
        st.session_state[f"day_submitted_{fv}"] = import_data["day_submitted"]

    if import_data.get("advisor"):
        st.session_state["_ro_scan_advisor"] = import_data["advisor"]
    if import_data.get("technician"):
        st.session_state["_ro_scan_technician"] = import_data["technician"]

    checkbox_map = {
        "oil_leak": "oil_leak",
        "battery_replacement": "battery",
        "sublet_repair": "sublet",
        "rental_involved": "rental",
        "warranty_add_on": "addon",
        "ac_repair": "ac",
        "parts_warranty": "parts_warranty",
        "alignment_involved": "alignment",
    }

    for idx, job in enumerate(jobs, start=1):
        if job.get("concern"):
            st.session_state[f"concern_{idx}_{fv}"] = job["concern"]
        if job.get("cause"):
            st.session_state[f"cause_{idx}_{fv}"] = job["cause"]
        if job.get("correction"):
            st.session_state[f"correction_{idx}_{fv}"] = job["correction"]
        if job.get("tech_flagged_time"):
            st.session_state[f"tech_time_{idx}"] = float(job["tech_flagged_time"])
        if job.get("time_allotted"):
            st.session_state[f"allotted_{idx}"] = float(job["time_allotted"])
        if job.get("claim_value"):
            st.session_state[f"claim_value_{idx}"] = float(job["claim_value"])
        if job.get("operation_code"):
            st.session_state[f"operation_code_{idx}"] = str(job["operation_code"]).strip()
        for src, dest in checkbox_map.items():
            if job.get(src):
                st.session_state[f"{dest}_{idx}"] = True


def _inline_text_color(color: str) -> str:
    return f' style="color: {color} !important; -webkit-text-fill-color: {color} !important;"'


def _render_app_workspace_header(theme: str = "Dark", *, supabase_client=None) -> None:
    if st.session_state.pop("_soft_refresh_notice", False):
        st.toast("App refreshed — you are still signed in.", icon="✅")

    key = "Light" if str(theme).lower() == "light" else "Dark"
    c = BRAND_TEXT[key]
    header_col, refresh_col = st.columns([5.75, 0.75], vertical_alignment="top")
    with header_col:
        st.markdown(
            f"""
<div class="app-workspace-header">
<div class="app-workspace-kicker">
<span class="app-workspace-brand"{_inline_text_color(c["workspace_brand"])}>RO Guard</span>
<span class="app-workspace-sep" aria-hidden="true">·</span>
<span class="app-workspace-title"{_inline_text_color(c["workspace_title"])}>Warranty Workspace</span>
</div>
<h2{_inline_text_color(c["workspace_h2"])}>Smarter Claims. <span{_inline_text_color(c["workspace_h2"])}>Stronger Profits.</span></h2>
<p{_inline_text_color(c["workspace_body"])}>Audit warranty ROs, protect claim dollars, and prove ROI across review, reporting, and admin tools.</p>
<div class="app-workspace-accent"{_inline_text_color(c["workspace_accent"])}>Control the Claim · Protect the Profit</div>
</div>
            """,
            unsafe_allow_html=True,
        )
        from core.ui_polish import render_workspace_feature_chips

        render_workspace_feature_chips()
    with refresh_col:
        st.markdown('<div class="app-top-refresh-slot"></div>', unsafe_allow_html=True)
        if st.button(
            "Refresh",
            key="app_soft_refresh_btn",
            help="Reload app data without signing out (unlike the browser refresh button).",
            use_container_width=True,
        ):
            request_soft_refresh()
            st.rerun()


def _render_ro_scanner(theme: str | None = None):
    theme = theme or st.session_state.get("appearance", "Dark")
    key = "Light" if str(theme).lower() == "light" else "Dark"
    c = BRAND_TEXT[key]
    st.markdown(
        f"""
<div class="review-scan-intro">
<h3{_inline_text_color(c["scan_h3"])}>Scan Repair Order &amp; Invoice</h3>
<p{_inline_text_color(c["scan_body"])}>Upload the <strong{_inline_text_color(c["scan_strong"])}>final repair order</strong> and <strong{_inline_text_color(c["scan_strong"])}>final invoice</strong> separately to auto-fill the review form below.</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    if not ocr_available():
        st.warning(
            "OCR is not set up yet. Run: `python3 -m pip install -r requirements.txt` "
            "and install Tesseract on your Mac (`brew install tesseract poppler`)."
        )
        return

    ro_tab, inv_tab = st.tabs(["Final Repair Order", "Final Invoice"])

    with ro_tab:
        st.caption(
            "Customer copy repair order — identifies warranty jobs by pay type **W**, **W+** (add-on), or **Warranty**."
        )
        repair_order_upload = st.file_uploader(
            "Upload Final Repair Order PDF",
            type=["pdf"],
            key="ro_scan_repair_order_upload",
        )

    with inv_tab:
        st.caption(
            "Reynolds/DMS invoice (service file copy or customer invoice) — supplies concern/cause/correction narratives."
        )
        invoice_upload = st.file_uploader(
            "Upload Final Invoice PDF",
            type=["pdf"],
            key="ro_scan_invoice_upload",
        )

    scan_clicked = st.button(
        "Scan & Fill Form",
        key="scan_ro_btn",
        type="primary",
        use_container_width=True,
        disabled=repair_order_upload is None and invoice_upload is None,
    )

    if scan_clicked and (repair_order_upload or invoice_upload):
        try:
            with st.spinner("Scanning documents… this may take 30–60 seconds for multi-page scans."):
                ro_import = None
                invoice_import = None
                if repair_order_upload:
                    ro_parsed = scan_repair_order_pdf(
                        repair_order_upload.getvalue(),
                        document_kind="repair_order",
                    )
                    ro_import = parsed_to_form_import(ro_parsed)
                if invoice_upload:
                    inv_parsed = scan_repair_order_pdf(
                        invoice_upload.getvalue(),
                        document_kind="invoice",
                    )
                    invoice_import = parsed_to_form_import(inv_parsed)

                if ro_import and invoice_import:
                    import_data = merge_form_imports(ro_import, invoice_import)
                else:
                    import_data = ro_import or invoice_import

                _apply_ro_scan_to_form(import_data)
                st.session_state.ro_scan_summary = import_data
            st.rerun()
        except Exception as e:
            st.error(f"Scan failed: {e}")

    summary = st.session_state.get("ro_scan_summary")
    if summary:
        filled = []
        if summary.get("ro_number"):
            filled.append(f"RO {summary['ro_number']}")
        if summary.get("vin"):
            filled.append(f"VIN {summary['vin']}")
        if summary.get("advisor"):
            filled.append(f"Advisor {summary['advisor']}")
        doc = summary.get("document_type", "")
        if doc == "merged":
            filled.append("repair order + invoice merged")
        elif doc == "repair_order":
            filled.append("repair order (add invoice tab for narratives)")
        job_n = len(summary.get("jobs") or [])
        if job_n:
            filled.append(f"{job_n} warranty job(s)")
        if filled:
            st.success("Auto-filled: " + ", ".join(filled) + ". Please verify everything below.")
        for msg in summary.get("warnings", []):
            st.warning(msg)


# =========================
# SCREENS
# =========================


def _review_job_tab_label(
    form_version: int,
    job_no: int,
    *,
    smart_warranty_time_exempt: bool,
    audit_rules: dict,
) -> str:
    job = _build_job_from_session(form_version, job_no)
    hard, warn, _ = audit_job(
        job,
        bool(st.session_state.get("time_bypass", False)),
        smart_warranty_time_exempt=smart_warranty_time_exempt,
        audit_rules=audit_rules,
    )
    if hard:
        return f"Job {job_no} · Stop"
    if warn:
        return f"Job {job_no} · Review"
    return f"Job {job_no} · OK"


def _render_review_job_panel(
    job_no: int,
    *,
    form_version: int,
    smart_warranty_time_exempt: bool,
    rental_dollars_per_day: float,
) -> tuple[dict, bool, str]:
    """Render one warranty job on the Review tab."""
    fv = form_version
    time_bypass = False
    time_bypass_user = ""

    st.markdown("**Narratives**")
    st.markdown(
        '<div class="review-job-narratives-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    st.caption("Use **Copy** under each field to paste into Dealer Connect.")
    concern = _render_narrative_field(
        "Concern",
        f"concern_{job_no}_{fv}",
        copy_id=f"copy_concern_{job_no}_{fv}",
    )
    cause = _render_narrative_field(
        "Cause",
        f"cause_{job_no}_{fv}",
        copy_id=f"copy_cause_{job_no}_{fv}",
    )
    correction = _render_narrative_field(
        "Correction",
        f"correction_{job_no}_{fv}",
        copy_id=f"copy_correction_{job_no}_{fv}",
    )

    if job_no == 1:
        if smart_warranty_time_exempt:
            st.caption(
                "Time punch validation waived — Smart Warranty Plus/Premium (no manual bypass needed)."
            )
        elif user_can_admin_write():
            time_bypass = st.checkbox(
                "Bypass Tech Flagged Time / Time Allotted Validation",
                key="time_bypass",
            )
            if time_bypass:
                time_bypass_user = current_person_name()
                st.caption(f"Bypass will be recorded under **{time_bypass_user}**.")
        else:
            st.caption(
                "Time punch bypass requires a linked **Manager** or **Warranty Admin** account."
            )

    st.markdown("**Times & claim value**")
    c1, c2, c3 = st.columns(3)
    with c1:
        tech_flagged_time = _render_number_input_with_copy(
            "Tech flagged time",
            f"tech_time_{job_no}",
            copy_id=f"copy_tech_time_{job_no}",
            min_value=0.0,
            step=0.1,
        )
    with c2:
        time_allotted = _render_number_input_with_copy(
            "Time allotted",
            f"allotted_{job_no}",
            copy_id=f"copy_allotted_{job_no}",
            min_value=0.0,
            step=0.1,
        )
    with c3:
        claim_value = _render_number_input_with_copy(
            "Claim value",
            f"claim_value_{job_no}",
            copy_id=f"copy_claim_value_{job_no}",
            min_value=0.0,
            step=1.0,
        )
    operation_code = _render_text_input_with_copy(
        "Labor operation code",
        f"operation_code_{job_no}",
        copy_id=f"copy_operation_code_{job_no}",
        help="Auto-filled from invoice scan — edit if needed before copying to Dealer Connect.",
    )

    st.markdown("**Warranty checks**")
    c1, c2 = st.columns(2)
    with c1:
        oil_leak = st.checkbox("Oil Leak", key=f"oil_leak_{job_no}")
        oil_dye_billed = st.checkbox("Oil Dye Billed", key=f"oil_dye_{job_no}")
        battery_replacement = st.checkbox("Battery Replacement", key=f"battery_{job_no}")
        battery_test_slip = st.checkbox("MAXIMUS Battery slip attached", key=f"battery_slip_{job_no}")
        alignment_involved = st.checkbox("Alignment", key=f"alignment_{job_no}")
        alignment_report_attached = st.checkbox(
            "Alignment Report Attached to RO",
            key=f"alignment_report_{job_no}",
        )
        sublet_repair = st.checkbox("Sublet Repair", key=f"sublet_{job_no}")
        sublet_vin = st.checkbox("Sublet VIN Present", key=f"sublet_vin_{job_no}")
        sublet_mileage = st.checkbox("Sublet Mileage Present", key=f"sublet_mileage_{job_no}")
        sublet_notes = st.checkbox("Sublet Detailed Notes Present", key=f"sublet_notes_{job_no}")
    with c2:
        rental_involved = st.checkbox("Rental Involved", key=f"rental_{job_no}")
        rental_days = _render_number_input_with_copy(
            "Rental days billed",
            f"rental_days_{job_no}",
            copy_id=f"copy_rental_days_{job_no}",
            min_value=0.0,
            step=1.0,
        )
        if rental_dollars_per_day > 0:
            rental_total = float(rental_days or 0) * rental_dollars_per_day
            st.caption(
                f"**Rental total:** ${rental_total:,.2f} "
                f"(${rental_dollars_per_day:,.2f}/day × {int(rental_days or 0)} days)"
            )
        manager_signed_rental = st.checkbox(
            service_manager_action_label("Signed Rental"),
            key=f"rental_signed_{job_no}",
        )
        warranty_add_on = st.checkbox("Warranty Add-On (W+)", key=f"addon_{job_no}")
        manager_approval = st.checkbox(
            service_manager_action_label("Signed Off"),
            key=f"manager_approval_{job_no}",
        )
        ac_repair = st.checkbox("A/C Repair", key=f"ac_{job_no}")
        ac_evac_slip = st.checkbox("A/C EVAC Slip", key=f"ac_slip_{job_no}")
        parts_warranty = st.checkbox("Parts Warranty", key=f"parts_warranty_{job_no}")
        mopa_original_ro = st.checkbox("MOPAR + Original RO", key=f"mopa_{job_no}")

    if alignment_involved and not alignment_report_attached:
        st.error("Hard stop: alignment printout report must be attached to the repair order.")
    if warranty_add_on and not manager_approval:
        st.error(
            f"Hard stop: W+ add-on requires {service_manager_signoff_phrase()} sign-off before submission."
        )

    preview_job = {
        "concern": concern,
        "cause": cause,
        "correction": correction,
        "oil_leak": oil_leak,
        "oil_dye_billed": oil_dye_billed,
        "battery_replacement": battery_replacement,
        "battery_test_slip": battery_test_slip,
        "sublet_repair": sublet_repair,
        "rental_involved": rental_involved,
        "warranty_add_on": warranty_add_on,
        "ac_repair": ac_repair,
        "ac_evac_slip": ac_evac_slip,
        "parts_warranty": parts_warranty,
        "alignment_involved": alignment_involved,
    }
    current_job_preview = {
        "concern": concern,
        "cause": cause,
        "correction": correction,
    }

    st.markdown(
        '<div class="review-job-coaching-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    applicable_manual = find_applicable_manual_sections(preview_job)
    render_applicable_manual_sections(
        applicable_manual,
        key_prefix=f"live_manual_{job_no}_{fv}",
    )
    similar_claims = find_similar_paid_claims(current_job_preview)
    render_narrative_gap_coach(current_job_preview, similar_claims, job_no)
    similar_declined = find_similar_declined_claims(current_job_preview)
    render_declined_claim_alert(current_job_preview, similar_declined)

    job = {
        "job_no": str(job_no),
        "concern": concern,
        "cause": cause,
        "correction": correction,
        "operation_code": str(operation_code or "").strip(),
        "tech_flagged_time": tech_flagged_time,
        "time_allotted": time_allotted,
        "claim_value": claim_value,
        "oil_leak": oil_leak,
        "oil_dye_billed": oil_dye_billed,
        "battery_replacement": battery_replacement,
        "battery_test_slip": battery_test_slip,
        "sublet_repair": sublet_repair,
        "sublet_vin": sublet_vin,
        "sublet_mileage": sublet_mileage,
        "sublet_notes": sublet_notes,
        "rental_involved": rental_involved,
        "rental_days": rental_days,
        "manager_signed_rental": manager_signed_rental,
        "warranty_add_on": warranty_add_on,
        "manager_approval": manager_approval,
        "ac_repair": ac_repair,
        "ac_evac_slip": ac_evac_slip,
        "parts_warranty": parts_warranty,
        "mopa_original_ro": mopa_original_ro,
        "alignment_involved": alignment_involved,
        "alignment_report_attached": alignment_report_attached,
    }
    return job, time_bypass, time_bypass_user


def render_pending_claims():
    st.header("Pending Claims")
    st.caption(
        "Repair orders saved in RO Shield that have **not** been marked paid or rejected by the OEM yet. "
        "Open one in **Review** to fix audit issues and update the saved record — no retyping required."
    )

    df = load_reviews()
    if df.empty:
        st.info("No saved reviews yet.")
        return

    pending = _pending_claims_dataframe(df)
    if pending.empty:
        st.success("No open claims — every saved review has a recorded OEM outcome.")
        return

    hard_stop_count = int(pending.get("status", pd.Series(dtype=str)).astype(str).str.contains("DO NOT SUBMIT", na=False).sum())
    needs_review_count = int(pending.get("status", pd.Series(dtype=str)).astype(str).str.contains("NEEDS REVIEW", na=False).sum())

    render_metric_rows([
        [
            ("Open Claims", f"{len(pending):,}"),
            ("Do Not Submit", f"{hard_stop_count:,}"),
            ("Needs Review", f"{needs_review_count:,}"),
        ],
    ])

    loaded_ro = str(st.session_state.get("loaded_review_ro") or "").strip()
    if loaded_ro:
        st.success(
            f"**RO {loaded_ro}** is loaded on the **Review** tab. "
            "Fix the issues there, then click **Update Review + Re-run Audit**."
        )
        if st.button("Clear loaded RO notice", key="pending_clear_loaded_notice"):
            st.session_state.pop("loaded_review_ro", None)
            st.session_state.pop("loaded_review_id", None)
            st.rerun()

    table_view = pending.copy()
    if "created_at" in table_view.columns:
        table_view["created_at"] = pd.to_datetime(
            table_view["created_at"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
    table_cols = [
        c
        for c in ("created_at", "ro_number", "advisor", "total_claim_value", "status", "score")
        if c in table_view.columns
    ]
    pending_export = table_view[table_cols] if table_cols else table_view
    render_branded_report_table(
        pending_export,
        pdf_title="RO GUARD Pending Claims Queue",
        period_label=period_label_from_df(pending, default="Current pending queue"),
        pdf_subtitle="Pending Claims",
        pdf_filename="RO_Guard_Pending_Claims.pdf",
        csv_filename="RO_Guard_Pending_Claims.csv",
        export_key="pending_claims_queue",
    )

    if "id" not in pending.columns:
        st.warning("Review IDs are missing — refresh after Supabase is up to date.")
        return

    option_rows = pending.to_dict("records")
    option_ids = [int(row["id"]) for row in option_rows]
    label_by_id = {int(row["id"]): _review_option_label(row) for row in option_rows}

    selected_id = st.selectbox(
        "Select claim to open",
        options=option_ids,
        format_func=lambda rid: label_by_id.get(int(rid), str(rid)),
        key="pending_claims_review_id",
    )
    selected = next(row for row in option_rows if int(row["id"]) == int(selected_id))

    info_cols = st.columns(4)
    info_cols[0].metric("RO", str(selected.get("ro_number") or "—"))
    info_cols[1].metric("Advisor", str(selected.get("advisor") or "—"))
    info_cols[2].metric(
        "Claim Value",
        f"${float(selected.get('total_claim_value') or 0):,.2f}",
    )
    info_cols[3].metric("Audit Status", str(selected.get("status") or "—"))

    st.caption(
        f"OEM outcome: **{review_outcome_label(selected.get('first_pass_paid'), selected.get('rejected'), selected.get('paid_after_rejection'))}** · "
        f"{len(_parse_review_jobs(selected))} job(s) on file"
    )

    if st.button("Open in Review for editing", type="primary", key="pending_open_in_review"):
        if _open_review_for_editing(int(selected_id)):
            st.rerun()
        else:
            st.error("Could not load that review. Try refreshing the page.")


def render_review():
    _ensure_review_form_session()
    st.markdown(
        '<div class="review-workspace-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )

    pending_review = st.session_state.pop("_pending_review_load", None)
    if pending_review is not None:
        _apply_saved_review_to_form(pending_review, st.session_state.form_version)

    _render_review_open_claims_strip()

    with st.expander(
        "Scan Repair Order & Invoice",
        expanded=bool(st.session_state.get("ro_scan_summary")),
    ):
        _render_ro_scanner()

    _, next_col = st.columns([5, 1])
    with next_col:
        if st.button("Next Claim"):
            fv = st.session_state.form_version
            st.session_state.pop(f"vin_recall_result_{fv}", None)
            st.session_state.pop(f"vin_recall_tracked_vin_{fv}", None)
            st.session_state.pop(_vin_recall_skip_fetch_key(fv), None)
            for key in (
                _active_review_id_key(fv),
                _active_review_ro_key(fv),
                _active_review_vin_key(fv),
            ):
                st.session_state.pop(key, None)
            st.session_state.form_version += 1
            st.session_state.pop("_ro_scan_advisor", None)
            st.session_state.pop("_ro_scan_technician", None)
            st.session_state.pop("ro_scan_summary", None)
            st.session_state.pop("loaded_review_ro", None)
            st.session_state.pop("loaded_review_id", None)
            st.rerun()

    if "job_count" not in st.session_state:
        st.session_state.job_count = 1

    sw_settings = load_smart_warranty_settings(supabase)
    sw_level = sw_settings.get("smart_warranty_level", "base")
    smart_warranty_time_exempt = smart_warranty_punch_exempt(sw_level)
    audit_rules = load_audit_rules(supabase)
    rejection_library = load_rejection_reason_library(supabase)
    rental_dollars_per_day = float(audit_rules["thresholds"].get("rental_dollars_per_day", 0) or 0)

    if smart_warranty_time_exempt:
        st.caption(
            f"Smart Warranty **{sw_level.title()}** — time punch validation waived (Plus/Premium)."
        )
    else:
        st.caption(
            f"Smart Warranty **Base** — tech flagged time vs. time allotted validation applies."
        )

    job_count = st.number_input(
        "How many warranty jobs are on this RO?",
        min_value=1,
        max_value=10,
        step=1,
        key="job_count",
    )
    multi_job = int(job_count) > 1
    fv = st.session_state.form_version

    ro_number, vin = _render_paired_fields_with_copy(
        "RO Number",
        f"copy_ro_number_{fv}",
        lambda: st.text_input(
            "RO Number",
            key=f"ro_number_{fv}",
            label_visibility="collapsed",
        ),
        "VIN",
        f"copy_vin_{fv}",
        lambda: st.text_input(
            "VIN",
            key=f"vin_{fv}",
            label_visibility="collapsed",
        ),
    )
    ro_invoiced, day_submitted = _render_paired_fields_with_copy(
        "RO Invoiced / Closed Date",
        f"copy_ro_invoiced_{fv}",
        lambda: st.date_input(
            "RO Invoiced / Closed Date",
            key=f"ro_invoiced_{fv}",
            label_visibility="collapsed",
        ),
        "Day Submitted",
        f"copy_day_submitted_{fv}",
        lambda: st.date_input(
            "Day Submitted",
            key=f"day_submitted_{fv}",
            label_visibility="collapsed",
        ),
        left_format_copy=_format_dc_copy_date,
        right_format_copy=_format_dc_copy_date,
    )

    render_vin_recall_panel(vin, st.session_state.form_version, job_count)

    live_summary = compute_live_audit_summary(
        st.session_state.form_version,
        int(job_count),
        vin,
        smart_warranty_time_exempt=smart_warranty_time_exempt,
        audit_rules=audit_rules,
    )
    render_live_submit_status_bar(live_summary)

    oem_paid_amount = None
    short_pay_reason = ""
    submitted_claim = 0.0
    with st.expander("Claim outcome (optional — save here or in Reporting)", expanded=False):
        st.caption(
            "Record the Stellantis result when you know it. Leave all unchecked if the claim "
            "is still pending. Click **Save outcome** to update the saved review without re-running "
            "the audit, or save together with **Run Audit + Save Review** below. "
            "**Reporting** still offers bulk outcome updates."
        )
        fv = st.session_state.form_version
        first_pass_paid = st.checkbox(
            "Paid on First Submission",
            key=f"first_pass_paid_{fv}",
        )

        rejected = st.checkbox(
            "Rejected / Returned",
            key=f"rejected_{fv}",
        )

        paid_after_rejection = st.checkbox(
            "Rejected — paid after first submission",
            key=f"paid_after_rejection_{fv}",
            help="Use when the claim was declined initially but later paid after correction.",
        )

        rejection_reason = ""
        initial_decline_reason = ""
        if rejected:
            reason_labels = active_rejection_reason_labels(rejection_library)
            if not reason_labels:
                reason_labels = active_rejection_reason_labels({})

            selected_reason = st.selectbox(
                "Rejection Reason",
                options=[""] + reason_labels,
                key=f"rejection_reason_select_{fv}",
                help="Standard reasons are managed under Admin → Rejection Reason Library.",
            )
            rejection_notes = st.text_input(
                "Additional rejection notes (optional)",
                key=f"rejection_reason_notes_{fv}",
                placeholder="Required for 'Other' — optional detail for any reason.",
            )
            if selected_reason:
                ok_reason, composed = _compose_rejection_reason(selected_reason, rejection_notes)
                if ok_reason:
                    rejection_reason = composed
                else:
                    st.warning(composed)

        if paid_after_rejection:
            initial_decline_reason = st.text_area(
                "Why was it initially declined?",
                key=f"initial_decline_reason_{fv}",
                placeholder="Enter the OEM decline reason from the first submission.",
                height=100,
            )
            if not str(initial_decline_reason or "").strip():
                st.warning("Enter why the claim was initially declined.")

        submitted_claim = _form_submitted_claim_value(int(st.session_state.get("job_count", 1)))
        oem_paid_amount = None
        short_pay_reason = ""
        if first_pass_paid or paid_after_rejection:
            oem_paid_amount, short_pay_reason = _render_oem_paid_amount_input(
                submitted=submitted_claim,
                key=f"review_oem_paid_{fv}",
                current=st.session_state.get(f"loaded_oem_paid_{fv}"),
                current_reason=st.session_state.get(f"loaded_short_pay_reason_{fv}", ""),
            )

        outcome_selected = sum(
            bool(x) for x in (first_pass_paid, rejected, paid_after_rejection)
        )
        if outcome_selected > 1:
            st.error(
                "Choose only one outcome — **First-Pass Paid**, **Rejected / Returned**, "
                "or **Rejected — paid after first submission** — or leave all unchecked if still pending."
            )

        saved_review_id = _resolve_review_id_for_outcome(fv, ro_number, vin)
        if saved_review_id:
            st.caption(
                "Saved review on file for this RO. "
                f"Selected outcome: **{review_outcome_label(first_pass_paid, rejected, paid_after_rejection)}**."
            )
        else:
            st.caption(
                "Run **Run Audit + Save Review** once before **Save outcome** can update Reporting."
            )

        if st.button(
            "Save outcome",
            key=f"save_review_outcome_{fv}",
            type="secondary",
            use_container_width=True,
        ):
            if not is_signed_in():
                st.warning("Sign in with your dealership account before saving outcomes.")
            else:
                ok_outcome, parsed_or_msg = _parse_review_outcome_selection(
                    first_pass_paid=first_pass_paid,
                    rejected=rejected,
                    paid_after_rejection=paid_after_rejection,
                    rejection_reason=rejection_reason,
                    initial_decline_reason=str(initial_decline_reason or ""),
                    oem_paid_amount=oem_paid_amount,
                    short_pay_reason=short_pay_reason,
                    submitted_claim_value=submitted_claim,
                )
                if not ok_outcome:
                    st.error(parsed_or_msg)
                elif _persist_review_outcome(
                    fv,
                    ro_number,
                    vin,
                    parsed_or_msg,
                    submitted_claim_value=submitted_claim,
                ):
                    st.rerun()

    days_to_submit = (day_submitted - ro_invoiced).days
    st.caption(f"Days to submit: **{days_to_submit}**")

    advisor_list = review_personnel_names("Advisor")

    scan_advisor = st.session_state.pop("_ro_scan_advisor", None)
    matched_advisor = _match_personnel_name(scan_advisor, advisor_list) if scan_advisor else None
    if matched_advisor:
        st.session_state[f"advisor_{st.session_state.form_version}"] = matched_advisor
    else:
        loaded_advisor = st.session_state.pop("_loaded_review_advisor", None)
        matched_advisor = _match_personnel_name(loaded_advisor, advisor_list) if loaded_advisor else None
        if matched_advisor:
            st.session_state[f"advisor_{st.session_state.form_version}"] = matched_advisor

    tech_list = review_personnel_names("Technician")

    scan_technician = st.session_state.pop("_ro_scan_technician", None)
    matched_technician = _match_personnel_name(scan_technician, tech_list) if scan_technician else None
    if matched_technician:
        st.session_state[f"technician_{st.session_state.form_version}"] = matched_technician
    else:
        loaded_technician = st.session_state.pop("_loaded_review_technician", None)
        matched_technician = _match_personnel_name(loaded_technician, tech_list) if loaded_technician else None
        if matched_technician:
            st.session_state[f"technician_{st.session_state.form_version}"] = matched_technician

    warranty_list = review_personnel_names("Warranty Admin")
    loaded_warranty = st.session_state.pop("_loaded_review_warranty_admin", None)
    matched_warranty = _match_personnel_name(loaded_warranty, warranty_list) if loaded_warranty else None
    if matched_warranty:
        st.session_state[f"warranty_admin_{fv}"] = matched_warranty

    person_col1, person_col2, person_col3 = st.columns(3)
    with person_col1:
        advisor = st.selectbox(
            "Advisor",
            advisor_list,
            key=f"advisor_{fv}",
        )
    with person_col2:
        technician = st.selectbox(
            "Technician",
            tech_list,
            key=f"technician_{fv}",
        )
    with person_col3:
        warranty_admin = st.selectbox(
            "Warranty Admin",
            warranty_list,
            key=f"warranty_admin_{fv}",
        )

    sm_names = service_manager_names()
    if sm_names:
        loaded_manager = st.session_state.pop("_loaded_review_service_manager", None)
        matched_manager = _match_personnel_name(loaded_manager, sm_names) if loaded_manager else None
        if matched_manager:
            st.session_state[f"service_manager_{fv}"] = matched_manager
        service_manager = st.selectbox(
            service_manager_selectbox_label(),
            sm_names,
            key=f"service_manager_{fv}",
        )
    else:
        st.session_state.pop("_loaded_review_service_manager", None)
        service_manager = ""
        st.caption("Add a **Manager** under Admin → Personnel to show the service manager on this RO.")
 
    st.markdown("---")
    st.subheader("Warranty Jobs")
    if multi_job:
        st.caption(
            "Use the tabs below to work one job at a time. **Stop / Review / OK** shows each job's live audit status."
        )

    jobs = []
    time_bypass = False
    time_bypass_user = ""

    if multi_job:
        job_numbers = list(range(1, int(job_count) + 1))
        tab_labels = [
            _review_job_tab_label(
                fv,
                job_no,
                smart_warranty_time_exempt=smart_warranty_time_exempt,
                audit_rules=audit_rules,
            )
            for job_no in job_numbers
        ]
        for job_no, tab in zip(job_numbers, st.tabs(tab_labels)):
            with tab:
                job, job_bypass, job_bypass_user = _render_review_job_panel(
                    job_no,
                    form_version=fv,
                    smart_warranty_time_exempt=smart_warranty_time_exempt,
                    rental_dollars_per_day=rental_dollars_per_day,
                )
                if job_no == 1:
                    time_bypass = job_bypass
                    time_bypass_user = job_bypass_user
                jobs.append(job)
    else:
        job, time_bypass, time_bypass_user = _render_review_job_panel(
            1,
            form_version=fv,
            smart_warranty_time_exempt=smart_warranty_time_exempt,
            rental_dollars_per_day=rental_dollars_per_day,
        )
        jobs.append(job)

    st.markdown("**Dealer Connect**")
    with st.container():
        st.markdown(
            '<div class="dealer-connect-workspace-marker" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        fv = st.session_state.form_version
        dc_expand_all = False
        if _dealer_connect_has_copy_sections(jobs, ro_number=ro_number, vin=vin):
            dc_expand_all = st.checkbox(
                "Expand all for copying into Dealer Connect",
                key=f"dc_expand_all_{fv}",
            )
        _render_paid_labor_op_helper(jobs, expand_all=dc_expand_all)
        _render_dealer_connect_job_lines_export(
            jobs,
            ro_number=ro_number,
            vin=vin,
            expand_all=dc_expand_all,
        )
        _inject_dealer_connect_expander_header_fix(st.session_state.get("appearance", "Dark"))

    st.markdown("---")

    recall_audit_block = _vin_recall_blocks_audit(st.session_state.form_version, vin, job_count)
    if recall_audit_block:
        st.caption("Open the recall alert above and acknowledge before running the audit.")

    sign_in_required = not is_signed_in()
    if sign_in_required:
        st.warning("Sign in with your dealership account before running the audit.")

    fv = st.session_state.form_version
    will_update_review = _review_will_update(fv, ro_number, vin)
    save_button_label = (
        "Update Review + Re-run Audit"
        if will_update_review
        else "Run Audit + Save Review"
    )
    if will_update_review and not _resolve_session_review_id(fv, ro_number, vin):
        st.caption(
            "A review for this RO is already on file — saving will update that record, "
            "not create a duplicate."
        )

    if st.button(
        save_button_label,
        type="primary",
        use_container_width=True,
        disabled=recall_audit_block or sign_in_required,
    ):
        ok_outcome, parsed_or_msg = _parse_review_outcome_selection(
            first_pass_paid=first_pass_paid,
            rejected=rejected,
            paid_after_rejection=paid_after_rejection,
            rejection_reason=rejection_reason,
            initial_decline_reason=str(initial_decline_reason or ""),
            oem_paid_amount=oem_paid_amount,
            short_pay_reason=short_pay_reason,
            submitted_claim_value=total_value,
        )
        if not ok_outcome:
            st.error(f"Fix claim outcome before saving: {parsed_or_msg}")
        else:
            outcome = parsed_or_msg
            all_hard = []
            all_warn = []
            scores = []

            total_value = sum(
                float(j.get("claim_value") or 0)
                for j in jobs
            )

            hard_value = 0.0

            for job in jobs:
                hard, warn, score = audit_job(
                    job,
                    time_bypass,
                    smart_warranty_time_exempt=smart_warranty_time_exempt,
                    audit_rules=audit_rules,
                )

                job["hard_stops"] = hard
                job["warnings"] = warn
                job["score"] = score

                scores.append(score)
                all_hard.extend(hard)
                all_warn.extend(warn)

                if hard:
                    hard_value += float(job.get("claim_value") or 0)

            final_score = int(sum(scores) / len(scores)) if scores else 0

            status = (
                "🔴 DO NOT SUBMIT"
                if all_hard
                else (
                    "🟡 NEEDS REVIEW"
                    if all_warn
                    else "🟢 READY"
                )
            )

            result_banner(status)

            recall_result = st.session_state.get(f"vin_recall_result_{st.session_state.form_version}")
            if recall_result and recall_result.get("ok"):
                related = _actionable_vin_recalls(
                    st.session_state.form_version,
                    job_count,
                    recall_result,
                )
                if related:
                    st.markdown("### VIN Recall Alert")
                    for recall in related[:3]:
                        st.warning(
                            f"NHTSA recall **{recall.get('campaign', '—')}** "
                            f"({recall.get('component', '')}) may apply to this repair. "
                            "Verify open status in OASIS / wiTECH before warranty submit."
                        )

            x1, x2, x3, x4, x5 = st.columns([1.1, 1.3, 1.7, 1.7, 1.2])

            x1.metric("Audit Score", final_score)
            x2.metric("Status", status)
            x3.metric("Total Claim Value", f"${total_value:,.2f}")
            x4.metric("Hard Stop Value", f"${hard_value:,.2f}")
            x5.metric("Hard Stops", len(all_hard))

            for job in jobs:
                with st.container(border=True):
                    st.markdown(
                        f'<div class="audit-job-result-header">Job {job["job_no"]} Results</div>',
                        unsafe_allow_html=True,
                    )
                    for h in job.get("hard_stops", []):
                        st.error(finding_message(h))

                    for w in job.get("warnings", []):
                        st.warning(finding_message(w))

                    render_applicable_manual_sections(
                        job.get("manual_sections", []),
                        key_prefix=f"audit_manual_{job['job_no']}",
                    )

                    if not job.get("hard_stops") and not job.get("warnings"):
                        st.success("No audit issues found.")

            report_payload = {
                "ro_number": ro_number,
                "vin": vin,
                "ro_invoiced": str(ro_invoiced),
                "day_submitted": str(day_submitted),
                "days_to_submit": days_to_submit,
                "first_pass_paid": outcome["first_pass_paid"],
                "rejected": outcome["rejected"],
                "paid_after_rejection": outcome["paid_after_rejection"],
                "rejection_reason": outcome["rejection_reason"],
                "oem_paid_amount": outcome.get("oem_paid_amount"),
                "short_pay_reason": outcome.get("short_pay_reason"),
                "advisor": advisor,
                "technician": technician,
                "warranty_admin": warranty_admin,
                "manager": service_manager,
                "score": final_score,
                "status": status,
                "total_claim_value": total_value,
                "hard_stop_value": hard_value,
                "hard_stop_count": len(all_hard),
                "warning_count": len(all_warn),
                "time_bypass": False if smart_warranty_time_exempt else time_bypass,
                "time_bypass_user": "" if smart_warranty_time_exempt else time_bypass_user,
                "entered_by": current_person_name(),
                "jobs": jobs,
                **_vin_recall_save_fields(st.session_state.form_version, vin, job_count),
            }

            session_review_id = _resolve_session_review_id(fv, ro_number, vin)
            save_result = save_review(report_payload, review_id=session_review_id)
            if save_result.get("ok"):
                invalidate_reviews_cache()
                saved_review_id = save_result.get("review_id")
                if saved_review_id:
                    st.session_state[_active_review_id_key(fv)] = int(saved_review_id)
                    st.session_state[_active_review_ro_key(fv)] = str(ro_number or "").strip()
                    st.session_state[_active_review_vin_key(fv)] = str(vin or "").strip()
                if save_result.get("created"):
                    st.success("Review saved to Reporting (Supabase).")
                else:
                    st.success("Review updated in Reporting — no duplicate was created.")

            try:
                safe_ro = re.sub(r"[^\w\-]+", "_", str(ro_number or "audit")).strip("_") or "audit"
                render_branded_pdf_download(
                    pdf_builder=lambda payload=report_payload: build_audit_report_pdf(payload),
                    pdf_filename=f"RO_Guard_Audit_{safe_ro}.pdf",
                    export_key=f"audit_pdf_{st.session_state.form_version}",
                    caption="Branded RO GUARD warranty audit PDF with ROGUARD watermark.",
                    label="Download Audit PDF",
                )
            except Exception as e:
                st.warning(f"Audit PDF could not be generated: {e}")

   

def _process_claim_pdf_upload(files, *, outcome: str, summary_key: str, nonce_key: str) -> None:
    totals = {"parsed": 0, "saved": 0, "duplicate": 0, "skipped": 0, "errors": 0, "updated": 0}
    per_file = []
    pdf_diagnostics: list[str] = []
    for f in files:
        if outcome == "declined":
            claims, document_text, pdf_info = prepare_declined_pdf_claims(f)
            page_count = pdf_info.get("page_count", 0)
            if not pdf_info.get("has_message_codes"):
                pdf_diagnostics.append(
                    f"**{f.name}:** No Message Code Information found in PDF text. "
                    "Try opening each declined claim in Dealer Connect → Claim Inquiry → Print/Save "
                    "so the export includes the Message Code Information page."
                )
            elif pdf_info.get("servlet_export"):
                pdf_diagnostics.append(
                    f"**{f.name}:** AcknowledgementServlet batch export detected — "
                    f"{pdf_info.get('claim_segments', 0)} claims grouped with message codes."
                )
            elif pdf_info.get("ocr_used"):
                pdf_diagnostics.append(
                    f"**{f.name}:** Message codes found using OCR ({pdf_info.get('claim_segments', 0)} segments)."
                )
        else:
            pages = extract_pages(f)
            document_text = "\n\n".join(pages)
            claims = split_claims_from_pages(pages)
            pdf_info = {}
            page_count = len(pages)
        stats = save_learned_claims(f.name, claims, outcome=outcome, document_text=document_text)
        for key in totals:
            totals[key] += stats.get(key, 0)
        per_file.append(
            f"**{f.name}:** {page_count} pages → {stats['parsed']} parsed → "
            f"**{stats['saved']} saved**, {stats.get('updated', 0)} updated, "
            f"{stats['duplicate']} duplicates, "
            f"{stats['skipped']} skipped, {stats['errors']} errors"
        )
    st.session_state[summary_key] = {
        "totals": totals,
        "per_file": per_file,
        "outcome": outcome,
        "diagnostics": pdf_diagnostics,
    }
    st.session_state[nonce_key] = int(st.session_state.get(nonce_key, 0)) + 1
    st.rerun()


def _render_claim_upload_summary(summary_key: str, clear_button_key: str) -> None:
    last_summary = st.session_state.get(summary_key)
    if not last_summary:
        return
    for line in last_summary.get("per_file", []):
        st.success(line)
    for line in last_summary.get("diagnostics", []):
        st.warning(line)
    totals = last_summary.get("totals") or {}
    st.info(
        f"Upload summary: **{totals.get('saved', 0)} new records saved** to your library "
        f"(from {totals.get('parsed', 0)} parsed segments). "
        f"{totals.get('duplicate', 0)} were already in the library, "
        f"{totals.get('skipped', 0)} did not pass narrative quality checks."
    )
    if st.button("Clear upload results", key=clear_button_key):
        st.session_state.pop(summary_key, None)
        st.rerun()


def _render_claim_library_table(
    df: pd.DataFrame,
    *,
    outcome: str,
    metric_label: str,
    empty_message: str,
    purge_key: str,
) -> None:
    scoped = _claims_for_outcome(df, outcome)
    useful_df = filter_useful_learned_claims(scoped) if outcome != "declined" else scoped.copy()
    if outcome == "declined" and not scoped.empty:
        with_reason = scoped[
            scoped.apply(lambda row: bool(_decline_reason_value(row.to_dict())), axis=1)
        ]
        if not with_reason.empty:
            useful_df = scoped.copy()

    hidden_junk = max(0, len(scoped) - len(useful_df)) if outcome != "declined" else 0
    st.metric(metric_label, len(useful_df))
    if outcome == "declined":
        coded = int(
            useful_df.apply(lambda row: bool(_decline_reason_value(row.to_dict())), axis=1).sum()
        ) if not useful_df.empty else 0
        wam_hits = int(
            useful_df.apply(lambda row: bool(_declined_wam_reference(row.to_dict())), axis=1).sum()
        ) if not useful_df.empty else 0
        st.caption(
            f"{coded} with message codes · {wam_hits} with WAM reference. "
            "Upload on this **Declined Claims** tab (not Paid Claims). "
            "Export from Dealer Connect must include the **Message Code Information** page."
        )
        if not useful_df.empty and coded == 0:
            st.warning(
                "No message codes found yet. Re-upload the PDF on this tab, or click "
                "**Reprocess Existing Claims** after confirming the PDF includes Message Code Information."
            )
    elif hidden_junk:
        st.caption(
            f"Hiding {hidden_junk} non-warranty or blank record(s) "
            f"(loaner/rental, recalls, oil changes, admin lines, or missing narratives)."
        )

    if user_can_admin_write() and not scoped.empty:
        if st.button("Remove junk from this library", key=purge_key):
            removed = 0
            for _, row in scoped.iterrows():
                row_dict = row.to_dict()
                if learned_claim_is_useful(row_dict):
                    continue
                if outcome == "declined" and _decline_reason_value(row_dict):
                    continue
                try:
                    supabase.table("claims").delete().eq("id", int(row["id"])).execute()
                    removed += 1
                except Exception as e:
                    st.warning(f"Could not remove claim {row.get('id')}: {e}")
            st.success(f"Removed {removed} junk record(s) from the library.")
            st.rerun()

    if useful_df.empty:
        st.info(empty_message)
        return

    if outcome == "declined":
        table_df = useful_df.copy()
        table_df["decline_reason"] = table_df.apply(
            lambda row: _decline_reason_value(row.to_dict()), axis=1
        )
        table_df["wam_issue"] = table_df.apply(
            lambda row: _declined_issue_summary(row.to_dict()), axis=1
        )
        if "vin" in table_df.columns:
            table_df["claim_ro"] = table_df["vin"].fillna("").astype(str)
        if "wam_reference" in table_df.columns:
            table_df["wam_reference"] = table_df["wam_reference"].fillna("").astype(str)
        display_cols = [
            c
            for c in [
                "claim_ro",
                "ro_number",
                "wam_reference",
                "wam_issue",
                "decline_reason",
                "concern",
                "correction",
                "labor_ops",
                "created_at",
            ]
            if c in table_df.columns
        ]
        export_df = table_df[display_cols].fillna("") if display_cols else table_df.fillna("")
        render_branded_report_table(
            export_df,
            pdf_title="RO GUARD Declined Claims Library",
            period_label=period_label_from_df(useful_df, default="Declined claims library"),
            pdf_subtitle="Claim Learning",
            pdf_landscape=True,
            pdf_filename="RO_Guard_Declined_Claims_Library.pdf",
            csv_filename="RO_Guard_Declined_Claims_Library.csv",
            export_key=f"claim_library_declined_{outcome}",
        )
        return

    display_cols = [
        c
        for c in [
            "ro_number",
            "reference" if outcome == "declined" else None,
            "concern",
            "cause",
            "correction",
            "labor_ops",
            "parts",
            "wam_reference",
            "created_at",
        ]
        if c and c in useful_df.columns
    ]
    display_df = useful_df[display_cols] if display_cols else useful_df
    if outcome == "declined" and "reference" in display_df.columns:
        display_df = display_df.rename(columns={"reference": "decline_reason"})
    label = "Paid" if outcome == "paid" else "Declined"
    render_branded_report_table(
        display_df,
        pdf_title=f"RO GUARD {label} Claims Library",
        period_label=period_label_from_df(useful_df, default=f"{label} claims library"),
        pdf_subtitle="Claim Learning",
        pdf_landscape=True,
        pdf_filename=f"RO_Guard_{label}_Claims_Library.pdf",
        csv_filename=f"RO_Guard_{label}_Claims_Library.csv",
        export_key=f"claim_library_{outcome}",
    )


def _render_paid_claims_learning(all_claims: pd.DataFrame) -> None:
    st.markdown(
        """
        <span class="claim-panel-paid-marker" aria-hidden="true"></span>
        <div class="claim-outcome-banner claim-outcome-banner--paid">
            <strong>Paid Claims</strong>
            Build your passed-claim library for the Narrative Gap Coach on Review.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "RO Shield reads all pages and builds a **passed claim** library for the Narrative Gap Coach on Review."
    )

    if "paid_claim_upload_nonce" not in st.session_state:
        st.session_state.paid_claim_upload_nonce = 0

    files = st.file_uploader(
        "Upload paid claim PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"paid_claim_upload_{st.session_state.paid_claim_upload_nonce}",
    )
    if files:
        _process_claim_pdf_upload(
            files,
            outcome="paid",
            summary_key="claim_upload_last_summary_paid",
            nonce_key="paid_claim_upload_nonce",
        )

    _render_claim_upload_summary("claim_upload_last_summary_paid", "clear_claim_upload_summary_paid")
    _render_claim_library_table(
        all_claims,
        outcome="paid",
        metric_label="Paid Claim Records",
        empty_message="No paid claims in your library yet. Upload paid warranty claim PDFs from Dealer Connect.",
        purge_key="purge_junk_paid_claims",
    )


def _render_declined_claims_learning(all_claims: pd.DataFrame) -> None:
    st.markdown(
        """
        <span class="claim-panel-declined-marker" aria-hidden="true"></span>
        <div class="claim-outcome-banner claim-outcome-banner--declined">
            <strong>Declined / Rejected Claims</strong>
            Build your rejection library — message codes, WAM references, and decline reasons for Review alerts.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "RO Shield extracts **WAM references**, **message codes**, and a short **WAM issue** summary — "
        "then warns on **Review** when a job looks similar to a past rejection."
    )
    with st.expander("Which Dealer Connect PDF should I upload?", expanded=False):
        st.markdown(
            """
            Use the **individual declined claim printout** that includes the **Message Code Information**
            section (RE5, LG4, etc.) — not the bulk **AcknowledgementServlet** narrative batch if that
            export omits message codes.

            **Recommended path:** Dealer Connect → Warranty → Claim Inquiry → open the declined claim →
            Print/Save PDF (confirm Message Code Information appears in the preview) → upload here.
            """
        )

    if "declined_claim_upload_nonce" not in st.session_state:
        st.session_state.declined_claim_upload_nonce = 0
    if ocr_available():
        st.caption("OCR is available — scanned PDFs can be read when message codes are not in the text layer.")
    else:
        st.caption(
            "OCR is not available on this server. PDFs must have selectable text (not scanned images) "
            "for message codes to import."
        )

    files = st.file_uploader(
        "Upload declined claim PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"declined_claim_upload_{st.session_state.declined_claim_upload_nonce}",
    )
    if files:
        _process_claim_pdf_upload(
            files,
            outcome="declined",
            summary_key="claim_upload_last_summary_declined",
            nonce_key="declined_claim_upload_nonce",
        )

    _render_claim_upload_summary("claim_upload_last_summary_declined", "clear_claim_upload_summary_declined")

    if user_can_admin_write():
        declined_count = len(_claims_for_outcome(all_claims, "declined"))
        if declined_count:
            st.markdown("---")
            st.caption(f"{declined_count} declined record(s) in your library.")
            confirm_clear = st.checkbox(
                "Permanently remove all declined claims from the library",
                key="confirm_clear_all_declined_claims",
            )
            if st.button(
                "Clear all declined claims",
                type="primary",
                disabled=not confirm_clear,
                key="clear_all_declined_claims_btn",
            ):
                result = clear_all_declined_claims()
                if result["removed"] > 0:
                    st.success(f"Removed {result['removed']} declined claim record(s).")
                    st.rerun()
                elif result["errors"]:
                    st.error(
                        "Could not remove declined claims. Run "
                        "`docs/CLEAR_DECLINED_CLAIMS.sql` in Supabase SQL Editor once, then retry."
                    )
                else:
                    st.info("No declined claims to remove.")

    _render_claim_library_table(
        all_claims,
        outcome="declined",
        metric_label="Declined Claim Records",
        empty_message=(
            "No declined claims in your library yet. Upload declined/returned warranty claim PDFs "
            "from Dealer Connect."
        ),
        purge_key="purge_junk_declined_claims",
    )


def render_claims():
    st.header("Claim Learning")
    st.caption(
        "Build two libraries from Dealer Connect: **paid claims** show what passed; "
        "**declined claims** show what to avoid before submit."
    )

    if st.button("Clear Claim Learning Cache"):
        try:
            st.cache_data.clear()
        except Exception:
            pass

        for key in list(st.session_state.keys()):
            if "claim" in key.lower():
                del st.session_state[key]

        st.session_state.paid_claim_upload_nonce = 0
        st.session_state.declined_claim_upload_nonce = 0
        st.success("Claim learning cache cleared. Refresh the app and re-upload claims.")

    if st.button("Reprocess Existing Claims"):
        rows = supabase.table("claims").select("*").limit(10000).execute().data or []
        updated = 0
        backfilled = 0

        declined_by_file: dict[str, list[dict]] = {}
        for row in rows:
            if _claim_status_value(row) != "declined":
                continue
            fname = str(row.get("ro_number") or "").strip()
            declined_by_file.setdefault(fname, []).append(row)

        file_doc_text = {
            fname: "\n\n".join(str(r.get("story") or "") for r in group)
            for fname, group in declined_by_file.items()
        }

        for row in rows:
            story = str(row.get("story", "") or row.get("content", "") or "").strip()
            if not story:
                continue

            try:
                fields = extract_claim_fields(story)
            except Exception as e:
                st.error(f"extract_claim_fields failed: {type(e).__name__}: {e}")
                return

            update_data = {
                "concern": fields.get("concern", ""),
                "cause": fields.get("cause", ""),
                "correction": fields.get("correction", ""),
                "labor_ops": fields.get("labor_ops", ""),
                "parts": fields.get("parts", ""),
                "wam_reference": fields.get("wam_reference", ""),
            }
            if _claim_status_value(row) == "declined":
                fname = str(row.get("ro_number") or "").strip()
                doc_text = file_doc_text.get(fname) or story
                meta = _document_decline_metadata(doc_text)
                update_data["reference"] = meta.get("decline_reason") or row.get("reference", "")
                if meta.get("decline_reason"):
                    update_data["content"] = meta["decline_reason"]
                wam_ref = meta.get("wam_reference") or update_data.get("wam_reference") or ""
                if wam_ref:
                    update_data["wam_reference"] = wam_ref
                    update_data["wam"] = meta.get("wam_summary") or summarize_wam_reference(wam_ref)

            try:
                supabase.table("claims").update(update_data).eq("id", row["id"]).execute()
                updated += 1
            except Exception as e:
                st.warning(f"Could not update claim {row.get('id')}: {e}")

        for fname, doc_text in file_doc_text.items():
            backfilled += _backfill_declined_file_metadata(fname, doc_text)

        st.success(
            f"Reprocessed {updated} learned claim record(s)."
            + (f" Backfilled decline/WAM data on {backfilled} row(s)." if backfilled else "")
        )

    if PdfReader is None:
        st.error("PyPDF2 is not installed. Run: python3 -m pip install -r requirements.txt")
        return

    all_claims = load_shared_claims()
    st.markdown(
        '<span class="claim-learning-tabs-marker" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
    paid_tab, declined_tab = st.tabs(["Paid Claims", "Declined / Rejected Claims"])

    with paid_tab:
        _render_paid_claims_learning(all_claims)

    with declined_tab:
        _render_declined_claims_learning(all_claims)


def render_metric_rows(rows: list[list], *, max_cols: int = 3) -> None:
    """Render dashboard metrics in equal-width rows (max 3 per row) so text is not clipped."""
    for row in rows:
        if not row:
            continue
        for start in range(0, len(row), max_cols):
            chunk = row[start : start + max_cols]
            cols = st.columns(len(chunk))
            for col, item in zip(cols, chunk):
                if len(item) >= 3:
                    label, value, help_text = item[0], item[1], item[2]
                    col.metric(str(label), str(value), help=help_text)
                else:
                    label, value = item[0], item[1]
                    col.metric(str(label), str(value))


def _default_report_date_range() -> tuple[date, date]:
    """Calendar month-to-date (1st of current month through today)."""
    today = date.today()
    return today.replace(day=1), today


def _filter_reviews_by_date(df, key_prefix="report"):
    if df.empty or "created_at" not in df.columns:
        return df
    today = date.today()
    calendar_min = date(today.year - 2, 1, 1)
    date_key = f"{key_prefix}_report_date_mtd_v3"
    if date_key not in st.session_state:
        st.session_state[date_key] = _default_report_date_range()
    date_range = st.date_input(
        "Report Date Range",
        min_value=calendar_min,
        max_value=today,
        key=date_key,
        help="Defaults to month-to-date. Select any range back to January 1, "
        f"{today.year - 2}.",
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range
    return df[
        (df["created_at"].dt.date >= start_date) &
        (df["created_at"].dt.date <= end_date)
    ]


def render_hard_stop_breakdown(df: pd.DataFrame, *, key_prefix: str = "roi") -> None:
    """Rule-level hard stop / warning analytics for manager coaching."""
    breakdown = compute_hard_stop_breakdown(df)
    if breakdown["finding_count"] <= 0:
        st.info(
            "No hard stops or warnings recorded in saved reviews for this period. "
            "Complete audits on the **Review** tab to populate this breakdown."
        )
        return

    st.markdown("### Hard Stop Breakdown")
    st.caption(
        "Which audit rules are firing most — use this to focus advisor and tech coaching."
    )

    severity_filter = st.radio(
        "Show findings",
        options=["All", "Hard stops only", "Warnings only"],
        horizontal=True,
        key=f"{key_prefix}_hs_severity_filter",
    )

    rule_summary = breakdown["rule_summary"].copy()
    advisor_rule = breakdown["advisor_rule_summary"].copy()
    if severity_filter == "Hard stops only":
        rule_summary = rule_summary[rule_summary["severity"] == "hard"]
        advisor_rule = advisor_rule[
            advisor_rule["rule_label"].isin(rule_summary["rule_label"].unique())
        ]
        show_total = int(rule_summary["count"].sum()) if not rule_summary.empty else 0
        show_hard = show_total
        show_warn = 0
    elif severity_filter == "Warnings only":
        rule_summary = rule_summary[rule_summary["severity"] == "warn"]
        advisor_rule = advisor_rule[
            advisor_rule["rule_label"].isin(rule_summary["rule_label"].unique())
        ]
        show_total = int(rule_summary["count"].sum()) if not rule_summary.empty else 0
        show_hard = 0
        show_warn = show_total
    else:
        show_total = breakdown["finding_count"]
        show_hard = breakdown["hard_count"]
        show_warn = breakdown["warn_count"]

    top_rule = "—"
    top_rule_count = 0
    rule_totals = breakdown["rule_totals"]
    if not rule_totals.empty:
        top_row = rule_totals.iloc[0]
        top_rule = str(top_row.get("rule_label", "—"))
        top_rule_count = int(top_row.get("total_count", 0))

    render_metric_rows([
        [
            ("Total Findings", f"{show_total:,}"),
            ("Hard Stops", f"{show_hard:,}"),
            ("Warnings", f"{show_warn:,}"),
        ],
        [
            ("ROs With Issues", f"{breakdown['reviews_with_findings']:,}"),
            ("Top Rule Count", f"{top_rule_count:,}", top_rule),
        ],
    ])

    chart_df = rule_totals.copy()
    if severity_filter == "Hard stops only":
        hard_rules = rule_summary.groupby(["rule_key", "rule_label"], as_index=False).agg(
            total_count=("count", "sum")
        )
        chart_df = hard_rules
    elif severity_filter == "Warnings only":
        warn_rules = rule_summary.groupby(["rule_key", "rule_label"], as_index=False).agg(
            total_count=("count", "sum")
        )
        chart_df = warn_rules

    chart_png = hard_stop_rules_chart(chart_df)
    if chart_png:
        st.image(chart_png, use_container_width=True, caption="Findings by audit rule")

    if breakdown["coaching_priorities"]:
        priority_lines = []
        for item in breakdown["coaching_priorities"][:5]:
            priority_lines.append(
                f"**{item['rule_label']}** — {item['count']} findings ({item['pct']:.1f}% of total)"
            )
        st.markdown("#### Coaching Priorities")
        for line in priority_lines:
            st.markdown(f"- {line}")

    c1, c2 = st.columns(2)
    st.caption("Color bands match Team Performance: red = highest priority, yellow = moderate, green = lower.")
    hs_period = period_label_from_df(df)
    with c1:
        st.markdown("**By Audit Rule**")
        if not rule_summary.empty:
            display_rules = rule_summary.rename(
                columns={
                    "rule_label": "Audit Rule",
                    "severity": "Type",
                    "count": "Count",
                    "pct": "% of Findings",
                }
            )
            display_rules["Type"] = display_rules["Type"].map(
                {"hard": "Hard Stop", "warn": "Warning"}
            )
            rules_export = display_rules[["Audit Rule", "Type", "Count", "% of Findings"]]
            render_branded_report_table(
                _style_audit_rule_breakdown(rules_export),
                export_df=rules_export,
                pdf_title="RO GUARD Hard Stop Breakdown — By Rule",
                period_label=hs_period,
                pdf_subtitle="Hard Stop Breakdown",
                pdf_filename="RO_Guard_Hard_Stop_By_Rule.pdf",
                csv_filename="RO_Guard_Hard_Stop_By_Rule.csv",
                export_key=f"{key_prefix}_hs_by_rule",
            )
        else:
            st.caption("No findings for this filter.")

    with c2:
        st.markdown("**By Advisor (top issues)**")
        if not advisor_rule.empty:
            top_rules = (
                chart_df.sort_values("total_count", ascending=False)
                .head(5)["rule_label"]
                .tolist()
            )
            advisor_pivot = (
                advisor_rule[advisor_rule["rule_label"].isin(top_rules)]
                .pivot_table(
                    index="advisor",
                    columns="rule_label",
                    values="count",
                    aggfunc="sum",
                    fill_value=0,
                )
            )
            advisor_pivot["Total"] = advisor_pivot.sum(axis=1)
            advisor_pivot = advisor_pivot.sort_values("Total", ascending=False).head(8)
            advisor_pivot = advisor_pivot.drop(columns=["Total"])
            render_branded_report_table(
                _style_advisor_rule_pivot(advisor_pivot),
                export_df=advisor_pivot.reset_index(),
                pdf_title="RO GUARD Hard Stop Breakdown — By Advisor",
                period_label=hs_period,
                pdf_subtitle="Hard Stop Breakdown",
                pdf_landscape=True,
                pdf_filename="RO_Guard_Hard_Stop_By_Advisor.pdf",
                csv_filename="RO_Guard_Hard_Stop_By_Advisor.csv",
                export_key=f"{key_prefix}_hs_by_advisor",
            )
        else:
            st.caption("Advisor data will appear once reviews include advisor names.")

    weekly = breakdown["weekly_rule_trend"]
    if not weekly.empty:
        st.markdown("**Trend — top rules by week**")
        pivot_weekly = weekly.pivot_table(
            index="week",
            columns="rule_label",
            values="count",
            aggfunc="sum",
            fill_value=0,
        )
        st.line_chart(pivot_weekly)


def _render_coaching_issue_item(issue, *, advisor: str, index: int) -> None:
    """Render one coaching issue with expandable RO examples."""
    if isinstance(issue, str):
        st.markdown(f"- {issue}")
        return

    label = str(issue.get("label") or "").strip()
    if not label:
        return

    examples = issue.get("examples") or []
    if not examples:
        st.markdown(f"- {label}")
        return

    with st.expander(label, expanded=False):
        st.caption("Review these ROs — note what was missing so the same issue is not repeated.")
        for example in examples:
            ro_number = str(example.get("ro_number") or "—")
            job_nos = example.get("job_nos") or []
            job_label = ", ".join(str(job) for job in job_nos) if job_nos else "—"
            severity = str(example.get("severity") or "warn")
            is_hard = severity == "hard"
            icon = "🔴" if is_hard else "🟡"
            severity_label = "Hard stop" if is_hard else "Warning"

            date_label = ""
            created = example.get("created_at")
            if created is not None and not pd.isna(created):
                try:
                    date_label = pd.to_datetime(created).strftime("%Y/%m/%d")
                except Exception:
                    date_label = str(created)[:10]

            claim_value = float(example.get("claim_value") or 0)
            meta_parts = [f"**{icon} RO {ro_number}**", f"Job {job_label}"]
            if date_label:
                meta_parts.append(date_label)
            if claim_value:
                meta_parts.append(f"${claim_value:,.0f} claim")
            meta_parts.append(severity_label)
            st.markdown(" · ".join(meta_parts))

            for message in example.get("messages") or []:
                st.markdown(f"- {message}")
            st.markdown("")


def render_advisor_coaching_focus(df: pd.DataFrame, advisor_summary: pd.DataFrame) -> None:
    """Show each advisor's specific audit issue areas for manager coaching."""
    breakdown = compute_hard_stop_breakdown(df)
    coaching = breakdown.get("advisor_coaching") or []

    review_lookup: dict[str, dict] = {}
    if advisor_summary is not None and not advisor_summary.empty:
        for _, row in advisor_summary.iterrows():
            name = str(row.get("advisor") or "").strip()
            if not name:
                continue
            review_lookup[name] = {
                "reviews": int(row.get("reviews") or 0),
                "avg_score": float(row.get("avg_score") or 0),
                "hard_stops": int(row.get("hard_stops") or 0),
            }

    st.markdown("**Advisor Coaching Focus**")
    st.caption(
        "Specific areas each advisor needs to tighten — expand an issue to see the RO examples to learn from."
    )

    if coaching:
        for entry in coaching[:12]:
            advisor = entry["advisor"]
            stats = review_lookup.get(advisor, {})
            reviews = stats.get("reviews", entry.get("ros_with_issues", 0))
            avg_score = stats.get("avg_score")
            title_parts = [
                advisor,
                f"{reviews} review(s)",
                f"{entry['ros_with_issues']} RO(s) with issues",
            ]
            if reviews and avg_score:
                title_parts.append(f"avg score {avg_score:.0f}")
            with st.expander(" · ".join(title_parts), expanded=len(coaching) <= 3):
                for index, issue in enumerate(entry["issues"]):
                    _render_coaching_issue_item(issue, advisor=advisor, index=index)
        return

    if advisor_summary is not None and not advisor_summary.empty:
        named = advisor_summary[advisor_summary["advisor"].astype(str).str.strip() != ""]
        if not named.empty:
            st.info(
                "Advisor names are on file, but saved reviews do not yet include job-level hard stops "
                "or warnings. Run **Run Audit + Save Review** on recent ROs to populate coaching areas."
            )
            advisor_export = named.head(8).rename(columns={
                "advisor": "Advisor",
                "reviews": "Reviews",
                "avg_score": "Avg Score",
                "hard_stops": "Hard Stops",
                "protected_value": "Protected $",
                "rejected": "Rejected",
            })
            render_branded_report_table(
                advisor_export,
                pdf_title="RO GUARD Advisor Coaching Summary",
                period_label=period_label_from_df(df),
                pdf_subtitle="Coaching",
                pdf_landscape=True,
                pdf_filename="RO_Guard_Advisor_Coaching_Summary.pdf",
                csv_filename="RO_Guard_Advisor_Coaching_Summary.csv",
                export_key="coaching_advisor_summary",
            )
            return

    st.caption("Advisor coaching areas will appear once reviews include advisor names and audit findings.")


def _top_rules_detail_frame(
    rule_summary: pd.DataFrame,
    advisor_rule: pd.DataFrame,
    *,
    severity: str,
    limit: int = 5,
) -> pd.DataFrame:
    subset = rule_summary[rule_summary["severity"] == severity].head(limit)
    if subset.empty:
        return pd.DataFrame()

    type_total = int(subset["count"].sum())
    rows = []
    for _, row in subset.iterrows():
        rule_label = str(row["rule_label"])
        adv = advisor_rule[advisor_rule["rule_label"] == rule_label]
        rows.append(
            {
                "Audit Rule": rule_label,
                "Type": "Hard Stop" if severity == "hard" else "Warning",
                "Findings": int(row["count"]),
                "% of Type": round(float(row["count"]) / type_total * 100, 1) if type_total else 0.0,
                "Advisors Affected": int(adv["advisor"].nunique()) if not adv.empty else 0,
            }
        )
    return pd.DataFrame(rows)


def _top_rules_advisor_detail_frame(
    rule_summary: pd.DataFrame,
    advisor_rule: pd.DataFrame,
    *,
    severity: str,
    limit: int = 5,
) -> pd.DataFrame:
    top_rules = rule_summary[rule_summary["severity"] == severity].head(limit)
    if top_rules.empty:
        return pd.DataFrame()

    labels = top_rules["rule_label"].tolist()
    scoped = advisor_rule[advisor_rule["rule_label"].isin(labels)].copy()
    if scoped.empty:
        return pd.DataFrame()

    type_label = "Hard Stop" if severity == "hard" else "Warning"
    scoped["advisor"] = scoped["advisor"].replace("", "Unknown")
    scoped = scoped.sort_values(["rule_label", "count"], ascending=[True, False])
    return scoped.rename(
        columns={
            "rule_label": "Audit Rule",
            "advisor": "Advisor",
            "count": "Findings",
        }
    ).assign(Type=type_label)[["Audit Rule", "Type", "Advisor", "Findings"]]


def _advisor_finding_count_table(breakdown: dict) -> pd.DataFrame:
    rule_summary = breakdown.get("rule_summary")
    advisor_rule = breakdown.get("advisor_rule_summary")
    if (
        rule_summary is None
        or advisor_rule is None
        or rule_summary.empty
        or advisor_rule.empty
    ):
        return pd.DataFrame()

    severity_map = rule_summary.set_index("rule_label")["severity"].to_dict()
    work = advisor_rule.copy()
    work["severity"] = work["rule_label"].map(severity_map)
    work = work[work["severity"].isin(["hard", "warn"])]
    if work.empty:
        return pd.DataFrame()

    pivot = work.pivot_table(
        index="advisor",
        columns="severity",
        values="count",
        aggfunc="sum",
        fill_value=0,
    )
    for col, label in (("hard", "Hard Stop Findings"), ("warn", "Warning Findings")):
        if col not in pivot.columns:
            pivot[col] = 0
    pivot["Total Findings"] = pivot["hard"] + pivot["warn"]
    pivot = pivot.sort_values("Total Findings", ascending=False)
    return pivot.rename(columns={"hard": "Hard Stop Findings", "warn": "Warning Findings"})


def _render_coaching_top_findings(df: pd.DataFrame) -> None:
    breakdown = compute_hard_stop_breakdown(df)
    if breakdown["finding_count"] <= 0:
        st.info(
            "No hard stops or warnings recorded in saved reviews for this period. "
            "Complete audits on the **Review** tab to populate coaching detail."
        )
        return

    rule_summary = breakdown["rule_summary"]
    advisor_rule = breakdown["advisor_rule_summary"]
    coach_period = period_label_from_df(df)

    st.markdown("### Top Hard Stops & Warnings")
    st.caption(
        "Top 5 hard stops and top 5 warnings in this date range, with advisor counts and per-rule breakdown."
    )

    render_metric_rows([
        [
            ("Hard Stops", f"{breakdown['hard_count']:,}"),
            ("Warnings", f"{breakdown['warn_count']:,}"),
            ("ROs With Issues", f"{breakdown['reviews_with_findings']:,}"),
        ],
    ])

    hard_detail = _top_rules_detail_frame(rule_summary, advisor_rule, severity="hard")
    warn_detail = _top_rules_detail_frame(rule_summary, advisor_rule, severity="warn")
    hard_advisor_detail = _top_rules_advisor_detail_frame(
        rule_summary, advisor_rule, severity="hard"
    )
    warn_advisor_detail = _top_rules_advisor_detail_frame(
        rule_summary, advisor_rule, severity="warn"
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Top 5 Hard Stops**")
        if hard_detail.empty:
            st.caption("No hard stops in this period.")
        else:
            render_branded_report_table(
                _style_audit_rule_breakdown(hard_detail),
                export_df=hard_detail,
                pdf_title="RO GUARD Coaching — Top Hard Stops",
                period_label=coach_period,
                pdf_subtitle="Coaching",
                pdf_filename="RO_Guard_Coaching_Top_Hard_Stops.pdf",
                csv_filename="RO_Guard_Coaching_Top_Hard_Stops.csv",
                export_key="coaching_top_hard",
            )

    with c2:
        st.markdown("**Top 5 Warnings**")
        if warn_detail.empty:
            st.caption("No warnings in this period.")
        else:
            render_branded_report_table(
                _style_audit_rule_breakdown(warn_detail),
                export_df=warn_detail,
                pdf_title="RO GUARD Coaching — Top Warnings",
                period_label=coach_period,
                pdf_subtitle="Coaching",
                pdf_filename="RO_Guard_Coaching_Top_Warnings.pdf",
                csv_filename="RO_Guard_Coaching_Top_Warnings.csv",
                export_key="coaching_top_warn",
            )

    st.markdown("#### Advisor Detail — Top Rules")
    st.caption("Finding counts by advisor for each top hard stop and warning rule.")
    detail_c1, detail_c2 = st.columns(2)
    with detail_c1:
        st.markdown("**Hard stops by advisor**")
        if hard_advisor_detail.empty:
            st.caption("No advisor attribution for top hard stops.")
        else:
            hard_adv_export = hard_advisor_detail.set_index(["Audit Rule", "Advisor"])
            render_branded_report_table(
                _style_advisor_rule_pivot(hard_adv_export),
                export_df=hard_advisor_detail,
                pdf_title="RO GUARD Coaching — Hard Stops By Advisor",
                period_label=coach_period,
                pdf_subtitle="Coaching",
                pdf_landscape=True,
                pdf_filename="RO_Guard_Coaching_Hard_Stops_By_Advisor.pdf",
                csv_filename="RO_Guard_Coaching_Hard_Stops_By_Advisor.csv",
                export_key="coaching_hard_by_advisor",
            )
    with detail_c2:
        st.markdown("**Warnings by advisor**")
        if warn_advisor_detail.empty:
            st.caption("No advisor attribution for top warnings.")
        else:
            warn_adv_export = warn_advisor_detail.set_index(["Audit Rule", "Advisor"])
            render_branded_report_table(
                _style_advisor_rule_pivot(warn_adv_export),
                export_df=warn_advisor_detail,
                pdf_title="RO GUARD Coaching — Warnings By Advisor",
                period_label=coach_period,
                pdf_subtitle="Coaching",
                pdf_landscape=True,
                pdf_filename="RO_Guard_Coaching_Warnings_By_Advisor.pdf",
                csv_filename="RO_Guard_Coaching_Warnings_By_Advisor.csv",
                export_key="coaching_warn_by_advisor",
            )

    advisor_counts = _advisor_finding_count_table(breakdown)
    st.markdown("#### By Advisor — Finding Counts")
    st.caption("Hard stop and warning findings attributed to each advisor in this date range.")
    if advisor_counts.empty:
        st.caption("Advisor counts will appear once reviews include advisor names and audit findings.")
    else:
        render_branded_report_table(
            _style_advisor_rule_pivot(advisor_counts),
            export_df=advisor_counts.reset_index(),
            pdf_title="RO GUARD Coaching — Advisor Finding Counts",
            period_label=coach_period,
            pdf_subtitle="Coaching",
            pdf_filename="RO_Guard_Coaching_Advisor_Findings.pdf",
            csv_filename="RO_Guard_Coaching_Advisor_Findings.csv",
            export_key="coaching_advisor_counts",
        )


def _render_coaching_focus_section(df: pd.DataFrame, metrics: dict) -> None:
    st.markdown("### Where to Focus Coaching")
    c1, c2 = st.columns(2)
    with c1:
        render_advisor_coaching_focus(df, metrics["advisor_summary"])

    with c2:
        st.markdown("**Top Rejection Reasons**")
        reasons = metrics["rejection_reasons"]
        if not reasons.empty:
            reasons_export = reasons.head(8).rename(columns={
                "rejection_reason": "Reason Category",
                "count": "Count",
                "total_value": "Claim Value",
            })
            render_branded_report_table(
                reasons_export,
                pdf_title="RO GUARD Coaching — Top Rejection Reasons",
                period_label=period_label_from_df(df),
                pdf_subtitle="Coaching",
                pdf_filename="RO_Guard_Coaching_Rejection_Reasons.pdf",
                csv_filename="RO_Guard_Coaching_Rejection_Reasons.csv",
                export_key="coaching_rejection_reasons",
            )
            st.caption("See **Rejections** tab for full decline text and user notes per claim.")
        else:
            st.caption(
                "Mark rejections on Review or Claim Outcomes — reasons and notes appear under **Rejections**."
            )


def render_coaching():
    st.header("Coaching")
    st.caption("Advisor focus areas and top rejection reasons for the selected date range.")

    col_refresh, _ = st.columns([1, 3])
    with col_refresh:
        if st.button("Refresh Coaching", key="refresh_coaching"):
            invalidate_reviews_cache()
            st.rerun()

    df = normalize_reviews_dataframe(load_reviews())
    if df.empty:
        st.info("No reviews saved yet. Complete audits on the Review tab to populate coaching insights.")
        return

    df = _filter_reviews_by_date(df, key_prefix="coaching")
    if df.empty:
        st.warning("No reviews in the selected date range.")
        return

    metrics = compute_roi_metrics(df)
    _render_coaching_top_findings(df)
    _render_coaching_focus_section(df, metrics)


def render_popps():
    appearance = st.session_state.get("appearance", "Dark")
    reviewer = current_person_name() or auth_user_email() or "User"
    render_popps_report(
        theme=appearance,
        supabase=supabase,
        reviewer=reviewer,
        auth_user=auth_user_email(),
        notes_admin=user_has_role("Admin"),
        is_warranty_admin=user_has_role("Warranty Admin"),
    )


def render_pricing_roi():
    render_pricing_roi_page(reviews_df=load_reviews())


def render_roi_dashboard():
    from core.ui_polish import render_section_hero

    render_section_hero(
        "ROI Dashboard",
        "Show the business value of RO Guard — dollars protected, quality trends, and team performance.",
        icon="📈",
        tips=["Dollars protected", "Quality trends", "Team scorecards"],
    )

    col_refresh, col_migrate = st.columns([1, 2])
    with col_refresh:
        if st.button("Refresh ROI Dashboard", key="refresh_roi"):
            invalidate_reviews_cache()
            st.rerun()
    with col_migrate:
        if st.button("Import old local reviews (SQLite → Supabase)", key="migrate_roi"):
            migrated, skipped = migrate_sqlite_to_supabase(supabase, DB_PATH)
            invalidate_reviews_cache()
            st.success(f"Imported {migrated} review(s). Skipped {skipped} duplicate or invalid row(s).")
            st.rerun()

    df = normalize_reviews_dataframe(load_reviews())
    if df.empty:
        st.info("No reviews saved yet. Complete audits on the Review tab to populate ROI metrics.")
        return

    df = _filter_reviews_by_date(df, key_prefix="roi")
    if df.empty:
        st.warning("No reviews in the selected date range.")
        return

    with st.expander("ROI assumptions (adjust for your store)", expanded=False):
        st.caption("These settings estimate dollars saved — they do not change your saved review data.")
        c1, c2, c3 = st.columns(3)
        with c1:
            rejection_rework_pct = st.slider(
                "Est. rework cost if a hard-stop RO had been submitted (%)",
                min_value=10,
                max_value=100,
                value=40,
                step=5,
                key="roi_rework_pct",
            ) / 100.0
        with c2:
            minutes_saved = st.slider(
                "Minutes saved per review vs manual audit",
                min_value=5,
                max_value=45,
                value=15,
                step=1,
                key="roi_minutes_saved",
            )
        with c3:
            if "roi_hourly_rate" not in st.session_state:
                st.session_state.roi_hourly_rate = 38.0
            hourly_rate = st.number_input(
                "Warranty admin loaded hourly cost ($)",
                min_value=20.0,
                max_value=100.0,
                step=1.0,
                key="roi_hourly_rate",
            )

    metrics = compute_roi_metrics(
        df,
        rejection_rework_pct=rejection_rework_pct,
        minutes_saved_per_review=float(minutes_saved),
        admin_hourly_rate=float(hourly_rate),
    )

    st.markdown(
        f"""
        <div class="hero">
            <h1>${metrics["total_estimated_value"]:,.0f}</h1>
            <p>Estimated value captured in this period from RO Shield reviews</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Value at a Glance")
    v1, v2, v3, v4 = st.columns(4)
    v1.metric(
        "Claims Protected",
        f"${metrics['protected_value']:,.0f}",
        help="Total claim dollars flagged with hard stops before submission",
    )
    v2.metric(
        "Est. Rework Avoided",
        f"${metrics['rework_savings']:,.0f}",
        help="Protected claim value × your rework cost assumption",
    )
    v3.metric(
        "Est. Labor Saved",
        f"${metrics['time_savings']:,.0f}",
        help="Reviews × minutes saved × admin hourly cost",
    )
    v4.metric("Reviews Audited", metrics["review_count"])

    st.markdown("### Quality & Approval")
    q1, q2, q3, q4, q5 = st.columns(5)
    q1.metric("Avg Audit Score", f"{metrics['avg_score']:.1f}")
    q2.metric(
        "First-Pass Approval",
        f"{metrics['first_pass_pct_resolved']:.1f}%",
        help="Of reviews with a recorded paid or rejected OEM outcome.",
    )
    q3.metric("Rejected Claim Value", f"${metrics['rejected_value']:,.0f}")
    q4.metric("Hard Stops Caught", metrics["hard_stop_count"])
    q5.metric("Warnings Flagged", metrics["warning_count"])

    st.markdown("### Audit Outcomes")
    o1, o2, o3 = st.columns(3)
    o1.metric("🔴 Do Not Submit", metrics["do_not_submit_count"])
    o2.metric("🟡 Needs Review", metrics["needs_review_count"])
    o3.metric("🟢 Ready", metrics["ready_count"])

    render_hard_stop_breakdown(df, key_prefix="roi")

    if metrics["review_count"] > 0:
        st.markdown("### Visual Summary")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.image(audit_outcomes_pie(metrics), use_container_width=True, caption="Audit Outcomes")
        with c2:
            st.image(first_pass_pie(metrics), use_container_width=True, caption="Submission Results")
        with c3:
            st.image(issue_breakdown_pie(metrics), use_container_width=True, caption="Issues Found")

    weekly = metrics["weekly_trend"]
    if not weekly.empty:
        st.markdown("### Trend Over Time")
        t1, t2 = st.columns(2)
        with t1:
            weekly_png = weekly_activity_chart(weekly)
            if weekly_png:
                st.image(weekly_png, use_container_width=True, caption="Reviews & Hard Stops by Week")
        with t2:
            st.line_chart(weekly.set_index("week")[["protected_value"]])

    advisor_df = metrics["advisor_summary"]
    advisor_png = advisor_hard_stops_chart(advisor_df)
    if advisor_png:
        st.image(advisor_png, use_container_width=True, caption="Hard Stops by Advisor")

    st.markdown("### How We Calculate ROI")
    st.info(
        f"**Claims Protected** is the actual hard-stop claim dollars RO Shield flagged before submission. "
        f"**Est. Rework Avoided** applies your {rejection_rework_pct:.0%} rework assumption to that protected value. "
        f"**Est. Labor Saved** assumes {minutes_saved:.0f} minutes saved per review at ${hourly_rate:,.0f}/hr. "
        f"Together, these give managers a clear story for adoption and investment."
    )

    if "created_at" in df.columns and df["created_at"].notna().any():
        period_label = (
            f"{df['created_at'].min().date()} to {df['created_at'].max().date()}"
        )
    else:
        period_label = "Selected period"

    render_branded_pdf_download(
        pdf_builder=lambda: build_roi_report_pdf(
            metrics,
            period_label=period_label,
            rejection_rework_pct=rejection_rework_pct,
            minutes_saved=float(minutes_saved),
            hourly_rate=float(hourly_rate),
        ),
        pdf_filename="RO_Guard_ROI_Summary.pdf",
        export_key="roi_summary_pdf",
        caption="Branded RO GUARD ROI summary with charts and ROGUARD watermark.",
        label="Download ROI Summary PDF",
    )


def _split_rejection_reason(reason: str) -> tuple[str, str]:
    """Return (category, notes) from stored rejection_reason text."""
    text = str(reason or "").strip()
    if not text:
        return "", ""
    if " — " in text:
        primary, _, notes = text.partition(" — ")
        return primary.strip(), notes.strip()
    return text, ""


def _declined_outcome_reviews(df: pd.DataFrame) -> pd.DataFrame:
    """Reviews marked rejected or paid-after-rejection (OEM decline tracking)."""
    if df.empty:
        return df.copy()
    work = df.copy()
    work["rejected"] = pd.to_numeric(work.get("rejected", 0), errors="coerce").fillna(0).astype(int)
    work["paid_after_rejection"] = pd.to_numeric(
        work.get("paid_after_rejection", 0), errors="coerce"
    ).fillna(0).astype(int)
    declined = (work["rejected"] == 1) | (work["paid_after_rejection"] == 1)
    return work[declined].copy()


def _rejection_detail_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Build a reporting table with outcome, category, and full user notes preserved."""
    declined = _declined_outcome_reviews(df)
    if declined.empty:
        return declined

    rows = []
    for _, row in declined.iterrows():
        fp = int(row.get("first_pass_paid") or 0)
        rej = int(row.get("rejected") or 0)
        par = int(row.get("paid_after_rejection") or 0)
        reason = str(row.get("rejection_reason") or "").strip()
        category, notes = _split_rejection_reason(reason)
        rows.append(
            {
                "created_at": row.get("created_at"),
                "ro_number": row.get("ro_number"),
                "advisor": row.get("advisor"),
                "outcome": review_outcome_label(fp, rej, par),
                "decline_category": category or "—",
                "decline_notes": notes or "—",
                "full_decline_reason": reason or "—",
                "total_claim_value": float(row.get("total_claim_value") or 0),
            }
        )
    detail = pd.DataFrame(rows)
    if "created_at" in detail.columns:
        detail["created_at"] = pd.to_datetime(detail["created_at"], errors="coerce").dt.strftime(
            "%Y-%m-%d %H:%M"
        )
    return detail.sort_values("created_at", ascending=False)


def _form_submitted_claim_value(job_count: int) -> float:
    total = 0.0
    for job_no in range(1, max(int(job_count or 0), 0) + 1):
        total += float(st.session_state.get(f"claim_value_{job_no}", 0) or 0)
    return total


def _render_oem_paid_amount_input(
    *,
    submitted: float,
    key: str,
    current=None,
    current_reason: str = "",
) -> tuple[float | None, str]:
    """Optional OEM paid amount when outcome is first-pass or paid-after-rejection."""
    submitted_val = float(submitted or 0)
    if submitted_val <= 0:
        st.caption("Add claim value on the RO before recording OEM paid amount.")
        return None, ""

    has_partial = False
    current_paid = submitted_val
    if current is not None and not pd.isna(current):
        try:
            current_paid = float(current)
            has_partial = current_paid < submitted_val - 0.01
        except (TypeError, ValueError):
            has_partial = False

    use_less = st.checkbox(
        "OEM paid less than full claim",
        key=f"{key}_partial",
        value=has_partial,
        help="Use when overlapping labor, disallowed parts, or other adjustments reduced OEM payment.",
    )
    if not use_less:
        return None, ""

    paid = st.number_input(
        "OEM paid amount",
        min_value=0.0,
        max_value=submitted_val,
        value=min(current_paid, submitted_val),
        step=1.0,
        format="%.2f",
        key=f"{key}_amount",
    )
    short = compute_short_pay(submitted_val, paid)
    if short > 0.01:
        st.caption(
            f"Short pay: **${short:,.2f}** "
            f"(audited ${submitted_val:,.2f} − OEM paid ${float(paid):,.2f})"
        )
    reason = st.text_area(
        "Why was it short paid? (required)",
        value=str(current_reason or ""),
        placeholder="Example: Overlapping labor op 1234A — OEM paid main line only.",
        height=90,
        key=f"{key}_reason",
        help="Required when OEM paid less than the audited claim value.",
    )
    return float(paid), str(reason or "").strip()


def _compose_rejection_reason(selected_reason: str, notes: str) -> tuple[bool, str]:
    selected_reason = str(selected_reason or "").strip()
    notes = str(notes or "").strip()
    if not selected_reason:
        return False, "Select a rejection reason."
    if selected_reason.lower().startswith("other") and not notes:
        return False, "Add notes when selecting **Other**."
    if notes:
        return True, f"{selected_reason} — {notes}"
    return True, selected_reason


def _parse_review_outcome_selection(
    *,
    first_pass_paid: bool,
    rejected: bool,
    paid_after_rejection: bool,
    rejection_reason: str = "",
    initial_decline_reason: str = "",
    oem_paid_amount: float | None = None,
    submitted_claim_value: float = 0,
    short_pay_reason: str = "",
) -> tuple[bool, dict | str]:
    outcome_selected = sum(
        1 for x in (first_pass_paid, rejected, paid_after_rejection) if x
    )
    if outcome_selected > 1:
        return False, (
            "Choose only one outcome — **First-Pass Paid**, **Rejected / Returned**, "
            "or **Rejected — paid after first submission** — or leave all unchecked to mark pending."
        )

    save_first_pass_paid = bool(first_pass_paid) and not rejected and not paid_after_rejection
    save_rejected = bool(rejected) and not first_pass_paid and not paid_after_rejection
    save_paid_after_rejection = bool(paid_after_rejection) and not first_pass_paid and not rejected

    final_reason = ""
    if save_rejected:
        final_reason = str(rejection_reason or "").strip()
        if not final_reason:
            return False, "Select a rejection reason (or add notes for **Other**)."
    elif save_paid_after_rejection:
        final_reason = str(initial_decline_reason or "").strip()
        if not final_reason:
            return False, "Enter why the claim was initially declined."

    stored_oem: float | None = None
    stored_short_reason = ""
    if is_paid_outcome(save_first_pass_paid, save_rejected, save_paid_after_rejection):
        try:
            stored_oem = normalize_oem_paid_amount(
                oem_paid_amount,
                submitted=float(submitted_claim_value or 0),
            )
            stored_short_reason = validate_short_pay_reason(
                stored_oem,
                submitted=float(submitted_claim_value or 0),
                reason=short_pay_reason,
            )
        except ValueError as exc:
            return False, str(exc)

    return True, {
        "first_pass_paid": save_first_pass_paid,
        "rejected": save_rejected,
        "paid_after_rejection": save_paid_after_rejection,
        "rejection_reason": final_reason,
        "oem_paid_amount": stored_oem,
        "short_pay_reason": stored_short_reason or None,
    }


def _resolve_review_id_for_outcome(form_version: int, ro_number: str, vin: str) -> int | None:
    review_id = _resolve_session_review_id(form_version, ro_number, vin)
    if review_id:
        return int(review_id)
    if str(ro_number or "").strip():
        found = find_review_id_for_update(supabase, ro_number, vin)
        if found:
            return int(found)
    return None


def _persist_review_outcome(
    form_version: int,
    ro_number: str,
    vin: str,
    outcome: dict,
    *,
    submitted_claim_value: float = 0,
) -> bool:
    review_id = _resolve_review_id_for_outcome(form_version, ro_number, vin)
    if not review_id:
        st.error(
            "No saved review found for this RO yet. Run **Run Audit + Save Review** first, "
            "or open a saved claim from **Pending Claims**."
        )
        return False

    try:
        update_review_outcome(
            supabase,
            int(review_id),
            first_pass_paid=outcome["first_pass_paid"],
            rejected=outcome["rejected"],
            paid_after_rejection=outcome["paid_after_rejection"],
            rejection_reason=outcome["rejection_reason"],
            oem_paid_amount=outcome.get("oem_paid_amount"),
            short_pay_reason=str(outcome.get("short_pay_reason") or ""),
            submitted_claim_value=float(submitted_claim_value or 0),
            updated_by=current_person_name() or auth_user_email(),
        )
        invalidate_reviews_cache()
        st.session_state[_active_review_id_key(form_version)] = int(review_id)
        st.session_state[_active_review_ro_key(form_version)] = str(ro_number or "").strip()
        st.session_state[_active_review_vin_key(form_version)] = str(vin or "").strip()
        ro_label = str(ro_number or "—").strip() or "—"
        label = review_outcome_label(
            outcome["first_pass_paid"],
            outcome["rejected"],
            outcome["paid_after_rejection"],
        )
        st.success(f"Outcome saved for RO **{ro_label}**: **{label}**.")
        return True
    except Exception as exc:
        message = str(exc)
        if "outcome_updated" in message.lower() or "column" in message.lower():
            st.error(
                "Could not save outcome. Run the latest `docs/SUPABASE_SCHEMA.sql` migration "
                "in Supabase (adds outcome_updated_at / outcome_updated_by), then try again."
            )
        else:
            st.error(f"Could not save outcome: {exc}")
        return False


def _outcome_radio_index(first_pass_paid: int, rejected: int, paid_after_rejection: int = 0) -> int:
    if paid_after_rejection and not first_pass_paid and not rejected:
        return 3
    if first_pass_paid and not rejected and not paid_after_rejection:
        return 1
    if rejected and not first_pass_paid and not paid_after_rejection:
        return 2
    return 0


def _review_option_label(row: dict) -> str:
    ro_number = str(row.get("ro_number") or "—").strip() or "—"
    advisor = str(row.get("advisor") or "—").strip() or "—"
    claim_value = float(row.get("total_claim_value") or 0)
    status = str(row.get("outcome_status") or review_outcome_label(
        row.get("first_pass_paid"), row.get("rejected"), row.get("paid_after_rejection")
    ))
    audited = row.get("created_at")
    audited_label = ""
    if audited is not None and str(audited) not in ("", "NaT"):
        try:
            audited_label = pd.to_datetime(audited).strftime("%Y-%m-%d")
        except Exception:
            audited_label = str(audited)[:10]
    parts = [f"RO {ro_number}", advisor, f"${claim_value:,.0f}", status]
    if audited_label:
        parts.append(audited_label)
    return " · ".join(parts)


def render_outcome_followup(df: pd.DataFrame, *, show_title: bool = True) -> None:
    """Let warranty staff record OEM paid/rejected results after submission."""
    if show_title:
        st.subheader("Update Claim Outcomes")
    st.caption(
        "After Stellantis pays or rejects the claim, record the result here — even if the audit "
        "was saved weeks ago with no outcome selected."
    )

    if "id" not in df.columns:
        st.warning("Review IDs are missing from Reporting data. Refresh after Supabase is up to date.")
        return

    work = df.copy()
    work["first_pass_paid"] = pd.to_numeric(work.get("first_pass_paid", 0), errors="coerce").fillna(0).astype(int)
    work["rejected"] = pd.to_numeric(work.get("rejected", 0), errors="coerce").fillna(0).astype(int)
    work = normalize_reviews_dataframe(work)
    if "outcome_status" not in work.columns:
        work["outcome_status"] = [
            review_outcome_label(fp, rej, par)
            for fp, rej, par in zip(
                work["first_pass_paid"], work["rejected"], work["paid_after_rejection"]
            )
        ]

    pending_mask = (
        (work["first_pass_paid"] == 0)
        & (work["rejected"] == 0)
        & (work["paid_after_rejection"] == 0)
    )
    pending_count = int(pending_mask.sum())
    first_pass_count = int(work["first_pass_paid"].sum())
    rejected_final_count = int(work["rejected"].sum())
    paid_after_count = int(work["paid_after_rejection"].sum())
    oem_rejection_total = rejected_final_count + paid_after_count
    partial_pay_count = int(work.get("is_partial_pay", pd.Series([False])).sum())
    short_pay_total = float(work.get("short_pay_amount", pd.Series([0])).sum())
    resolved_count = len(work) - pending_count

    render_metric_rows([
        [
            ("Pending Outcome", f"{pending_count:,}", "No OEM paid/rejected outcome recorded yet."),
            (
                "First-Pass Paid",
                f"{first_pass_count:,}",
                "OEM paid the claim on the first submission (no rejection).",
            ),
            (
                "Paid After Rejection",
                f"{paid_after_count:,}",
                "OEM initially rejected or returned the claim, then paid after resubmit or correction.",
            ),
        ],
        [
            (
                "Rejected (Final)",
                f"{rejected_final_count:,}",
                "OEM rejected the claim and it was not paid (final denial).",
            ),
            (
                "OEM Rejections (Total)",
                f"{oem_rejection_total:,}",
                "All claims rejected at least once — includes those later paid after rejection.",
            ),
            (
                "First-Pass % (resolved)",
                f"{(first_pass_count / resolved_count * 100):.1f}%" if resolved_count else "—",
                "First-pass paid ÷ reviews with any recorded OEM outcome.",
            ),
        ],
        [
            (
                "Partial-pay claims",
                f"{partial_pay_count:,}",
                "Paid outcomes where OEM paid less than the audited claim value.",
            ),
            (
                "Short-pay total ($)",
                f"${short_pay_total:,.0f}",
                "Sum of (audited claim − OEM paid) across partial-pay claims.",
            ),
        ],
    ])
    if paid_after_count and not rejected_final_count:
        st.caption(
            f"**{paid_after_count:,}** claim(s) were rejected by the OEM and later paid — they count under "
            "**OEM Rejections (Total)** and **Paid After Rejection**, not **Rejected (Final)**."
        )

    filter_choice = st.radio(
        "Show reviews",
        [
            "Pending only",
            "All in date range",
            "First-Pass Paid",
            "Rejected (Final)",
            "Paid After Rejection",
            "Any OEM rejection",
            "Partial pay / Short pay",
        ],
        horizontal=True,
        key="outcome_followup_filter",
    )

    filtered = work.copy()
    if filter_choice == "Pending only":
        filtered = filtered[pending_mask]
    elif filter_choice == "First-Pass Paid":
        filtered = filtered[work["first_pass_paid"] == 1]
    elif filter_choice == "Rejected (Final)":
        filtered = filtered[work["rejected"] == 1]
    elif filter_choice == "Paid After Rejection":
        filtered = filtered[work["paid_after_rejection"] == 1]
    elif filter_choice == "Any OEM rejection":
        filtered = filtered[(work["rejected"] == 1) | (work["paid_after_rejection"] == 1)]
    elif filter_choice == "Partial pay / Short pay":
        filtered = filtered[work.get("is_partial_pay", pd.Series([False] * len(work)))]

    if filtered.empty:
        st.info(f"No reviews match **{filter_choice}** for this date range.")
        return

    if "created_at" in filtered.columns:
        filtered = filtered.sort_values("created_at", ascending=False)

    option_rows = filtered.to_dict("records")
    option_ids = [int(row["id"]) for row in option_rows]
    label_by_id = {int(row["id"]): _review_option_label(row) for row in option_rows}

    selected_id = st.selectbox(
        "Select review to update",
        options=option_ids,
        format_func=lambda rid: label_by_id.get(int(rid), str(rid)),
        key="outcome_followup_review_id",
    )

    selected = next(row for row in option_rows if int(row["id"]) == int(selected_id))
    current_fp = int(selected.get("first_pass_paid") or 0)
    current_rej = int(selected.get("rejected") or 0)
    current_par = int(selected.get("paid_after_rejection") or 0)
    current_reason = str(selected.get("rejection_reason") or "").strip()

    info_cols = st.columns(4)
    info_cols[0].metric("RO", str(selected.get("ro_number") or "—"))
    info_cols[1].metric("Advisor", str(selected.get("advisor") or "—"))
    info_cols[2].metric(
        "Claim Value",
        f"${float(selected.get('total_claim_value') or 0):,.2f}",
    )
    info_cols[3].metric("Current", review_outcome_label(current_fp, current_rej, current_par))

    submitted_claim = float(selected.get("total_claim_value") or 0)
    current_oem = selected.get("oem_paid_amount")
    if current_oem is not None and not pd.isna(current_oem):
        short_pay = compute_short_pay(submitted_claim, current_oem)
        if short_pay > 0.01:
            st.info(
                f"**Partial OEM payment:** audited **${submitted_claim:,.2f}** · "
                f"OEM paid **${float(current_oem):,.2f}** · short pay **${short_pay:,.2f}**"
            )
            current_short_reason = str(selected.get("short_pay_reason") or "").strip()
            if current_short_reason:
                st.caption(f"**Short pay reason:** {current_short_reason}")
            else:
                st.warning("Short pay is recorded but no reason is saved yet — add one below.")

    if current_reason:
        category, notes = _split_rejection_reason(current_reason)
        st.info(
            f"**Recorded decline reason:** {current_reason}"
            + (f"\n\nCategory: **{category}** · Notes: {notes}" if notes else "")
        )

    if selected.get("outcome_updated_by") or selected.get("outcome_updated_at"):
        updated_by = str(selected.get("outcome_updated_by") or "—")
        updated_at = selected.get("outcome_updated_at")
        updated_label = ""
        if updated_at is not None and str(updated_at) not in ("", "NaT"):
            try:
                updated_label = pd.to_datetime(updated_at).strftime("%Y-%m-%d %H:%M")
            except Exception:
                updated_label = str(updated_at)[:16]
        st.caption(f"Last outcome update: **{updated_by}** · {updated_label or '—'}")

    rejection_library = load_rejection_reason_library(supabase)
    reason_labels = active_rejection_reason_labels(rejection_library)
    if not reason_labels:
        reason_labels = active_rejection_reason_labels({})

    existing_primary = current_reason.split(" — ")[0].strip() if current_reason else ""
    existing_notes = current_reason.split(" — ", 1)[1].strip() if " — " in current_reason else ""

    with st.form("outcome_followup_form", clear_on_submit=False):
        outcome_choice = st.radio(
            "OEM outcome",
            [
                "Pending",
                "First-Pass Paid",
                "Rejected / Returned",
                "Paid After Rejection",
            ],
            index=_outcome_radio_index(current_fp, current_rej, current_par),
            horizontal=True,
        )

        selected_reason = ""
        rejection_notes = ""
        initial_decline_reason = ""
        if outcome_choice == "Rejected / Returned":
            reason_default = existing_primary if existing_primary in reason_labels else ""
            reason_index = reason_labels.index(reason_default) + 1 if reason_default in reason_labels else 0
            selected_reason = st.selectbox(
                "Rejection reason",
                options=[""] + reason_labels,
                index=reason_index,
                help="Managed under Admin → Rejection Reason Library.",
            )
            rejection_notes = st.text_input(
                "Additional rejection notes (optional)",
                value=existing_notes,
                placeholder="Required for 'Other' — optional detail for any reason.",
            )
        elif outcome_choice == "Paid After Rejection":
            initial_decline_reason = st.text_area(
                "Why was it initially declined?",
                value=current_reason if current_par else "",
                placeholder="Enter the OEM decline reason from the first submission.",
                height=100,
            )

        oem_paid_amount = None
        short_pay_reason = ""
        if outcome_choice in ("First-Pass Paid", "Paid After Rejection"):
            oem_paid_amount, short_pay_reason = _render_oem_paid_amount_input(
                submitted=submitted_claim,
                key="outcome_followup_oem",
                current=current_oem,
                current_reason=str(selected.get("short_pay_reason") or ""),
            )

        submitted = st.form_submit_button("Save outcome", type="primary", use_container_width=True)

    if submitted:
        first_pass_paid = outcome_choice == "First-Pass Paid"
        rejected = outcome_choice == "Rejected / Returned"
        paid_after_rejection = outcome_choice == "Paid After Rejection"
        rejection_reason = ""
        if rejected:
            ok, rejection_reason = _compose_rejection_reason(selected_reason, rejection_notes)
            if not ok:
                st.error(rejection_reason)
                return
        elif paid_after_rejection:
            rejection_reason = str(initial_decline_reason or "").strip()
            if not rejection_reason:
                st.error("Enter why the claim was initially declined.")
                return

        stored_oem = None
        stored_short_reason = ""
        if is_paid_outcome(first_pass_paid, rejected, paid_after_rejection):
            try:
                stored_oem = normalize_oem_paid_amount(
                    oem_paid_amount,
                    submitted=submitted_claim,
                )
                stored_short_reason = validate_short_pay_reason(
                    stored_oem,
                    submitted=submitted_claim,
                    reason=short_pay_reason,
                )
            except ValueError as exc:
                st.error(str(exc))
                return

        try:
            update_review_outcome(
                supabase,
                int(selected_id),
                first_pass_paid=first_pass_paid,
                rejected=rejected,
                paid_after_rejection=paid_after_rejection,
                rejection_reason=rejection_reason,
                oem_paid_amount=stored_oem,
                short_pay_reason=stored_short_reason,
                submitted_claim_value=submitted_claim,
                updated_by=current_person_name() or auth_user_email(),
            )
            invalidate_reviews_cache()
            st.success(f"Outcome saved for RO **{selected.get('ro_number', '—')}**.")
            st.rerun()
        except Exception as exc:
            message = str(exc)
            if "outcome_updated" in message.lower() or "column" in message.lower():
                st.error(
                    "Could not save outcome. Run the latest `docs/SUPABASE_SCHEMA.sql` migration "
                    "in Supabase (adds outcome_updated_at / outcome_updated_by), then try again."
                )
            else:
                st.error(f"Could not save outcome: {exc}")

    if pending_count > 0:
        st.markdown("**Still pending OEM outcome**")
        pending_view = work[pending_mask].copy()
        if "created_at" in pending_view.columns:
            pending_view["created_at"] = pd.to_datetime(
                pending_view["created_at"], errors="coerce"
            ).dt.strftime("%Y-%m-%d")
        pending_cols = [
            c for c in ("created_at", "ro_number", "advisor", "total_claim_value", "status")
            if c in pending_view.columns
        ]
        pending_export = pending_view[pending_cols].head(15) if pending_cols else pending_view.head(15)
        render_branded_report_table(
            pending_export,
            pdf_title="RO GUARD Pending OEM Outcomes",
            period_label=period_label_from_df(work, default="Claim outcomes — pending"),
            pdf_subtitle="Claim Outcomes",
            pdf_filename="RO_Guard_Pending_OEM_Outcomes.pdf",
            csv_filename="RO_Guard_Pending_OEM_Outcomes.csv",
            export_key="outcome_pending_oem",
        )

    rejection_detail = _rejection_detail_frame(work)
    if not rejection_detail.empty:
        st.markdown("**Recorded rejections & decline reasons**")
        st.caption(
            "Every reason entered on Review or Claim Outcomes is kept here — category, notes, "
            "and the full text as entered."
        )
        missing_reason = int((rejection_detail["full_decline_reason"] == "—").sum())
        if missing_reason:
            st.warning(
                f"{missing_reason} declined claim(s) have **no reason recorded** yet. "
                "Select the review above and add the OEM decline reason."
            )
        rejection_export = rejection_detail.rename(
            columns={
                "created_at": "Audited",
                "ro_number": "RO",
                "advisor": "Advisor",
                "outcome": "Outcome",
                "decline_category": "Reason Category",
                "decline_notes": "User Notes",
                "full_decline_reason": "Full Decline Reason (as entered)",
                "total_claim_value": "Claim Value",
            }
        )
        render_branded_report_table(
            rejection_export,
            pdf_builder=lambda: build_decline_reasons_pdf(
                rejection_export,
                period_label=period_label_from_df(rejection_detail),
            ),
            pdf_filename="RO_Guard_Claim_Outcomes_Declines.pdf",
            csv_filename="RO_Guard_Claim_Outcomes_Declines.csv",
            export_key="outcome_rejection_detail",
        )


def render_reporting_summary(df: pd.DataFrame) -> None:
    review_count = len(df)
    avg_score = pd.to_numeric(df.get("score", 0), errors="coerce").fillna(0).mean()
    avg_days = pd.to_numeric(df.get("days_to_submit", 0), errors="coerce").fillna(0).mean()
    total_claim = pd.to_numeric(df.get("total_claim_value", 0), errors="coerce").fillna(0).sum()
    hard_stop_val = pd.to_numeric(df.get("hard_stop_value", 0), errors="coerce").fillna(0).sum()
    hard_stops = int(pd.to_numeric(df.get("hard_stop_count", 0), errors="coerce").fillna(0).sum())
    time_bypasses = int(pd.to_numeric(df.get("time_bypass", 0), errors="coerce").fillna(0).sum())

    render_metric_rows([
        [
            ("Reviews", f"{review_count:,}"),
            ("Avg Score", f"{avg_score:.1f}"),
            ("Avg Days to Submit", f"{avg_days:.1f}"),
        ],
        [
            ("Hard Stops", f"{hard_stops:,}"),
            ("Total Claim Value", f"${total_claim:,.2f}"),
            ("Hard Stop Value", f"${hard_stop_val:,.2f}"),
        ],
        [
            ("Time Bypasses", f"{time_bypasses:,}"),
        ],
    ])


def render_reporting_charts(df: pd.DataFrame) -> None:
    if df.empty:
        return
    with st.container(border=True):
        st.markdown("### Visual Summary")
        r1, r2 = st.columns(2)
        with r1:
            status_png = review_status_pie(df)
            if status_png:
                st.image(status_png, use_container_width=True, caption="Review Status Mix")
        with r2:
            score_png = score_distribution_chart(df)
            if score_png:
                st.image(score_png, use_container_width=True, caption="Audit Score Distribution")


def render_reporting_vin_recalls(
    df: pd.DataFrame,
    *,
    all_time_df: pd.DataFrame | None = None,
) -> None:
    st.caption("VINs flagged with open or identified recall campaigns during the selected period.")
    if "vin_recall_identified" not in df.columns:
        st.info(
            "VIN recall columns are not in Supabase yet. Run the migration in "
            "`docs/SUPABASE_SCHEMA.sql`, then save new reviews to populate this report."
        )
        return

    recall_flag = pd.to_numeric(df["vin_recall_identified"], errors="coerce").fillna(0).astype(int)
    recall_df = df[recall_flag == 1].copy()
    all_time_source = all_time_df if all_time_df is not None else df
    all_time_total = 0
    if not all_time_source.empty and "vin_recall_identified" in all_time_source.columns:
        all_time_total = int(
            pd.to_numeric(all_time_source["vin_recall_identified"], errors="coerce").fillna(0).astype(int).sum()
        )

    render_metric_rows([
        [
            ("VINs With Recalls (period)", f"{len(recall_df):,}"),
            ("VINs With Recalls (all time)", f"{all_time_total:,}"),
            (
                "Recall Acknowledgments",
                f"{int(pd.to_numeric(recall_df.get('vin_recall_acknowledged', 0), errors='coerce').fillna(0).sum()) if not recall_df.empty else 0:,}",
            ),
        ],
    ])

    if recall_df.empty:
        st.info("No VINs with identified recalls in the selected reporting period.")
        return

    recall_display = recall_df.copy()
    if "created_at" in recall_display.columns:
        recall_display["created_at"] = pd.to_datetime(
            recall_display["created_at"], errors="coerce"
        ).dt.strftime("%Y-%m-%d %H:%M")
    show_cols = [
        c for c in (
            "created_at", "ro_number", "vin", "vin_recall_count",
            "vin_recall_campaigns", "vin_recall_acknowledged", "advisor",
        )
        if c in recall_display.columns
    ]
    recall_export = recall_display[show_cols] if show_cols else recall_display
    render_branded_report_table(
        recall_export,
        pdf_title="RO GUARD VIN Recall Report",
        period_label=period_label_from_df(recall_df),
        pdf_subtitle="VIN Recalls",
        pdf_landscape=True,
        pdf_filename="RO_Guard_VIN_Recalls.pdf",
        csv_filename="RO_Guard_VIN_Recalls.csv",
        export_key="reporting_vin_recalls",
    )


def render_reporting_rejections(df: pd.DataFrame) -> None:
    st.caption(
        "Track why claims were declined — standard reason, user notes, and paid-after-rejection "
        "initial decline text are all preserved exactly as entered."
    )
    declined = _declined_outcome_reviews(df)
    if declined.empty:
        st.info(
            "No rejected or paid-after-rejection outcomes in this date range. "
            "Mark outcomes on **Review** or **Claim Outcomes**."
        )
        return

    detail = _rejection_detail_frame(df)
    with_reason = detail[detail["full_decline_reason"] != "—"]
    missing = len(detail) - len(with_reason)

    render_metric_rows([
        [
            ("Declined Claims", f"{len(declined):,}"),
            ("With Decline Reason", f"{len(with_reason):,}"),
            ("Missing Reason", f"{missing:,}"),
        ],
    ])

    if not with_reason.empty:
        summary = with_reason.copy()
        summary["decline_category"] = summary["decline_category"].replace("—", "Uncategorized")
        reason_summary = summary.groupby("decline_category", as_index=False).agg(
            count=("ro_number", "count"),
            total_value=("total_claim_value", "sum"),
        ).sort_values(["count", "total_value"], ascending=[False, False])
        st.markdown("**Decline reasons by category**")
        category_export = reason_summary.rename(
            columns={
                "decline_category": "Reason Category",
                "count": "Claims",
                "total_value": "Claim Value",
            }
        )
        render_branded_report_table(
            category_export,
            pdf_title="RO GUARD Decline Reasons Summary",
            period_label=period_label_from_df(detail),
            pdf_subtitle="Decline Summary",
            pdf_filename="RO_Guard_Decline_Reasons_Summary.pdf",
            csv_filename="RO_Guard_Decline_Reasons_Summary.csv",
            export_key="decline_reasons_summary",
        )

    st.markdown("**All decline detail (full text preserved)**")
    if missing:
        st.warning(
            f"{missing} declined claim(s) are missing a reason — update them under **Claim Outcomes**."
        )
    export_detail = detail.rename(
        columns={
            "created_at": "Audited",
            "ro_number": "RO",
            "advisor": "Advisor",
            "outcome": "Outcome",
            "decline_category": "Reason Category",
            "decline_notes": "User Notes",
            "full_decline_reason": "Full Decline Reason (as entered)",
            "total_claim_value": "Claim Value",
        }
    )

    if "created_at" in detail.columns and detail["created_at"].notna().any():
        decline_period = f"{detail['created_at'].min()} to {detail['created_at'].max()}"
    else:
        decline_period = "Selected period"

    render_branded_report_table(
        export_detail,
        pdf_builder=lambda: build_decline_reasons_pdf(export_detail, period_label=decline_period),
        pdf_filename="RO_Guard_Decline_Reasons.pdf",
        csv_filename="RO_Guard_Decline_Reasons.csv",
        export_key="decline_reasons",
    )


_SCORE_BAND_GREEN = "background-color: #dcfce7; color: #166534; font-weight: 700"
_SCORE_BAND_YELLOW = "background-color: #fef9c3; color: #854d0e; font-weight: 700"
_SCORE_BAND_RED = "background-color: #fee2e2; color: #991b1b; font-weight: 700"


def _band_style_for_score(score: float) -> str:
    if score >= 90:
        return _SCORE_BAND_GREEN
    if score >= 80:
        return _SCORE_BAND_YELLOW
    return _SCORE_BAND_RED


def _band_style_for_severity_type(val) -> str:
    text = str(val).lower()
    if "hard" in text:
        return _SCORE_BAND_RED
    if "warn" in text:
        return _SCORE_BAND_YELLOW
    return ""


def _band_style_for_count(val, *, high: float, mid: float) -> str:
    try:
        count = float(val)
    except (TypeError, ValueError):
        return ""
    if count <= 0:
        return ""
    if count >= high:
        return _SCORE_BAND_RED
    if count >= mid:
        return _SCORE_BAND_YELLOW
    return _SCORE_BAND_GREEN


def _style_audit_rule_breakdown(df: pd.DataFrame):
    """Color-code audit rule table to match team performance score bands."""
    display = df.copy()
    if "% of Findings" in display.columns:
        display["% of Findings"] = pd.to_numeric(display["% of Findings"], errors="coerce").round(1)

    styler = display.style
    if "Type" in display.columns:
        styler = styler.map(_band_style_for_severity_type, subset=["Type"])

    if "Count" in display.columns:
        counts = pd.to_numeric(display["Count"], errors="coerce").fillna(0)
        high = float(counts.max()) if len(counts) else 0
        mid = high * 0.5 if high else 0
        styler = styler.map(
            lambda val: _band_style_for_count(val, high=high, mid=mid),
            subset=["Count"],
        )

    if "% of Findings" in display.columns:
        pcts = pd.to_numeric(display["% of Findings"], errors="coerce").fillna(0)
        high = float(pcts.max()) if len(pcts) else 0
        mid = high * 0.75 if high else 0
        styler = styler.map(
            lambda val: _band_style_for_count(val, high=high, mid=mid),
            subset=["% of Findings"],
        )

    return styler


def _style_advisor_rule_pivot(df: pd.DataFrame):
    """Color-code advisor issue counts with the same red / yellow / green bands."""
    display = df.copy()
    numeric_cols = list(display.select_dtypes(include="number").columns)
    if not numeric_cols:
        return display.style

    max_val = float(display[numeric_cols].max().max())
    high = max_val if max_val > 0 else 1
    mid = high * 0.5

    styler = display.style
    for col in numeric_cols:
        styler = styler.map(
            lambda val, h=high, m=mid: _band_style_for_count(val, high=h, mid=m),
            subset=[col],
        )
    return styler


def _style_avg_score_table(df: pd.DataFrame):
    """Color-code avg_score: green 90+, yellow 80-89, red below 80."""
    display = df.copy()
    if "avg_score" in display.columns:
        display["avg_score"] = pd.to_numeric(display["avg_score"], errors="coerce").round(1)

    def _avg_score_color(val) -> str:
        try:
            score = float(val)
        except (TypeError, ValueError):
            return ""
        return _band_style_for_score(score)

    styler = display.style
    if "avg_score" in display.columns:
        styler = styler.map(_avg_score_color, subset=["avg_score"])
    return styler


def render_reporting_team_performance(df: pd.DataFrame) -> None:
    st.caption("Rank advisors, technicians, and warranty admins by audit quality.")
    perf_df = df.copy()
    perf_df["score"] = pd.to_numeric(perf_df.get("score", 0), errors="coerce").fillna(0)
    perf_df["hard_stop_count"] = pd.to_numeric(perf_df.get("hard_stop_count", 0), errors="coerce").fillna(0)
    perf_df["warning_count"] = pd.to_numeric(perf_df.get("warning_count", 0), errors="coerce").fillna(0)

    rank_col = st.selectbox(
        "Rank By",
        ["advisor", "technician", "warranty_admin"],
        key="rank_by_employee",
    )

    if rank_col in perf_df.columns and not perf_df.empty:
        ranking = perf_df.groupby(rank_col).agg(
            reviews=("ro_number", "count"),
            avg_score=("score", "mean"),
            hard_stops=("hard_stop_count", "sum"),
            warnings=("warning_count", "sum"),
        ).reset_index()
        worst = ranking.sort_values(["hard_stops", "warnings"], ascending=[False, False]).head(5)
        best = ranking.sort_values(["avg_score", "hard_stops"], ascending=[False, True]).head(5)
        perf_period = period_label_from_df(perf_df)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Top Offenders")
            st.caption("Avg score: green 90+, yellow 80–89, red below 80.")
            render_branded_report_table(
                _style_avg_score_table(worst),
                export_df=worst,
                pdf_title="RO GUARD Team Performance — Top Offenders",
                period_label=perf_period,
                pdf_subtitle="Team Performance",
                pdf_filename="RO_Guard_Team_Top_Offenders.pdf",
                csv_filename="RO_Guard_Team_Top_Offenders.csv",
                export_key="team_perf_worst",
            )
        with c2:
            st.markdown("### Best Performers")
            st.caption("Avg score: green 90+, yellow 80–89, red below 80.")
            render_branded_report_table(
                _style_avg_score_table(best),
                export_df=best,
                pdf_title="RO GUARD Team Performance — Best Performers",
                period_label=perf_period,
                pdf_subtitle="Team Performance",
                pdf_filename="RO_Guard_Team_Best_Performers.pdf",
                csv_filename="RO_Guard_Team_Best_Performers.csv",
                export_key="team_perf_best",
            )

    st.markdown("### Employee Scorecards")
    scorecard_role = st.selectbox(
        "Scorecard Type",
        ["Advisor", "Technician", "Warranty Admin"],
        key="report_scorecard_role",
    )
    employee_col = {
        "Advisor": "advisor",
        "Technician": "technician",
        "Warranty Admin": "warranty_admin",
    }[scorecard_role]

    if employee_col in df.columns and not df.empty:
        score_df = df.copy()
        score_df["score"] = pd.to_numeric(score_df.get("score", 0), errors="coerce").fillna(0)
        score_df["hard_stop_count"] = pd.to_numeric(score_df.get("hard_stop_count", 0), errors="coerce").fillna(0)
        score_df["warning_count"] = pd.to_numeric(score_df.get("warning_count", 0), errors="coerce").fillna(0)
        score_df["days_to_submit"] = pd.to_numeric(score_df.get("days_to_submit", 0), errors="coerce").fillna(0)
        scorecard = score_df.groupby(employee_col).agg(
            reviews=("ro_number", "count"),
            avg_score=("score", "mean"),
            hard_stops=("hard_stop_count", "sum"),
            warnings=("warning_count", "sum"),
            avg_days_to_submit=("days_to_submit", "mean"),
        ).reset_index().sort_values(["hard_stops", "avg_score"], ascending=[False, True])
        render_branded_report_table(
            scorecard,
            pdf_title=f"RO GUARD {scorecard_role} Scorecards",
            period_label=period_label_from_df(df),
            pdf_subtitle="Team Performance",
            pdf_landscape=True,
            pdf_filename=f"RO_Guard_{scorecard_role.replace(' ', '_')}_Scorecards.pdf",
            csv_filename=f"RO_Guard_{scorecard_role.replace(' ', '_')}_Scorecards.csv",
            export_key=f"team_scorecard_{employee_col}",
        )


def render_reporting_short_pay(df: pd.DataFrame) -> None:
    st.caption(
        "Claims where OEM paid less than the audited value. Each row includes the required short-pay explanation."
    )
    data = normalize_reviews_dataframe(df)
    partial_count = int(data.get("is_partial_pay", pd.Series([False])).sum())
    short_pay_total = float(data.get("short_pay_amount", pd.Series([0])).sum())
    missing_reason = 0
    if partial_count and "short_pay_reason" in data.columns:
        partial_rows = data[data.get("is_partial_pay", False)]
        missing_reason = int(
            partial_rows["short_pay_reason"].fillna("").astype(str).str.strip().eq("").sum()
        )

    render_metric_rows([
        [
            ("Partial-pay claims", f"{partial_count:,}"),
            ("Short-pay total ($)", f"${short_pay_total:,.0f}"),
            ("Missing short-pay reason", f"{missing_reason:,}"),
        ],
    ])

    short_pay_df = build_short_pay_report_dataframe(df)
    if short_pay_df.empty:
        st.info(
            "No partial OEM payments in this date range. Record OEM paid amount on **Review** or **Claim Outcomes**."
        )
        return

    if missing_reason:
        st.warning(
            f"{missing_reason} partial-pay claim(s) are missing a short-pay reason — update them under **Claim Outcomes**."
        )

    render_branded_report_table(
        short_pay_df,
        pdf_builder=lambda: build_short_pay_report_pdf(
            short_pay_df,
            period_label=period_label_from_df(data),
        ),
        pdf_title="RO GUARD Short Pay Report",
        period_label=period_label_from_df(data),
        pdf_subtitle="Partial OEM Payments",
        pdf_filename="RO_Guard_Short_Pay_Report.pdf",
        csv_filename="RO_Guard_Short_Pay_Report.csv",
        export_key="short_pay_report",
    )


def render_reporting_review_log(df: pd.DataFrame) -> None:
    st.caption("Full review history for the selected date range. Export for meetings or records.")
    display_df = normalize_reviews_dataframe(df.drop(columns=["jobs"], errors="ignore").copy())
    if "outcome_status" not in display_df.columns and "first_pass_paid" in display_df.columns:
        display_df["outcome_status"] = [
            review_outcome_label(fp, rej, par)
            for fp, rej, par in zip(
                display_df.get("first_pass_paid", 0),
                display_df.get("rejected", 0),
                display_df.get("paid_after_rejection", 0),
            )
        ]
    priority_cols = [
        c for c in (
            "created_at",
            "ro_number",
            "advisor",
            "outcome_status",
            "rejection_reason",
            "score",
            "status",
            "total_claim_value",
            "oem_paid_amount",
            "short_pay_amount",
            "short_pay_reason",
            "hard_stop_count",
            "rejected",
            "paid_after_rejection",
            "first_pass_paid",
        )
        if c in display_df.columns
    ]
    other_cols = [c for c in display_df.columns if c not in priority_cols]
    display_df = display_df[priority_cols + other_cols]

    if "created_at" in df.columns and df["created_at"].notna().any():
        report_period = f"{df['created_at'].min().date()} to {df['created_at'].max().date()}"
    else:
        report_period = "Selected period"

    render_branded_report_table(
        display_df,
        pdf_builder=lambda: build_review_report_pdf(display_df, period_label=report_period),
        pdf_filename="RO_Guard_Review_Report.pdf",
        csv_filename="RO_Guard_Review_Report.csv",
        export_key="review_report",
    )


def render_reporting():
    st.markdown(
        """
        <div class="reporting-hero">
            <h2>Reporting</h2>
            <p>Team-wide review history stored in Supabase.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_refresh, col_migrate = st.columns([1, 2])
    with col_refresh:
        if st.button("Refresh Reporting"):
            invalidate_reviews_cache()
            st.rerun()
    with col_migrate:
        if st.button("Import old local reviews (SQLite → Supabase)"):
            migrated, skipped = migrate_sqlite_to_supabase(supabase, DB_PATH)
            invalidate_reviews_cache()
            st.success(f"Imported {migrated} review(s). Skipped {skipped} duplicate or invalid row(s).")
            st.rerun()

    all_reviews = normalize_reviews_dataframe(load_reviews())

    if user_can_admin_write():
        review_count = len(all_reviews)
        if review_count:
            with st.expander("Manager tools — clear test data", expanded=False):
                st.caption(
                    f"{review_count:,} saved review(s) in Reporting. "
                    "Use this before handing the app to your warranty administrator."
                )
                confirm_clear = st.checkbox(
                    "Permanently delete all saved reviews from Reporting",
                    key="confirm_clear_all_reviews",
                )
                if st.button(
                    "Clear all reporting data",
                    type="primary",
                    disabled=not confirm_clear,
                    key="clear_all_reviews_btn",
                ):
                    result = clear_all_reviews()
                    if result["removed"] > 0:
                        invalidate_reviews_cache()
                        st.success(f"Removed {result['removed']:,} review(s) from Reporting.")
                        st.rerun()
                    elif result["errors"]:
                        st.error(
                            "Could not clear reviews. Run `docs/CLEAR_REPORTING.sql` in Supabase SQL Editor once, "
                            "then retry."
                        )
                    else:
                        st.info("No reviews to remove.")

    if all_reviews.empty:
        st.info("No reviews saved yet. Complete a review on the Review tab and click Run Audit + Save Review.")
        return

    df = _filter_reviews_by_date(all_reviews, key_prefix="report")
    if df.empty:
        st.warning("No reviews in the selected date range.")
        return

    report_views = [
        "Overview",
        "Claim Outcomes",
        "VIN Recalls",
        "Rejections",
        "Short Pay",
        "Team Performance",
        "Review Log",
    ]
    report_view = st.radio(
        "Reporting view",
        report_views,
        horizontal=True,
        label_visibility="collapsed",
        key="reporting_view_nav",
    )

    if report_view == "Overview":
        st.markdown("### Summary")
        render_reporting_summary(df)
        render_reporting_charts(df)
    elif report_view == "Claim Outcomes":
        render_outcome_followup(df, show_title=False)
    elif report_view == "VIN Recalls":
        render_reporting_vin_recalls(df, all_time_df=all_reviews)
    elif report_view == "Rejections":
        render_reporting_rejections(df)
    elif report_view == "Short Pay":
        render_reporting_short_pay(df)
    elif report_view == "Team Performance":
        render_reporting_team_performance(df)
    elif report_view == "Review Log":
        render_reporting_review_log(df)


def render_personnel_admin():
    st.header("Personnel")
    st.caption(
        "Manage advisors, technicians, warranty admins, managers, and platform admins. "
        "Each person can hold **multiple roles** (e.g. Advisor + Warranty Admin). "
        "The **Email** must match their Supabase login."
    )

    def _personnel_display_table(frame):
        if frame.empty:
            return frame
        show = frame.copy()
        show["roles"] = show.apply(
            lambda row: format_roles_display(parse_personnel_roles(row)),
            axis=1,
        )
        cols = [c for c in ("name", "roles", "email", "employee_number", "id") if c in show.columns]
        return show[cols] if cols else show

    df = load_personnel()
    if not user_can_manage_personnel():
        render_role_gate_message(PERSONNEL_ADMIN_ROLES, "manage personnel")
        if df.empty:
            st.info("No personnel added yet.")
        else:
            st.dataframe(_personnel_display_table(df), use_container_width=True)
        return

    with st.form("add_person"):
        name = st.text_input("Name")
        email = st.text_input("Email (login)", placeholder="you@dealership.com")
        employee_number = st.text_input("Employee Number")
        add_roles = assignable_personnel_roles()
        selected_roles = _pick_personnel_roles(
            add_roles,
            ["Advisor"] if "Advisor" in add_roles else add_roles[:1],
            key_prefix="add_person_roles",
        )
        submitted = st.form_submit_button("Add Person")
        if submitted and name.strip():
            if email.strip() and not is_valid_email(email):
                st.error("Enter a valid email address, or leave email blank.")
            elif not selected_roles:
                st.error("Select at least one role.")
            else:
                add_person_shared(name.strip(), selected_roles, employee_number, email)
                st.success("Person added.")

    df = load_personnel()
    st.subheader("Edit Existing Employee")

    if df.empty:
        st.info("No personnel added yet.")
        return

    employee_names = df["name"].tolist()
    selected_employee = st.selectbox("Select Employee to Edit", employee_names)
    selected_row = df[df["name"] == selected_employee].iloc[0]
    existing_roles = parse_personnel_roles(selected_row)
    protected_admin = "Admin" in existing_roles and not user_is_platform_admin()

    edit_name = st.text_input("Edit Name", value=selected_row.get("name", ""))
    edit_email = st.text_input(
        "Edit Email (login)",
        value=str(selected_row.get("email", "") or ""),
        placeholder="you@dealership.com",
    )
    edit_employee_number = st.text_input(
        "Edit Employee Number",
        value=str(selected_row.get("employee_number", "")),
    )

    if protected_admin:
        st.info("This account has the **Admin** role. Only another Admin can change it.")

    edit_role_options = assignable_personnel_roles()
    edit_roles_selected = _pick_personnel_roles(
        edit_role_options,
        existing_roles,
        key_prefix=f"edit_person_roles_{selected_row['id']}",
        disabled=protected_admin,
    )

    if st.button("Save Employee Changes"):
        if protected_admin:
            st.error("Only an Admin can modify another Admin account.")
        elif edit_email.strip() and not is_valid_email(edit_email):
            st.error("Enter a valid email address, or clear the email field.")
        elif not edit_roles_selected:
            st.error("Select at least one role.")
        else:
            role_list = normalize_roles_list(edit_roles_selected)
            update_payload = {
                "name": edit_name,
                "employee_number": edit_employee_number,
                "roles": role_list,
                "role": primary_personnel_role(role_list),
                "email": normalize_email(edit_email) or None,
            }
            supabase.table("personnel").update(update_payload).eq("id", selected_row["id"]).execute()

            st.success("Employee updated.")
            st.rerun()

    st.dataframe(_personnel_display_table(df), use_container_width=True)
    remove_id = st.number_input("Deactivate personnel ID", min_value=0, value=0, step=1)
    if st.button("Deactivate") and remove_id:
        deactivate_person(remove_id)
        st.success("Personnel deactivated.")


def render_admin():
    st.header("Admin")
    st.caption(
        "Dealership settings, audit rules, rejection reasons, and personnel. "
        "Saves require a linked **Manager**, **Warranty Admin**, or **Admin** account."
    )

    admin_tab_labels = [
        "Smart Warranty",
        "Audit Rules",
        "Rejection Reasons",
        "Personnel",
    ]
    admin_tab_fns = [
        render_smart_warranty_admin,
        render_audit_rules_admin,
        render_rejection_reason_library_admin,
        render_personnel_admin,
    ]
    if user_can_view_deployment():
        admin_tab_labels.append("Deployment & Secrets")
        admin_tab_fns.append(render_deployment_secrets_admin)
    if user_can_see_pricing():
        admin_tab_labels.append("Pricing & ROI")
        admin_tab_fns.append(render_pricing_roi)

    admin_tabs = st.tabs(admin_tab_labels)
    for tab, render_fn in zip(admin_tabs, admin_tab_fns):
        with tab:
            render_fn()


def render_scheduled_reports():
    render_scheduled_reports_admin(supabase)


def render_tsb_bulletins():
    st.header("TSB / Service Bulletins")
    st.caption(
        "Upload Stellantis Technical Service Bulletins (PDF) or add manual rules. "
        "During Review, matching bulletins appear when the repair applies to the job."
    )

    can_upload = user_can_upload_library()
    if not can_upload:
        render_role_gate_message(CONTENT_ADMIN_ROLES, "upload or add bulletins")

    upload_tab, manual_tab = st.tabs(["Upload TSB (PDF)", "Manual entry"])

    with upload_tab:
        if not can_upload:
            st.info("PDF upload is available to Manager and Warranty Admin only.")
        else:
            uploaded_files = st.file_uploader(
                "Upload TSB PDF",
                type=["pdf"],
                accept_multiple_files=True,
                key="tsb_upload",
            )
            if uploaded_files:
                for file in uploaded_files:
                    try:
                        text, ocr_used = extract_ro_text(file.getvalue())
                        if len(text.strip()) < 40:
                            st.warning(f"{file.name}: little or no text could be extracted.")
                            continue

                        bulletin_number, title, auto_keywords = _extract_tsb_metadata(text, file.name)
                        save_bulletin(
                            title,
                            auto_keywords,
                            text[:4000],
                            source_file=file.name,
                            bulletin_number=bulletin_number,
                            content=text,
                        )
                        ocr_note = " (scanned — OCR used)" if ocr_used else ""
                        label = f"TSB {bulletin_number}" if bulletin_number else title
                        st.success(f"{file.name} saved{ocr_note} — {label}")
                    except Exception as e:
                        st.error(f"TSB upload failed for {file.name}: {e}")

            if not ocr_available():
                st.caption(
                    "Scanned TSB PDFs need OCR. Install Tesseract and `pdf2image` for image-only bulletins."
                )

    with manual_tab:
        if not can_upload:
            st.info("Manual bulletin entry is available to Manager and Warranty Admin only.")
        else:
            with st.form("add_bulletin"):
                title = st.text_input("Bulletin / Rule Title")
                keywords = st.text_input("Keywords (comma-separated)")
                notes = st.text_area("Notes / rule text")
                bulletin_number = st.text_input("TSB number (optional)", placeholder="e.g. 23-045")
                if st.form_submit_button("Add Bulletin / Rule") and title.strip():
                    save_bulletin(
                        title,
                        keywords,
                        notes,
                        bulletin_number=bulletin_number,
                        content=notes,
                    )
                    st.success("Bulletin/rule added.")

    st.subheader("Saved bulletins")
    bdf = load_bulletins(supabase)
    if bdf.empty:
        st.info("No bulletins saved yet.")
        return

    search_col, filter_col, sort_col = st.columns([3, 1.2, 1.2])
    with search_col:
        tsb_search = st.text_input(
            "Search bulletins",
            placeholder="TSB number, title, keyword, component, source file…",
            key="tsb_search_query",
        )
    with filter_col:
        tsb_entry_filter = st.selectbox(
            "Entry type",
            ["All", "PDF upload", "Manual entry"],
            key="tsb_entry_filter",
        )
    with sort_col:
        tsb_sort = st.selectbox(
            "Sort by",
            ["Newest first", "Oldest first", "TSB number", "Title"],
            key="tsb_sort_by",
        )

    filtered = sort_bulletins_df(
        filter_bulletins_df(
            bdf,
            query=tsb_search,
            entry_type=tsb_entry_filter,
        ),
        sort_by=tsb_sort,
    )
    st.caption(f"Showing **{len(filtered)}** of **{len(bdf)}** bulletin(s).")

    if filtered.empty:
        st.warning("No bulletins match your search or filters.")
        return

    display_cols = [
        c for c in ("created_at", "bulletin_number", "title", "source_file", "keywords")
        if c in filtered.columns
    ]
    st.dataframe(filtered[display_cols] if display_cols else filtered, use_container_width=True)

    st.markdown("#### Bulletin preview")
    preview_idx = st.selectbox(
        "Select a bulletin to preview",
        options=list(filtered.index),
        format_func=lambda idx: _bulletin_preview_label(filtered.loc[idx]),
        key="tsb_preview_select",
    )
    preview_row = filtered.loc[preview_idx]
    preview_title = str(preview_row.get("title") or "").strip() or "Untitled bulletin"
    st.markdown(f"**{preview_title}**")

    meta_bits = []
    bulletin_num = str(preview_row.get("bulletin_number") or "").strip()
    if bulletin_num:
        meta_bits.append(f"TSB **{bulletin_num}**")
    source_file = str(preview_row.get("source_file") or "").strip()
    if source_file:
        meta_bits.append(f"PDF: `{source_file}`")
    else:
        meta_bits.append("Manual entry")
    created_at = str(preview_row.get("created_at") or "").strip()
    if created_at:
        meta_bits.append(f"Added {created_at[:10]}")
    if meta_bits:
        st.caption(" · ".join(meta_bits))

    keywords = str(preview_row.get("keywords") or "").strip()
    if keywords:
        st.markdown(f"**Keywords:** {keywords}")

    preview_content = str(
        preview_row.get("content") or preview_row.get("notes") or ""
    ).strip()
    if preview_content:
        st.text_area(
            "Bulletin text",
            preview_content[:12000],
            height=320,
            disabled=True,
            label_visibility="collapsed",
            key=f"tsb_preview_text_{preview_idx}",
        )
        if len(preview_content) > 12000:
            st.caption("Preview truncated — full text is stored in Supabase.")
    else:
        st.caption("No bulletin text stored for this entry.")


def render_smart_warranty_admin():
    st.header("Smart Warranty Program")
    st.caption(
        "Set your Stellantis Smart Warranty level here. "
        "**Manager or Warranty Admin only** — this controls time-punch rules for the entire dealership."
    )

    settings = load_smart_warranty_settings(supabase)
    current_level = settings.get("smart_warranty_level", "base")
    updated_by = settings.get("updated_by") or "—"
    updated_at = settings.get("updated_at") or "—"

    with st.expander("Smart Warranty level benefits (reference)"):
        st.markdown(
            """
| Policy | Base | Plus | Premium |
|--------|------|------|---------|
| **Time punching** | Required for everything | Not required* | Not required* |
| Actual Time (A/T) review threshold | 0.5 hrs | 1.5 hrs | 2.5 hrs |
| Diagnostic / NTF review threshold | 0.5–1.0 hrs | 1.5 hrs | 4.0 hrs |

*Except Actual Time and Diagnostic Time — those still apply per Stellantis policy.
            """
        )

    authorized_names = admin_write_names()

    if not authorized_names:
        st.warning(
            "Add at least one **Manager** or **Warranty Admin** under Personnel before saving Smart Warranty level."
        )
    if not user_can_admin_write():
        render_role_gate_message(ADMIN_WRITE_ROLES, "save Smart Warranty settings")

    st.info(f"**Current level:** {current_level.title()} · Last saved by: {updated_by} · {updated_at}")

    with st.form("smart_warranty_level_form"):
        st.markdown("**Select dealer Smart Warranty level** (check one only):")
        c1, c2, c3 = st.columns(3)
        sw_base = c1.checkbox(
            "Base",
            value=current_level == "base",
            help="Time punch validation required on all jobs.",
        )
        sw_plus = c2.checkbox(
            "Plus",
            value=current_level == "plus",
            help="Time punch validation waived (except A/T and diagnostic time).",
        )
        sw_premium = c3.checkbox(
            "Premium",
            value=current_level == "premium",
            help="Time punch validation waived (except A/T and diagnostic time).",
        )

        author = render_admin_author_field(authorized_names, key="sw_author")

        if st.form_submit_button("Save Smart Warranty Level", type="primary"):
            selected = sum([sw_base, sw_plus, sw_premium])
            if not user_can_admin_write():
                st.error("Sign in as Manager or Warranty Admin to save Smart Warranty settings.")
            elif selected != 1:
                st.error("Check exactly one Smart Warranty level: Base, Plus, or Premium.")
            elif not author:
                st.error("Select an authorized Manager or Warranty Admin.")
            else:
                new_level = "base"
                if sw_plus:
                    new_level = "plus"
                elif sw_premium:
                    new_level = "premium"
                try:
                    save_smart_warranty_settings(supabase, new_level, author)
                    st.success(f"Smart Warranty level saved: **{new_level.title()}**")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not save Smart Warranty level: {e}")


def render_audit_rules_admin():
    st.header("Audit Rules & Thresholds")
    st.caption(
        "Configure dealership-wide warranty audit rules. "
        "**Hard Stop** blocks submission; **Warning** flags the job for review. "
        "**Manager or Warranty Admin only**."
    )

    settings = load_audit_rules(supabase)
    thresholds = settings["thresholds"]
    rules = settings["rules"]
    updated_by = settings.get("updated_by") or "—"
    updated_at = settings.get("updated_at") or "—"

    authorized_names = admin_write_names()

    if not authorized_names:
        st.warning(
            "Add at least one **Manager** or **Warranty Admin** under Personnel before saving audit rules."
        )
    if not user_can_admin_write():
        render_role_gate_message(ADMIN_WRITE_ROLES, "save audit rules")

    st.info(f"**Last saved by:** {updated_by} · {updated_at}")

    with st.form("audit_rules_form"):
        st.subheader("Thresholds")
        t1, t2, t3 = st.columns(3)
        tech_min_pct = t1.number_input(
            "Tech time minimum (% of allotted)",
            min_value=0,
            max_value=100,
            value=int(round(float(thresholds["tech_time_min_pct"]) * 100)),
            help="Flag when flagged time is below this percentage of time allotted.",
        )
        tech_max_pct = t2.number_input(
            "Tech time maximum (% of allotted)",
            min_value=100,
            max_value=500,
            value=int(round(float(thresholds["tech_time_max_pct"]) * 100)),
            help="Flag when flagged time exceeds this percentage of time allotted.",
        )
        rental_days_warn = t3.number_input(
            "Rental high-day warning (days)",
            min_value=1,
            max_value=90,
            value=int(thresholds["rental_days_warn"]),
            help="Warn when billed rental days reach this count.",
        )
        rental_dollars_per_day = st.number_input(
            "Rental dollars per day ($)",
            min_value=0.0,
            value=float(thresholds.get("rental_dollars_per_day", 0) or 0),
            step=1.0,
            format="%.2f",
            help="Daily rental rate used on Review to calculate rental total (rate × days billed).",
        )

        st.subheader("Rule packs")
        st.caption("Turn rules off entirely with the checkbox, or change whether they hard-stop or warn.")

        new_rules = {}
        for rule_key in DEFAULT_AUDIT_RULES:
            label = AUDIT_RULE_LABELS[rule_key]
            current = rules[rule_key]
            c1, c2, c3 = st.columns([0.55, 0.25, 0.20])
            enabled = c1.checkbox(label, value=current["enabled"], key=f"audit_en_{rule_key}")
            severity_label = c2.selectbox(
                "Severity",
                ["Hard Stop", "Warning"],
                index=0 if current["severity"] == "hard" else 1,
                key=f"audit_sev_{rule_key}",
                disabled=not enabled,
                label_visibility="collapsed",
            )
            c3.caption("Off" if not enabled else severity_label)
            new_rules[rule_key] = {
                "enabled": enabled,
                "severity": "hard" if severity_label == "Hard Stop" else "warn",
            }

        author = render_admin_author_field(authorized_names, key="audit_rules_author")

        if st.form_submit_button("Save Audit Rules", type="primary"):
            if not user_can_admin_write():
                st.error("Sign in as Manager or Warranty Admin to save audit rules.")
            elif not author:
                st.error("Select an authorized Manager or Warranty Admin.")
            else:
                payload = {
                    "thresholds": {
                        "tech_time_min_pct": tech_min_pct / 100.0,
                        "tech_time_max_pct": tech_max_pct / 100.0,
                        "rental_days_warn": int(rental_days_warn),
                        "rental_dollars_per_day": float(rental_dollars_per_day),
                    },
                    "rules": new_rules,
                }
                try:
                    save_audit_rules(supabase, payload, author)
                    st.success("Audit rules saved for this dealership.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not save audit rules: {e}")
                    st.caption(
                        "If the column is missing, run in Supabase SQL Editor: "
                        "`ALTER TABLE dealer_settings ADD COLUMN IF NOT EXISTS audit_rules JSONB DEFAULT '{}'::jsonb;`"
                    )


def render_rejection_reason_library_admin():
    st.header("Rejection Reason Library")
    st.caption(
        "Standardize why warranty claims were rejected or returned. "
        "These options appear on the Review tab when **Rejected / Returned** is checked. "
        "**Manager or Warranty Admin only**."
    )

    library = load_rejection_reason_library(supabase)
    reasons = library.get("reasons", [])
    updated_by = library.get("updated_by") or "—"
    updated_at = library.get("updated_at") or "—"

    authorized_names = admin_write_names()

    if not authorized_names:
        st.warning(
            "Add at least one **Manager** or **Warranty Admin** under Personnel before saving rejection reasons."
        )
    if not user_can_admin_write():
        render_role_gate_message(ADMIN_WRITE_ROLES, "save rejection reasons")

    st.info(f"**Last saved by:** {updated_by} · {updated_at}")

    with st.form("rejection_reason_library_form"):
        st.subheader("Active rejection reasons")
        st.caption("Uncheck a reason to hide it from the Review dropdown.")

        updated_reasons = []
        for item in reasons:
            reason_id = item.get("id", "")
            label = item.get("label", "")
            active = st.checkbox(
                label,
                value=bool(item.get("active", True)),
                key=f"rej_reason_active_{reason_id}",
            )
            updated_reasons.append({
                "id": reason_id,
                "label": label,
                "active": active,
            })

        st.subheader("Add custom reason")
        new_reason = st.text_input(
            "New rejection reason",
            placeholder="e.g. Missing star case / photos",
        )

        author = render_admin_author_field(authorized_names, key="rejection_author")

        save_clicked = st.form_submit_button("Save Rejection Library", type="primary")
        if save_clicked:
            if not user_can_admin_write():
                st.error("Sign in as Manager or Warranty Admin to save rejection reasons.")
            elif not author:
                st.error("Select an authorized Manager or Warranty Admin.")
            else:
                final_reasons = list(updated_reasons)
                if new_reason.strip():
                    final_reasons.append({
                        "id": "",
                        "label": new_reason.strip(),
                        "active": True,
                    })
                try:
                    save_rejection_reason_library(supabase, final_reasons, author)
                    st.success("Rejection reason library saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not save rejection reason library: {e}")
                    st.caption(
                        "If the column is missing, run in Supabase SQL Editor: "
                        "`ALTER TABLE dealer_settings ADD COLUMN IF NOT EXISTS rejection_reasons JSONB DEFAULT '{}'::jsonb;`"
                    )

    if st.button("Restore default rejection reasons", key="restore_rejection_defaults"):
        author = resolve_admin_author(authorized_names)
        if not author:
            if not user_can_admin_write():
                st.error("Sign in as Manager or Warranty Admin to restore defaults.")
            elif not authorized_names:
                st.error("Add a Manager or Warranty Admin under Personnel first.")
            else:
                st.error("Select an authorized Manager or Warranty Admin.")
        else:
            try:
                save_rejection_reason_library(
                    supabase,
                    normalize_rejection_reason_library({})["reasons"],
                    author,
                )
                st.success("Default rejection reasons restored.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not restore defaults: {e}")


def render_wam():
    st.header("WAM / Warranty Manual Learning")
    st.caption("Upload WAM PDFs or warranty policy documents. RO Shield will store the text and use it for audit reference.")

    can_upload = user_can_upload_library()
    if not can_upload:
        render_role_gate_message(CONTENT_ADMIN_ROLES, "upload WAM documents")
        st.info("WAM upload is available to Manager and Warranty Admin only.")
    else:
        uploaded_files = st.file_uploader(
            "Upload WAM / Warranty Manual PDFs",
            type=["pdf"],
            accept_multiple_files=True,
            key="wam_upload"
        )

        if uploaded_files:
            for file in uploaded_files:
                try:
                    reader = PdfReader(file)
                    text = ""

                    for page in reader.pages:
                        page_text = page.extract_text() or ""
                        text += page_text + "\n"

                    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]

                    for idx, chunk in enumerate(chunks):
                        supabase.table("wam_documents").insert({
                            "source_file": file.name,
                            "section": f"{file.name} — Part {idx + 1}",
                            "keywords": _guess_wam_keywords(chunk),
                            "content": chunk
                        }).execute()

                    st.success(f"{file.name} uploaded and learned.")

                except Exception as e:
                    st.error(f"WAM upload failed for {file.name}: {e}")

    st.subheader("Saved WAM Entries")

    try:
        rows = supabase.table("wam_documents").select("*").execute().data or []
        st.dataframe(pd.DataFrame(rows), use_container_width=True)
    except Exception as e:
        st.warning(f"WAM entries could not load: {e}")

   
def main():
    init_db()

    if supabase is None:
        apply_style("Dark")
        st.error(
            "Supabase is not configured. "
            "**Local:** copy `.env.example` to `.env` and set `SUPABASE_URL` + `SUPABASE_KEY`. "
            "**Streamlit Cloud:** open **Manage app** → **Settings** → **Secrets** and paste the same values (see `docs/DEPLOY_STREAMLIT.md`)."
        )
        st.stop()

    inject_auth_hash_bridge()

    if is_password_recovery_mode():
        bootstrap_recovery_session(supabase)
        render_password_reset_page(supabase, apply_style=apply_style)
        st.stop()

    if not is_authenticated():
        restore_client_session(supabase)

    if not is_authenticated():
        render_login_page(supabase, apply_style=apply_style)
        st.stop()

    sync_personnel_identity(supabase)
    apply_session_to_client(supabase, get_stored_session())
    run_soft_refresh_if_requested(supabase)
    try:
        from core.popps_report import hydrate_popps_report_from_cloud

        hydrate_popps_report_from_cloud(supabase, auth_user=auth_user_email())
    except Exception:
        pass
    _ensure_review_form_session()
    configure_streamlit_toolbar()

    render_sidebar_brand()

    render_authenticated_sidebar(supabase)

    ensure_sidebar_expanded()

    st.sidebar.divider()

    if "appearance" not in st.session_state:
        st.session_state.appearance = "Dark"

    st.sidebar.markdown(
        '<div class="rg-sidebar-settings-title">Settings</div>',
        unsafe_allow_html=True,
    )

    appearance = st.sidebar.selectbox(
        "Appearance",
        ["Dark", "Light"],
        index=0 if st.session_state.appearance == "Dark" else 1,
        key="appearance_select",
    )
    st.session_state.appearance = appearance

    if st.session_state.get("_display_theme") != appearance:
        st.session_state._display_theme = appearance
        request_display_widget_resync()

    display_prefs = render_display_settings_sidebar(supabase, theme=appearance)
    apply_style(appearance, display_prefs)

    _render_app_workspace_header(appearance, supabase_client=supabase)

    try:
        from core.popps_report import (
            process_popps_notes_compliance,
            render_popps_compliance_global_banner,
        )

        process_popps_notes_compliance(supabase)
        render_popps_compliance_global_banner(
            supabase,
            is_warranty_admin=user_has_role("Warranty Admin"),
        )
    except Exception:
        pass

    tab_entries: list[tuple[str, callable]] = [
        ("Review", render_review),
        ("Pending Claims", render_pending_claims),
        ("ROI Dashboard", render_roi_dashboard),
        ("Coaching", render_coaching),
        ("POPPS Report", render_popps),
        ("Claim Learning", render_claims),
        ("Reporting", render_reporting),
        ("Admin", render_admin),
        ("TSB / Bulletins", render_tsb_bulletins),
        ("Scheduled Reports", render_scheduled_reports),
        ("WAM", render_wam),
    ]

    section_labels = [label for label, _ in tab_entries]
    st.markdown(
        '<div class="rg-section-nav-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    active_section = st.radio(
        "Section",
        section_labels,
        horizontal=True,
        label_visibility="collapsed",
        key="main_section_nav",
    )
    from core.ui_polish import notify_section_change

    notify_section_change(active_section)
    for label, render_fn in tab_entries:
        if label == active_section:
            render_fn()
            break

if __name__ == "__main__":
    main()
