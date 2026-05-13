from supabase import create_client

SUPABASE_URL = "https://eyufnhnabdgehkfvhqzf.supabase.co"
SUPABASE_KEY = "sb_publishable_5SXVN_OB5aIouuZAOa3b3Q_Mq4chxUT"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

st.set_page_config(page_title="RO Shield Final Production", layout="wide", initial_sidebar_state="expanded")

DB_PATH = Path("ro_shield_final.db")


# =========================
# DATABASE
# =========================
def db():
    return sqlite3.connect(DB_PATH)
# =====================
# SUPABASE (SHARED DB)
# =====================

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
        response = supabase.table("claims").select("*").execute()
        rows = response.data or []
        df = pd.DataFrame(rows)

        if df.empty:
            return pd.DataFrame(columns=["uploaded_at", "source_file", "claim_index", "raw_text"])

        return pd.DataFrame({
            "uploaded_at": df.get("created_at", ""),
            "source_file": df.get("ro_number", ""),
            "claim_index": df.get("id", range(1, len(df)+1)),
            "raw_text": df.get("story", "")
        })

    except Exception as e:
        st.warning(f"Load failed: {e}")
        return pd.DataFrame(columns=["uploaded_at", "source_file", "claim_index", "raw_text"])

def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            ro_number TEXT,
            vin TEXT,
            advisor TEXT,
            technician TEXT,
            warranty_admin TEXT,
            manager TEXT,
            entered_by TEXT,
            score INTEGER,
            status TEXT,
            total_claim_value REAL,
            hard_stop_value REAL,
            hard_stop_count INTEGER,
            warning_count INTEGER,
            time_bypass INTEGER DEFAULT 0,
            time_bypass_user TEXT,
            jobs_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS personnel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            name TEXT,
            role TEXT,
            active INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS learned_claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uploaded_at TEXT,
            source_file TEXT,
            claim_index INTEGER,
            raw_text TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bulletins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            title TEXT,
            keywords TEXT,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()


def read_df(table):
    conn = db()
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY id DESC", conn)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    return df


def save_review(data):
    try:
        result = supabase.table("reviews").insert(data).execute()
        st.success("Review saved to Reporting.")
        st.write(result)
    except Exception as e:
        st.error(f"Review save failed: {e}")

def load_reviews():
    try:
        response = supabase.table("reviews").select("*").execute()
        rows = response.data or []
        return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"Review load failed: {e}")
        return pd.DataFrame()
    

def load_personnel():
    try:
        response = supabase.table("personnel").select("*").eq("active", True).execute()
        rows = response.data or []
        return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"Personnel load failed: {e}")
        return pd.DataFrame(columns=["name", "role"])


def add_person_shared(name, role, employee_number):
    try:
        existing = supabase.table("personnel").select("id").eq("name", name).eq("role", role).execute()

        if not existing.data:
            supabase.table("personnel").insert({
                "name": name,
                "employee_number": employee_number,
                "role": role,
                "active": True
            }).execute()

    except Exception as e:
        st.warning(f"Personnel save failed: {e}")

def deactivate_person(pid):
    try:
        supabase.table("personnel").update({"active": False}).eq("id", int(pid)).execute()
    except Exception as e:
        st.warning(f"Personnel deactivate failed: {e}")


def role_options(role):
    df = load_personnel()
    if df.empty:
        return [""]
    df = df[(df["role"] == role) & (df["active"] == 1)]
    return [""] + sorted(df["name"].astype(str).tolist())


def save_learned_claims(file_name, claims):
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
            supabase.table("claims").insert(data).execute()
        except Exception as e:
            st.warning(f"Save failed: {e}")
  
def save_bulletin(title, keywords, notes):
    conn = db()
    conn.execute("""
        INSERT INTO bulletins (created_at, title, keywords, notes)
        VALUES (?, ?, ?, ?)
    """, (datetime.now().isoformat(timespec="seconds"), title, keywords, notes))
    conn.commit()
    conn.close()


# =========================
# STYLE
# =========================
def apply_style():
    st.markdown("""
    <style>
    .stApp {
        background:
            linear-gradient(rgba(1, 7, 14, .91), rgba(1, 7, 14, .95)),
            radial-gradient(circle at 14% 8%, rgba(0, 114, 255, .32), transparent 28%),
            radial-gradient(circle at 90% 10%, rgba(45, 156, 255, .18), transparent 26%),
            linear-gradient(135deg, #06101d 0%, #02070d 100%);
        color: #ffffff !important;
    }
    header[data-testid="stHeader"] { background: rgba(0,0,0,0); }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #071322, #030811) !important;
        border-right: 1px solid rgba(36,135,255,.30);
    }
    h1,h2,h3,h4,h5,h6,p,span,label,div { color: #ffffff !important; }
    .hero {
        padding: 28px 30px;
        border-radius: 22px;
        background: linear-gradient(135deg, rgba(10, 31, 57, .94), rgba(2, 9, 19, .94));
        border: 1px solid rgba(62,150,255,.40);
        box-shadow: 0 20px 60px rgba(0,0,0,.35);
        margin-bottom: 22px;
    }
    .hero h1 { margin: 0; font-size: 48px; letter-spacing: .5px; }
    .hero p { color: #d6e8ff !important; font-size: 16px; }
    .section-card {
        padding: 18px;
        border-radius: 18px;
        background: rgba(7, 19, 34, .62);
        border: 1px solid rgba(62,150,255,.22);
        margin: 10px 0 18px 0;
    }
    textarea, input {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        background-color: rgba(13, 30, 55, .96) !important;
        border: 1px solid rgba(140, 200, 255, .70) !important;
    }
    textarea::placeholder, input::placeholder { color: #d8eaff !important; opacity: 1 !important; }
    div[data-baseweb="select"] > div {
        background-color: rgba(13, 30, 55, .96) !important;
        border: 1px solid rgba(140, 200, 255, .70) !important;
    }
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] input,
    div[data-baseweb="select"] svg {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        fill: #ffffff !important;
    }
    section[data-testid="stFileUploaderDropzone"] {
        background-color: rgba(13, 30, 55, .92) !important;
        border: 1px dashed rgba(140, 200, 255, .70) !important;
    }
    div[data-testid="stMetric"] {
        background: rgba(7, 19, 34, .86);
        border: 1px solid rgba(62,150,255,.28);
        border-radius: 16px;
        padding: 14px;
        min-height: 112px;
    }
    div[data-testid="stMetricValue"] {
        white-space: nowrap !important;
        overflow: visible !important;
        text-overflow: clip !important;
        font-size: 1.9rem !important;
    }
    div[data-testid="stMetricLabel"] {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }
    .status-ready {background:rgba(0,150,90,.20); border:1px solid rgba(0,220,130,.45); padding:16px; border-radius:16px;}
    .status-review {background:rgba(255,200,0,.18); border:1px solid rgba(255,210,0,.50); padding:16px; border-radius:16px;}
    .status-stop {background:rgba(255,50,50,.18); border:1px solid rgba(255,90,90,.50); padding:16px; border-radius:16px;}
    </style>
    """, unsafe_allow_html=True)


# =========================
# CLAIM LEARNING
# =========================
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
def find_wam_matches(job):
    text = " ".join([
        str(job.get("concern", "")),
        str(job.get("cause", "")),
        str(job.get("correction", ""))
    ]).lower()

    matches = []

    try:
        rows = supabase.table("wam_documents").select("*").execute().data or []

        for row in rows:
            keywords = str(row.get("keywords", "")).lower()
            content = str(row.get("content", "")).lower()
            section = row.get("section", "WAM Reference")

            keyword_hits = [
                k.strip()
                for k in keywords.split(",")
                if k.strip() and k.strip() in text
            ]

            content_hit = any(word in content for word in text.split() if len(word) > 5)

            if keyword_hits or content_hit:
                matches.append({
                    "section": section,
                    "source_file": row.get("source_file", ""),
                    "content": row.get("content", "")[:700]
                })

    except Exception:
        pass

    return matches[:3]
def audit_job(job, time_bypass):
    hard = []
    warn = []
    text = f"{job['concern']} {job['cause']} {job['correction']}".lower()

    if not job["concern"].strip():
        hard.append("Missing concern.")
    if not job["cause"].strip():
        hard.append("Missing cause.")
    if not job["correction"].strip():
        hard.append("Missing correction.")

    # Pencil Wrench cause grading
    cause_text = job["cause"].lower()
    if job["cause"].strip():
        if not any(x in cause_text for x in ["found", "tested", "verified", "diagnosed", "inspected", "scanned"]):
            warn.append("Pencil Wrench Cause: missing diagnostic steps used to get to the failure.")
        if not any(x in cause_text for x in ["dtc", "code", "inspection", "measured", "scan", "test", "voltage", "pressure", "leak test"]):
            warn.append("Pencil Wrench Cause: missing supporting evidence such as DTC, test result, inspection, or measurement.")
        if not any(x in cause_text for x in ["failed", "inoperative", "not working", "leak", "shorted", "open", "broken", "faulty"]):
            warn.append("Pencil Wrench Cause: failure is not clearly identified.")

    # Pencil Wrench correction grading
    correction_text = job["correction"].lower()
    if job["correction"].strip():
        if not any(x in correction_text for x in ["replaced", "repaired", "installed", "removed", "programmed", "performed"]):
            warn.append("Pencil Wrench Correction: repair action is not clearly identified.")
        if not any(x in correction_text for x in ["due to", "because", "failed", "leaking", "shorted", "open", "damaged"]):
            warn.append("Pencil Wrench Correction: parts replaced are not clearly justified.")
        if not any(x in correction_text for x in ["verified", "operates", "working", "proper operation", "no further issues", "test drove"]):
            warn.append("Pencil Wrench Correction: proper operation was not verified after repair.")

    if job["oil_leak"]:
        warn.append("Oil leak selected: confirm oil dye is billed and narrative states dye was used.")
        if not job["dye_billed"]:
            hard.append("Oil leak repair requires oil dye billed.")
        if "dye" not in text:
            hard.append("Oil leak narrative must state dye was used to locate the leak.")

    if job.get("sublet_repair"):
        warn.append("Sublet selected: invoice must include VIN, mileage, and detailed repair notes.")
        if not job["sublet_vin"]:
            hard.append("Sublet invoice must show VIN.")
        if not job["sublet_mileage"]:
            hard.append("Sublet invoice must show mileage.")
        if not job["sublet_repair_notes"]:
            hard.append("Sublet invoice must include detailed repair notes.")

    if job.get("rental_involved"):
        if job["rental_days"] <= 0:
            hard.append("Rental involved but rental days are not billed.")
        if not job["rental_signed"]:
            hard.append("Rental involved but manager sign-off is missing.")
        if job["rental_days"] >= 15:
            warn.append("15 or more rental days billed: make sure all documentation to support rental days is submitted to Stellantis with the claim.")

    if job.get("warranty_add_on") and not job.get("manager_approval"):
        hard.append("Warranty add-on requires service manager approval.")

    tech_flagged_time = float(job.get("tech_flagged_time") or 0)
    time_allotted = float(job.get("time_allotted") or 0)

    if time_bypass:
        warn.append("Tech Flagged Time / Time Allotted validation was bypassed for this review.")
    else:
        if time_allotted > 0 and tech_flagged_time > 0:
            pct = tech_flagged_time / time_allotted
            if pct < 0.70:
                hard.append(f"Tech Flagged Time is below 70% of Time Allotted ({pct:.0%}).")
            if pct > 2.00:
                hard.append(f"Tech Flagged Time exceeds 200% of Time Allotted ({pct:.0%}).")
        elif time_allotted > 0 and tech_flagged_time <= 0:
            hard.append("Tech Flagged Time is missing.")
        elif tech_flagged_time > 0 and time_allotted <= 0:
            hard.append("Time Allotted for the job is missing.")

        if job.get("battery_replacement") and not job.get("battery_test_slip"):
             hard.append("Battery replacement requires failed battery test slip/code.")
        if job.get("ac_repair") and not job.get("ac_evac_slip"):
            hard.append("A/C repair requires EVAC/recharge slip.")
        if job["parts_warranty"] and not job["mopa"]:
            hard.append("Parts warranty requires MOPA and original RO support.")

        score = max(0, 100 - len(hard) * 15 - len(warn) * 5)
        wam_matches = find_wam_matches(job)

        if wam_matches:
            warn.append("WAM reference found. Review related warranty manual guidance before submission.")
            job["wam_matches"] = wam_matches

            for match in wam_matches:
                section = str(match.get("section", "WAM Reference"))
                content = str(match.get("content", ""))

        if "battery" in content.lower() and not job.get("battery_test_slip"):
            warn.append(f"WAM Suggestion - {section}: Battery claim may require battery test slip/code.")

        if "a/c" in content.lower() or "evac" in content.lower() or "recharge" in content.lower():
            if job.get("ac_repair") and not job.get("ac_evac_slip"):
                warn.append(f"WAM Suggestion - {section}: A/C claim may require EVAC/recharge documentation.")

        if "oil dye" in content.lower() or "dye" in content.lower():
            if job.get("oil_leak") and not job.get("oil_dye_billed"):
                warn.append(f"WAM Suggestion - {section}: Oil leak documentation should mention dye usage and dye billing.")

        if "manager approval" in content.lower() or "authorization" in content.lower():
            if job.get("add_on") and not job.get("manager_signed"):
                hard.append(f"WAM Hard Stop - {section}: Add-on repair may require manager authorization.")

        else:
         job["wam_matches"] = []

        return hard, warn, score
    
        return hard, warn, score

def result_banner(status):
    if "DO NOT" in status:
        cls = "status-stop"
    elif "NEEDS" in status:
        cls = "status-review"
    else:
        cls = "status-ready"
    st.markdown(f'<div class="{cls}"><h2>{status}</h2></div>', unsafe_allow_html=True)


# =========================
# SCREENS
# =========================

def render_review():
    st.header("RO Warranty Review")

    col_a, col_b = st.columns([8, 2])

    with col_b:
        if st.button("Next Claim"):
            keep_keys = ["appearance"]
            for key in list(st.session_state.keys()):
                if key not in keep_keys:
                    del st.session_state[key]
            st.rerun()

    ro_number = st.text_input("RO Number")
    vin = st.text_input("VIN")
    ro_invoiced = st.date_input("RO Invoiced / Closed Date")
    day_submitted = st.date_input("Day Submitted")
    first_pass_paid = st.checkbox("Paid on First Submission")
    rejected = st.checkbox("Rejected / Returned")
    rejection_reason = st.text_area("Rejection Reason", height=100) if rejected else ""

    days_to_submit = (day_submitted - ro_invoiced).days

    st.metric("Days to Submit", days_to_submit)
    personnel_df = load_personnel()

    advisor_list = personnel_df[personnel_df["role"] == "Advisor"]["name"].tolist()
    tech_list = personnel_df[personnel_df["role"] == "Technician"]["name"].tolist()
    warranty_list = personnel_df[personnel_df["role"] == "Warranty Admin"]["name"].tolist()
    manager_list = personnel_df[personnel_df["role"] == "Manager"]["name"].tolist()

    advisor = st.selectbox("Advisor", advisor_list)
    technician = st.selectbox("Technician", tech_list)
    warranty_admin = st.selectbox("Warranty Admin", warranty_list)

    st.divider()

    job_count = st.number_input(
        "How many warranty jobs are on this RO?",
        min_value=1,
        max_value=10,
        value=1,
        step=1
    )

    jobs = []

    for i in range(int(job_count)):
        job_no = i + 1

        with st.expander(f"Job {job_no}", expanded=True):
            st.subheader(f"Job {job_no} Documentation")

            concern = st.text_area(
            f"Concern – Job {job_no}",
            height=110,
            key=f"concern_{job_no}"
        )

            cause = st.text_area(
            f"Cause – Job {job_no}",
            height=110,
            key=f"cause_{job_no}"
        )

            correction = st.text_area(
            f"Correction – Job {job_no}",
            height=110,
            key=f"correction_{job_no}"
        )
            c1, c2, c3, c4 = st.columns(4)

with c1:
    oil_leak = st.checkbox("Oil Leak")
    oil_dye_billed = st.checkbox("Oil Dye Billed")
    battery_replacement = st.checkbox("Battery Replacement")
    battery_test_slip = st.checkbox("Battery Test Slip")

with c2:
    sublet_repair = st.checkbox("Sublet Repair")
    sublet_vin_present = st.checkbox("Sublet VIN Present")
    sublet_mileage_present = st.checkbox("Sublet Mileage Present")
    sublet_notes_present = st.checkbox("Sublet Detailed Notes Present")

with c3:
    rental_involved = st.checkbox("Rental Involved")
    rental_days = st.number_input("Rental Days Billed", min_value=0, step=1)
    manager_signed_rental = st.checkbox("Manager Signed Rental")

with c4:
    warranty_add_on = st.checkbox("Warranty Add-On (+)")
    manager_approval = st.checkbox("Manager Approval")
    ac_repair = st.checkbox("A/C Repair")
    ac_evac_slip = st.checkbox("A/C EVAC Slip")
    parts_warranty = st.checkbox("Parts Warranty")
    mopa_original_ro = st.checkbox("MOPA + Original RO")
if st.button(f"Use Suggested Narrative – Job {job_no}"):
    st.session_state[f"concern_{job_no}"] = built_concern
    st.session_state[f"cause_{job_no}"] = built_cause
    st.session_state[f"correction_{job_no}"] = built_correction
    st.rerun()

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

    a, b, c, d = st.columns(4)

with a:
    oil_leak = st.checkbox("Oil Leak", key=f"oil_leak_{job_no}")
    oil_dye_billed = st.checkbox("Oil Dye Billed", key=f"oil_dye_{job_no}")
    battery_replacement = st.checkbox("Battery Replacement", key=f"battery_{job_no}")
    battery_test_slip = st.checkbox("Battery Test Slip", key=f"battery_slip_{job_no}")

with b:
    sublet_repair = st.checkbox("Sublet Repair", key=f"sublet_{job_no}")
    sublet_vin = st.checkbox("Sublet VIN Present", key=f"sublet_vin_{job_no}")
    sublet_mileage = st.checkbox("Sublet Mileage Present", key=f"sublet_mileage_{job_no}")
    sublet_notes = st.checkbox("Sublet Detailed Notes Present", key=f"sublet_notes_{job_no}")

with c:
    rental_involved = st.checkbox("Rental Involved", key=f"rental_{job_no}")
    rental_days = st.number_input(
    "Rental Days Billed",
    min_value=0,
    value=0,
    step=1,
     key=f"rental_days_{job_no}"
                )
    manager_signed_rental = st.checkbox("Manager Signed Rental", key=f"rental_signed_{job_no}")

with d:
    warranty_add_on = st.checkbox("Warranty Add-On (+)", key=f"addon_{job_no}")
    manager_approval = st.checkbox("Manager Approval", key=f"manager_approval_{job_no}")
    ac_repair = st.checkbox("A/C Repair", key=f"ac_{job_no}")
    ac_evac_slip = st.checkbox("A/C EVAC Slip", key=f"ac_slip_{job_no}")
    parts_warranty = st.checkbox("Parts Warranty", key=f"parts_warranty_{job_no}")
    mopa_original_ro = st.checkbox("MOPA + Original RO", key=f"mopa_{job_no}")

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
            })

    st.divider()

    time_bypass = st.checkbox("Bypass Tech Flagged Time / Time Allotted Validation")
    time_bypass_user = st.text_input("Bypass Approved By") if time_bypass else ""

    if st.button("Run Audit + Save Review", type="primary", use_container_width=True):
        all_hard = []
        all_warn = []
        scores = []
        total_value = sum(float(j.get("claim_value") or 0) for j in jobs)
        hard_value = 0.0

        for job in jobs:
            hard, warn, score = audit_job(job, time_bypass)
            job["hard_stops"] = hard
            job["warnings"] = warn
            job["score"] = score

            scores.append(score)
            all_hard.extend(hard)
            all_warn.extend(warn)

            if hard:
                hard_value += float(job.get("claim_value") or 0)

        final_score = int(sum(scores) / len(scores)) if scores else 0
        status = "🔴 DO NOT SUBMIT" if all_hard else ("🟡 NEEDS REVIEW" if all_warn else "🟢 READY")

        result_banner(status)

        x1, x2, x3, x4, x5 = st.columns([1.1, 1.3, 1.7, 1.7, 1.2])
        x1.metric("Audit Score", final_score)
        x2.metric("Status", status)
        x3.metric("Total Claim Value", f"${total_value:,.2f}")
        x4.metric("Hard Stop Value", f"${hard_value:,.2f}")
        x5.metric("Hard Stops", len(all_hard))

        for job in jobs:
            with st.expander(f"Job {job['job_no']} Results", expanded=True):
                for h in job["hard_stops"]:
                    st.error(h)
                for w in job["warnings"]:
                    st.warning(w)
                if not job["hard_stops"] and not job["warnings"]:
                    st.success("No audit issues found.")
            st.markdown("### Auto-Built CCC Narrative")

            concern_text = str(job.get("concern", "")).strip()
            cause_text = str(job.get("cause", "")).strip()
            correction_text = str(job.get("correction", "")).strip()

            built_concern = concern_text if concern_text else "Customer concern needs to be clearly documented."
            built_cause = cause_text if cause_text else "Technician needs to document diagnostic steps, test results, and confirmed failure."
            built_correction = correction_text if correction_text else "Technician needs to document repair performed, parts replaced, and verification of proper operation."

            if job.get("battery_replacement"):
                built_cause += " Battery testing documentation should support the failure."
                built_correction += " Battery test code/slip should be attached or referenced."

            if job.get("ac_repair"):
                built_cause += " A/C diagnosis should include pressures, leak test results, and system findings."
                built_correction += " EVAC/recharge documentation should be attached or referenced."

            if job.get("oil_leak"):
                built_cause += " Leak diagnosis should identify the exact source of the leak and whether dye was used."
                built_correction += " Correction should document repair of the leak and verification that no leak remains."

            if job.get("wam_matches"):
                built_cause += " Matched WAM guidance should be reviewed and referenced where applicable."
                built_correction += " Narrative should align with matched WAM documentation requirements."

            ccc_text = f"""Concern:
{built_concern}

Cause:
{built_cause}

Correction:
{built_correction}
"""

            st.text_area("Suggested CCC Narrative", value=ccc_text, height=220, key=f"ccc_{job['job_no']}")
            st.markdown("### AI Narrative Recommendations")

            ai_suggestions = []

            cause_text = str(job.get("cause", "")).lower()
            correction_text = str(job.get("correction", "")).lower()

            if not any(word in cause_text for word in ["tested", "verified", "scanned", "measured"]):
                ai_suggestions.append(
                    "Cause recommendation: Add diagnostic steps used to identify the failure including scan results, measurements, or testing performed."
            )

            if not any(word in correction_text for word in ["replaced", "repaired", "installed", "performed"]):
                ai_suggestions.append(
                    "Correction recommendation: Clearly identify the repair performed and parts replaced."
            )

            if job.get("oil_leak") and not job.get("oil_dye_billed"):
                ai_suggestions.append(
                    "Oil leak recommendation: Add oil dye usage and dye billing documentation."
            )

            if job.get("battery_replacement") and not job.get("battery_test_slip"):
                ai_suggestions.append(
                    "Battery recommendation: Include battery test slip/code documentation."
            )

            if job.get("ac_repair") and not job.get("ac_evac_slip"):
                ai_suggestions.append(
                    "A/C recommendation: Include EVAC/recharge machine documentation."
            )

            if job.get("wam_matches"):
                ai_suggestions.append(
                    "WAM recommendation: Review matched WAM/manual guidance and incorporate required terminology into the narrative."
            )

            if ai_suggestions:
                for suggestion in ai_suggestions:
                    st.info(suggestion)
    else:
        st.success("Narrative documentation looks strong.")

    save_review({
        "ro_number": ro_number,
        "vin": vin,
        "ro_invoiced": str(ro_invoiced),
        "day_submitted": str(day_submitted),
        "days_to_submit": days_to_submit,
        "first_pass_paid": 1 if first_pass_paid else 0,
        "rejected": 1 if rejected else 0,
        "rejection_reason": rejection_reason,
        "advisor": advisor,
        "technician": technician,
        "warranty_admin": warranty_admin,
        "score": 0,
        "score": 0,
        "score": 0,
        "score": 0,
        "score": 0,
        "score": 0,
        "time_bypass": 1 if time_bypass else 0,
        "time_bypass_user": time_bypass_user,
        "jobs": jobs,
    })

    st.success("Review saved to Reporting.")
st.success("Review saved to Reporting.")
def render_claims():
    st.header("Claim Learning Upload")
    st.caption("Optional: upload paid-claim packets. RO Shield reads all pages and splits claim packets into learned claim records.")

    if PdfReader is None:
        st.error("PyPDF2 is not installed. Run: python3 -m pip install -r requirements.txt")
        return

    files = st.file_uploader("Upload paid claim PDFs", type=["pdf"], accept_multiple_files=True, key="paid_claim_upload")
    if files:
        total = 0
        for f in files:
            pages = extract_pages(f)
            claims = split_claims_from_pages(pages)
            save_learned_claims(f.name, claims)
            st.success(f"{f.name}: {len(pages)} pages → learned {len(claims)} claim records")
            total += len(claims)
        st.success(f"Total learned claim records added: {total}")

    df = load_shared_claims()
    st.metric("Learned Claim Records", len(df))
    if not df.empty:
        st.dataframe(df[["uploaded_at", "source_file", "claim_index"]], use_container_width=True)

def render_reporting():
        df =load_reviews()
        if not df.empty and "created_at" in df.columns:
            df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

            start_date, end_date = st.date_input(
                "Report Date Range",
                 value=(
                      df["created_at"].min().date(),
                      df["created_at"].max().date()
                )
            )

            df = df[
                (df["created_at"].dt.date >= start_date) &
                (df["created_at"].dt.date <= end_date)
        ]
                
        a, b, c, d, e, f = st.columns([1.0, 1.1, 1.8, 1.8, 1.1, 1.5])

        a.metric("Reviews", len(df))
    
        avg_score = pd.to_numeric(df.get("score", pd.Series([0])), errors="coerce").fillna(0).mean()
        b.metric("Avg Score", f"{avg_score:.1f}")

        avg_days_to_submit = pd.to_numeric(df.get("days_to_submit", pd.Series([0])), errors="coerce").fillna(0).mean()
        b.metric("Avg Days to Submit", f"{avg_days_to_submit:.1f}")
    
        total_claim_value = pd.to_numeric(df.get("total_claim_value", pd.Series([0])), errors="coerce").fillna(0).sum()
        c.metric("Total Claim Value", f"${total_claim_value:,.2f}")
    
        hard_stop_value = pd.to_numeric(df.get("hard_stop_value", pd.Series([0])), errors="coerce").fillna(0).sum()
        d.metric("Hard Stop Value", f"${hard_stop_value:,.2f}")
    
        hard_stop_count = pd.to_numeric(df.get("hard_stop_count", pd.Series([0])), errors="coerce").fillna(0).sum()
        e.metric("Hard Stops", int(hard_stop_count))
    
        time_bypass = pd.to_numeric(df.get("time_bypass", pd.Series([0])), errors="coerce").fillna(0).sum()
        f.metric("Time Bypasses", int(time_bypass))
        st.subheader("First-Pass Approval Tracking")
        st.subheader("First-Pass Approval Tracking")

        if not df.empty:
            fp_df = df.copy()
            fp_df["first_pass_paid"] = pd.to_numeric(fp_df.get("first_pass_paid", 0), errors="coerce").fillna(0)
            fp_df["rejected"] = pd.to_numeric(fp_df.get("rejected", 0), errors="coerce").fillna(0)
            fp_df["total_claim_value"] = pd.to_numeric(fp_df.get("total_claim_value", 0), errors="coerce").fillna(0)

            total_reviews = len(fp_df)
            first_pass_count = int(fp_df["first_pass_paid"].sum())
            rejected_count = int(fp_df["rejected"].sum())

            first_pass_pct = (first_pass_count / total_reviews * 100) if total_reviews else 0
            rejected_pct = (rejected_count / total_reviews * 100) if total_reviews else 0
            rejected_value = fp_df.loc[fp_df["rejected"] == 1, "total_claim_value"].sum()

            fp1, fp2, fp3, fp4 = st.columns(4)
            fp1.metric("First-Pass Approval %", f"{first_pass_pct:.1f}%")
            fp2.metric("First-Pass Paid Count", first_pass_count)
            fp3.metric("Rejected %", f"{rejected_pct:.1f}%")
            fp4.metric("Rejected Claim Value", f"${rejected_value:,.2f}")

        if "rejection_reason" in fp_df.columns:
            reasons = fp_df[fp_df["rejection_reason"].astype(str).str.strip() != ""]
        if not reasons.empty:
            st.markdown("### Rejection Reasons")
            reason_summary = reasons.groupby("rejection_reason").agg(
                count=("ro_number", "count"),
                total_value=("total_claim_value", "sum")
            ).reset_index().sort_values("count", ascending=False)

            st.dataframe(reason_summary, use_container_width=True)
        st.subheader("Top Offenders / Best Performers")

        if not df.empty:
            perf_df = df.copy()
            perf_df["score"] = pd.to_numeric(perf_df.get("score", 0), errors="coerce").fillna(0)
            perf_df["hard_stop_count"] = pd.to_numeric(perf_df.get("hard_stop_count", 0), errors="coerce").fillna(0)
            perf_df["warning_count"] = pd.to_numeric(perf_df.get("warning_count", 0), errors="coerce").fillna(0)

            rank_col = st.selectbox(
                "Rank By",
                ["advisor", "technician", "warranty_admin"],
                key="rank_by_employee"
    )

        if rank_col in perf_df.columns:
            ranking = perf_df.groupby(rank_col).agg(
            reviews=("ro_number", "count"),
            avg_score=("score", "mean"),
            hard_stops=("hard_stop_count", "sum"),
            warnings=("warning_count", "sum")
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
        st.subheader("Employee Scorecards")
    
        if not df.empty:
            scorecard_role = st.selectbox(
            "Scorecard Type",
            ["Advisor", "Technician", "Warranty Admin"]
    )

        employee_col = {
        "Advisor": "advisor",
        "Technician": "technician",
        "Warranty Admin": "warranty_admin"
    }[scorecard_role]

        if employee_col in df.columns:
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
            avg_days_to_submit=("days_to_submit", "mean")
        ).reset_index()

        scorecard = scorecard.sort_values(
            by=["hard_stops", "avg_score"],
            ascending=[False, True]
        )

        st.dataframe(scorecard, use_container_width=True)
        st.subheader("Review Log")
        st.dataframe(df, use_container_width=True)
        st.download_button("Download Review Report CSV", df.to_csv(index=False), "ro_shield_review_report.csv", "text/csv")


def render_admin():
    st.header("Admin")
    with st.form("add_person"):
        name = st.text_input("Name")
        employee_number = st.text_input("Employee Number")
        role = st.selectbox("Role", ["Advisor", "Technician", "Warranty Admin", "Manager"])
        submitted = st.form_submit_button("Add Person")
        if submitted and name.strip():
            add_person_shared(name.strip(), role, employee_number)
            st.success("Person added.")

    df = load_personnel()
    st.subheader("Edit Existing Employee")

    if not df.empty:
            employee_names = df["name"].tolist()
    selected_employee = st.selectbox("Select Employee to Edit", employee_names)

    selected_row = df[df["name"] == selected_employee].iloc[0]

    edit_name = st.text_input("Edit Name", value=selected_row.get("name", ""))
    edit_employee_number = st.text_input("Edit Employee Number", value=str(selected_row.get("employee_number", "")))

    edit_role = st.selectbox(
        "Edit Role",
        ["Advisor", "Technician", "Warranty Admin", "Manager"],
        index=["Advisor", "Technician", "Warranty Admin", "Manager"].index(selected_row.get("role", "Advisor"))
    )

    if st.button("Save Employee Changes"):
        supabase.table("personnel").update({
            "name": edit_name,
            "employee_number": edit_employee_number,
            "role": edit_role
        }).eq("id", selected_row["id"]).execute()

        st.success("Employee updated.")
        st.rerun()
    if df.empty:
        st.info("No personnel added yet.")
    else:
        st.dataframe(df, use_container_width=True)
        remove_id = st.number_input("Deactivate personnel ID", min_value=0, value=0, step=1)
        if st.button("Deactivate") and remove_id:
            deactivate_person(remove_id)
            st.success("Personnel deactivated.")

    st.header("Service Bulletins / Rules")
    with st.form("add_bulletin"):
        title = st.text_input("Bulletin / Rule Title")
        keywords = st.text_input("Keywords")
        notes = st.text_area("Notes")
        if st.form_submit_button("Add Bulletin / Rule") and title.strip():
            save_bulletin(title, keywords, notes)
            st.success("Bulletin/rule added.")

    bdf = read_df("bulletins")
    if not bdf.empty:
        st.dataframe(bdf, use_container_width=True)
def render_wam():
    st.header("WAM / Warranty Manual Learning")
    st.caption("Upload WAM PDFs or warranty policy documents. RO Shield will store the text and use it for audit reference.")

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
                        "section": f"{file.name} - Section {idx + 1}",
                        "keywords": "",
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
    apply_style()

    st.sidebar.markdown("## 🛡️ RO Shield")
    st.sidebar.caption("Final Production Polish")
    st.sidebar.selectbox("Appearance", ["Dark"], index=0)

    tabs = st.tabs(["Review", "Claim Learning", "Reporting", "Admin", "WAM"])
    with tabs[0]:
        render_review()
    with tabs[1]:
        render_claims()
    with tabs[2]:
        render_reporting()
    with tabs[3]:
        render_admin()
    with tabs[4]:
        render_wam()

if __name__ == "__main__":
    main()
