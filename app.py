from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from charts import (
    advisor_hard_stops_chart,
    hard_stop_rules_chart,
    audit_outcomes_pie,
    first_pass_pie,
    issue_breakdown_pie,
    review_status_pie,
    score_distribution_chart,
    weekly_activity_chart,
)
from pdf_reports import build_audit_report_pdf, build_review_report_pdf, build_roi_report_pdf
from auth import (
    auth_user_email,
    capture_recovery_from_query,
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
    sync_personnel_identity,
)
from review_store import (
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
    review_outcome_label,
    save_audit_rules,
    save_bulletin as persist_bulletin,
    save_rejection_reason_library,
    save_review as persist_review,
    save_smart_warranty_settings,
    smart_warranty_punch_exempt,
    update_review_outcome,
)
from theme_styles import (
    BRAND_TEXT,
    THEME_CSS,
    brand_color_lock_css,
    claim_learning_css,
    metric_display_css,
)
from display_prefs import build_user_display_css, render_display_settings_sidebar, request_display_widget_resync
from ro_ocr import extract_ro_text, merge_form_imports, ocr_available, parsed_to_form_import, scan_repair_order_pdf
from vin_recalls import apply_job_relevance, lookup_vin_recalls, normalize_vin

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
if "form_version" not in st.session_state:
    st.session_state.form_version = 0

DB_PATH = Path("ro_shield_final.db")


# =========================
# DATABASE (Supabase = source of truth for reviews, claims, personnel, WAM)
# =========================
def save_review(data):
    try:
        persist_review(supabase, data)
        return True
    except Exception as e:
        st.error(f"Review save failed: {e}")
        st.caption("If this is your first deploy, run docs/SUPABASE_SCHEMA.sql in Supabase SQL Editor.")
        return False


def load_reviews():
    try:
        return fetch_reviews(supabase)
    except Exception as e:
        st.warning(f"Review load failed: {e}")
        return pd.DataFrame()


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


def add_person_shared(name, role, employee_number, email=""):
    try:
        existing = supabase.table("personnel").select("id").eq("name", name).eq("role", role).execute()

        if not existing.data:
            payload = {
                "name": name,
                "employee_number": employee_number,
                "role": role,
                "active": True,
            }
            email_clean = normalize_email(email)
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


ADMIN_WRITE_ROLES = ("Manager", "Warranty Admin")
PERSONNEL_ADMIN_ROLES = ("Manager",)
CONTENT_ADMIN_ROLES = ("Manager", "Warranty Admin")


def admin_write_names() -> list[str]:
    df = load_personnel()
    if df.empty:
        return []
    return df[df["role"].isin(ADMIN_WRITE_ROLES)]["name"].astype(str).tolist()


def current_person_name() -> str:
    return str(st.session_state.get("current_person_name") or "").strip()


def current_person_role() -> str:
    return str(st.session_state.get("current_person_role") or "").strip()


def is_signed_in() -> bool:
    return is_authenticated()


def user_has_role(*roles: str) -> bool:
    return current_person_role() in roles


def user_can_admin_write() -> bool:
    return user_has_role(*ADMIN_WRITE_ROLES)


def user_can_manage_personnel() -> bool:
    return user_has_role(*PERSONNEL_ADMIN_ROLES)


def user_can_upload_library() -> bool:
    return user_has_role(*CONTENT_ADMIN_ROLES)


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


def role_options(role):
    df = load_personnel()
    if df.empty:
        return [""]
    df = df[(df["role"] == role) & (df["active"].astype(bool))]
    return [""] + sorted(df["name"].astype(str).tolist())


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
        ["verified", "operates", "working", "proper operation", "test drove", "road test", "no further issues"],
        correction_blob,
    )
    if _current_missing(verification, correction):
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


def render_narrative_gap_coach(current_job: dict, similar_claims: list, job_no: int):
    st.markdown("### Narrative Gap Coach")
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


def render_declined_claim_alert(current_job: dict, similar_declined: list) -> None:
    text_len = len(
        f"{current_job.get('concern', '')} {current_job.get('cause', '')} {current_job.get('correction', '')}".strip()
    )
    if text_len < 20 or not similar_declined:
        return

    st.markdown("### Declined Claim Alert")
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
.stDeployButton {
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
    """Streamlit Share / Manage app chrome only for configured owner login(s)."""
    owners = _owner_emails()
    if not owners:
        # No owner list configured — rely on Streamlit Cloud toolbarMode=auto
        # (workspace admins see Share; regular app users do not).
        return True
    if not is_authenticated():
        return True
    email = normalize_email(auth_user_email())
    if not email:
        return True
    return email in owners


def _inject_streamlit_cloud_chrome_restore() -> None:
    """Undo any prior hide scripts/styles so owners see Share again."""
    components.html(
        """
        <script>
        (function () {
          function restoreChrome(doc) {
            if (!doc || !doc.body) return;
            doc.querySelectorAll(
              '[data-testid="stHeaderActionElements"], [data-testid="stToolbar"], [data-testid="stToolbarActions"], .stAppDeployButton, .stDeployButton'
            ).forEach(function (el) {
              el.style.removeProperty("display");
            });
            doc.querySelectorAll("a, button, span, p, div").forEach(function (el) {
              var text = (el.textContent || "").trim();
              if (text === "Share" || text === "Manage app") {
                var target = el.closest("a, button, [role='button']") || el;
                target.style.removeProperty("display");
                if (target.parentElement) {
                  target.parentElement.style.removeProperty("display");
                }
              }
            });
          }
          function sweep() {
            try { restoreChrome(document); } catch (e) {}
            try { restoreChrome(window.parent.document); } catch (e) {}
          }
          sweep();
          setTimeout(sweep, 250);
          setTimeout(sweep, 1000);
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def apply_style(theme="Dark", display_prefs: dict | None = None):
    css = THEME_CSS.get(theme, THEME_CSS["Dark"])
    if display_prefs:
        css += build_user_display_css(display_prefs, theme=theme)
    css += brand_color_lock_css(theme)
    css += metric_display_css()
    css += claim_learning_css(theme)
    if streamlit_cloud_chrome_allowed():
        _inject_streamlit_cloud_chrome_restore()
    else:
        css = STREAMLIT_CHROME_HIDE_CSS + css
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


def detect_claim_pdf_outcome(document_text: str) -> str:
    """Guess whether a Dealer Connect claim PDF is paid or declined/rejected."""
    flat = re.sub(r"\s+", " ", str(document_text or "")).strip()
    if len(flat) < 40:
        return "unknown"

    lower = flat.lower()
    declined = 0
    paid = 0

    if re.search(r"status\s*:\s*reject", lower):
        declined += 4
    if "global claim acknowledgement" in lower and re.search(r"\breject", lower):
        declined += 3
    if re.search(r"message code information", lower):
        declined += 3
    if re.search(
        r"dealer correctable message codes|authorization required message codes",
        lower,
    ):
        declined += 2
    if extract_message_code_reasons(document_text):
        declined += 3

    if re.search(r"status\s*:\s*paid", lower):
        paid += 4
    if re.search(r"status\s*:\s*approv", lower):
        paid += 3
    if re.search(r"claim\s+paid|payment\s+amount|paid\s+amount|amount\s+paid", lower):
        paid += 2

    if declined >= 3 and declined > paid:
        return "declined"
    if paid >= 3 and paid > declined:
        return "paid"
    if declined >= 2 and paid == 0:
        return "declined"
    if paid >= 2 and declined == 0:
        return "paid"
    return "unknown"


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


def render_applicable_manual_sections(sections, key_prefix="manual"):
    if not sections:
        return

    st.markdown("### Applicable Manual & TSB Guidance")
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
        if not any(x in correction_text for x in ["verified", "operates", "working", "proper operation", "no further issues", "test drove"]):
            _add_audit_finding(
                hard, warn, audit_rules, "pencil_wrench_correction",
                "Pencil Wrench Correction: proper operation was not verified after repair.",
            )

    if job.get("oil_leak"):
        _add_audit_finding(
            hard, warn, audit_rules, "oil_leak",
            "Oil leak selected: confirm oil dye is billed and narrative states dye was used.",
        )
        if not job.get("oil_dye_billed"):
            _add_audit_finding(hard, warn, audit_rules, "oil_leak", "Oil leak repair requires oil dye billed.")
        if "dye" not in text:
            _add_audit_finding(
                hard, warn, audit_rules, "oil_leak",
                "Oil leak narrative must state dye was used to locate the leak.",
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
        _add_audit_finding(
            hard, warn, audit_rules, "warranty_add_on",
            "Warranty add-on (W+) requires Service Manager sign-off.",
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
    ack = st.session_state.get(_vin_recall_ack_key(form_version, vin_clean)) or {}
    return bool(ack.get("acknowledged"))


def _ensure_vin_recall_lookup(vin: str, form_version: int) -> dict | None:
    """Auto-fetch NHTSA recalls when the VIN is long enough."""
    vin_clean = normalize_vin(vin)
    recall_key = f"vin_recall_result_{form_version}"
    tracked_vin_key = f"vin_recall_tracked_vin_{form_version}"

    if len(vin_clean) < 11:
        return None

    if st.session_state.get(tracked_vin_key) != vin_clean:
        st.session_state[recall_key] = _cached_vin_recall_lookup(vin_clean)
        st.session_state[tracked_vin_key] = vin_clean

    result = st.session_state.get(recall_key)
    if result and result.get("vin") != vin_clean:
        st.session_state[recall_key] = _cached_vin_recall_lookup(vin_clean)
        st.session_state[tracked_vin_key] = vin_clean
        result = st.session_state.get(recall_key)

    return result


def _vin_recall_save_fields(form_version: int, vin: str) -> dict:
    vin_clean = normalize_vin(vin)
    result = st.session_state.get(f"vin_recall_result_{form_version}") or {}
    count = int(result.get("recall_count") or 0) if result.get("ok") else 0
    campaigns = [
        str(item.get("campaign", "")).strip()
        for item in (result.get("recalls") or [])
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


@st.dialog("VIN Recall & Campaign Notice", width="large")
def _recall_acknowledgment_dialog(recall_result: dict, form_version: int):
    vehicle = recall_result.get("vehicle") or {}
    recalls = list(recall_result.get("recalls") or [])[:10]
    vin_clean = recall_result.get("vin") or ""

    vehicle_label = " ".join(
        p for p in (
            vehicle.get("model_year"),
            vehicle.get("make"),
            vehicle.get("model"),
            vehicle.get("trim"),
        )
        if p
    )

    st.warning(
        f"**{vehicle_label}** has **{recall_result.get('recall_count', 0)}** NHTSA recall campaign(s) on file "
        "for this vehicle configuration."
    )
    st.markdown(
        "This is **not a hard stop** — many campaigns may not have parts available yet. "
        "You must acknowledge this notice to continue with the claim, then verify completion status in "
        "**OASIS / wiTECH / DealerCONNECT**."
    )
    st.caption(recall_result.get("disclaimer", ""))

    for recall in recalls:
        flags = []
        if recall.get("park_it"):
            flags.append("Park It")
        if recall.get("park_outside"):
            flags.append("Park Outside")
        if recall.get("ota"):
            flags.append("OTA")
        flag_text = f" · {' / '.join(flags)}" if flags else ""
        st.markdown(f"**{recall.get('campaign', 'Campaign')}** — {recall.get('component', '')}{flag_text}")
        if recall.get("summary"):
            st.caption(recall.get("summary")[:280] + ("…" if len(recall.get("summary", "")) > 280 else ""))

    remaining = int(recall_result.get("recall_count") or 0) - len(recalls)
    if remaining > 0:
        st.caption(f"+ {remaining} additional campaign(s) listed in the recall panel below.")

    if st.button("I acknowledge — continue with this claim", type="primary", use_container_width=True):
        st.session_state[_vin_recall_ack_key(form_version, vin_clean)] = {
            "acknowledged": True,
            "acknowledged_at": datetime.now().isoformat(timespec="seconds"),
        }
        st.rerun()


def render_vin_recall_panel(vin: str, form_version: int, job_count: int):
    recall_key = f"vin_recall_result_{form_version}"
    vin_clean = normalize_vin(vin)

    st.markdown("### VIN Recall & Campaign Check")
    st.caption(
        "Recalls are checked automatically when a VIN is entered or scanned. "
        "Verify open/completed status in **OASIS / wiTECH / DealerCONNECT** before submit."
    )

    if len(vin_clean) < 11:
        st.info("Enter or scan the full VIN — recall lookup runs automatically.")
        return

    tracked_vin_key = f"vin_recall_tracked_vin_{form_version}"
    needs_fetch = st.session_state.get(tracked_vin_key) != vin_clean
    if needs_fetch:
        with st.spinner("Checking NHTSA recalls for this VIN…"):
            result = _ensure_vin_recall_lookup(vin, form_version)
    else:
        result = _ensure_vin_recall_lookup(vin, form_version)

    if not result:
        return

    if not result.get("ok"):
        st.error(result.get("error") or "Recall lookup failed.")
        return

    if result.get("recall_count", 0) > 0 and not _is_vin_recall_acknowledged(form_version, vin_clean):
        _recall_acknowledgment_dialog(result, form_version)

    vehicle = result.get("vehicle") or {}
    recalls = list(result.get("recalls") or [])
    job_text = _review_job_text_from_session(form_version, job_count)
    if job_text.strip() and recalls:
        recalls = apply_job_relevance(recalls, job_text)

    vehicle_label = " ".join(
        p for p in (
            vehicle.get("model_year"),
            vehicle.get("make"),
            vehicle.get("model"),
            vehicle.get("trim"),
        )
        if p
    )

    if result.get("recall_count", 0) > 0:
        if _is_vin_recall_acknowledged(form_version, vin_clean):
            st.success(
                f"**{vehicle_label}** · {result.get('recall_count', 0)} recall campaign(s) on file · "
                "**Acknowledged**"
            )
        else:
            st.warning(
                f"**{vehicle_label}** · {result.get('recall_count', 0)} recall campaign(s) on file · "
                "**Acknowledgment required** (see popup)"
            )
    else:
        st.success(f"**{vehicle_label}** · No NHTSA recalls returned for this configuration.")

    if result.get("critical_count"):
        st.error(
            f"{result.get('critical_count')} campaign(s) flagged **Park It / Park Outside** — "
            "verify immediately in OASIS."
        )

    related = [r for r in recalls if r.get("relevance_score", 0) >= 12]
    if related:
        st.warning(
            f"**{len(related)} recall(s) may relate to this repair** based on the job narrative — "
            "confirm whether the campaign applies and is complete."
        )
    elif job_text.strip() and result.get("recall_count", 0) > 0:
        st.caption("No strong narrative match to a listed recall — still verify VIN status in OASIS.")

    st.caption(result.get("disclaimer", ""))

    if result.get("recall_count", 0) <= 0:
        return

    show_recalls = related[:5] if related else recalls[:8]
    for idx, recall in enumerate(show_recalls):
        campaign = recall.get("campaign") or "Campaign"
        component = recall.get("component") or "Component not listed"
        flags = []
        if recall.get("park_it"):
            flags.append("Park It")
        if recall.get("park_outside"):
            flags.append("Park Outside")
        if recall.get("ota"):
            flags.append("OTA")
        flag_text = f" · **{' / '.join(flags)}**" if flags else ""

        rel_score = recall.get("relevance_score", 0)
        rel_note = ""
        if rel_score >= 12:
            hits = ", ".join(recall.get("relevance_hits") or [])
            rel_note = f" · Possible repair match ({hits})" if hits else " · Possible repair match"

        with st.expander(f"{campaign} — {component}{flag_text}", expanded=idx == 0 and rel_score >= 12):
            if recall.get("report_date"):
                st.caption(f"Report date: {recall['report_date']}{rel_note}")
            if recall.get("summary"):
                st.markdown(f"**Summary:** {recall['summary']}")
            if recall.get("consequence"):
                st.markdown(f"**Risk:** {recall['consequence']}")
            if recall.get("remedy"):
                st.markdown(f"**Remedy:** {recall['remedy']}")

    remaining = len(recalls) - len(show_recalls)
    if remaining > 0:
        st.caption(f"+ {remaining} additional recall(s) on file for this vehicle configuration.")


def _vin_recall_blocks_audit(form_version: int, vin: str) -> bool:
    vin_clean = normalize_vin(vin)
    result = st.session_state.get(f"vin_recall_result_{form_version}") or {}
    if not result.get("ok"):
        return False
    if int(result.get("recall_count") or 0) <= 0:
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

    recall_block = _vin_recall_blocks_audit(form_version, vin)

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
        for src, dest in checkbox_map.items():
            if job.get(src):
                st.session_state[f"{dest}_{idx}"] = True


def _inline_text_color(color: str) -> str:
    return f' style="color: {color} !important; -webkit-text-fill-color: {color} !important;"'


def _render_app_workspace_header(theme: str = "Dark") -> None:
    key = "Light" if str(theme).lower() == "light" else "Dark"
    c = BRAND_TEXT[key]
    st.markdown(
        f"""
<div class="app-workspace-header">
<div class="app-workspace-kicker"{_inline_text_color(c["workspace_kicker"])}>RO Guard · Warranty Workspace</div>
<h2{_inline_text_color(c["workspace_h2"])}>Smarter Claims. <span{_inline_text_color(c["workspace_h2"])}>Stronger Profits.</span></h2>
<p{_inline_text_color(c["workspace_body"])}>Audit warranty ROs, protect claim dollars, and prove ROI across review, reporting, and admin tools.</p>
<div class="app-workspace-accent"{_inline_text_color(c["workspace_accent"])}>Control the Claim · Protect the Profit</div>
</div>
        """,
        unsafe_allow_html=True,
    )


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

def render_review():
    _render_ro_scanner()

    _, next_col = st.columns([5, 1])
    with next_col:
        if st.button("Next Claim"):
            fv = st.session_state.form_version
            st.session_state.pop(f"vin_recall_result_{fv}", None)
            st.session_state.pop(f"vin_recall_tracked_vin_{fv}", None)
            st.session_state.form_version += 1
            st.session_state.pop("_ro_scan_advisor", None)
            st.session_state.pop("_ro_scan_technician", None)
            st.session_state.pop("ro_scan_summary", None)
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
        st.success(
            f"Smart Warranty **{sw_level.title()}** — time punch validation is not required for this dealership "
            "(Plus/Premium benefit). No bypass will be recorded on saved reviews."
        )
    else:
        st.caption(
            f"Smart Warranty level: **Base** — tech flagged time vs. time allotted validation applies."
        )

    job_count = st.number_input(
        "How many warranty jobs are on this RO?",
        min_value=1,
        max_value=10,
        value=st.session_state.job_count,
        step=1,
        key="job_count"
    )

    ro_number = st.text_input("RO Number", key=f"ro_number_{st.session_state.form_version}")
    vin = st.text_input("VIN", key=f"vin_{st.session_state.form_version}")
    ro_invoiced = st.date_input(
        "RO Invoiced / Closed Date",
        key=f"ro_invoiced_{st.session_state.form_version}"
    )
    day_submitted = st.date_input(
        "Day Submitted",
        key=f"day_submitted_{st.session_state.form_version}"
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

    with st.expander("Claim outcome (optional — update later in Reporting)", expanded=False):
        st.caption(
            "Record the Stellantis result when you know it. Leave both unchecked if the claim "
            "is still pending — you can update outcomes anytime under **Reporting**."
        )
        first_pass_paid = st.checkbox(
            "Paid on First Submission",
            key=f"first_pass_paid_{st.session_state.form_version}",
        )

        rejected = st.checkbox(
            "Rejected / Returned",
            key=f"rejected_{st.session_state.form_version}",
        )

        rejection_reason = ""
        if rejected:
            reason_labels = active_rejection_reason_labels(rejection_library)
            if not reason_labels:
                reason_labels = active_rejection_reason_labels({})

            fv = st.session_state.form_version
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
                if selected_reason.lower().startswith("other") and not rejection_notes.strip():
                    st.warning("Add notes when selecting **Other**.")
                elif rejection_notes.strip():
                    rejection_reason = f"{selected_reason} — {rejection_notes.strip()}"
                else:
                    rejection_reason = selected_reason

        if first_pass_paid and rejected:
            st.error("Choose **either** First-Pass Paid **or** Rejected — not both.")

    days_to_submit = (day_submitted - ro_invoiced).days
    st.metric("Days to Submit", days_to_submit)

    personnel_df = load_personnel()

    advisor_list = personnel_df[
        personnel_df["role"] == "Advisor"
    ]["name"].tolist()

    scan_advisor = st.session_state.pop("_ro_scan_advisor", None)
    matched_advisor = _match_personnel_name(scan_advisor, advisor_list) if scan_advisor else None
    if matched_advisor:
        st.session_state[f"advisor_{st.session_state.form_version}"] = matched_advisor

    tech_list = personnel_df[
        personnel_df["role"] == "Technician"
    ]["name"].tolist()

    scan_technician = st.session_state.pop("_ro_scan_technician", None)
    matched_technician = _match_personnel_name(scan_technician, tech_list) if scan_technician else None
    if matched_technician:
        st.session_state[f"technician_{st.session_state.form_version}"] = matched_technician

    warranty_list = personnel_df[
        personnel_df["role"] == "Warranty Admin"
    ]["name"].tolist()

    advisor = st.selectbox(
        "Advisor",
        advisor_list,
        key=f"advisor_{st.session_state.form_version}"
    )

    technician = st.selectbox(
        "Technician",
        tech_list,
        key=f"technician_{st.session_state.form_version}"
    )

    warranty_admin = st.selectbox(
        "Warranty Admin",
        warranty_list,
        key=f"warranty_admin_{st.session_state.form_version}"
    )
 
    st.markdown("---")
    st.subheader("Warranty Job Documentation")

    jobs = []
    time_bypass = False
    time_bypass_user = ""

    for i in range(int(job_count)):
        job_no = i + 1

        with st.expander(f"Job {job_no}", expanded=True):
            st.subheader(f"Job {job_no} Documentation")

            concern = st.text_area(
                "Concern",
                key=f"concern_{job_no}_{st.session_state.form_version}"

            )

            cause = st.text_area(
             "Cause",
             key=f"cause_{job_no}_{st.session_state.form_version}"
            )

            correction = st.text_area(
            "Correction",
            key=f"correction_{job_no}_{st.session_state.form_version}"
                
            )

            st.button(
                f"Use Suggested Narrative - Job {job_no}",
                key=f"use_suggested_{job_no}"
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
                        time_bypass_user = ""
                else:
                    st.caption(
                        "Time punch bypass requires a linked **Manager** or **Warranty Admin** account."
                    )
                    time_bypass = False
                    time_bypass_user = ""

            c1, c2, c3 = st.columns(3)

            with c1:
                tech_flagged_time = st.number_input(
                    f"Tech Flagged Time - Job {job_no}",
                    min_value=0.0,
                    value=0.0,
                    step=0.1,
                    key=f"tech_time_{job_no}"
                )

            with c2:
                time_allotted = st.number_input(
                    f"Time Allotted - Job {job_no}",
                    min_value=0.0,
                    value=0.0,
                    step=0.1,
                    key=f"allotted_{job_no}"
                )

            with c3:
                claim_value = st.number_input(
                    f"Claim Value - Job {job_no}",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    key=f"claim_value_{job_no}"
                )

            st.subheader("Required Warranty Checks")

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                oil_leak = st.checkbox("Oil Leak", key=f"oil_leak_{job_no}")
                oil_dye_billed = st.checkbox("Oil Dye Billed", key=f"oil_dye_{job_no}")
                battery_replacement = st.checkbox("Battery Replacement", key=f"battery_{job_no}")
                battery_test_slip = st.checkbox("Battery Test Slip", key=f"battery_slip_{job_no}")
                alignment_involved = st.checkbox("Alignment", key=f"alignment_{job_no}")
                alignment_report_attached = st.checkbox(
                    "Alignment Report Attached to RO",
                    key=f"alignment_report_{job_no}",
                )
                if alignment_involved and not alignment_report_attached:
                    st.error(
                        "Hard stop: alignment printout report must be attached to the repair order."
                    )

            with c2:
                sublet_repair = st.checkbox("Sublet Repair", key=f"sublet_{job_no}")
                sublet_vin = st.checkbox("Sublet VIN Present", key=f"sublet_vin_{job_no}")
                sublet_mileage = st.checkbox("Sublet Mileage Present", key=f"sublet_mileage_{job_no}")
                sublet_notes = st.checkbox("Sublet Detailed Notes Present", key=f"sublet_notes_{job_no}")

            with c3:
                rental_involved = st.checkbox("Rental Involved", key=f"rental_{job_no}")
                rental_days = st.number_input(
                    "Rental Days Billed",
                    min_value=0,
                    value=0,
                    step=1,
                    key=f"rental_days_{job_no}"
                )
                if rental_dollars_per_day > 0:
                    rental_total = float(rental_days or 0) * rental_dollars_per_day
                    st.caption(
                        f"**Rental Total:** ${rental_total:,.2f} "
                        f"(${rental_dollars_per_day:,.2f}/day × {int(rental_days or 0)} days)"
                    )
                manager_signed_rental = st.checkbox(
                    "Manager Signed Rental",
                    key=f"rental_signed_{job_no}"
                )

            with c4:
                warranty_add_on = st.checkbox(
                    "Warranty Add-On (W+)",
                    key=f"addon_{job_no}"
                )
                manager_approval = st.checkbox(
                    "Service Manager Signed Off",
                    key=f"manager_approval_{job_no}"
                )
                if warranty_add_on and not manager_approval:
                    st.error("Hard stop: W+ add-on requires Service Manager sign-off before submission.")
                ac_repair = st.checkbox("A/C Repair", key=f"ac_{job_no}")
                ac_evac_slip = st.checkbox("A/C EVAC Slip", key=f"ac_slip_{job_no}")
                parts_warranty = st.checkbox(
                    "Parts Warranty",
                    key=f"parts_warranty_{job_no}"
                )
                mopa_original_ro = st.checkbox(
                    "MOPAR + Original RO",
                    key=f"mopa_{job_no}"
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
            applicable_manual = find_applicable_manual_sections(preview_job)
            render_applicable_manual_sections(
                applicable_manual,
                key_prefix=f"live_manual_{job_no}_{st.session_state.form_version}",
            )

            current_job_preview = {
                "concern": concern,
                "cause": cause,
                "correction": correction,
            }
            similar_claims = find_similar_paid_claims(current_job_preview)
            render_narrative_gap_coach(current_job_preview, similar_claims, job_no)
            similar_declined = find_similar_declined_claims(current_job_preview)
            render_declined_claim_alert(current_job_preview, similar_declined)

            jobs.append({
                "job_no": str(job_no),
                "concern": concern,
                "cause": cause, 
                "correction": correction,
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
            })

    st.markdown("---")

    recall_audit_block = _vin_recall_blocks_audit(st.session_state.form_version, vin)
    if recall_audit_block:
        st.warning(
            "This VIN has recall campaign(s) on file. Acknowledge the recall notice in the popup "
            "before running the audit."
        )

    sign_in_required = not is_signed_in()
    if sign_in_required:
        st.warning("Sign in with your dealership account before running the audit.")

    if st.button(
        "Run Audit + Save Review",
        type="primary",
        use_container_width=True,
        disabled=recall_audit_block or sign_in_required,
    ):
        if first_pass_paid and rejected:
            st.error(
                "Fix claim outcome before saving: choose First-Pass Paid **or** Rejected, "
                "or leave both unchecked if still pending."
            )
        if not (first_pass_paid and rejected):

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
                job_text = _review_job_text_from_session(st.session_state.form_version, job_count)
                recalls = apply_job_relevance(list(recall_result.get("recalls") or []), job_text)
                related = [r for r in recalls if r.get("relevance_score", 0) >= 12]
                if related:
                    st.markdown("### VIN Recall Alert")
                    for recall in related[:3]:
                        st.warning(
                            f"NHTSA recall **{recall.get('campaign', '—')}** "
                            f"({recall.get('component', '')}) may relate to this repair. "
                            "Verify campaign status in OASIS / wiTECH before warranty submit."
                        )
                elif recall_result.get("recall_count"):
                    st.info(
                        f"This vehicle configuration has {recall_result['recall_count']} NHTSA recall(s) on file — "
                        "confirm VIN-specific completion status before submit."
                    )

            x1, x2, x3, x4, x5 = st.columns([1.1, 1.3, 1.7, 1.7, 1.2])

            x1.metric("Audit Score", final_score)
            x2.metric("Status", status)
            x3.metric("Total Claim Value", f"${total_value:,.2f}")
            x4.metric("Hard Stop Value", f"${hard_value:,.2f}")
            x5.metric("Hard Stops", len(all_hard))

            for job in jobs:
                with st.expander(
                    f"Job {job['job_no']} Results",
                    expanded=True
                ):

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
                "first_pass_paid": first_pass_paid,
                "rejected": rejected,
                "rejection_reason": rejection_reason,
                "advisor": advisor,
                "technician": technician,
                "warranty_admin": warranty_admin,
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
                **_vin_recall_save_fields(st.session_state.form_version, vin),
            }

            if save_review(report_payload):
                st.success("Review saved to Reporting (Supabase).")

            try:
                audit_pdf = build_audit_report_pdf(report_payload)
                safe_ro = re.sub(r"[^\w\-]+", "_", str(ro_number or "audit")).strip("_") or "audit"
                st.download_button(
                    "Download Audit PDF",
                    data=audit_pdf,
                    file_name=f"RO_Shield_Audit_{safe_ro}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"audit_pdf_{st.session_state.form_version}",
                )
            except ImportError:
                st.error("PDF export needs fpdf2. Run: python3 -m pip install -r requirements.txt")
            except Exception as e:
                st.warning(f"Audit PDF could not be generated: {e}")

   

def _process_claim_pdf_upload(files, *, outcome: str, summary_key: str, nonce_key: str) -> None:
    totals = {
        "parsed": 0,
        "saved": 0,
        "duplicate": 0,
        "skipped": 0,
        "errors": 0,
        "updated": 0,
        "blocked": 0,
    }
    per_file = []
    pdf_diagnostics: list[str] = []
    for f in files:
        _, probe_text = extract_pdf_document_text(f)
        detected = detect_claim_pdf_outcome(probe_text)
        if outcome == "paid" and detected == "declined":
            totals["blocked"] += 1
            pdf_diagnostics.append(
                f"BLOCKED:{f.name}: This PDF looks like a **declined/rejected** claim. "
                "Upload it on the **Declined / Rejected Claims** tab (red), not here."
            )
            per_file.append(f"**{f.name}:** blocked — declined claim belongs on the red tab")
            continue
        if outcome == "declined" and detected == "paid":
            totals["blocked"] += 1
            pdf_diagnostics.append(
                f"BLOCKED:{f.name}: This PDF looks like a **paid/approved** claim. "
                "Upload it on the **Paid Claims** tab (green), not here."
            )
            per_file.append(f"**{f.name}:** blocked — paid claim belongs on the green tab")
            continue

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
        if "blocked" in line.lower():
            st.error(line)
        else:
            st.success(line)
    for line in last_summary.get("diagnostics", []):
        if str(line).startswith("BLOCKED:"):
            st.error(str(line)[8:])
        else:
            st.warning(line)
    totals = last_summary.get("totals") or {}
    blocked = totals.get("blocked", 0)
    st.info(
        f"Upload summary: **{totals.get('saved', 0)} new records saved** to your library "
        f"(from {totals.get('parsed', 0)} parsed segments). "
        f"{totals.get('duplicate', 0)} were already in the library, "
        f"{totals.get('skipped', 0)} did not pass narrative quality checks."
        + (f" **{blocked} file(s) blocked** — wrong tab for paid vs declined." if blocked else "")
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
        st.dataframe(
            table_df[display_cols].fillna("") if display_cols else table_df.fillna(""),
            use_container_width=True,
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
    st.dataframe(display_df, use_container_width=True)


def _render_paid_claims_learning(all_claims: pd.DataFrame) -> None:
    st.markdown(
        """
        <span class="claim-panel-paid-marker" aria-hidden="true"></span>
        <div class="claim-outcome-banner claim-outcome-banner--paid">
            <strong>Paid Claims</strong>
            Upload approved/paid warranty claim PDFs only. Declined or rejected exports belong on the red tab.
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
            Upload declined, returned, or rejected warranty claim PDFs only. Paid exports belong on the green tab.
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


def _filter_reviews_by_date(df, key_prefix="report"):
    if df.empty or "created_at" not in df.columns:
        return df
    df = normalize_reviews_dataframe(df)
    min_d = df["created_at"].min().date()
    max_d = df["created_at"].max().date()
    date_range = st.date_input(
        "Report Date Range",
        value=(min_d, max_d),
        key=f"{key_prefix}_date_range",
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
            st.dataframe(
                display_rules[["Audit Rule", "Type", "Count", "% of Findings"]],
                use_container_width=True,
                hide_index=True,
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
            st.dataframe(advisor_pivot, use_container_width=True)
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
        "Specific areas each advisor needs to tighten — counted by distinct ROs in this date range."
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
                for issue in entry["issues"]:
                    st.markdown(f"- {issue}")
        return

    if advisor_summary is not None and not advisor_summary.empty:
        named = advisor_summary[advisor_summary["advisor"].astype(str).str.strip() != ""]
        if not named.empty:
            st.info(
                "Advisor names are on file, but saved reviews do not yet include job-level hard stops "
                "or warnings. Run **Run Audit + Save Review** on recent ROs to populate coaching areas."
            )
            st.dataframe(
                named.head(8).rename(columns={
                    "advisor": "Advisor",
                    "reviews": "Reviews",
                    "avg_score": "Avg Score",
                    "hard_stops": "Hard Stops",
                    "protected_value": "Protected $",
                    "rejected": "Rejected",
                }),
                use_container_width=True,
            )
            return

    st.caption("Advisor coaching areas will appear once reviews include advisor names and audit findings.")


def render_roi_dashboard():
    st.header("ROI Dashboard")
    st.caption("Show the business value of RO Shield — dollars protected, quality trends, and team performance.")

    col_refresh, col_migrate = st.columns([1, 2])
    with col_refresh:
        if st.button("Refresh ROI Dashboard", key="refresh_roi"):
            st.rerun()
    with col_migrate:
        if st.button("Import old local reviews (SQLite → Supabase)", key="migrate_roi"):
            migrated, skipped = migrate_sqlite_to_supabase(supabase, DB_PATH)
            st.success(f"Imported {migrated} review(s). Skipped {skipped} duplicate or invalid row(s).")
            st.rerun()

    df = load_reviews()
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
            hourly_rate = st.number_input(
                "Warranty admin loaded hourly cost ($)",
                min_value=20.0,
                max_value=100.0,
                value=38.0,
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

    st.markdown("### Where to Focus Coaching")
    c1, c2 = st.columns(2)
    with c1:
        render_advisor_coaching_focus(df, metrics["advisor_summary"])

    with c2:
        st.markdown("**Top Rejection Reasons**")
        reasons = metrics["rejection_reasons"]
        if not reasons.empty:
            st.dataframe(
                reasons.head(8).rename(columns={
                    "rejection_reason": "Reason",
                    "count": "Count",
                    "total_value": "Claim Value",
                }),
                use_container_width=True,
            )
        else:
            st.caption("Mark rejections on the Review tab to track reasons and cost here.")

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

    try:
        roi_pdf = build_roi_report_pdf(
            metrics,
            period_label=period_label,
            rejection_rework_pct=rejection_rework_pct,
            minutes_saved=float(minutes_saved),
            hourly_rate=float(hourly_rate),
        )
        st.download_button(
            "Download ROI Summary PDF",
            data=roi_pdf,
            file_name="RO_Shield_ROI_Summary.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="roi_summary_pdf",
        )
    except ImportError:
        st.error("PDF export needs fpdf2. Run: python3 -m pip install -r requirements.txt")
    except Exception as e:
        st.warning(f"ROI PDF could not be generated: {e}")


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


def _outcome_radio_index(first_pass_paid: int, rejected: int) -> int:
    if first_pass_paid and not rejected:
        return 1
    if rejected and not first_pass_paid:
        return 2
    return 0


def _review_option_label(row: dict) -> str:
    ro_number = str(row.get("ro_number") or "—").strip() or "—"
    advisor = str(row.get("advisor") or "—").strip() or "—"
    claim_value = float(row.get("total_claim_value") or 0)
    status = str(row.get("outcome_status") or review_outcome_label(
        row.get("first_pass_paid"), row.get("rejected")
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
    if "outcome_status" not in work.columns:
        work["outcome_status"] = [
            review_outcome_label(fp, rej) for fp, rej in zip(work["first_pass_paid"], work["rejected"])
        ]

    pending_mask = (work["first_pass_paid"] == 0) & (work["rejected"] == 0)
    pending_count = int(pending_mask.sum())
    first_pass_count = int(work["first_pass_paid"].sum())
    rejected_count = int(work["rejected"].sum())
    resolved_count = len(work) - pending_count

    render_metric_rows([
        [
            ("Pending Outcome", f"{pending_count:,}"),
            ("First-Pass Paid", f"{first_pass_count:,}"),
            ("Rejected / Returned", f"{rejected_count:,}"),
        ],
        [
            (
                "First-Pass % (resolved)",
                f"{(first_pass_count / resolved_count * 100):.1f}%" if resolved_count else "—",
                "Paid on first submission ÷ reviews with a recorded paid or rejected outcome.",
            ),
        ],
    ])

    filter_choice = st.radio(
        "Show reviews",
        ["Pending only", "All in date range", "First-Pass Paid", "Rejected / Returned"],
        horizontal=True,
        key="outcome_followup_filter",
    )

    filtered = work.copy()
    if filter_choice == "Pending only":
        filtered = filtered[pending_mask]
    elif filter_choice == "First-Pass Paid":
        filtered = filtered[work["first_pass_paid"] == 1]
    elif filter_choice == "Rejected / Returned":
        filtered = filtered[work["rejected"] == 1]

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
    current_reason = str(selected.get("rejection_reason") or "").strip()

    info_cols = st.columns(4)
    info_cols[0].metric("RO", str(selected.get("ro_number") or "—"))
    info_cols[1].metric("Advisor", str(selected.get("advisor") or "—"))
    info_cols[2].metric(
        "Claim Value",
        f"${float(selected.get('total_claim_value') or 0):,.2f}",
    )
    info_cols[3].metric("Current", review_outcome_label(current_fp, current_rej))

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
            ["Pending", "First-Pass Paid", "Rejected / Returned"],
            index=_outcome_radio_index(current_fp, current_rej),
            horizontal=True,
        )

        selected_reason = ""
        rejection_notes = ""
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

        submitted = st.form_submit_button("Save outcome", type="primary", use_container_width=True)

    if submitted:
        first_pass_paid = outcome_choice == "First-Pass Paid"
        rejected = outcome_choice == "Rejected / Returned"
        rejection_reason = ""
        if rejected:
            ok, rejection_reason = _compose_rejection_reason(selected_reason, rejection_notes)
            if not ok:
                st.error(rejection_reason)
                return

        try:
            update_review_outcome(
                supabase,
                int(selected_id),
                first_pass_paid=first_pass_paid,
                rejected=rejected,
                rejection_reason=rejection_reason,
                updated_by=current_person_name() or auth_user_email(),
            )
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
        st.dataframe(pending_view[pending_cols].head(15), use_container_width=True, hide_index=True)


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


def render_reporting_vin_recalls(df: pd.DataFrame) -> None:
    st.caption("VINs flagged with open or identified recall campaigns during the selected period.")
    if "vin_recall_identified" not in df.columns:
        st.info(
            "VIN recall columns are not in Supabase yet. Run the migration in "
            "`docs/SUPABASE_SCHEMA.sql`, then save new reviews to populate this report."
        )
        return

    recall_flag = pd.to_numeric(df["vin_recall_identified"], errors="coerce").fillna(0).astype(int)
    recall_df = df[recall_flag == 1].copy()
    all_time_df = load_reviews()
    all_time_total = 0
    if not all_time_df.empty and "vin_recall_identified" in all_time_df.columns:
        all_time_total = int(
            pd.to_numeric(all_time_df["vin_recall_identified"], errors="coerce").fillna(0).astype(int).sum()
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
    st.dataframe(recall_display[show_cols], use_container_width=True)


def render_reporting_rejections(df: pd.DataFrame) -> None:
    st.caption("Rejected and returned claims grouped by standard rejection reason.")
    fp_df = df.copy()
    fp_df["rejection_reason"] = fp_df.get("rejection_reason", "").astype(str)
    fp_df["total_claim_value"] = pd.to_numeric(fp_df.get("total_claim_value", 0), errors="coerce").fillna(0)

    reasons = fp_df[fp_df["rejection_reason"].str.strip() != ""].copy()
    if reasons.empty:
        st.info("No rejection reasons recorded yet. Mark rejections on Review or under Claim Outcomes.")
        return

    reasons["rejection_reason_primary"] = (
        reasons["rejection_reason"].astype(str).str.split(" — ").str[0].str.strip()
    )
    reason_summary = reasons.groupby("rejection_reason_primary").agg(
        count=("ro_number", "count"),
        total_value=("total_claim_value", "sum"),
    ).reset_index().sort_values("count", ascending=False)
    reason_summary = reason_summary.rename(columns={"rejection_reason_primary": "rejection_reason"})
    st.dataframe(reason_summary, use_container_width=True)

    with st.expander("All rejection detail (including notes)"):
        detail = reasons.copy()
        if "created_at" in detail.columns:
            detail["created_at"] = pd.to_datetime(
                detail["created_at"], errors="coerce"
            ).dt.strftime("%Y-%m-%d %H:%M")
        detail_cols = [
            c for c in ("created_at", "ro_number", "rejection_reason", "total_claim_value", "advisor")
            if c in detail.columns
        ]
        st.dataframe(detail[detail_cols], use_container_width=True)


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
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Top Offenders")
            st.dataframe(worst, use_container_width=True)
        with c2:
            st.markdown("### Best Performers")
            st.dataframe(best, use_container_width=True)

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
        st.dataframe(scorecard, use_container_width=True)


def render_reporting_review_log(df: pd.DataFrame) -> None:
    st.caption("Full review history for the selected date range. Export for meetings or records.")
    display_df = df.drop(columns=["jobs"], errors="ignore")
    st.dataframe(display_df, use_container_width=True)

    if "created_at" in df.columns and df["created_at"].notna().any():
        report_period = f"{df['created_at'].min().date()} to {df['created_at'].max().date()}"
    else:
        report_period = "Selected period"

    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            "Download Review Report CSV",
            display_df.to_csv(index=False),
            "ro_shield_review_report.csv",
            "text/csv",
            use_container_width=True,
            key="review_report_csv",
        )
    with dl2:
        try:
            review_pdf = build_review_report_pdf(display_df, period_label=report_period)
            st.download_button(
                "Download Review Report PDF",
                data=review_pdf,
                file_name="RO_Shield_Review_Report.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="review_report_pdf",
            )
        except ImportError:
            st.error("PDF export needs fpdf2. Run: python3 -m pip install -r requirements.txt")
        except Exception as e:
            st.error(f"Review PDF could not be generated: {e}")


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
            st.rerun()
    with col_migrate:
        if st.button("Import old local reviews (SQLite → Supabase)"):
            migrated, skipped = migrate_sqlite_to_supabase(supabase, DB_PATH)
            st.success(f"Imported {migrated} review(s). Skipped {skipped} duplicate or invalid row(s).")
            st.rerun()

    df = load_reviews()
    if df.empty:
        st.info("No reviews saved yet. Complete a review on the Review tab and click Run Audit + Save Review.")
        return

    df = _filter_reviews_by_date(df, key_prefix="report")
    if df.empty:
        st.warning("No reviews in the selected date range.")
        return

    df = normalize_reviews_dataframe(df)

    overview_tab, outcomes_tab, recalls_tab, rejections_tab, team_tab, log_tab = st.tabs([
        "Overview",
        "Claim Outcomes",
        "VIN Recalls",
        "Rejections",
        "Team Performance",
        "Review Log",
    ])

    with overview_tab:
        st.markdown("### Summary")
        render_reporting_summary(df)
        render_reporting_charts(df)

    with outcomes_tab:
        render_outcome_followup(df, show_title=False)

    with recalls_tab:
        render_reporting_vin_recalls(df)

    with rejections_tab:
        render_reporting_rejections(df)

    with team_tab:
        render_reporting_team_performance(df)

    with log_tab:
        render_reporting_review_log(df)


def render_personnel_admin():
    st.header("Personnel")
    st.caption(
        "Manage advisors, technicians, warranty admins, and managers. "
        "The **Email** must match each person's Supabase login so roles apply after sign-in."
    )

    df = load_personnel()
    if not user_can_manage_personnel():
        render_role_gate_message(PERSONNEL_ADMIN_ROLES, "manage personnel")
        if df.empty:
            st.info("No personnel added yet.")
        else:
            display_cols = [
                c for c in ("name", "role", "email", "employee_number", "id")
                if c in df.columns
            ]
            st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
        return

    with st.form("add_person"):
        name = st.text_input("Name")
        email = st.text_input("Email (login)", placeholder="you@dealership.com")
        employee_number = st.text_input("Employee Number")
        role = st.selectbox("Role", ["Advisor", "Technician", "Warranty Admin", "Manager"])
        submitted = st.form_submit_button("Add Person")
        if submitted and name.strip():
            if email.strip() and not is_valid_email(email):
                st.error("Enter a valid email address, or leave email blank.")
            else:
                add_person_shared(name.strip(), role, employee_number, email)
                st.success("Person added.")

    df = load_personnel()
    st.subheader("Edit Existing Employee")

    if df.empty:
        st.info("No personnel added yet.")
        return

    employee_names = df["name"].tolist()
    selected_employee = st.selectbox("Select Employee to Edit", employee_names)
    selected_row = df[df["name"] == selected_employee].iloc[0]

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

    edit_role = st.selectbox(
        "Edit Role",
        ["Advisor", "Technician", "Warranty Admin", "Manager"],
        index=["Advisor", "Technician", "Warranty Admin", "Manager"].index(
            selected_row.get("role", "Advisor")
        ),
    )

    if st.button("Save Employee Changes"):
        if edit_email.strip() and not is_valid_email(edit_email):
            st.error("Enter a valid email address, or clear the email field.")
        else:
            update_payload = {
                "name": edit_name,
                "employee_number": edit_employee_number,
                "role": edit_role,
                "email": normalize_email(edit_email) or None,
            }
            supabase.table("personnel").update(update_payload).eq("id", selected_row["id"]).execute()

            st.success("Employee updated.")
            st.rerun()

    display_cols = [
        c for c in ("name", "role", "email", "employee_number", "id")
        if c in df.columns
    ]
    st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
    remove_id = st.number_input("Deactivate personnel ID", min_value=0, value=0, step=1)
    if st.button("Deactivate") and remove_id:
        deactivate_person(remove_id)
        st.success("Personnel deactivated.")


def render_admin():
    st.header("Admin")
    st.caption(
        "Dealership settings, audit rules, rejection reasons, and personnel. "
        "Admin saves require a linked Manager or Warranty Admin account."
    )

    admin_tabs = st.tabs([
        "Smart Warranty",
        "Audit Rules",
        "Rejection Reasons",
        "Personnel",
    ])
    with admin_tabs[0]:
        render_smart_warranty_admin()
    with admin_tabs[1]:
        render_audit_rules_admin()
    with admin_tabs[2]:
        render_rejection_reason_library_admin()
    with admin_tabs[3]:
        render_personnel_admin()


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

    render_sidebar_brand()

    render_authenticated_sidebar(supabase)

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

    _render_app_workspace_header(appearance)

    tabs = st.tabs(["Review", "ROI Dashboard", "Claim Learning", "Reporting", "Admin", "TSB / Bulletins", "WAM"])
    with tabs[0]:
        render_review()
    with tabs[1]:
        render_roi_dashboard()
    with tabs[2]:
        render_claims()
    with tabs[3]:
        render_reporting()
    with tabs[4]:
        render_admin()
    with tabs[5]:
        render_tsb_bulletins()
    with tabs[6]:
        render_wam()

if __name__ == "__main__":
    main()
