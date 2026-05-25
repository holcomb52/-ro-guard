"""OCR and parsing for scanned service invoices and repair orders."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from itertools import combinations
from typing import BinaryIO, Optional, Union

try:
    from PyPDF2 import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

try:
    import pytesseract
    from pdf2image import convert_from_bytes
except ImportError:  # pragma: no cover
    pytesseract = None
    convert_from_bytes = None


PayType = str  # warranty | customer | internal | unknown


@dataclass
class ParsedJob:
    job_no: int
    pay_type: PayType
    operation_code: str = ""
    description: str = ""
    concern: str = ""
    cause: str = ""
    correction: str = ""
    tech_flagged_time: float = 0.0
    claim_value: float = 0.0
    warranty_add_on: bool = False


@dataclass
class ParsedRepairOrder:
    ro_number: str = ""
    vin: str = ""
    mileage: str = ""
    advisor: str = ""
    technician: str = ""
    customer_name: str = ""
    ro_invoiced: Optional[date] = None
    day_received: Optional[date] = None
    document_type: str = "unknown"  # invoice | repair_order
    jobs: list[ParsedJob] = field(default_factory=list)
    warranty_jobs: list[ParsedJob] = field(default_factory=list)
    raw_text: str = ""
    ocr_used: bool = False
    warnings: list[str] = field(default_factory=list)


def ocr_available() -> bool:
    return pytesseract is not None and convert_from_bytes is not None


def _normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = text.replace("—", "-").replace("–", "-")
    text = re.sub(r"[ \t]+", " ", text)
    return text


def _extract_text_layer(pdf_bytes: bytes) -> str:
    if PdfReader is None:
        return ""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    chunks = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return _normalize_text("\n".join(chunks))


def _ocr_pdf_bytes(pdf_bytes: bytes, dpi: int = 200) -> str:
    if not ocr_available():
        raise RuntimeError(
            "OCR is not available. Install: python3 -m pip install pytesseract pdf2image Pillow "
            "and ensure Tesseract is installed on your computer."
        )
    images = convert_from_bytes(pdf_bytes, dpi=dpi)
    chunks = [pytesseract.image_to_string(img) for img in images]
    return _normalize_text("\n".join(chunks))


def _is_extracted_text_usable(text: str) -> bool:
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 80:
        return False
    words = re.findall(r"[A-Za-z]{3,}", text)
    if len(words) < 10:
        return False
    encoding_artifacts = len(re.findall(r"/(?:i255|\d+)(?:\s|/)", text))
    if encoding_artifacts > 15 and len(words) < 25:
        return False
    return True


def extract_ro_text(source: Union[bytes, BinaryIO], *, force_ocr: bool = False) -> tuple[str, bool]:
    pdf_bytes = source.read() if hasattr(source, "read") else source
    text = "" if force_ocr else _extract_text_layer(pdf_bytes)
    if not force_ocr and _is_extracted_text_usable(text):
        return text, False
    return _ocr_pdf_bytes(pdf_bytes), True


def _fix_vin_ocr(vin: str) -> str:
    if _is_plausible_vin(vin):
        return vin
    corrected = vin.replace("O", "0").replace("I", "1").replace("Q", "0")
    return corrected if _is_plausible_vin(corrected) else vin


def _clean_vin(candidate: str) -> str:
    vin = re.sub(r"[^A-Z0-9]", "", candidate.upper())
    if len(vin) > 17:
        extras = len(vin) - 17
        if extras <= 3:
            for combo in combinations(range(len(vin)), extras):
                trimmed = vin
                for i in sorted(combo, reverse=True):
                    trimmed = trimmed[:i] + trimmed[i + 1 :]
                if _is_plausible_vin(trimmed) and trimmed[0].isdigit():
                    return trimmed[:17]
        while len(vin) > 17:
            vin = vin[1:]
    vin = _fix_vin_ocr(vin)
    if len(vin) == 16 and vin.startswith(("C4", "C3")):
        vin = "1" + vin
    return vin[:17]


def _is_plausible_vin(vin: str) -> bool:
    if len(vin) not in (15, 16, 17):
        return False
    if any(ch in vin for ch in ("I", "O", "Q")):
        return False
    if not any(ch.isdigit() for ch in vin) or not any(ch.isalpha() for ch in vin):
        return False
    if any(skip in vin for skip in ("CHRYSLER", "SMYRNA", "FLORIDA", "JEEP", "RYSLER", "MAKE", "MODEL", "YEAR")):
        return False
    return True


def _extract_vin(text: str) -> str:
    upper = text.upper()
    candidates: list[tuple[int, str]] = []

    def _add_vin(raw: str, priority: int) -> None:
        vin = _clean_vin(raw)
        if len(vin) == 16 and vin.startswith(("C3CCAAG", "E3CCAAG")):
            vin = "2" + vin[1:]
        if _is_plausible_vin(vin):
            candidates.append((priority, vin))

    for m in re.finditer(r"(1C4P[A-Z0-9]{13,15})", upper):
        _add_vin(m.group(1), 11)
    for m in re.finditer(r"(2C3C[A-Z0-9]{13,15})", upper):
        _add_vin(m.group(1), 11)
    for m in re.finditer(
        r"VEHICLE\s*(?:I\.D\.?\s*NO\.?|LD\s*NO\.?|\.D-?\s*NO\.?).{0,120}?([A-Z0-9]{15,18})",
        upper,
        re.S,
    ):
        _add_vin(m.group(1), 10)
    for m in re.finditer(r"([A-Z0-9]{15,18})\s*[-–=|]\s*\d{2}/(?:JEEP|RAM|CHRYSLER|DODGE)", upper):
        _add_vin(m.group(1), 9)
    for m in re.finditer(r"\b([A-Z0-9]{17,18})\b", upper):
        _add_vin(m.group(1), 1)

    if not candidates:
        return ""
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _extract_ro_number(text: str) -> str:
    patterns = [
        r"INVOICE\s*NO\.?\s*CH(?:WS|CS)(\d{5,7})",
        r"CH(?:WS|CS)(\d{6,7})",
        r"REPAIR ORDER[^\d]{0,40}(\d{5,7})",
        r"RO\s*#?\s*(\d{5,7})",
        r"RO\.?\s*NO\.?\s*(\d{5,7})",
        r"\b(56\d{4})\b",
        r"\b(57\d{4})\b",
    ]
    counts: dict[str, int] = {}
    for pat in patterns:
        for match in re.finditer(pat, text, re.I):
            counts[match.group(1)] = counts.get(match.group(1), 0) + 3
    for match in re.finditer(r"\b(\d{6,7})\b", text):
        val = match.group(1)
        if val.startswith(("38", "40", "39", "107")):
            continue
        counts[val] = counts.get(val, 0) + 1
    if not counts:
        return ""
    return max(counts, key=counts.get)


def _extract_mileage(text: str) -> str:
    patterns = [
        r"MILEAGE[^\d]{0,20}(\d{1,3}[,\.]?\d{3})",
        r"(\d{2,3}[,\.]?\d{3})\s*//",
        r"(\d{2,3}[,\.]?\d{3})\)\s*\d{3,4}\s+[A-Z]",
        r"FLAT RATE[^\d]{0,20}(\d{1,3}[,\.]?\d{3})",
        r"\|\s*(\d{2,3}[,\.]?\d{3})\s*\|",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return re.sub(r"[^\d]", "", m.group(1))
    return ""


def _extract_advisor(text: str) -> str:
    name_patterns = (
        r"ADVISOR[:\s]+([A-Z][A-Z]+(?:[ \t]+[A-Z][A-Z]+)+)",
        r"\d{1,3}[,\.]?\d{3}\)\s+(\d{3,5})\s+([A-Z][A-Z]+(?:[ \t]+[A-Z][A-Z]+)+)",
        r"\d{5,6}\s+([A-Z][A-Z]+(?:[ \t]+[A-Z][A-Z]+)+)\s+\d{3,5}\s+\d",
        r"\d{1,3}[,\.]?\d{3}\)\s+\d{3,5}\s+([A-Z][A-Z]+(?:[ \t]+[A-Z][A-Z]+)+)",
    )
    m = re.search(name_patterns[0], text, re.I)
    if m:
        name = re.split(r"\b(LABOR|LICENSE|RATE|INVOICE|TAG)\b", m.group(1), maxsplit=1, flags=re.I)[0].strip()
        if name and name.upper() not in {"TAG NO", "NO"} and not name.upper().startswith("CI"):
            return name.title()
    m = re.search(name_patterns[1], text, re.I)
    if m:
        return m.group(2).strip().title()
    m = re.search(name_patterns[2], text, re.I)
    if m:
        name = m.group(1).strip()
        if "NEW SMYRNA" not in name.upper():
            return name.title()
    m = re.search(name_patterns[3], text, re.I)
    if m:
        name = re.split(
            r"\b(CIHALY|FLAT|RATE|RESIDENCE|BUSINESS|ORIGINAL|ESTIMATE|OCUHRLY)\b",
            m.group(1),
            maxsplit=1,
            flags=re.I,
        )[0].strip()
        if name:
            return name.title()
    return ""


def _parse_mdy(value: str) -> Optional[date]:
    value = value.strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _extract_dates(text: str) -> tuple[Optional[date], Optional[date]]:
    ro_invoiced = None
    received = None
    inv = re.search(r"INVOICE\s*DATE[^\d]{0,20}(\d{1,2}/\d{1,2}/\d{2,4})", text, re.I)
    if inv:
        ro_invoiced = _parse_mdy(inv.group(1))
    promised = re.search(
        r"(?:DATE/TIME PROMISED|PROMISED)[^\d]{0,30}(\d{1,2}/\d{1,2}/\d{2,4})",
        text,
        re.I,
    )
    if promised and not ro_invoiced:
        ro_invoiced = _parse_mdy(promised.group(1))
    recv = re.search(
        r"(?:TIME RECEIVED|RECEIVED|RO\.?\s*DATE)[^\d]{0,40}(\d{1,2}/\d{1,2}/\d{2,4})",
        text,
        re.I,
    )
    if recv:
        received = _parse_mdy(recv.group(1))
    if ro_invoiced is None:
        fallback = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})\s+\d{1,2}:\d{2}\s*[ap]m", text, re.I)
        if fallback:
            ro_invoiced = _parse_mdy(fallback.group(1))
    return ro_invoiced, received


def _extract_technician(text: str) -> str:
    m = re.search(r"TECH\(S\)\s*:\s*(\d{3,6})", text, re.I)
    if m:
        return m.group(1)
    m = re.search(
        r"TECHNICIAN[^\n]{0,30}(\d{3,6})\s+([A-Z][A-Z]+(?:\s+[A-Z][A-Z]+)+)",
        text,
        re.I,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(2)).strip().title()
    return ""


def _extract_customer_name(text: str) -> str:
    m = re.search(
        r"CUSTOMER NO[^\n]*\n\s*([A-Z][A-Z\s\.\'-]{4,40})\s+\d",
        text,
        re.I,
    )
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip().title()
    m = re.search(
        r"\d{5,7}\s+([A-Z][A-Z\s\.\'-]{4,40})\s+(?:\d|,|\|)",
        text,
    )
    if m and "NEW SMYRNA" not in m.group(1):
        return re.sub(r"\s+", " ", m.group(1)).strip().title()
    return ""


def _is_service_invoice(text: str) -> bool:
    upper = text.upper()
    has_invoice = "INVOICE NO" in upper and re.search(r"CH(?:WS|CS)", upper)
    has_job = "JOB#" in upper or "JOBH" in upper
    markers = (
        "SERVICE FILE COPY" in upper,
        bool(has_invoice),
        "REYNOLDS AND REYNOLDS" in upper,
        has_job and "CLAIM #" in upper,
        has_job and "VERIFIED THE CUSTOMER" in upper,
        has_job and bool(re.search(r"J#\s*\d+", upper)),
    )
    return sum(markers) >= 2


def _is_table_noise(line: str) -> bool:
    upper = line.upper().strip()
    if not upper or len(upper) < 4:
        return True
    if upper in {"START", "FINISH", "ACT", "TIME", "LABOR"}:
        return True
    if re.match(r"^(START|FINISH|ACT|TIME)\s+(START|FINISH|ACT|TIME|DESCRIPTION)?", upper):
        return True
    noise = (
        "FP-NUMBER",
        "U/COST",
        "E/COST",
        "U/PRICE",
        "QTY--",
        "OVERRIDE IN INVOICING",
        "TECH#",
        "PAGE ",
        "SERVICE FILE COPY",
        "REYNOLDS",
        "SHOP SUPPLIES",
        "FLORIDA REQUIRES",
        "ALL PARTS NEW",
        "COST TOTAL",
        "TOTAL - PARTS",
        "TOTAL TECH TIME",
        "HOURS:",
        "TIME DESCRIPTION",
        "CSTM",
        "AIRBAG SI",
        "FASTENER",
        "LAMP CENT",
        "DOES NOT APPLY",
        "AFTERMARKET PART",
        "WASTE DISPOSAL",
        "LABOR RATE",
        "LICENSE NO",
        "DELIVERY DATE",
        "DELIVERY MILES",
        "SELLING DEALER",
        "PRODUCTION DATE",
        "RESIDENCE PHONE",
        "BUSINESS PHONE",
        "CONTINUED ON NEXT PAGE",
        "INVOICE DATE",
        "INVOICE OATE",
        "VEHICLE LD NO",
        "VEHICLE I.D",
        "YEAR / MAKE / MODEL",
    )
    return any(n in upper for n in noise)


_BOILERPLATE_PHRASES = (
    r"2\s+YEARS\s+AND\s+UNLIMITED\s+MILES[^\.\n]*",
    r"CHRYSLER\s+PARTS\s+AND\s+LABOR[^\.\n]*",
    r"VEHICLE\s+IDENTIFICATION\s+NUMBER\s+STATUS\s+INQUIRY[^\.\n]*",
    r"CHRYSLER\s*\(FCA[^\.\n]*",
    r"STELLANTIS[^\.\n]*",
    r"IS\s+RECALLING\s+CERTAIN[^\.\n]*",
    r"THE\s+RIGHT\s+AND\s+LEFT\s+SIDE\s+CURTAIN\s+AIR\s+BAG[^\.\n]*",
    r"INFLATORS\s+MAY[^\.\n]*",
    r"WASTE\s+DISPOSAL[^\.\n]*",
    r"DISPOSAL[^\.\n]*",
    r"FOR\s+MISCELLANEOUS[^\.\n]*",
    r"SHOP\s+SUPPLIES[^\.\n]*",
    r"MISCELLANEOUS\s+SHOP\s+SUPPLIES[^\.\n]*",
    r"PAGE\s+\d+\s*OF\s*\d+",
    r"SERVICE\s+FILE\s+COPY",
    r"STATE\s+LAW[^\.\n]*",
    r"WRITTEN\s+ESTIMATE",
)


def _strip_boilerplate(text: str) -> str:
    cleaned = text
    for pat in _BOILERPLATE_PHRASES:
        cleaned = re.sub(pat, " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\bCSTM[A-Z0-9\-]+\b[^A-Z]*(?:\d+\.\d{2}\s*)+", " ", cleaned, flags=re.I)
    cleaned = re.sub(r"\b\d{6,8}\s+\d+\.\d{2}\s+\d+\.\d{2}\s+\d+\.\d{2}", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _split_narrative(narrative: str) -> tuple[str, str, str]:
    text = _strip_boilerplate(re.sub(r"\s+", " ", narrative).strip())
    if not text:
        return "", "", ""

    concern = ""
    cause = ""
    correction = ""

    concern_m = re.search(
        r"(CUSTOMER STATES.+?)"
        r"(?=\s+(?:VERIFIED|PERFORMED A VISUAL|PERFORMED A COMPLETE|CAMPAIGN NUMBER|DRAINED THE|FURTHER EXAMINATION|INSPECTED THE|ACCESSED,|ACCESSED AND|ACCESSED THE))",
        text,
        re.I,
    )
    if concern_m:
        concern = concern_m.group(1).strip(" .")
    elif text.upper().startswith("CUSTOMER STATES"):
        concern = re.split(
            r"(?=\s+(?:VERIFIED|PERFORMED|CAMPAIGN|DRAINED|FURTHER|INSPECTED|ACCESSED))",
            text,
            maxsplit=1,
            flags=re.I,
        )[0].strip(" .")
    else:
        pre_m = re.search(
            r"^(.+?)(?=\s+(?:VERIFIED|PERFORMED A VISUAL|PERFORMED A COMPLETE|CAMPAIGN NUMBER|DRAINED THE|FURTHER EXAMINATION|INSPECTED THE))",
            text,
            re.I,
        )
        if pre_m:
            concern = pre_m.group(1).strip(" .")

    if concern.upper().endswith("REPLACE BACK UP"):
        concern = f"{concern} CAMERA"
    concern = re.sub(r"\s+\d+\.\d{2}\s*$", "", concern).strip(" .")

    cause_m = re.search(
        r"((?:VERIFIED|PERFORMED A VISUAL|PERFORMED A COMPLETE|CAMPAIGN NUMBER|FURTHER EXAMINATION FOUND|INSPECTED THE|ACCESSED THE DIAGNOSTIC).+?)"
        r"(?=\s+(?:ACCESSED,\s|ACCESSED AND REMOVED|ACCESSED AND REPLACED|DRAINED THE|REPLACED THE|CLEARED ALL))",
        text,
        re.I,
    )
    if cause_m:
        cause = _strip_boilerplate(cause_m.group(1)).strip(" .")
        cause = re.split(
            r"\b(?:PAGE\s+\S+|CONTINUED ON NEXT PAGE|SHOP SUPPLIES|ALL PARTS NEW|REYNOLDS|INVOICE NO|ADVISOR:)\b",
            cause,
            maxsplit=1,
            flags=re.I,
        )[0].strip(" .")

    correction_m = re.search(
        r"((?:ACCESSED,\s|ACCESSED AND REMOVED|ACCESSED AND REPLACED|DRAINED THE|REPLACED THE|CLEARED ALL).+?"
        r"(?:OPERATING AS DESIGNED|AS DESIGNED\.?|SYSTEM IS NOW OPERATING AS DESIGNED))",
        text,
        re.I,
    )
    if correction_m:
        correction = correction_m.group(1).strip(" .")
    else:
        tail_m = re.search(
            r"((?:ACCESSED,\s|ACCESSED AND REMOVED|ACCESSED AND REPLACED|DRAINED THE|REPLACED THE|CLEARED ALL).+)$",
            text,
            re.I,
        )
        if tail_m:
            correction = tail_m.group(1).strip(" .")

    if not concern and text:
        concern = text[:280].strip(" .")
    return concern, cause, correction


def _extract_narrative_from_block(block: str) -> str:
    """Pull the warranty narrative immediately preceding a CLAIM # marker."""
    tail = block[-2800:]
    matches = list(re.finditer(r"CUSTOMER STATES", tail, re.I))
    if not matches:
        lines = []
        for line in tail.splitlines():
            line = line.strip()
            if _is_table_noise(line):
                continue
            if re.match(r"^[\d\.\s\$]+$", line):
                continue
            if re.match(r"^J#\s*\d+", line, re.I):
                continue
            if re.match(r"^JOBH?\s*\d+", line, re.I):
                continue
            if len(line) < 12:
                continue
            if line.isupper() or "CUSTOMER STATES" in line.upper():
                lines.append(line)
        return _strip_boilerplate(re.sub(r"\s+", " ", " ".join(lines)).strip())

    start = matches[-1].start()
    narrative = tail[start:]
    narrative = re.split(r"\bCLAIM\s*#", narrative, maxsplit=1, flags=re.I)[0]
    return _strip_boilerplate(re.sub(r"\s+", " ", narrative).strip())


def _collect_invoice_op_codes(text: str) -> dict[int, str]:
    codes: dict[int, str] = {}
    patterns = (
        r"J#\s*(\d+)\s+([A-Z0-9+\-]+)",
        r"[Jj]J?\#?\s*(\d+)\+?([A-Z0-9+\-]{4,})",
    )
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            job_no = int(m.group(1))
            op_code = re.sub(r"[^A-Z0-9+\-]", "", m.group(2).upper())
            if op_code and len(op_code) >= 4:
                codes[job_no] = op_code
    return codes


def _extract_narrative_from_labor_section(body: str) -> str:
    lines = []
    for line in body.splitlines():
        line = line.strip()
        if _is_table_noise(line):
            continue
        if re.match(r"^Added Operation", line, re.I):
            continue
        if re.match(r"^ELECTRICAL\b", line, re.I):
            continue
        if re.match(r"^TECH\(S\)", line, re.I):
            continue
        if re.match(r"^[Jj]J?#", line, re.I):
            continue
        if re.match(r"^JOBH?\#?\s*\d+", line, re.I):
            continue
        if re.match(r"^LABOR[-\s]*$", line, re.I):
            continue
        if re.match(r"^[\d\.\s\$]+$", line):
            continue
        if len(line) < 8:
            continue
        lines.append(line)
    return _strip_boilerplate(re.sub(r"\s+", " ", " ".join(lines)).strip())


def _parse_invoice_labor_sections(text: str) -> list[ParsedJob]:
    """Parse Reynolds customer-copy invoices using JOB# / J# labor sections."""
    jobs: list[ParsedJob] = []
    op_code_map = _collect_invoice_op_codes(text)

    section_starts = list(re.finditer(r"JOBH?\#?\s*(\d+)\s*CHARGES", text, re.I))
    if not section_starts:
        return jobs

    for idx, sec in enumerate(section_starts):
        job_no = int(sec.group(1))
        start = sec.start()
        end = section_starts[idx + 1].start() if idx + 1 < len(section_starts) else len(text)
        segment = text[start:end]

        op_code = op_code_map.get(job_no, "")
        jm = re.search(r"[Jj]J?\#?\s*(\d+)\+?([A-Z0-9+\-]{4,})", segment, re.I)
        if jm and int(jm.group(1)) == job_no:
            op_code = re.sub(r"[^A-Z0-9+\-]", "", jm.group(2).upper())

        body = segment[jm.end():] if jm else segment
        body = re.split(r"PARTS[-\s]+(?:QTY|---)", body, maxsplit=1, flags=re.I)[0]
        body = re.split(r"JOBH?\#?\s*\d+\s*TOTALS", body, maxsplit=1, flags=re.I)[0]

        narrative = _extract_narrative_from_labor_section(body)
        if len(narrative) < 25:
            continue

        concern, cause, correction = _split_narrative(narrative)
        if not cause and not correction:
            continue

        labor_m = re.search(r"LABOR\s+([\d,\.]+)", segment, re.I)
        tech_time = 0.0
        if labor_m:
            try:
                labor_val = float(labor_m.group(1).replace(",", ""))
                if 0 < labor_val <= 20:
                    tech_time = labor_val
            except ValueError:
                tech_time = 0.0

        time_m = re.search(r"TOTAL TECH TIME\s+([\d\.]+)", segment, re.I)
        if time_m:
            try:
                tech_time = float(time_m.group(1))
            except ValueError:
                pass

        desc = concern[:80] if concern else narrative[:80]
        jobs.append(
            ParsedJob(
                job_no=job_no,
                pay_type="warranty",
                operation_code=op_code,
                description=desc,
                concern=concern,
                cause=cause,
                correction=correction,
                tech_flagged_time=tech_time,
                claim_value=tech_time,
            )
        )

    deduped: dict[int, ParsedJob] = {}
    for job in jobs:
        if job.job_no in deduped:
            existing = deduped[job.job_no]
            score = len(job.concern) + len(job.cause) + len(job.correction)
            prev = len(existing.concern) + len(existing.cause) + len(existing.correction)
            if score > prev:
                deduped[job.job_no] = job
        else:
            deduped[job.job_no] = job
    return sorted(deduped.values(), key=lambda j: j.job_no)


def _parse_invoice_job_blocks(text: str) -> list[ParsedJob]:
    """Parse Reynolds-style service invoice warranty jobs (CLAIM # sections)."""
    jobs: list[ParsedJob] = []
    op_code_map = _collect_invoice_op_codes(text)

    claim_splits = list(re.finditer(r"CLAIM\s*#\s*(\d+)", text, re.I))
    if not claim_splits:
        return jobs

    for idx, claim_m in enumerate(claim_splits):
        start = claim_m.start()
        if idx == 0:
            block_start = max(0, start - 3500)
        else:
            block_start = claim_splits[idx - 1].end()
        segment = text[block_start:start]

        job_no = idx + 1
        op_code = ""

        j_matches = list(re.finditer(r"J#\s*(\d+)\s+([A-Z0-9+\-]+)", segment, re.I))
        if j_matches:
            job_no = int(j_matches[-1].group(1))
            op_code = re.sub(r"[^A-Z0-9+\-]", "", j_matches[-1].group(2).upper())

        jobh_matches = list(re.finditer(r"JOBH?\s*(\d+)\s*((?:TOTALS|CHARGES)|LABOR)", segment, re.I))
        if jobh_matches:
            job_no = int(jobh_matches[-1].group(1))

        if not op_code and job_no in op_code_map:
            op_code = op_code_map[job_no]

        narrative = _extract_narrative_from_block(segment)
        if len(narrative) < 20:
            continue

        concern, cause, correction = _split_narrative(narrative)

        time_m = re.search(r"TOTAL TECH TIME\s+([\d\.]+)", segment, re.I)
        tech_time = float(time_m.group(1)) if time_m else 0.0

        desc = concern[:80] if concern else narrative[:80]
        jobs.append(
            ParsedJob(
                job_no=job_no,
                pay_type="warranty",
                operation_code=op_code,
                description=desc,
                concern=concern,
                cause=cause,
                correction=correction,
                tech_flagged_time=tech_time,
            )
        )

    deduped: dict[int, ParsedJob] = {}
    for job in jobs:
        if job.job_no in deduped:
            existing = deduped[job.job_no]
            if len(job.concern) + len(job.cause) + len(job.correction) > len(existing.concern) + len(existing.cause) + len(existing.correction):
                deduped[job.job_no] = job
        else:
            deduped[job.job_no] = job
    return sorted(deduped.values(), key=lambda j: j.job_no)


def parse_service_invoice(text: str) -> ParsedRepairOrder:
    text = _normalize_text(text)
    result = ParsedRepairOrder(raw_text=text, document_type="invoice")
    result.ro_number = _extract_ro_number(text)
    result.vin = _extract_vin(text)
    result.mileage = _extract_mileage(text)
    result.advisor = _extract_advisor(text)
    result.technician = _extract_technician(text)
    result.customer_name = _extract_customer_name(text)
    result.ro_invoiced, result.day_received = _extract_dates(text)

    result.jobs = _parse_invoice_job_blocks(text)
    if not result.jobs:
        result.jobs = _parse_invoice_labor_sections(text)
    result.warranty_jobs = list(result.jobs)

    if not result.ro_number:
        result.warnings.append("RO / invoice number was not detected — please verify.")
    if not result.vin:
        result.warnings.append("VIN was not detected — please enter manually.")
    if not result.warranty_jobs:
        result.warnings.append(
            "No warranty job narratives were found on this invoice. "
            "Try the service file copy or customer invoice PDF from Reynolds/DMS."
        )
    else:
        result.warnings.insert(
            0,
            f"Parsed {len(result.warranty_jobs)} warranty job narrative(s) from service invoice.",
        )
    return result


# --- Legacy repair order parser (customer copy — header fields only) ---

def _parse_pay_token(token: str) -> tuple[PayType, bool]:
    raw = (token or "").strip().upper()
    is_add_on = raw in {"W+", "W +"} or (raw.startswith("W") and "+" in raw)
    clean = raw.replace("+", "").strip()
    if clean in {"W", "WR", "WTY", "WARRANTY"}:
        return "warranty", is_add_on
    if clean in {"C", "CP"}:
        return "customer", False
    if clean in {"I", "*"}:
        return "internal", False
    return "unknown", is_add_on


def _map_pay_type(token: str) -> PayType:
    pay_type, _ = _parse_pay_token(token)
    return pay_type


def _norm_op_code(op: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (op or "").upper())


def _parse_job_line(line: str) -> Optional[ParsedJob]:
    line = line.strip()
    patterns = [
        re.compile(
            r"^(\d+)\s*\|\s*(W\+?|WARRANTY|[WCI\*])\s*_?\s*([A-Z0-9\-!]{4,24})\s+(.+?)(?:\s+\d+\.\d{2})?$",
            re.I,
        ),
        re.compile(
            r"^(\d+)\s*\|\s*(W\+?|WARRANTY|[WCI\*])\s+([A-Z0-9\-!]{4,24})\s+(.+?)(?:\s+\d+\.\d{2})?$",
            re.I,
        ),
    ]
    for pat in patterns:
        m = pat.match(line)
        if not m:
            continue
        job_no = int(m.group(1))
        pay_token = m.group(2)
        pay_type, is_add_on = _parse_pay_token(pay_token)
        op = m.group(3).upper().replace(" ", "")
        desc = re.sub(r"\s+", " ", m.group(4)).strip(" .-|")
        desc = re.split(r"CUSTOMER STATES:|PLEASE ADVISE|SIGNATURE", desc, maxsplit=1, flags=re.I)[0].strip()
        if len(desc) < 3:
            continue
        return ParsedJob(
            job_no=job_no,
            pay_type=pay_type,
            operation_code=op,
            description=desc,
            warranty_add_on=is_add_on,
        )
    return None


def _parse_repair_order_warranty_jobs(text: str) -> list[ParsedJob]:
    jobs: list[ParsedJob] = []
    patterns = (
        (r"(?:^|\n)\s*[xX]?\s*(W\+|W\s*\+)\s+([A-Z0-9]{4,12})\b", True),
        (r"(?:^|\n)\s*[xX]?\s*WARRANTY\s+([A-Z0-9]{4,12})\b", False),
        (r"(?:^|\n)\s*[xX]?\s*W\s+([A-Z0-9]{4,12})\b", False),
    )
    w_matches: list[tuple[bool, re.Match[str]]] = []
    for pat, is_add_on in patterns:
        for m in re.finditer(pat, text, re.I):
            w_matches.append((is_add_on, m))

    if not w_matches:
        return jobs

    cs_m = re.search(
        r"CUSTOMER STATES\s+(.+?)(?=METHOD OF|PAGE\s+\d|ORIGINAL CUSTOMER|SIGNED|PLEASE READ|\Z)",
        text,
        re.I | re.S,
    )
    concern = re.sub(r"\s+", " ", cs_m.group(1)).strip(" .") if cs_m else ""

    seen_ops: set[str] = set()
    job_no = 0
    for is_add_on, wm in w_matches:
        op_code = wm.group(wm.lastindex).upper()
        op_key = _norm_op_code(op_code)
        if op_key in seen_ops:
            continue
        seen_ops.add(op_key)
        job_no += 1
        desc = concern[:80] if concern else ""
        if not desc:
            after = text[wm.end(): wm.end() + 120]
            line_m = re.search(r"^[\s\n]*(.+?)(?:\n|$)", after)
            if line_m:
                desc = line_m.group(1).strip(" .")[:80]

        jobs.append(
            ParsedJob(
                job_no=job_no,
                pay_type="warranty",
                operation_code=op_code,
                description=desc,
                concern=concern or desc,
                warranty_add_on=is_add_on,
            )
        )
    return jobs


def parse_repair_order(text: str) -> ParsedRepairOrder:
    """Parse customer-copy repair order — header fields and W-job concern lines."""
    text = _normalize_text(text)
    result = ParsedRepairOrder(raw_text=text, document_type="repair_order")
    result.ro_number = _extract_ro_number(text)
    result.vin = _extract_vin(text)
    result.mileage = _extract_mileage(text)
    result.advisor = _extract_advisor(text)
    result.technician = _extract_technician(text)
    result.customer_name = _extract_customer_name(text)
    result.ro_invoiced, result.day_received = _extract_dates(text)

    jobs: list[ParsedJob] = []
    for line in text.splitlines():
        if not re.match(r"^\s*\d+\s*\|", line):
            continue
        job = _parse_job_line(line)
        if job:
            jobs.append(job)

    if not jobs:
        jobs = _parse_repair_order_warranty_jobs(text)

    deduped: dict[int, ParsedJob] = {}
    for job in jobs:
        deduped[job.job_no] = job
    result.jobs = list(deduped.values())
    result.warranty_jobs = [j for j in result.jobs if j.pay_type == "warranty"]

    if result.warranty_jobs and not any(j.cause or j.correction for j in result.warranty_jobs):
        result.warnings.append(
            "Warranty job concern imported from repair order. "
            "Upload the invoice PDF for cause/correction narratives."
        )
    elif not result.warranty_jobs:
        result.warnings.append(
            "This looks like a customer repair order. "
            "Upload the invoice PDF for full concern/cause/correction narratives."
        )
    if not result.ro_number:
        result.warnings.append("RO number was not detected — please verify.")
    return result


def parse_document(text: str) -> ParsedRepairOrder:
    if _is_service_invoice(text):
        return parse_service_invoice(text)
    return parse_repair_order(text)


def _infer_job_flags(job: ParsedJob) -> dict[str, bool]:
    blob = " ".join([job.concern, job.cause, job.correction, job.description, job.operation_code]).upper()
    return {
        "oil_leak": ("OIL" in blob and ("LEAK" in blob or "LEAKING" in blob)),
        "battery_replacement": bool(re.search(r"\bBATT\b|BATTERY", blob)),
        "ac_repair": bool(re.search(r"\bA/C\b|AC REPAIR|EVAC|RECHARGE", blob)),
        "parts_warranty": bool(re.search(r"PARTS WARRANTY|MOPAR|MOPA", blob)),
        "sublet_repair": "SUBLET" in blob,
        "rental_involved": bool(re.search(r"LOANER|RENTAL", blob)),
        "warranty_add_on": bool(re.search(r"ADD-ON|ADD ON", blob)),
    }


def _job_to_form_dict(job: ParsedJob) -> dict:
    flags = _infer_job_flags(job)
    return {
        "job_no": job.job_no,
        "concern": job.concern or job.description,
        "cause": job.cause,
        "correction": job.correction,
        "operation_code": job.operation_code,
        "pay_type": job.pay_type,
        "tech_flagged_time": job.tech_flagged_time,
        "time_allotted": job.tech_flagged_time,
        "claim_value": job.claim_value,
        "warranty_add_on": job.warranty_add_on or flags.get("warranty_add_on", False),
        **{k: v for k, v in flags.items() if k != "warranty_add_on"},
    }


def scan_repair_order_pdf(
    source: Union[bytes, BinaryIO],
    *,
    force_ocr: bool = False,
    document_kind: str = "auto",
) -> ParsedRepairOrder:
    text, ocr_used = extract_ro_text(source, force_ocr=force_ocr)
    if document_kind == "repair_order":
        parsed = parse_repair_order(text)
    elif document_kind == "invoice":
        parsed = parse_service_invoice(text)
    else:
        parsed = parse_document(text)
    parsed.ocr_used = ocr_used
    if ocr_used:
        parsed.warnings.insert(0, "Scanned PDF processed with OCR — please verify all imported fields.")
    return parsed


def _merge_job_dicts(ro_job: dict, invoice_job: dict) -> dict:
    merged = dict(ro_job)
    for key, value in invoice_job.items():
        if value not in (None, "", 0, 0.0, False):
            merged[key] = value

    ro_concern = (ro_job.get("concern") or "").strip()
    inv_concern = (invoice_job.get("concern") or "").strip()
    if ro_concern.upper().startswith("CUSTOMER STATES") or len(ro_concern) > len(inv_concern):
        merged["concern"] = ro_concern
    elif inv_concern:
        merged["concern"] = inv_concern

    merged["warranty_add_on"] = bool(ro_job.get("warranty_add_on") or invoice_job.get("warranty_add_on"))
    merged["job_no"] = invoice_job.get("job_no") or ro_job.get("job_no")
    merged["operation_code"] = invoice_job.get("operation_code") or ro_job.get("operation_code")
    return merged


def merge_form_imports(ro_import: dict | None, invoice_import: dict | None) -> dict:
    """Combine repair order header/concern with invoice narratives."""
    ro_import = ro_import or {}
    invoice_import = invoice_import or {}

    header_fields = (
        "ro_number",
        "vin",
        "mileage",
        "advisor",
        "technician",
        "customer_name",
        "ro_invoiced",
        "day_submitted",
    )
    merged: dict = {
        "warnings": [],
        "ocr_used": bool(ro_import.get("ocr_used") or invoice_import.get("ocr_used")),
        "document_type": "merged",
    }
    for field in header_fields:
        merged[field] = invoice_import.get(field) or ro_import.get(field)

    ro_jobs = ro_import.get("jobs") or []
    inv_jobs = invoice_import.get("jobs") or []
    inv_by_op = {_norm_op_code(j.get("operation_code")): j for j in inv_jobs if j.get("operation_code")}
    used_inv_ids: set[int] = set()
    merged_jobs: list[dict] = []

    for ro_job in ro_jobs:
        inv_job = inv_by_op.get(_norm_op_code(ro_job.get("operation_code")))
        if not inv_job and len(ro_jobs) == 1 and len(inv_jobs) == 1:
            inv_job = inv_jobs[0]
        if inv_job:
            used_inv_ids.add(id(inv_job))
            merged_jobs.append(_merge_job_dicts(ro_job, inv_job))
        else:
            merged_jobs.append(dict(ro_job))

    for inv_job in inv_jobs:
        if id(inv_job) not in used_inv_ids:
            merged_jobs.append(dict(inv_job))

    if not merged_jobs:
        merged_jobs = inv_jobs or ro_jobs

    merged["jobs"] = merged_jobs
    merged["job_count"] = max(len(merged_jobs), 1) if merged_jobs else 1
    merged["warnings"] = list(ro_import.get("warnings") or []) + list(invoice_import.get("warnings") or [])
    if ro_jobs and inv_jobs:
        merged["warnings"].insert(
            0,
            f"Merged {len(ro_jobs)} repair order job(s) with {len(inv_jobs)} invoice job narrative(s).",
        )
    return merged


def parsed_to_form_import(parsed: ParsedRepairOrder) -> dict:
    """Map parsed document into Review tab defaults (warranty jobs from invoice)."""
    jobs = [_job_to_form_dict(job) for job in (parsed.warranty_jobs or [])]
    return {
        "ro_number": parsed.ro_number,
        "vin": parsed.vin,
        "mileage": parsed.mileage,
        "advisor": parsed.advisor,
        "technician": parsed.technician,
        "customer_name": parsed.customer_name,
        "ro_invoiced": parsed.ro_invoiced,
        "day_submitted": parsed.day_received or parsed.ro_invoiced,
        "document_type": parsed.document_type,
        "job_count": max(len(jobs), 1) if jobs else 1,
        "jobs": jobs,
        "warnings": parsed.warnings,
        "ocr_used": parsed.ocr_used,
        "detected_jobs": [
            {
                "job_no": j.job_no,
                "pay_type": j.pay_type,
                "operation_code": j.operation_code,
                "concern": (j.concern or j.description)[:60],
            }
            for j in parsed.jobs
        ],
    }
