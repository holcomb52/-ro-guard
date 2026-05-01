import streamlit as st
from PyPDF2 import PdfReader
import re

st.set_page_config(page_title="RO Shield v87", layout="wide")

st.title("🛡️ RO Shield v87 - Full Claim Extraction")

tabs = st.tabs(["Review", "Upload Learning Data"])

if "memory" not in st.session_state:
    st.session_state.memory = []

# =========================
# PAGE-LEVEL EXTRACTION
# =========================
def extract_pages(file):
    reader = PdfReader(file)
    pages = []

    for p in reader.pages:
        try:
            txt = p.extract_text() or ""
            if len(txt.strip()) > 100:
                pages.append(txt.lower())
        except:
            pass

    return pages

# =========================
# SMART SPLIT
# =========================
def split_claims(pages):

    claims = []

    for page in pages:

        # Try structured split first
        parts = re.split(
            r"(advisor:\s*process date:|claim type:|submission type:|date received:)",
            page,
            flags=re.I
        )

        # Rebuild chunks
        chunk = ""
        for part in parts:
            if any(x in part for x in ["advisor:", "claim type", "submission type"]):
                if chunk:
                    claims.append(chunk)
                chunk = part
            else:
                chunk += part

        if chunk:
            claims.append(chunk)

    # Fallback: if still too small → treat each page as claim
    if len(claims) < len(pages):
        claims = pages

    return [c for c in claims if len(c) > 200]

# =========================
# CLEAN CCC
# =========================

# =========================
# IMPROVED CCC FILTERING
# =========================
def is_bad_line(line):
    l = line.lower()

    bad_patterns = [
        "part number",
        "quantity",
        "qty",
        "description",
        "extended",
        "price",
        "labor op",
        "line",
        "invoice",
        "amount"
    ]

    return any(p in l for p in bad_patterns)

def extract_ccc(text):
    concern = ""
    cause = ""
    correction = ""

    for line in text.split("\n"):
        l = line.strip()

        if len(l) < 10:
            continue

        if "____" in l:
            continue

        if is_bad_line(l):
            continue

        if not concern and any(x in l.lower() for x in ["customer", "complaint", "leak", "noise", "no start"]):
            concern = l

        elif not cause and any(x in l.lower() for x in ["found", "verified", "tested", "failed", "diagnosed", "inspection"]):
            cause = l

        elif not correction and any(x in l.lower() for x in ["replaced", "repaired", "installed", "performed"]):
            correction = l

    return concern, cause, correction


# =========================
# LEARNING TAB
# =========================
with tabs[1]:
    st.header("Upload Paid Claim Packets")

    files = st.file_uploader("Upload PDFs", type=["pdf"], accept_multiple_files=True)

    if files:
        total = 0

        for f in files:
            pages = extract_pages(f)
            claims = split_claims(pages)

            st.write(f"📄 {f.name}: {len(pages)} pages → {len(claims)} claims")

            for c in claims:
                con, cau, cor = extract_ccc(c)

                st.session_state.memory.append({
                    "raw": c,
                    "concern": con,
                    "cause": cau,
                    "correction": cor
                })

            total += len(claims)

        st.success(f"🔥 Learned from {total} TOTAL claims")


# =========================
# SMART MATCHING ENGINE
# =========================
STOPWORDS = {
    "the","and","or","to","of","in","on","for","with","a","an","is","was","were",
    "customer","states","vehicle","repair","claim","date","type","advisor"
}

def clean_words(text):
    text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    words = text.split()
    return [w for w in words if len(w) > 2 and w not in STOPWORDS]

def repair_phrases(text):
    text = text.lower()
    phrases = [
        "oil leak", "coolant leak", "water leak", "transmission leak",
        "backup camera", "camera inop", "radio inop",
        "no start", "hard start", "cranks no start",
        "check engine", "misfire", "dtc", "noise", "vibration",
        "a/c not cold", "ac not cold", "evap leak",
        "battery failed", "alternator", "starter",
        "brake noise", "alignment", "tire"
    ]
    return [p for p in phrases if p in text]

def smart_score(user_text, claim):
    raw = claim["raw"].lower()

    user_words = clean_words(user_text)
    claim_words = set(clean_words(raw))

    score = 0

    # Word match
    for w in user_words:
        if w in claim_words:
            score += 2

    # Phrase boost
    for p in repair_phrases(user_text):
        if p in raw:
            score += 12

    # Concern/cause/correction specific boosts
    for field in ["concern", "cause", "correction"]:
        if claim.get(field):
            field_words = set(clean_words(claim[field]))
            overlap = len(set(user_words) & field_words)
            score += overlap * 4

    # Labor op boost if user typed one
    lops = re.findall(r"[A-Z]{2,5}[0-9]{2,5}", user_text.upper())
    for lop in lops:
        if lop.lower() in raw:
            score += 20

    return score

# =========================
# REVIEW TAB
# =========================
with tabs[0]:
    st.header("Smart Review")

    concern = st.text_area("Concern")
    cause = st.text_area("Cause")
    correction = st.text_area("Correction")

    if st.button("Get Suggestions"):

        user = f"{concern} {cause} {correction}".lower()
        matches = []

        for c in st.session_state.memory:
            score = smart_score(user, c)

            if score > 10:
                matches.append((score, c))

        matches = sorted(matches, reverse=True)[:5]

        if matches:
            for i, m in enumerate(matches):
                st.markdown(f"### Match {i+1}")

                st.text_area("Concern", m[1]["concern"], key=f"c{i}")
                st.text_area("Cause", m[1]["cause"], key=f"ca{i}")
                st.text_area("Correction", m[1]["correction"], key=f"co{i}")

                lops = re.findall(r"[A-Z]{2,5}[0-9]{2,5}", m[1]["raw"].upper())
                if lops:
                    st.info("Suggested Labor Ops: " + ", ".join(sorted(set(lops[:8]))))

        else:
            st.warning("Upload more claims")
