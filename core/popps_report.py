"""Parse and display Dealer POPPS (Performance Overview & Potential Problem Summary) PDFs."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd
import streamlit as st

try:
    from PyPDF2 import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

MONTH_LABELS = ("March", "April", "May")

CONCERN_CODE_DESCRIPTIONS: dict[str, str] = {
    "1": "High frequency of repair conditions per vehicle serviced",
    "2": "High frequency of repair conditions on low mileage and/or in-stock vehicles",
    "3": "High parts cost per repair condition",
    "4": "High labor cost per repair condition",
    "5": "High frequency of message code occurrences",
    "6": "High frequency of Actual Time or Operation Diagnostics usage",
    "7": "High hours per repair for Actual Time or Operation Diagnostics",
    "8": "High frequency of repair conditions per vehicle serviced (Goodwill)",
    "9": "High total cost per repair condition",
}

CONCERN_TYPE_LABELS = {
    "Labor": "Labor cost concern",
    "Parts": "Parts cost concern",
    "Frequency": "Repair frequency concern",
    "N/A": "Not applicable",
}

STANDARD_CLAIM_LINE = re.compile(
    r"^(?P<vehicle_id>\S+)\s+(?P<vehicle_number>\S+)\s+"
    r"(?P<claim_condition>\d{6}-\S+)\s+(?P<labor_operation>\S+)\s+"
    r"(?P<technician_id>\d+)\s+(?P<mileage>[\d,]+)\s+"
    r"(?:(?P<authorization_flag>\S+)\s+)?"
    r"(?P<expense>[\d,]+\.?\d*)\s+(?P<concern_codes>.+)$"
)

MESSAGE_CLAIM_LINE = re.compile(
    r"^(?:(?P<fleet_marker>X)\s+)?(?P<vehicle_id>\S+)\s+(?P<vehicle_number>\S+)\s+"
    r"(?P<claim_number>\d{6})\s+(?P<message_code>\S+)\s+(?P<authorization_id>\S+)\s+"
    r"(?P<technician_id>\d+)\s+(?P<mileage>[\d,]+)\s+"
    r"(?P<expense>[\d,]+\.?\d*)\s+(?P<days_to_process>\d+)\s+(?P<concern_codes>.+)$"
)

CAP_HEADER_LINE = re.compile(
    r"^(?P<priority>\d+)\s+"
    r"(?P<labor_operation>\d{4})\s+"
    r"-(?P<repair_group>.+?)\s+"
    r"(?P<quarters>\d+)\s+(?P<total_conditions>\d+)\s+"
    r"(?P<concern_codes>[\d,\s#]+)\s+"
    r"(?P<march>\d+)\s+(?P<april>\d+)\s+(?P<may>\d+)\s*$",
    re.IGNORECASE,
)

MSG_CAP_HEADER_LINE = re.compile(
    r"^(?P<priority>MSG\s+CODE)\s+"
    r"(?P<repair_group>.+?)\s+"
    r"(?P<quarters>\d+)\s+(?P<total_conditions>\d+)\s+"
    r"(?P<concern_codes>[\d,\s#]+)\s+"
    r"(?P<march>\d+)\s+(?P<april>\d+)\s+(?P<may>\d+)\s*$",
    re.IGNORECASE,
)

EW_HEADER_LINE = re.compile(
    r"^EW\s+(?P<labor_operation>\d{4})\s+"
    r"-(?P<repair_group>.+?)\s+"
    r"(?P<total_conditions>\d+)\s+"
    r"(?P<march_pct>[\d.]+)\s+(?P<april_pct>[\d.]+)\s+"
    r"(?P<concern_type>\w+)",
    re.IGNORECASE,
)


@dataclass
class PoppsClaimRow:
    vehicle_identification: str
    vehicle_number: str
    claim_condition_or_number: str
    labor_operation_or_message_code: str
    technician_id: str
    mileage: str
    expense_amount: str
    concern_codes_raw: str
    concern_codes_plain: str
    authorization_flag: str = ""
    labor_hours: str = ""
    days_to_process: str = ""
    fleet_vehicle: str = ""
    row_type: str = "repair"  # repair | message


@dataclass
class PoppsPrioritySection:
    priority_rank: str
    priority_label: str
    labor_operation_code: str
    repair_description: str
    quarters_on_popps: str
    total_conditions: str
    concern_codes_raw: str
    concern_codes_plain: str
    group_march: str = ""
    group_april: str = ""
    group_may: str = ""
    detail_lines: list[str] = field(default_factory=list)
    claims: list[PoppsClaimRow] = field(default_factory=list)
    no_claims_message: str = ""


@dataclass
class PoppsSummaryRow:
    rank_label: str
    labor_operation_code: str
    repair_description: str
    total_conditions: str
    march_percent: str
    april_percent: str
    may_percent: str
    concern_type: str
    march_group_value: str
    april_group_value: str
    may_group_value: str
    may_expense: str = ""
    is_early_warning: bool = False


@dataclass
class PoppsDazeSummary:
    dealership_march: str = ""
    dealership_april: str = ""
    dealership_may: str = ""
    business_center_march: str = ""
    business_center_april: str = ""
    business_center_may: str = ""
    expense_march: str = ""
    expense_april: str = ""
    expense_may: str = ""


@dataclass
class PoppsCustomerCareRow:
    metric_name: str
    march_value: str = ""
    april_value: str = ""
    may_value: str = ""
    notes: str = ""


@dataclass
class PoppsReport:
    report_title: str = "Dealer POPPS Management Report"
    period_label: str = ""
    dealer_code: str = ""
    dealer_name: str = ""
    raw_text: str = ""
    parse_warnings: list[str] = field(default_factory=list)
    daze: PoppsDazeSummary = field(default_factory=PoppsDazeSummary)
    top_problems: list[PoppsSummaryRow] = field(default_factory=list)
    early_warning: list[PoppsSummaryRow] = field(default_factory=list)
    customer_care: list[PoppsCustomerCareRow] = field(default_factory=list)
    priority_sections: list[PoppsPrioritySection] = field(default_factory=list)


def expand_concern_codes(raw: str) -> str:
    """Turn numeric concern codes into full DWIN descriptions."""
    text = str(raw or "").strip().replace("#", " ").strip()
    if not text:
        return "—"
    parts = re.split(r"[\s,]+", text)
    expanded: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.isdigit() and part in CONCERN_CODE_DESCRIPTIONS:
            expanded.append(f"{part} — {CONCERN_CODE_DESCRIPTIONS[part]}")
        else:
            expanded.append(part)
    return "; ".join(expanded) if expanded else text


def expand_concern_type(raw: str) -> str:
    key = str(raw or "").strip()
    return CONCERN_TYPE_LABELS.get(key, key or "—")


def _normalize_popps_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = text.replace("—", "-").replace("–", "-")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    if PdfReader is None:
        raise RuntimeError("PyPDF2 is required to read POPPS PDFs.")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    chunks = [page.extract_text() or "" for page in reader.pages]
    return _normalize_popps_text("\n".join(chunks))


def _parse_money(value: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned or cleaned.upper() == "N/A":
        return cleaned or "—"
    if cleaned.startswith("$"):
        return cleaned
    if re.match(r"^[\d,]+\.?\d*$", cleaned):
        return f"${cleaned}"
    return cleaned


def _parse_claim_line(line: str) -> PoppsClaimRow | None:
    line = line.strip()
    if not line or line.lower().startswith("no potential problem"):
        return None

    match = STANDARD_CLAIM_LINE.match(line)
    if match:
        groups = match.groupdict()
        concerns = groups.get("concern_codes") or ""
        return PoppsClaimRow(
            vehicle_identification=groups["vehicle_id"],
            vehicle_number=groups["vehicle_number"],
            claim_condition_or_number=groups["claim_condition"],
            labor_operation_or_message_code=groups["labor_operation"],
            technician_id=groups["technician_id"],
            mileage=groups["mileage"],
            authorization_flag=groups.get("authorization_flag") or "",
            expense_amount=_parse_money(groups["expense"]),
            concern_codes_raw=concerns.strip(),
            concern_codes_plain=expand_concern_codes(concerns),
            row_type="repair",
        )

    match = MESSAGE_CLAIM_LINE.match(line)
    if match:
        groups = match.groupdict()
        concerns = groups.get("concern_codes") or ""
        return PoppsClaimRow(
            fleet_vehicle="Yes" if groups.get("fleet_marker") else "No",
            vehicle_identification=groups["vehicle_id"],
            vehicle_number=groups["vehicle_number"],
            claim_condition_or_number=groups["claim_number"],
            labor_operation_or_message_code=groups["message_code"],
            technician_id=groups["technician_id"],
            mileage=groups["mileage"],
            authorization_flag=groups.get("authorization_id") or "",
            expense_amount=_parse_money(groups["expense"]),
            days_to_process=groups.get("days_to_process") or "",
            concern_codes_raw=concerns.strip(),
            concern_codes_plain=expand_concern_codes(concerns),
            row_type="message",
        )
    return None


def _parse_header(text: str, report: PoppsReport) -> None:
    period = re.search(
        r"([A-Za-z]+),\s*(\d{4})\s*-\s*(Interim Report|Final Report)",
        text,
        re.IGNORECASE,
    )
    if period:
        report.period_label = f"{period.group(1)} {period.group(2)} — {period.group(3)}"

    dealer = re.search(
        r"Dealer:\s*(\d+)\s*-\s*(.+?)\s*-\s*Warranty",
        text,
        re.IGNORECASE,
    )
    if dealer:
        report.dealer_code = dealer.group(1).strip()
        report.dealer_name = dealer.group(2).strip()


def _parse_daze(text: str, report: PoppsReport) -> None:
    daze = report.daze
    dealer = re.search(
        r"Dealership DAZE:\s*([\d.]+)%\s*([\d.]+)%\s*([\d.]+)%",
        text,
        re.IGNORECASE,
    )
    if dealer:
        daze.dealership_march = f"{dealer.group(1)}%"
        daze.dealership_april = f"{dealer.group(2)}%"
        daze.dealership_may = f"{dealer.group(3)}%"

    center = re.search(
        r"Business Center DAZE:\s*([\d.]+)%\s*([\d.]+)%\s*([\d.]+)%",
        text,
        re.IGNORECASE,
    )
    if center:
        daze.business_center_march = f"{center.group(1)}%"
        daze.business_center_april = f"{center.group(2)}%"
        daze.business_center_may = f"{center.group(3)}%"

    expense = re.search(
        r"DAZE Expense\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)",
        text,
        re.IGNORECASE,
    )
    if expense:
        daze.expense_march = _parse_money(expense.group(1))
        daze.expense_april = _parse_money(expense.group(2))
        daze.expense_may = _parse_money(expense.group(3))


def _parse_summary_line(line: str, *, early_warning: bool = False) -> PoppsSummaryRow | None:
    line = line.strip()
    if not line or line.startswith("TOP ") or line.startswith("---"):
        return None

    ew_match = EW_HEADER_LINE.match(line)
    if ew_match or early_warning:
        if ew_match:
            g = ew_match.groupdict()
            return PoppsSummaryRow(
                rank_label="Early Warning",
                labor_operation_code=g["labor_operation"],
                repair_description=g["repair_group"].strip(),
                total_conditions=g["total_conditions"],
                march_percent=f"{g['march_pct']}%",
                april_percent=f"{g['april_pct']}%",
                may_percent="",
                concern_type=expand_concern_type(g["concern_type"]),
                march_group_value="",
                april_group_value="",
                may_group_value="",
                is_early_warning=True,
            )

    msg_match = re.match(
        r"^MSG CODE\s+(?P<desc>.+?)\s+"
        r"(?P<conds>\d+)\s+"
        r"(?P<ctype>\w+)\s+"
        r"(?P<g1>[\d.N/A]+)\s+(?P<g2>[\d.N/A]+)\s+(?P<g3>[\d.N/A]+)",
        line,
        re.IGNORECASE,
    )
    if msg_match:
        g = msg_match.groupdict()
        return PoppsSummaryRow(
            rank_label="Message Code",
            labor_operation_code="Message Code",
            repair_description=g["desc"].strip(),
            total_conditions=g["conds"],
            march_percent="—",
            april_percent="—",
            may_percent="—",
            concern_type=expand_concern_type(g["ctype"]),
            march_group_value=g["g1"] if g["g1"] != "N/A" else "—",
            april_group_value=g["g2"] if g["g2"] != "N/A" else "—",
            may_group_value=g["g3"] if g["g3"] != "N/A" else "—",
        )

    top_match = re.match(
        r"^(?P<rank>\d+)\s+"
        r"(?P<lop>\d{4})\s+"
        r"-(?P<desc>.+?)\s+"
        r"(?P<conds>\d+)\s+"
        r"(?:(?P<p1>[\d.]+)\s+(?P<p2>[\d.]+)\s+(?P<p3>[\d.]+)|(?P<p_single>[\d.]+))\s+"
        r"(?P<ctype>\w+)\s+"
        r"(?P<g1>[\d.N/A]+)\s+(?P<g2>[\d.N/A]+)\s+(?P<g3>[\d.N/A]+)"
        r"(?:\s+(?P<expense>N/A|[\d,]+))?",
        line,
        re.IGNORECASE,
    )
    if top_match:
        g = top_match.groupdict()
        rank = g["rank"]
        return PoppsSummaryRow(
            rank_label=f"Priority {rank}",
            labor_operation_code=g["lop"],
            repair_description=g["desc"].strip(),
            total_conditions=g["conds"],
            march_percent=(g.get("p1") or g.get("p_single") or "—"),
            april_percent=(g.get("p2") or "—"),
            may_percent=(g.get("p3") or "—"),
            concern_type=expand_concern_type(g["ctype"]),
            march_group_value=g["g1"] if g["g1"] != "N/A" else "—",
            april_group_value=g["g2"] if g["g2"] != "N/A" else "—",
            may_group_value=g["g3"] if g["g3"] != "N/A" else "—",
            may_expense=_parse_money(g.get("expense") or ""),
        )
    return None


def _parse_top_and_early_warning(text: str, report: PoppsReport) -> None:
    if "Quarterly Potential Problem Summary" in text:
        chunk = text.split("Quarterly Potential Problem Summary", 1)[1]
        chunk = chunk.split("Early Warning Indicator:", 1)[0]
        for line in chunk.splitlines():
            row = _parse_summary_line(line)
            if row:
                report.top_problems.append(row)

    if "Early Warning Indicator:" in text:
        chunk = text.split("Early Warning Indicator:", 1)[1]
        chunk = chunk.split("Customer Care Metrics", 1)[0]
        for line in chunk.splitlines():
            row = _parse_summary_line(line, early_warning=True)
            if row:
                report.early_warning.append(row)


def _parse_customer_care(text: str, report: PoppsReport) -> None:
    if "Customer Care Metrics" not in text:
        return
    chunk = text.split("Customer Care Metrics", 1)[1]
    chunk = chunk.split("Technician Applied Skill Comparison", 1)[0]

    patterns = [
        (
            "Repeat Repair Percentage (codes HB4, HB6, and HB7)",
            r"Repeat Repair %\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
        ),
        (
            "Business Center Average Repeat Repair Percentage",
            r"Business Center Avg %\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
        ),
        (
            "Repeat Repair Dollars",
            r"Repeat Repair \$\s+(\$?[\d,]+)\s+(\$?[\d,]+)\s+(\$?[\d,]+)",
        ),
    ]
    for name, pattern in patterns:
        match = re.search(pattern, chunk, re.IGNORECASE)
        if match:
            report.customer_care.append(
                PoppsCustomerCareRow(
                    metric_name=name,
                    march_value=match.group(1),
                    april_value=match.group(2),
                    may_value=match.group(3),
                )
            )

    for block_name in (
        "Diagnostic Time",
        "Goodwill",
        "Special Services (Loaner Vehicles)",
        "Competitive Vehicles",
    ):
        if block_name in chunk:
            report.customer_care.append(
                PoppsCustomerCareRow(
                    metric_name=f"{block_name} — see POPPS PDF for full Business Center comparison",
                    notes="Expense per vehicle serviced, conditions per 100 vehicles, and cost per condition are in the factory report.",
                )
            )


def _parse_priority_sections(text: str, report: PoppsReport) -> None:
    if "Repair Group Summary & Related Claims" not in text:
        return
    chunk = text.split("Repair Group Summary & Related Claims", 1)[1]
    lines = chunk.splitlines()

    current: PoppsPrioritySection | None = None
    detail_buffer: list[str] = []

    def flush_detail() -> None:
        nonlocal detail_buffer, current
        if current is None:
            detail_buffer = []
            return
        for item in detail_buffer:
            if item.startswith("(") and item.endswith(")"):
                current.repair_description = (
                    f"{current.repair_description} {item}".strip()
                )
            else:
                current.detail_lines.append(item)
        detail_buffer = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("FCA US LLC"):
            continue
        if line.startswith("NOTE:") or line.startswith("Claim ") or line.startswith("Fleet "):
            continue
        if line.startswith("---") or "Priority LOP" in line:
            continue

        if line.lower().startswith("no potential problem claims"):
            flush_detail()
            if current and not current.claims:
                current.no_claims_message = line
            continue

        header = CAP_HEADER_LINE.match(line) or MSG_CAP_HEADER_LINE.match(line)
        if header:
            flush_detail()
            if current and (current.claims or current.no_claims_message or current.detail_lines):
                report.priority_sections.append(current)

            g = header.groupdict()
            priority = g["priority"].replace(" ", " ")
            lop = str(g.get("labor_operation") or "Message Code").replace(" ", " ")
            current = PoppsPrioritySection(
                priority_rank=priority,
                priority_label=(
                    f"Claims Analysis Process Priority {priority}"
                    if priority.isdigit()
                    else "Message Code Priority"
                ),
                labor_operation_code=lop,
                repair_description=g["repair_group"].strip(),
                quarters_on_popps=g["quarters"],
                total_conditions=g["total_conditions"],
                concern_codes_raw=g["concern_codes"].strip(),
                concern_codes_plain=expand_concern_codes(g["concern_codes"]),
                group_march=g["march"],
                group_april=g["april"],
                group_may=g["may"],
            )
            continue

        claim = _parse_claim_line(line)
        if claim:
            flush_detail()
            if current:
                current.claims.append(claim)
            continue

        if current and (line.startswith("(") or len(line) < 48):
            detail_buffer.append(line)

    flush_detail()
    if current and (current.claims or current.no_claims_message or current.detail_lines):
        report.priority_sections.append(current)


def parse_popps_pdf(pdf_bytes: bytes) -> PoppsReport:
    """Parse a Dealer POPPS PDF into structured, plain-language sections."""
    text = _extract_pdf_text(pdf_bytes)
    report = PoppsReport(raw_text=text)
    _parse_header(text, report)
    _parse_daze(text, report)
    _parse_top_and_early_warning(text, report)
    _parse_customer_care(text, report)
    _parse_priority_sections(text, report)

    if not report.priority_sections and not report.top_problems:
        report.parse_warnings.append(
            "We could read the PDF but could not match the expected POPPS layout. "
            "Try uploading the full Dealer POPPS Management Report PDF from DealerCONNECT."
        )
    return report


def _claims_dataframe(claims: list[PoppsClaimRow]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for claim in claims:
        if claim.row_type == "message":
            rows.append(
                {
                    "Fleet Vehicle": claim.fleet_vehicle,
                    "Vehicle Identification": claim.vehicle_identification,
                    "Vehicle Number": claim.vehicle_number,
                    "Claim Number": claim.claim_condition_or_number,
                    "Message Code": claim.labor_operation_or_message_code,
                    "Authorization Identifier": claim.authorization_flag,
                    "Technician Identification Number": claim.technician_id,
                    "Mileage": claim.mileage,
                    "Expense Amount": claim.expense_amount,
                    "Days to Process": claim.days_to_process,
                    "Concern Codes (plain language)": claim.concern_codes_plain,
                }
            )
        else:
            rows.append(
                {
                    "Vehicle Identification": claim.vehicle_identification,
                    "Vehicle Number": claim.vehicle_number,
                    "Claim and Condition Number": claim.claim_condition_or_number,
                    "Labor Operation Code": claim.labor_operation_or_message_code,
                    "Technician Identification Number": claim.technician_id,
                    "Mileage": claim.mileage,
                    "Authorization Flag": claim.authorization_flag or "—",
                    "Expense Amount": claim.expense_amount,
                    "Concern Codes (plain language)": claim.concern_codes_plain,
                }
            )
    return pd.DataFrame(rows)


def _summary_dataframe(rows: list[PoppsSummaryRow]) -> pd.DataFrame:
    data = []
    for row in rows:
        data.append(
            {
                "Rank": row.rank_label,
                "Labor Operation Code": row.labor_operation_code,
                "Repair Area Description": row.repair_description,
                "Total Conditions": row.total_conditions,
                f"{MONTH_LABELS[0]} — Percent of Total": row.march_percent,
                f"{MONTH_LABELS[1]} — Percent of Total": row.april_percent,
                f"{MONTH_LABELS[2]} — Percent of Total": row.may_percent,
                "Concern Type": row.concern_type,
                f"{MONTH_LABELS[0]} — Percent of Business Center Group": row.march_group_value,
                f"{MONTH_LABELS[1]} — Percent of Business Center Group": row.april_group_value,
                f"{MONTH_LABELS[2]} — Percent of Business Center Group": row.may_group_value,
            }
        )
    return pd.DataFrame(data)


def popps_page_css(theme: str = "Dark") -> str:
    is_light = str(theme).lower() == "light"
    card_bg = "rgba(244, 248, 252, 0.96)" if is_light else "rgba(7, 19, 34, 0.88)"
    border = "#b6c7da" if is_light else "rgba(62, 150, 255, 0.28)"
    text = "#0f172a" if is_light else "#f8fbff"
    muted = "#475569" if is_light else "#94a3b8"
    return f"""
    .popps-hero {{
        padding: 18px 22px;
        border-radius: 16px;
        background: {card_bg};
        border: 1px solid {border};
        margin-bottom: 16px;
    }}
    .popps-hero h2 {{
        margin: 0 0 6px 0;
        color: {text} !important;
        font-size: 1.35rem !important;
    }}
    .popps-hero p {{
        margin: 0;
        color: {muted} !important;
        line-height: 1.45;
    }}
    .popps-section-title {{
        margin: 1.2rem 0 0.35rem 0;
        color: {text} !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important;
    }}
    """


def render_popps_report(*, theme: str = "Dark") -> None:
    """POPPS upload tab — plain-language breakdown of the factory report."""
    st.markdown(
        '<div class="popps-workspace-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"<style>{popps_page_css(theme)}</style>", unsafe_allow_html=True)

    st.header("POPPS Report")
    st.caption(
        "Upload your Dealer **Performance Overview & Potential Problem Summary (POPPS)** "
        "PDF from DealerCONNECT. RO Guard expands abbreviations into plain language for coaching and review."
    )

    if "popps_upload_nonce" not in st.session_state:
        st.session_state.popps_upload_nonce = 0

    uploaded = st.file_uploader(
        "Upload POPPS report (PDF)",
        type=["pdf"],
        key=f"popps_upload_{st.session_state.popps_upload_nonce}",
        help="Use the monthly Dealer POPPS Management Report PDF (DWIN).",
    )

    if uploaded is not None:
        try:
            report = parse_popps_pdf(uploaded.getvalue())
            st.session_state.popps_parsed_report = report
            st.session_state.popps_upload_name = uploaded.name
            st.success(f"Loaded {uploaded.name}")
        except Exception as exc:
            st.error(f"Could not read that PDF: {exc}")

    if st.button("Clear POPPS report", key="popps_clear_report"):
        st.session_state.pop("popps_parsed_report", None)
        st.session_state.pop("popps_upload_name", None)
        st.session_state.popps_upload_nonce = int(st.session_state.get("popps_upload_nonce", 0)) + 1
        st.rerun()

    report: PoppsReport | None = st.session_state.get("popps_parsed_report")
    if report is None:
        st.info(
            "Upload a POPPS PDF to see dealership DAZE trends, top problem areas, "
            "early warnings, and itemized claims with full concern code descriptions."
        )
        with st.expander("What is POPPS?", expanded=False):
            st.markdown(
                """
                **POPPS** is the factory **Performance Overview & Potential Problem Summary**.
                It highlights repair areas where your dealership exceeds the Business Center group
                for frequency, labor cost, or parts cost — and lists sample claims to review.

                RO Guard re-labels factory shorthand (for example **CAP**, **LOP**, **Conds**)
                so managers and advisors can read the report without memorizing codes.
                """
            )
        return

    file_name = st.session_state.get("popps_upload_name", "POPPS report")
    st.markdown(
        f"""
        <div class="popps-hero">
            <h2>Performance Overview &amp; Potential Problem Summary</h2>
            <p><strong>Dealer:</strong> {report.dealer_code} — {report.dealer_name}<br>
            <strong>Report period:</strong> {report.period_label or "—"}<br>
            <strong>Source file:</strong> {file_name}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for warning in report.parse_warnings:
        st.warning(warning)

    st.markdown('<div class="popps-section-title">Three-month dealership overview</div>', unsafe_allow_html=True)
    st.caption(
        "**DAZE** is the Dealer Average Zone Expense index from DWIN — your dealership compared to "
        "the Business Center group."
    )
    overview = st.columns(3)
    months = MONTH_LABELS
    dealership = [
        report.daze.dealership_march,
        report.daze.dealership_april,
        report.daze.dealership_may,
    ]
    business_center = [
        report.daze.business_center_march,
        report.daze.business_center_april,
        report.daze.business_center_may,
    ]
    expense = [report.daze.expense_march, report.daze.expense_april, report.daze.expense_may]
    for idx, col in enumerate(overview):
        with col:
            st.markdown(f"**{months[idx]}**")
            st.metric("Dealership DAZE Index", dealership[idx] or "—")
            st.metric("Business Center DAZE Index", business_center[idx] or "—")
            st.metric("DAZE Expense", expense[idx] or "—")

    if report.top_problems:
        st.markdown('<div class="popps-section-title">Quarterly top problem summary</div>', unsafe_allow_html=True)
        st.dataframe(_summary_dataframe(report.top_problems), use_container_width=True, hide_index=True)

    if report.early_warning:
        st.markdown('<div class="popps-section-title">Early warning indicators</div>', unsafe_allow_html=True)
        st.caption(
            "Early warning flags a labor operation that escalated quickly during the quarter. "
            "Review matching claims in DealerCONNECT."
        )
        st.dataframe(_summary_dataframe(report.early_warning), use_container_width=True, hide_index=True)

    if report.customer_care:
        st.markdown('<div class="popps-section-title">Customer care metrics (summary)</div>', unsafe_allow_html=True)
        care_rows = []
        for row in report.customer_care:
            if row.march_value or row.april_value or row.may_value:
                care_rows.append(
                    {
                        "Metric": row.metric_name,
                        MONTH_LABELS[0]: row.march_value,
                        MONTH_LABELS[1]: row.april_value,
                        MONTH_LABELS[2]: row.may_value,
                    }
                )
            else:
                care_rows.append({"Metric": row.metric_name, "Notes": row.notes})
        if care_rows:
            st.dataframe(pd.DataFrame(care_rows), use_container_width=True, hide_index=True)

    with st.expander("Concern code reference (plain language)", expanded=False):
        st.dataframe(
            pd.DataFrame(
                [
                    {"Code": code, "Description": description}
                    for code, description in sorted(CONCERN_CODE_DESCRIPTIONS.items())
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    if report.priority_sections:
        st.markdown(
            '<div class="popps-section-title">Repair groups and related claims</div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Each **Claims Analysis Process Priority** lists sample claims RO Guard pulled from the POPPS PDF. "
            "Concern codes are written out in full."
        )
        for section in report.priority_sections:
            title = (
                f"{section.priority_label} — "
                f"Labor Operation {section.labor_operation_code} — "
                f"{section.repair_description}"
            )
            with st.expander(title, expanded=section.priority_rank == "1"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Quarters on POPPS", section.quarters_on_popps or "—")
                c2.metric("Total Conditions", section.total_conditions or "—")
                c3.metric("Group values (Mar / Apr / May)", f"{section.group_march} / {section.group_april} / {section.group_may}")
                st.markdown(f"**Concern codes:** {section.concern_codes_plain}")
                if section.claims:
                    st.dataframe(
                        _claims_dataframe(section.claims),
                        use_container_width=True,
                        hide_index=True,
                    )
                elif section.no_claims_message:
                    st.info(section.no_claims_message)
                else:
                    st.caption("No itemized claims were listed for this priority in the PDF text.")

    with st.expander("View extracted PDF text (troubleshooting)", expanded=False):
        st.text_area(
            "Extracted text",
            value=report.raw_text[:120000],
            height=280,
            label_visibility="collapsed",
        )
