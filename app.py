from supabase import create_client

SUPABASE_URL = "https://eyufnhnabdgehkfvhqzf.supabase.co"
SUPABASE_KEY = "sb_publishable_5SXVN_OB5aIouuZAOa3b3Q_Mq4chxUT"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

import json
import re
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
        supabase.table("reviews").insert(data).execute()
    except Exception as e:
        st.warning(f"Review save failed: {e}")

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


def add_person_shared(name, role):
    try:
        existing = supabase.table("personnel").select("id").eq("name", name).eq("role", role).execute()

        if not existing.data:
            supabase.table("personnel").insert({
                "name": name,
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
        keys = ["found", "verified", "tested", "failed", "diagnosed", "inspection", "dtc"]
    else:
        keys = ["replaced", "repaired", "installed", "performed", "completed", "programmed"]
    for line in lines:
        if any(k in line.lower() for k in keys):
            return line[:700]
    return ""


# =========================
# AUDIT ENGINE
# =========================
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

    if job["sublet"]:
        warn.append("Sublet selected: invoice must include VIN, mileage, and detailed repair notes.")
        if not job["sublet_vin"]:
            hard.append("Sublet invoice must show VIN.")
        if not job["sublet_mileage"]:
            hard.append("Sublet invoice must show mileage.")
        if not job["sublet_repair_notes"]:
            hard.append("Sublet invoice must include detailed repair notes.")

    if job["rental"]:
        if job["rental_days"] <= 0:
            hard.append("Rental involved but rental days are not billed.")
        if not job["rental_signed"]:
            hard.append("Rental involved but manager sign-off is missing.")
        if job["rental_days"] >= 15:
            warn.append("15 or more rental days billed: make sure all documentation to support rental days is submitted to Stellantis with the claim.")

    if job["add_on"] and not job["manager_signed"]:
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

    if job["battery"] and not job["battery_test"]:
        hard.append("Battery replacement requires failed battery test slip/code.")
    if job["ac"] and not job["ac_slip"]:
        hard.append("A/C repair requires EVAC/recharge slip.")
    if job["parts_warranty"] and not job["mopa"]:
        hard.append("Parts warranty requires MOPA and original RO support.")

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


# =========================
# SCREENS
# =========================
def render_review():
    st.markdown("""
    <div class="hero">
        <h1>🛡️ RO Shield</h1>
        <p>Final production validation build — warranty review, Pencil Wrench narrative grading, hard-stop audit scoring, reporting, and admin controls.</p>
    </div>
    """, unsafe_allow_html=True)

    st.header("Repair Order Review")

    a, b, c, d = st.columns(4)
    ro_number = a.text_input("RO Number")
    vin = b.text_input("VIN")
    advisor = c.selectbox("Advisor", role_options("Advisor"))
    technician = d.selectbox("Technician", role_options("Technician"))

    e, f, g = st.columns(3)
    warranty_admin = e.selectbox("Warranty Admin", role_options("Warranty Admin"))
    manager = f.selectbox("Manager", role_options("Manager"))
    entered_by = g.text_input("Entered By / User")

    st.markdown("### Time Validation")
    time_bypass = st.checkbox("Bypass Tech Flagged Time / Time Allotted validation")
    time_bypass_user = ""
    if time_bypass:
        time_bypass_user = st.text_input("Bypass entered by", value=entered_by or manager or warranty_admin or advisor)
        st.warning("This bypass will be saved in Reporting with RO number and user information.")

    job_count = st.number_input("Number of Jobs", 1, 20, 1)

    jobs = []
    for i in range(int(job_count)):
        with st.container(border=True):
            st.subheader(f"Job {i+1}")

            j1, j2, j3, j4, j5 = st.columns(5)
            job_no = j1.text_input("Line / Job Number", value=str(i+1), key=f"job_no_{i}")
            job_type = j2.selectbox("Job Type", ["Warranty", "Recall/Campaign", "Service Contract", "Mopar", "Customer Pay", "Internal"], key=f"type_{i}")
            claim_value = j3.number_input("Claim Value ($)", 0.0, step=1.0, format="%.2f", key=f"value_{i}")
            tech_flagged_time = j4.number_input("Tech Flagged Time", 0.0, step=0.1, format="%.1f", key=f"tech_flagged_{i}", disabled=time_bypass)
            time_allotted = j5.number_input("Time Allotted for the Job", 0.0, step=0.1, format="%.1f", key=f"time_allotted_{i}", disabled=time_bypass)

            n1, n2, n3 = st.columns(3)
            concern = n1.text_area("Concern", key=f"concern_{i}", height=135)
            cause = n2.text_area("Cause / Diagnosis", key=f"cause_{i}", height=135, placeholder="Pencil Wrench style: identify failure, test steps, DTCs, inspection/test results.")
            correction = n3.text_area("Correction / Repair Performed", key=f"correction_{i}", height=135, placeholder="Pencil Wrench style: identify repair, justify parts, verify proper operation.")

            st.markdown("### Required Warranty Checks")
            r1, r2, r3, r4 = st.columns(4)

            oil_leak = r1.checkbox("Oil Leak", key=f"oil_{i}")
            dye_billed = r1.checkbox("Oil Dye Billed", key=f"dye_{i}")
            battery = r1.checkbox("Battery Replacement", key=f"battery_{i}")
            battery_test = r1.checkbox("Battery Test Slip", key=f"battery_test_{i}")

            sublet = r2.checkbox("Sublet Repair", key=f"sublet_{i}")
            sublet_vin = False
            sublet_mileage = False
            sublet_repair_notes = False
            if sublet:
                r2.caption("Sublet invoice checklist")
                sublet_vin = r2.checkbox("VIN on sublet invoice", key=f"sublet_vin_{i}")
                sublet_mileage = r2.checkbox("Mileage on sublet invoice", key=f"sublet_mileage_{i}")
                sublet_repair_notes = r2.checkbox("Detailed repair notes on sublet invoice", key=f"sublet_repair_notes_{i}")

            rental = r3.checkbox("Rental Involved", key=f"rental_{i}")
            rental_days = r3.number_input("Rental Days Billed", 0, 60, key=f"rental_days_{i}")
            rental_signed = r3.checkbox("Manager Signed Rental", key=f"rental_signed_{i}")

            add_on = r4.checkbox("Warranty Add-On (+)", key=f"addon_{i}")
            manager_signed = r4.checkbox("Manager Approval", key=f"manager_signed_{i}")
            ac = r4.checkbox("A/C Repair", key=f"ac_{i}")
            ac_slip = r4.checkbox("A/C EVAC Slip", key=f"ac_slip_{i}")
            parts_warranty = r4.checkbox("Parts Warranty", key=f"parts_warranty_{i}")
            mopa = r4.checkbox("MOPA + Original RO", key=f"mopa_{i}")

            jobs.append({
                "job_no": job_no, "job_type": job_type, "claim_value": claim_value,
                "tech_flagged_time": tech_flagged_time, "time_allotted": time_allotted,
                "concern": concern, "cause": cause, "correction": correction,
                "oil_leak": oil_leak, "dye_billed": dye_billed,
                "sublet": sublet, "sublet_vin": sublet_vin, "sublet_mileage": sublet_mileage,
                "sublet_repair_notes": sublet_repair_notes,
                "rental": rental, "rental_days": rental_days, "rental_signed": rental_signed,
                "add_on": add_on, "manager_signed": manager_signed,
                "battery": battery, "battery_test": battery_test,
                "ac": ac, "ac_slip": ac_slip,
                "parts_warranty": parts_warranty, "mopa": mopa
            })

            learned = load_shared_claims()
            if not learned.empty and st.button("Suggest From Paid Claims", key=f"suggest_{i}"):
                query = f"{concern} {cause} {correction}"
                scored = []
                for _, row in learned.iterrows():
                    s = score_match(query, row["raw_text"])
                    if s > 8:
                        scored.append((s, row["raw_text"]))
                scored = sorted(scored, key=lambda x: x[0], reverse=True)[:3]
                if scored:
                    for n, (s, raw) in enumerate(scored, start=1):
                        st.info(f"Paid-claim match {n} | Score {s}")
                        st.text_area("Suggested Concern", extract_sentence(raw, "concern"), key=f"sug_con_{i}_{n}")
                        st.text_area("Suggested Cause", extract_sentence(raw, "cause"), key=f"sug_cau_{i}_{n}")
                        st.text_area("Suggested Correction", extract_sentence(raw, "correction"), key=f"sug_cor_{i}_{n}")
                        lops = suggested_lops(raw)
                        if lops:
                            st.success("Suggested Labor Ops: " + ", ".join(lops))
                else:
                    st.warning("No strong paid-claim match found yet.")

    if st.button("Run Audit + Save Review", type="primary", use_container_width=True):
        all_hard = []
        all_warn = []
        total_value = sum(float(j["claim_value"] or 0) for j in jobs)
        hard_value = 0.0
        scores = []

        for j in jobs:
            hard, warn, score = audit_job(j, time_bypass)
            j["hard_stops"] = hard
            j["warnings"] = warn
            j["score"] = score
            scores.append(score)
            all_hard.extend(hard)
            all_warn.extend(warn)
            if hard:
                hard_value += float(j["claim_value"] or 0)

        final_score = int(sum(scores) / len(scores)) if scores else 0
        status = "🔴 DO NOT SUBMIT" if all_hard else ("🟡 NEEDS REVIEW" if all_warn else "🟢 READY")

        result_banner(status)

        x1, x2, x3, x4, x5 = st.columns([1.1, 1.3, 1.7, 1.7, 1.2])
        x1.metric("Audit Score", final_score)
        x2.metric("Status", status)
        x3.metric("Total Claim Value", f"${total_value:,.2f}")
        x4.metric("Hard Stop Value", f"${hard_value:,.2f}")
        x5.metric("Hard Stops", len(all_hard))

        for j in jobs:
            with st.expander(f"Job {j['job_no']} Results", expanded=True):
                for h in j["hard_stops"]:
                    st.error(h)
                for w in j["warnings"]:
                    st.warning(w)
                if not j["hard_stops"] and not j["warnings"]:
                    st.success("No audit issues found.")

        save_review({
            "ro_number": ro_number, "vin": vin, "advisor": advisor, "technician": technician,
            "warranty_admin": warranty_admin, "manager": manager, "entered_by": entered_by,
            "score": final_score, "status": status, "total_claim_value": total_value,
            "hard_stop_value": hard_value, "hard_stop_count": len(all_hard),
            "warning_count": len(all_warn), "time_bypass": time_bypass,
            "time_bypass_user": time_bypass_user, "jobs": jobs
        })
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
    df = load_reviews()
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

total_claim_value = pd.to_numeric(df.get("total_claim_value", pd.Series([0])), errors="coerce").fillna(0).sum()
c.metric("Total Claim Value", f"${total_claim_value:,.2f}")

hard_stop_value = pd.to_numeric(df.get("hard_stop_value", pd.Series([0])), errors="coerce").fillna(0).sum()
d.metric("Hard Stop Value", f"${hard_stop_value:,.2f}")

hard_stop_count = pd.to_numeric(df.get("hard_stop_count", pd.Series([0])), errors="coerce").fillna(0).sum()
e.metric("Hard Stops", int(hard_stop_count))

time_bypass = pd.to_numeric(df.get("time_bypass", pd.Series([0])), errors="coerce").fillna(0).sum()
f.metric("Time Bypasses", int(time_bypass))

st.subheader("Time Validation Bypass Log")
if "time_bypass" in df.columns:
        bypass_df = df[df["time_bypass"].fillna(0).astype(int) == 1][[
            "created_at", "ro_number", "vin", "advisor", "technician", "manager",
            "entered_by", "time_bypass_user", "status", "score"
        ]]
if bypass_df.empty:
     st.success("No time-validation bypasses recorded.")
else:
    st.dataframe(bypass_df, use_container_width=True)
    st.download_button("Download Time Bypass Report CSV", bypass_df.to_csv(index=False), "ro_shield_time_bypass_report.csv", "text/csv")

    st.subheader("Review Log")
    st.dataframe(df, use_container_width=True)
    st.download_button("Download Review Report CSV", df.to_csv(index=False), "ro_shield_review_report.csv", "text/csv")


def render_admin():
    st.header("Admin")
    with st.form("add_person"):
        name = st.text_input("Name")
        role = st.selectbox("Role", ["Advisor", "Technician", "Warranty Admin", "Manager"])
        submitted = st.form_submit_button("Add Person")
        if submitted and name.strip():
            add_person_shared(name.strip(), role)
            st.success("Person added.")

    df = load_personnel()
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


def main():
    init_db()
    apply_style()

    st.sidebar.markdown("## 🛡️ RO Shield")
    st.sidebar.caption("Final Production Polish")
    st.sidebar.selectbox("Appearance", ["Dark"], index=0)

    tabs = st.tabs(["Review", "Claim Learning", "Reporting", "Admin"])
    with tabs[0]:
        render_review()
    with tabs[1]:
        render_claims()
    with tabs[2]:
        render_reporting()
    with tabs[3]:
        render_admin()


if __name__ == "__main__":
    main()
