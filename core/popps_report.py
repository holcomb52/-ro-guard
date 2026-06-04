"""Parse and display Dealer POPPS (Performance Overview & Potential Problem Summary) PDFs."""

from __future__ import annotations

import hashlib
import html
import io
import re
import secrets
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from typing import Any, get_args, get_origin, get_type_hints

import pandas as pd
import streamlit as st

try:
    from PyPDF2 import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None

MONTH_LABELS = ("March", "April", "May")

# Shown in the POPPS tab so you can confirm Streamlit Cloud deployed the latest build.
POPPS_UI_VERSION = "2026-06-02-popps-ui-polish"

POPPS_NOTES_WARNING_DAYS = 15
POPPS_NOTES_MANAGER_ALERT_DAYS = 17

# Stellantis WAM / DWIN — same wording used on Dealer POPPS Management Reports.
DAZE_ACRONYM = "DAZE"
DAZE_FULL_NAME = "Dealer Average Zone Expense"
DAZE_LABEL = f"{DAZE_ACRONYM} ({DAZE_FULL_NAME})"
DAZE_WAM_DEFINITION = (
    f"{DAZE_LABEL} is a DWIN warranty performance measure defined in the Stellantis "
    "Warranty Administration Manual (WAM). It compares your dealership's warranty spending "
    "to the average for your Business Center zone. The dealership index is your store; "
    "the business center index is the zone benchmark. DAZE Expense is the warranty dollars "
    "included in that calculation for the month."
)
DAZE_METRIC_HELP = DAZE_WAM_DEFINITION
DAZE_HELP_DEALERSHIP = DAZE_METRIC_HELP
DAZE_HELP_BUSINESS_CENTER = (
    f"{DAZE_METRIC_HELP} This value is the zone (Business Center) benchmark for comparison."
)
DAZE_HELP_EXPENSE = (
    f"{DAZE_FULL_NAME} ({DAZE_ACRONYM}) expense dollars for this month — warranty costs "
    "counted in the DAZE measure per WAM / DWIN POPPS reporting."
)

# Compare dealership index to Business Center (zone) each month — lower vs zone is favorable.
DAZE_COMPARE_MARGIN_PCT = 0.35


def _parse_percent_number(raw: str) -> float | None:
    match = re.search(r"([\d.]+)", str(raw or "").replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _parse_money_number(raw: str) -> float | None:
    match = re.search(r"([\d,]+(?:\.\d+)?)", str(raw or "").replace("$", ""))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _daze_compare_zone(dealer_raw: str, zone_raw: str) -> tuple[str, str]:
    """Return (css_tone, short_hint) for dealership DAZE vs zone benchmark."""
    dealer = _parse_percent_number(dealer_raw)
    zone = _parse_percent_number(zone_raw)
    if dealer is None or zone is None:
        return "neutral", ""
    if zone > 75 and dealer < 25:
        return "neutral", "Zone benchmark unavailable for color compare"
    diff = dealer - zone
    zone_display = str(zone_raw or "").strip() or f"{zone:g}%"
    if diff <= -DAZE_COMPARE_MARGIN_PCT:
        return "good", f"At or below zone ({zone_display})"
    if diff <= DAZE_COMPARE_MARGIN_PCT:
        return "watch", f"Near zone average ({zone_display})"
    return "high", f"Above zone ({zone_display})"


def _daze_expense_trend(current_raw: str, prior_raw: str | None) -> tuple[str, str]:
    """Month-over-month DAZE expense dollars — down is favorable."""
    current = _parse_money_number(current_raw)
    prior = _parse_money_number(prior_raw) if prior_raw else None
    if current is None or prior is None:
        return "neutral", ""
    diff = current - prior
    if diff < -1:
        return "good", f"Down ${abs(diff):,.0f} vs prior month"
    if diff > 1:
        return "high", f"Up ${diff:,.0f} vs prior month"
    return "watch", "Flat vs prior month"


def _daze_metric_label_html(label: str, help_text: str = "") -> str:
    safe_label = html.escape(str(label or ""))
    if not str(help_text or "").strip():
        return f'<div class="popps-daze-metric-label">{safe_label}</div>'
    safe_help = html.escape(str(help_text), quote=True)
    return (
        f'<div class="popps-daze-metric-label-row">'
        f'<span class="popps-daze-metric-label">{safe_label}</span>'
        f'<span class="popps-daze-help" title="{safe_help}" aria-label="Metric help">?</span>'
        f"</div>"
    )


def _render_daze_colored_metric(
    label: str,
    value: str,
    *,
    tone: str,
    hint: str = "",
    help_text: str = "",
) -> None:
    display = html.escape(str(value or "").strip() or "—")
    hint_html = (
        f'<div class="popps-daze-metric-hint">{html.escape(hint)}</div>' if hint else ""
    )
    with st.container(border=True):
        st.markdown(
            f'<div class="popps-daze-metric-card">'
            f"{_daze_metric_label_html(label, help_text)}"
            f'<div class="popps-daze-metric-value popps-daze-{tone}">{display}</div>'
            f"{hint_html}"
            f"</div>",
            unsafe_allow_html=True,
        )


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


def popps_report_fingerprint(report: PoppsReport, file_name: str) -> str:
    """Stable key for saving review notes against one uploaded POPPS file."""
    period = re.sub(r"\s+", " ", str(report.period_label or "").strip())
    dealer = str(report.dealer_code or "").strip()
    source = str(file_name or "").strip()
    return f"{dealer}|{period}|{source}"


MONTH_NAME_TO_NUMBER: dict[str, int] = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def popps_period_sort_key(
    period_label: str,
    *,
    file_name: str = "",
    uploaded_at: str = "",
) -> int:
    """Sortable YYYYMM from POPPS header (e.g. May 2026 — Interim Report)."""
    text = str(period_label or "").lower()
    year_match = re.search(r"\b(20\d{2})\b", text)
    year = int(year_match.group(1)) if year_match else 0
    month = 0
    for name, number in MONTH_NAME_TO_NUMBER.items():
        if re.search(rf"\b{re.escape(name)}\b", text):
            month = number
            break
    if not month:
        file_low = str(file_name or "").lower()
        for name, number in MONTH_NAME_TO_NUMBER.items():
            if name[:3] in file_low:
                month = number
                break
    if not year:
        file_year = re.search(r"(20\d{2})", str(file_name or ""))
        if file_year:
            year = int(file_year.group(1))
    if year and month:
        return year * 100 + month
    if uploaded_at:
        try:
            dt = datetime.fromisoformat(str(uploaded_at).replace("Z", "+00:00"))
            return dt.year * 100 + dt.month
        except Exception:
            pass
    return 0


def popps_quarter_from_period_sort(period_sort: int) -> tuple[int, str]:
    """Calendar quarter from YYYYMM (e.g. May 2026 → Q2 2026)."""
    if period_sort < 100001:
        return 0, ""
    year = period_sort // 100
    month = period_sort % 100
    if month < 1 or month > 12:
        return 0, ""
    quarter = (month - 1) // 3 + 1
    return year * 10 + quarter, f"Q{quarter} {year}"


def _enrich_entry_quarter_fields(entry: dict) -> dict:
    entry = dict(entry)
    period_sort = int(entry.get("period_sort") or 0)
    quarter_sort, quarter_label = popps_quarter_from_period_sort(period_sort)
    if quarter_sort:
        entry["quarter_sort"] = quarter_sort
        entry["quarter_label"] = quarter_label
    return entry


def _normalize_popps_library(raw: dict | None) -> dict:
    raw = raw or {}
    reports = raw.get("reports")
    if not isinstance(reports, dict):
        reports = {}
    return {
        "active_fingerprint": str(raw.get("active_fingerprint") or "").strip(),
        "reports": dict(reports),
    }


def _popps_entry_from_report(
    report: PoppsReport,
    file_name: str,
    uploaded_by: str,
    *,
    uploaded_at: str | None = None,
) -> dict:
    uploaded_at = uploaded_at or datetime.now(timezone.utc).isoformat()
    fingerprint = popps_report_fingerprint(report, file_name)
    period_label = str(report.period_label or "").strip()
    period_sort = popps_period_sort_key(
        period_label,
        file_name=file_name,
        uploaded_at=uploaded_at,
    )
    quarter_sort, quarter_label = popps_quarter_from_period_sort(period_sort)
    entry = {
        "fingerprint": fingerprint,
        "file_name": str(file_name or "").strip(),
        "period_label": period_label,
        "period_sort": period_sort,
        "quarter_sort": quarter_sort,
        "quarter_label": quarter_label,
        "dealer_code": str(report.dealer_code or "").strip(),
        "uploaded_at": uploaded_at,
        "uploaded_by": str(uploaded_by or "").strip(),
        "report": popps_report_to_storage_dict(report),
    }
    return entry


def _sort_popps_library_entries(
    entries: list[dict],
    *,
    newest_first: bool = False,
) -> list[dict]:
    """Order saved POPPS months by calendar quarter and report period."""
    enriched = [_enrich_entry_quarter_fields(entry) for entry in entries]
    return sorted(
        enriched,
        key=lambda entry: (
            int(entry.get("quarter_sort") or 0),
            int(entry.get("period_sort") or 0),
            str(entry.get("uploaded_at") or ""),
            str(entry.get("fingerprint") or ""),
        ),
        reverse=newest_first,
    )


def _active_library_fingerprint(reports: dict[str, dict]) -> str:
    """Newest month within the most recent calendar quarter."""
    if not reports:
        return ""
    enriched = [_enrich_entry_quarter_fields(entry) for entry in reports.values()]
    max_quarter = max(int(entry.get("quarter_sort") or 0) for entry in enriched)
    if not max_quarter:
        ordered = _sort_popps_library_entries(enriched, newest_first=True)
        return str(ordered[0].get("fingerprint") or "")

    in_current_quarter = [
        entry for entry in enriched if int(entry.get("quarter_sort") or 0) == max_quarter
    ]
    ordered = _sort_popps_library_entries(in_current_quarter, newest_first=True)
    return str(ordered[0].get("fingerprint") or "")


def _migrate_legacy_active_into_library(library: dict, active_blob: dict | None) -> dict:
    if not active_blob or not active_blob.get("report"):
        return library
    report_data = active_blob.get("report")
    try:
        report = popps_report_from_storage_dict(report_data)
    except Exception:
        return library
    file_name = str(active_blob.get("file_name") or "POPPS report").strip()
    entry = _popps_entry_from_report(
        report,
        file_name,
        str(active_blob.get("uploaded_by") or ""),
        uploaded_at=str(active_blob.get("uploaded_at") or ""),
    )
    fingerprint = entry["fingerprint"]
    if fingerprint not in library["reports"]:
        library["reports"][fingerprint] = entry
    if not library["active_fingerprint"]:
        library["active_fingerprint"] = fingerprint
    library["active_fingerprint"] = _active_library_fingerprint(library["reports"])
    return library


def load_popps_library(supabase) -> dict:
    """All saved POPPS months plus which fingerprint is the current-quarter report."""
    library = _normalize_popps_library({})
    if supabase is None:
        return library
    try:
        response = (
            supabase.table("dealer_settings")
            .select("popps_reports_library, popps_active_report")
            .eq("id", 1)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return library
        library = _normalize_popps_library(rows[0].get("popps_reports_library"))
        library = _migrate_legacy_active_into_library(
            library,
            rows[0].get("popps_active_report"),
        )
        if library["reports"]:
            library["active_fingerprint"] = _active_library_fingerprint(library["reports"])
        return library
    except Exception:
        return library


def _persist_popps_library(
    supabase,
    library: dict,
    *,
    uploaded_by: str,
    auth_user: str = "",
    apply_session: bool = True,
) -> str:
    """Write library to Supabase and return the active (current quarter) fingerprint."""
    library["active_fingerprint"] = _active_library_fingerprint(library["reports"])
    active_fp = str(library.get("active_fingerprint") or "")
    active_entry = (library.get("reports") or {}).get(active_fp) or {}
    active_payload = {
        "file_name": active_entry.get("file_name"),
        "uploaded_at": active_entry.get("uploaded_at"),
        "uploaded_by": active_entry.get("uploaded_by"),
        "report": active_entry.get("report"),
    }
    supabase.table("dealer_settings").update(
        {
            "popps_reports_library": library,
            "popps_active_report": active_payload,
        }
    ).eq("id", 1).execute()
    user_marker = re.sub(
        r"[^a-zA-Z0-9@._-]", "_", str(auth_user or uploaded_by or "").strip().lower()
    ) or "_anonymous"
    st.session_state[f"_popps_hydrate_ok_{user_marker}"] = True
    st.session_state.pop(f"_popps_hydrate_empty_{user_marker}", None)
    st.session_state.pop("popps_cloud_load_error", None)
    st.session_state.pop("popps_viewing_fingerprint", None)
    if apply_session and active_entry:
        apply_popps_entry_to_session(active_entry)
    if supabase is not None:
        newest = newest_popps_upload_entry(library)
        if newest:
            _sync_popps_notes_compliance_upload(supabase, str(newest.get("fingerprint") or ""))
    st.session_state.pop("_popps_compliance_status", None)
    return active_fp


def import_popps_pdf_files(
    supabase,
    uploaded_files: list,
    uploaded_by: str,
    *,
    auth_user: str = "",
) -> dict[str, Any]:
    """Parse and store multiple POPPS PDFs in one import."""
    results: dict[str, Any] = {
        "imported": [],
        "failed": [],
        "active_fingerprint": "",
        "active_period_label": "",
        "active_quarter_label": "",
    }
    if not uploaded_files:
        return results

    library = load_popps_library(supabase) if supabase is not None else _normalize_popps_library({})

    for uploaded in uploaded_files:
        file_name = str(getattr(uploaded, "name", "") or "POPPS report.pdf")
        try:
            report = parse_popps_pdf(uploaded.getvalue())
            entry = _popps_entry_from_report(report, file_name, uploaded_by)
            library["reports"][entry["fingerprint"]] = entry
            results["imported"].append(entry)
        except Exception as exc:
            results["failed"].append({"file_name": file_name, "error": str(exc)})

    if supabase is None:
        if results["imported"]:
            library["active_fingerprint"] = _active_library_fingerprint(library["reports"])
            active_entry = library["reports"].get(library["active_fingerprint"]) or {}
            apply_popps_entry_to_session(active_entry)
            results["active_fingerprint"] = library["active_fingerprint"]
            results["active_period_label"] = active_entry.get("period_label") or ""
            results["active_quarter_label"] = active_entry.get("quarter_label") or ""
        return results

    if results["imported"]:
        try:
            active_fp = _persist_popps_library(
                supabase,
                library,
                uploaded_by=uploaded_by,
                auth_user=auth_user,
                apply_session=True,
            )
            active_entry = library["reports"].get(active_fp) or {}
            results["active_fingerprint"] = active_fp
            results["active_period_label"] = active_entry.get("period_label") or ""
            results["active_quarter_label"] = active_entry.get("quarter_label") or ""
        except Exception as exc:
            results["persist_error"] = str(exc)

    return results


def _active_library_entry(library: dict) -> dict | None:
    fingerprint = str(library.get("active_fingerprint") or "").strip()
    if not fingerprint:
        return None
    entry = (library.get("reports") or {}).get(fingerprint)
    return dict(entry) if entry else None


def _entry_to_loaded_report(entry: dict) -> tuple[PoppsReport | None, str, dict, str]:
    if not entry or not entry.get("report"):
        return None, "", {}, ""
    try:
        report = popps_report_from_storage_dict(entry["report"])
    except Exception as exc:
        return None, "", {}, f"Stored POPPS report could not be loaded: {exc}"
    meta = {
        "file_name": entry.get("file_name"),
        "uploaded_at": entry.get("uploaded_at"),
        "uploaded_by": entry.get("uploaded_by"),
        "period_label": entry.get("period_label"),
        "fingerprint": entry.get("fingerprint"),
    }
    return report, str(entry.get("file_name") or "POPPS report").strip(), meta, ""


def apply_popps_entry_to_session(entry: dict, *, restored_from_cloud: bool = False) -> None:
    report, file_name, meta, _ = _entry_to_loaded_report(entry)
    if report is None:
        return
    st.session_state.popps_parsed_report = report
    st.session_state.popps_upload_name = file_name
    st.session_state.popps_restored_meta = meta
    if restored_from_cloud:
        st.session_state.popps_restored_from_cloud = True


def save_popps_to_library(
    supabase,
    report: PoppsReport,
    file_name: str,
    uploaded_by: str,
    *,
    auth_user: str = "",
) -> tuple[bool, str, str]:
    """Save one POPPS month and set the current-quarter report as active for all users."""
    if supabase is None:
        return False, "Supabase is not configured", ""
    entry = _popps_entry_from_report(report, file_name, uploaded_by)
    fingerprint = entry["fingerprint"]
    try:
        library = load_popps_library(supabase)
        library["reports"][fingerprint] = entry
        active_fp = _persist_popps_library(
            supabase,
            library,
            uploaded_by=uploaded_by,
            auth_user=auth_user,
            apply_session=True,
        )
        return True, "", active_fp
    except Exception as exc:
        return False, str(exc), fingerprint


def _list_item_type(field_type: Any) -> Any | None:
    """Resolve list[Inner] on Python 3.9+ (get_origin may be None for PEP 585 types)."""
    args = get_args(field_type)
    if not args:
        args = getattr(field_type, "__args__", ()) or ()
    if get_origin(field_type) is list or getattr(field_type, "__origin__", None) is list:
        return args[0] if args else None
    return None


def _dataclass_from_dict(cls: type, data: dict | None) -> Any:
    data = dict(data or {})
    hints = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        val = data.get(f.name)
        field_type = hints.get(f.name, f.type)
        inner_cls = _list_item_type(field_type)
        if inner_cls is not None:
            if is_dataclass(inner_cls):
                kwargs[f.name] = [_dataclass_from_dict(inner_cls, item) for item in (val or [])]
            else:
                kwargs[f.name] = list(val or [])
        elif is_dataclass(field_type):
            kwargs[f.name] = _dataclass_from_dict(field_type, val or {})
        elif val is not None:
            kwargs[f.name] = val
    return cls(**kwargs)


def popps_report_to_storage_dict(report: PoppsReport) -> dict:
    """Serialize parsed report for Supabase (cap very large extracted text)."""
    payload = asdict(report)
    raw = str(payload.get("raw_text") or "")
    max_raw = 120_000
    if len(raw) > max_raw:
        payload["raw_text"] = raw[:max_raw]
        payload["raw_text_truncated"] = True
    return payload


def popps_report_from_storage_dict(data: dict | None) -> PoppsReport:
    return _dataclass_from_dict(PoppsReport, data)


def reset_popps_hydrate_attempt_flags() -> None:
    """Allow another cloud load attempt (e.g. after Refresh or manual reload)."""
    for key in list(st.session_state.keys()):
        name = str(key)
        if name.startswith("_popps_hydrate_"):
            st.session_state.pop(key, None)
    st.session_state.pop("popps_cloud_load_error", None)


def clear_popps_session_state() -> None:
    """Clear POPPS UI state (call on sign-out / sign-in so the next user reloads from cloud)."""
    reset_popps_hydrate_attempt_flags()
    for key in list(st.session_state.keys()):
        name = str(key)
        if name.startswith("popps_") or name.startswith("_popps_"):
            st.session_state.pop(key, None)


def load_active_popps_report(
    supabase,
    *,
    viewing_fingerprint: str = "",
) -> tuple[PoppsReport | None, str, dict, str]:
    """Load the current-quarter POPPS report, or a specific archived month if requested."""
    library = load_popps_library(supabase)
    if not library.get("reports"):
        return None, "", {}, ""
    fingerprint = str(viewing_fingerprint or "").strip()
    if not fingerprint or fingerprint not in library["reports"]:
        fingerprint = _active_library_fingerprint(library["reports"])
        if not fingerprint:
            fingerprint = str(library.get("active_fingerprint") or "")
    entry = library["reports"].get(fingerprint)
    if not entry:
        return None, "", {}, ""
    return _entry_to_loaded_report(entry)


def save_active_popps_report(
    supabase,
    report: PoppsReport,
    file_name: str,
    uploaded_by: str,
    *,
    auth_user: str = "",
) -> tuple[bool, str]:
    """Persist POPPS to the year archive and refresh the current-quarter active report."""
    ok, err, _active_fp = save_popps_to_library(
        supabase,
        report,
        file_name,
        uploaded_by,
        auth_user=auth_user,
    )
    return ok, err


def clear_active_popps_report(supabase) -> None:
    if supabase is None:
        return
    try:
        supabase.table("dealer_settings").update(
            {"popps_active_report": None, "popps_reports_library": {"active_fingerprint": "", "reports": {}}}
        ).eq("id", 1).execute()
    except Exception:
        pass


def prepare_popps_tab_on_enter(supabase, *, auth_user: str = "") -> None:
    """When the POPPS tab opens or the page reloads, default to the newest month on file."""
    current = str(st.session_state.get("main_section_nav") or "")
    previous = str(st.session_state.get("_popps_nav_previous") or "")
    st.session_state["_popps_nav_previous"] = current

    if current != "POPPS Report":
        return

    entering_tab = previous != "POPPS Report"
    missing_report = st.session_state.get("popps_parsed_report") is None
    if not entering_tab and not missing_report:
        return

    st.session_state.pop("popps_viewing_fingerprint", None)
    reset_popps_hydrate_attempt_flags()
    for key in (
        "popps_parsed_report",
        "popps_upload_name",
        "popps_restored_from_cloud",
        "popps_restored_meta",
        "popps_cloud_load_error",
    ):
        st.session_state.pop(key, None)

    if supabase is None:
        return

    hydrate_popps_report_from_cloud(supabase, auth_user=auth_user, force=True)


def hydrate_popps_report_from_cloud(
    supabase,
    *,
    auth_user: str = "",
    force: bool = False,
) -> bool:
    """Restore the dealership POPPS report from cloud for this signed-in user."""
    if st.session_state.get("popps_parsed_report") is not None:
        return False

    user_marker = re.sub(r"[^a-zA-Z0-9@._-]", "_", str(auth_user or "").strip().lower()) or "_anonymous"
    ok_key = f"_popps_hydrate_ok_{user_marker}"
    empty_key = f"_popps_hydrate_empty_{user_marker}"

    if not force:
        if st.session_state.get(ok_key):
            return False
        if st.session_state.get(empty_key):
            return False

    viewing_fp = str(st.session_state.get("popps_viewing_fingerprint") or "").strip()
    report, file_name, meta, load_error = load_active_popps_report(
        supabase,
        viewing_fingerprint=viewing_fp,
    )
    st.session_state.popps_cloud_load_error = load_error or ""

    if load_error:
        return False

    if report is None:
        library = load_popps_library(supabase) if supabase is not None else {}
        reports = library.get("reports") or {}
        if reports:
            for entry in _sort_popps_library_entries(list(reports.values()), newest_first=True):
                fp = str(entry.get("fingerprint") or "")
                if not fp:
                    continue
                report, file_name, meta, load_error = _entry_to_loaded_report(reports.get(fp) or {})
                if report is not None:
                    st.session_state.popps_viewing_fingerprint = fp
                    break
        if report is None:
            st.session_state[empty_key] = True
            return False

    st.session_state[ok_key] = True
    st.session_state.pop(empty_key, None)
    st.session_state.popps_parsed_report = report
    st.session_state.popps_upload_name = file_name
    st.session_state.popps_restored_from_cloud = True
    st.session_state.popps_restored_meta = meta
    st.session_state.pop("popps_cloud_load_error", None)
    return True


def _render_popps_archive_panel(
    library: dict,
    *,
    supabase,
    active_fingerprint: str,
    viewing_fingerprint: str,
) -> None:
    """Compact list of saved months; main screen stays on the current calendar quarter only."""
    reports = list((library.get("reports") or {}).values())
    if not reports:
        return

    ordered = _sort_popps_library_entries(reports, newest_first=False)
    archive_count = len(ordered)
    active_entry = _enrich_entry_quarter_fields(
        (library.get("reports") or {}).get(active_fingerprint) or {}
    )
    active_quarter_label = str(active_entry.get("quarter_label") or "").strip()
    active_period_label = str(active_entry.get("period_label") or "").strip()
    active_quarter_sort = int(active_entry.get("quarter_sort") or 0)
    archive_scope = _safe_widget_suffix(active_fingerprint or "none", "popps_archive", scope="panel")

    if active_quarter_label and active_period_label:
        st.caption(
            f"**Current quarter:** {active_quarter_label} — displaying **{active_period_label}**. "
            "Older quarters stay in the archive below."
        )
    elif archive_count <= 1 and not viewing_fingerprint:
        st.caption(
            "Upload each month's POPPS PDF as you receive it. RO Guard stores every month "
            "and shows the **newest month in the current calendar quarter** on this screen."
        )
        return

    if viewing_fingerprint and viewing_fingerprint != active_fingerprint:
        view_entry = _enrich_entry_quarter_fields(
            (library["reports"].get(viewing_fingerprint) or {})
        )
        period = str(view_entry.get("period_label") or "Archived month")
        quarter = str(view_entry.get("quarter_label") or "").strip()
        label = f"{quarter} — {period}" if quarter else period
        c1, c2 = st.columns([4, 1])
        with c1:
            st.info(f"Previewing archived report: **{label}**. Reviews still save per month.")
        with c2:
            if st.button(
                "Current quarter",
                key=f"popps_back_to_latest_{archive_scope}",
                use_container_width=True,
            ):
                st.session_state.pop("popps_viewing_fingerprint", None)
                reset_popps_hydrate_attempt_flags()
                st.session_state.pop("popps_parsed_report", None)
                hydrate_popps_report_from_cloud(supabase, force=True)
                st.rerun()

    st.caption(
        f"**{archive_count} monthly POPPS report(s) saved** — expand the archive below "
        "to preview older quarters or switch months."
    )
    st.markdown('<div class="popps-archive-zone" aria-hidden="true"></div>', unsafe_allow_html=True)
    archive_title = f"POPPS archive — {archive_count} month(s) on file"
    _render_popps_expander_header(archive_title, "archive")
    _popps_expander_anchor("popps-anchor-archive")
    with st.expander(
        "Open archive — preview older quarters",
        expanded=False,
        key=f"popps_archive_expander_{archive_scope}",
    ):
        st.caption(
            "The main screen shows only the **current calendar quarter** (newest month in that quarter). "
            "Use this list to preview older quarters or other months in the archive."
        )
        rows = []
        for row_num, entry in enumerate(ordered, start=1):
            fingerprint = str(entry.get("fingerprint") or "")
            in_current_quarter = int(entry.get("quarter_sort") or 0) == active_quarter_sort
            is_active = fingerprint == active_fingerprint
            if is_active:
                status = "On screen (latest month in quarter)"
            elif in_current_quarter:
                status = "Same quarter"
            else:
                status = "Older quarter"
            rows.append(
                {
                    "#": row_num,
                    "Quarter": entry.get("quarter_label") or "—",
                    "Report period": entry.get("period_label") or "—",
                    "Source file": entry.get("file_name") or "—",
                    "Uploaded": str(entry.get("uploaded_at") or "")[:10],
                    "Status": status,
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        if len(ordered) > 1:
            options = {
                str(e.get("fingerprint") or ""): (
                    f"{e.get('quarter_label') or ''} — {e.get('period_label') or 'POPPS'} "
                    f"({e.get('file_name') or 'file'})"
                ).strip(" — ")
                for e in ordered
            }
            fingerprints = list(options.keys())
            selected_fp = viewing_fingerprint or active_fingerprint
            try:
                default_idx = fingerprints.index(selected_fp)
            except ValueError:
                default_idx = len(fingerprints) - 1
            pick = st.selectbox(
                "Switch to another saved month",
                options=fingerprints,
                index=default_idx,
                format_func=lambda fp: options.get(fp, fp),
                key=f"popps_archive_pick_{archive_scope}",
            )
            if st.button(
                "Open selected report",
                key=f"popps_archive_open_btn_{archive_scope}",
                use_container_width=True,
            ):
                if pick and pick != active_fingerprint:
                    st.session_state.popps_viewing_fingerprint = pick
                    reset_popps_hydrate_attempt_flags()
                    st.session_state.pop("popps_parsed_report", None)
                    hydrate_popps_report_from_cloud(supabase, force=True)
                    st.rerun()
                elif pick == active_fingerprint:
                    st.session_state.pop("popps_viewing_fingerprint", None)
                    reset_popps_hydrate_attempt_flags()
                    st.session_state.pop("popps_parsed_report", None)
                    hydrate_popps_report_from_cloud(supabase, force=True)
                    st.rerun()
        else:
            st.caption(
                "Only one month is saved so far. Upload additional months as you receive them."
            )


def _slug_token(text: str, *, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(text or "").strip()).strip("_")
    return slug[:max_len] or "item"


def _safe_widget_suffix(entry_key: str, report_fingerprint: str, *, scope: str = "") -> str:
    """Stable unique Streamlit widget key (avoids truncation collisions)."""
    raw = f"{report_fingerprint}|{entry_key}|{scope}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    return f"w_{digest}"


def section_review_entry_key(section: PoppsPrioritySection) -> str:
    rank = _slug_token(section.priority_rank, max_len=24)
    lop = _slug_token(section.labor_operation_code, max_len=24)
    desc = _slug_token(section.repair_description, max_len=40)
    return f"section:{rank}:{lop}:{desc}"


def claim_review_entry_key(
    section: PoppsPrioritySection,
    claim: PoppsClaimRow,
    *,
    claim_index: int,
) -> str:
    """Unique per claim row (RO numbers may repeat or be blank in the PDF)."""
    claim_id = re.sub(r"\s+", "_", str(claim.claim_condition_or_number or "").strip())
    if not claim_id:
        claim_id = "no_number"
    vin = _slug_token(claim.vehicle_identification, max_len=24)
    lop = _slug_token(claim.labor_operation_or_message_code, max_len=24)
    return (
        f"{section_review_entry_key(section)}:claim:{claim_index}:{claim_id}:"
        f"vin:{vin}:lop:{lop}"
    )


def summary_review_entry_key(row: PoppsSummaryRow, *, group: str) -> str:
    lop = _slug_token(row.labor_operation_code, max_len=24)
    rank = _slug_token(row.rank_label, max_len=24)
    desc = _slug_token(row.repair_description, max_len=40)
    return f"summary:{group}:{rank}:{lop}:{desc}"


def customer_care_review_entry_key(row: PoppsCustomerCareRow) -> str:
    metric = re.sub(r"\s+", "_", row.metric_name)
    return f"summary:customer_care:{metric}"


def _normalize_popps_reviews_blob(raw: dict | None) -> dict:
    raw = raw or {}
    reports = raw.get("reports")
    if not isinstance(reports, dict):
        reports = {}
    return {"reports": reports}


def load_popps_reviews_store(supabase, report_fingerprint: str) -> dict[str, dict]:
    """Return entry_key -> review record for the active POPPS report."""
    if not report_fingerprint:
        return {}
    cache_key = f"popps_reviews_{report_fingerprint}"
    if cache_key in st.session_state:
        return dict(st.session_state[cache_key])

    entries: dict[str, dict] = {}
    if supabase is not None:
        try:
            response = (
                supabase.table("dealer_settings")
                .select("popps_reviews")
                .eq("id", 1)
                .limit(1)
                .execute()
            )
            rows = response.data or []
            if rows and rows[0].get("popps_reviews"):
                blob = _normalize_popps_reviews_blob(rows[0]["popps_reviews"])
                report_data = blob["reports"].get(report_fingerprint) or {}
                stored = report_data.get("entries")
                if isinstance(stored, dict):
                    entries = dict(stored)
        except Exception:
            pass

    st.session_state[cache_key] = entries
    return entries


def _popps_report_context(report: PoppsReport, file_name: str, report_fingerprint: str) -> dict[str, str]:
    return {
        "report_fingerprint": report_fingerprint,
        "dealer_code": str(report.dealer_code or "").strip(),
        "report_period": str(report.period_label or "").strip(),
        "source_file": str(file_name or "").strip(),
    }


def _is_message_code_priority_section(section: PoppsPrioritySection) -> bool:
    """Factory MSG CODE blocks (e.g. Too Old to Process) — summary only, no RO review."""
    label = str(section.priority_label or "").lower()
    if "message code" in label:
        return True
    rank = str(section.priority_rank or "").upper().replace(" ", "")
    if rank.startswith("MSG"):
        return True
    return str(section.labor_operation_code or "").strip().lower() == "message code"


def newest_popps_upload_entry(library: dict) -> dict | None:
    """Most recently uploaded POPPS month in the dealership library."""
    reports = list((library.get("reports") or {}).values())
    if not reports:
        return None
    ordered = sorted(
        reports,
        key=lambda entry: (
            str(entry.get("uploaded_at") or ""),
            str(entry.get("fingerprint") or ""),
        ),
        reverse=True,
    )
    return dict(ordered[0]) if ordered else None


def _parse_utc_timestamp(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _days_since_timestamp(value: str) -> int | None:
    parsed = _parse_utc_timestamp(value)
    if parsed is None:
        return None
    today = datetime.now(timezone.utc).date()
    return (today - parsed.date()).days


def _priority_sections_needing_notes(report: PoppsReport) -> list[PoppsPrioritySection]:
    sections: list[PoppsPrioritySection] = []
    for section in report.priority_sections:
        if _is_popps_review_exempt_section(section):
            continue
        if not section.claims:
            continue
        sections.append(section)
    return sections


def _priority_section_note_label(section: PoppsPrioritySection) -> str:
    rank = str(section.priority_rank or "").strip()
    lop = str(section.labor_operation_code or "").strip()
    desc = str(section.repair_description or "").strip()
    if rank.isdigit():
        return f"Priority {rank} — {lop} — {desc}"
    return f"{section.priority_label} — {lop}"


def popps_report_has_claim_notes(reviews_store: dict[str, dict]) -> bool:
    for entry in (reviews_store or {}).values():
        if _active_notes(entry):
            return True
    return False


def _load_popps_notes_compliance(supabase) -> dict:
    if supabase is None:
        return {}
    try:
        response = (
            supabase.table("dealer_settings")
            .select("popps_notes_compliance")
            .eq("id", 1)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if rows and isinstance(rows[0].get("popps_notes_compliance"), dict):
            return dict(rows[0]["popps_notes_compliance"])
    except Exception:
        pass
    return {}


def _save_popps_notes_compliance(supabase, state: dict) -> None:
    if supabase is None:
        return
    try:
        supabase.table("dealer_settings").update(
            {"popps_notes_compliance": dict(state)}
        ).eq("id", 1).execute()
    except Exception:
        pass


def _sync_popps_notes_compliance_upload(supabase, upload_fingerprint: str) -> None:
    """Reset manager alert tracking when a newer POPPS file is uploaded."""
    fingerprint = str(upload_fingerprint or "").strip()
    if not fingerprint:
        return
    state = _load_popps_notes_compliance(supabase)
    if str(state.get("tracked_upload_fingerprint") or "") == fingerprint:
        return
    state["tracked_upload_fingerprint"] = fingerprint
    state.pop("manager_alert_sent_at", None)
    state.pop("manager_alert_sent_for_fingerprint", None)
    state.pop("manager_alert_last_error", None)
    _save_popps_notes_compliance(supabase, state)


def _maybe_send_popps_manager_notes_alert(
    supabase,
    *,
    upload_fingerprint: str,
    upload_label: str,
    uploaded_at: str,
    days_since_upload: int,
) -> tuple[bool, str]:
    """Email managers once per upload when notes are still missing after day 17."""
    from core.scheduled_reports import load_manager_emails, send_plain_email

    state = _load_popps_notes_compliance(supabase)
    if str(state.get("manager_alert_sent_for_fingerprint") or "") == upload_fingerprint:
        return False, ""

    managers = load_manager_emails(supabase)
    if not managers:
        return False, "No manager emails found in Personnel."

    uploaded_display = str(uploaded_at or "")[:19].replace("T", " ")
    period = upload_label or "POPPS report"
    body = (
        f"RO Guard — POPPS review notes are overdue\n\n"
        f"The dealership's most recent POPPS upload ({period}) was saved on "
        f"{uploaded_display or '—'} UTC.\n\n"
        f"It has been {days_since_upload} days and no claim review notes have been added "
        f"in the POPPS Report tab under **Repair groups and related claims (add notes)**.\n\n"
        f"Warranty administrators were warned starting on day {POPPS_NOTES_WARNING_DAYS}. "
        f"Please follow up so each Claims Analysis repair group with sample claims is documented.\n\n"
        f"— RO Shield (automated alert)\n"
    )
    try:
        send_plain_email(
            recipients=managers,
            subject="RO Guard alert — POPPS notes overdue (17+ days)",
            body_text=body,
        )
    except Exception as exc:
        state["manager_alert_last_error"] = str(exc)
        _save_popps_notes_compliance(supabase, state)
        return False, str(exc)

    state["manager_alert_sent_for_fingerprint"] = upload_fingerprint
    state["manager_alert_sent_at"] = datetime.now(timezone.utc).isoformat()
    state.pop("manager_alert_last_error", None)
    _save_popps_notes_compliance(supabase, state)
    return True, ""


def evaluate_popps_notes_compliance(
    supabase,
    *,
    library: dict | None = None,
    report_fingerprint: str = "",
    reviews_store: dict[str, dict] | None = None,
    report: PoppsReport | None = None,
    run_manager_alert: bool = False,
) -> dict | None:
    """Compliance state for POPPS claim notes vs most recent upload date."""
    library = library or {}
    upload_entry = newest_popps_upload_entry(library)
    if not upload_entry:
        return None

    uploaded_at = str(upload_entry.get("uploaded_at") or "")
    days = _days_since_timestamp(uploaded_at)
    if days is None:
        return None

    upload_fp = str(upload_entry.get("fingerprint") or "")
    report_fp = str(report_fingerprint or library.get("active_fingerprint") or upload_fp)
    reviews = reviews_store if reviews_store is not None else load_popps_reviews_store(supabase, report_fp)
    has_notes = popps_report_has_claim_notes(reviews)

    categories: list[str] = []
    if report is not None:
        categories = [_priority_section_note_label(section) for section in _priority_sections_needing_notes(report)]

    compliance_state = _load_popps_notes_compliance(supabase)
    already_sent = str(compliance_state.get("manager_alert_sent_for_fingerprint") or "") == upload_fp

    status = {
        "upload_fingerprint": upload_fp,
        "uploaded_at": uploaded_at,
        "upload_label": str(upload_entry.get("period_label") or upload_entry.get("file_name") or "POPPS"),
        "days_since_upload": days,
        "has_notes": has_notes,
        "needs_warning": (not has_notes) and days >= POPPS_NOTES_WARNING_DAYS,
        "needs_manager_alert": (not has_notes) and days >= POPPS_NOTES_MANAGER_ALERT_DAYS,
        "categories": categories,
        "manager_alert_sent": False,
        "manager_alert_already_sent": already_sent,
        "manager_alert_error": str(compliance_state.get("manager_alert_last_error") or ""),
    }

    if run_manager_alert and status["needs_manager_alert"] and not already_sent:
        sent, err = _maybe_send_popps_manager_notes_alert(
            supabase,
            upload_fingerprint=upload_fp,
            upload_label=status["upload_label"],
            uploaded_at=uploaded_at,
            days_since_upload=days,
        )
        status["manager_alert_sent"] = sent
        status["manager_alert_error"] = err
        compliance = _load_popps_notes_compliance(supabase)
        if str(compliance.get("manager_alert_sent_for_fingerprint") or "") == upload_fp:
            status["manager_alert_already_sent"] = True

    return status


def process_popps_notes_compliance(supabase) -> dict | None:
    """Run once per session: evaluate notes deadlines and send manager alert if due."""
    if st.session_state.get("_popps_compliance_status") is not None:
        return st.session_state.get("_popps_compliance_status")

    library = load_popps_library(supabase) if supabase is not None else _normalize_popps_library({})
    report: PoppsReport | None = st.session_state.get("popps_parsed_report")
    file_name = str(st.session_state.get("popps_upload_name") or "POPPS report")
    report_fp = str(library.get("active_fingerprint") or "")
    if report is not None:
        report_fp = popps_report_fingerprint(report, file_name) or report_fp
    elif report_fp:
        entry = (library.get("reports") or {}).get(report_fp) or {}
        if entry.get("report"):
            try:
                report = popps_report_from_storage_dict(entry["report"])
                file_name = str(entry.get("file_name") or file_name)
            except Exception:
                report = None

    reviews_store = load_popps_reviews_store(supabase, report_fp) if report_fp else {}
    status = evaluate_popps_notes_compliance(
        supabase,
        library=library,
        report_fingerprint=report_fp,
        reviews_store=reviews_store,
        report=report,
        run_manager_alert=True,
    )
    st.session_state["_popps_compliance_status"] = status
    return status


def render_popps_notes_compliance_messages(
    status: dict | None,
    *,
    is_warranty_admin: bool,
    on_popps_tab: bool = False,
) -> None:
    if not status or not is_warranty_admin:
        return
    if status.get("has_notes"):
        return

    days = int(status.get("days_since_upload") or 0)
    upload_label = str(status.get("upload_label") or "POPPS report")
    uploaded_display = str(status.get("uploaded_at") or "")[:19].replace("T", " ")
    categories = status.get("categories") or []
    cat_text = "; ".join(categories[:6])
    if len(categories) > 6:
        cat_text += f"; +{len(categories) - 6} more"

    if status.get("needs_warning"):
        message = (
            f"**POPPS notes due:** {days} days since the latest POPPS upload "
            f"({upload_label}, {uploaded_display} UTC) and **no claim notes** have been added yet. "
            f"Open **Repair groups and related claims (add notes)**"
        )
        if on_popps_tab:
            message += " below"
        message += (
            f" and add notes under each repair group with sample claims"
            f"{f' ({cat_text})' if cat_text else ''}."
        )
        if days >= POPPS_NOTES_MANAGER_ALERT_DAYS:
            message += " Managers have been emailed about this overdue review."
        else:
            message += (
                f" Managers are emailed automatically if notes are still missing after "
                f"day {POPPS_NOTES_MANAGER_ALERT_DAYS}."
            )
        st.warning(message)

    if status.get("manager_alert_error") and is_warranty_admin:
        st.caption(
            f"Manager alert email could not be sent ({status['manager_alert_error']}). "
            "Confirm report SMTP secrets are configured."
        )


def render_popps_compliance_global_banner(supabase, *, is_warranty_admin: bool) -> None:
    """Warranty Admin reminder on any tab (once per session)."""
    if not is_warranty_admin:
        return
    if st.session_state.get("_popps_global_compliance_banner"):
        return
    status = st.session_state.get("_popps_compliance_status")
    if not status or not status.get("needs_warning"):
        return
    days = int(status.get("days_since_upload") or 0)
    upload_label = str(status.get("upload_label") or "POPPS report")
    st.warning(
        f"POPPS claim notes are overdue ({days} days since {upload_label}). "
        "Open the **POPPS Report** tab → **Repair groups and related claims (add notes)**."
    )
    st.session_state["_popps_global_compliance_banner"] = True


def _is_popps_review_exempt_section(section: PoppsPrioritySection) -> bool:
    """Sections shown as plain summary only — no gold header or per-claim notes."""
    if _is_message_code_priority_section(section):
        return True
    rank = str(section.priority_rank or "").strip()
    if rank == "5":
        return True
    lop = str(section.labor_operation_code or "").strip()
    desc = str(section.repair_description or "").upper()
    if lop == "0200" and "SUSPENSION" in desc:
        return True
    return not section.claims


def _note_thread_from_entry(entry: dict | None) -> list[dict]:
    entry = entry or {}
    thread = entry.get("note_thread")
    if isinstance(thread, list):
        return [dict(note) for note in thread if isinstance(note, dict)]
    legacy = str(entry.get("notes") or "").strip()
    if not legacy:
        return []
    return [
        {
            "id": "legacy",
            "text": legacy,
            "author": str(entry.get("reviewed_by") or "").strip(),
            "created_at": str(entry.get("updated_at") or ""),
            "deleted": False,
        }
    ]


def _active_notes(entry: dict | None) -> list[dict]:
    return [note for note in _note_thread_from_entry(entry) if not note.get("deleted")]


def _notes_export_text(entry: dict | None) -> str:
    parts = []
    for note in _active_notes(entry):
        author = str(note.get("author") or "").strip() or "Unknown"
        text = str(note.get("text") or "").strip()
        if text:
            parts.append(f"{author}: {text}")
    return "\n---\n".join(parts)


def _review_status_label(entry: dict | None) -> str:
    entry = entry or {}
    if entry.get("reviewed_charged_back"):
        return "Charged claim back"
    if entry.get("reviewed_no_issues"):
        return "No issues found"
    if _active_notes(entry):
        return "Notes only"
    return "Not reviewed"


def _claim_select_label(claim: PoppsClaimRow) -> str:
    number = str(claim.claim_condition_or_number or "").strip()
    if claim.row_type == "message":
        return f"Claim {number}" if number else "Claim"
    return f"RO {number}" if number else "Repair order"


def _claim_ro_or_claim_number(claim: PoppsClaimRow) -> str:
    return str(claim.claim_condition_or_number or "").strip()


def _append_session_popps_audit_row(row: dict) -> None:
    log = list(st.session_state.get("popps_audit_log_session") or [])
    log.append(row)
    st.session_state.popps_audit_log_session = log[-500:]


def append_popps_audit_log(supabase, row: dict) -> None:
    """Append-only audit row (Supabase table or session fallback)."""
    row = dict(row)
    row.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    _append_session_popps_audit_row(row)
    if supabase is None:
        return
    try:
        supabase.table("popps_review_log").insert(row).execute()
    except Exception:
        pass


def fetch_popps_audit_history(supabase, report_fingerprint: str) -> list[dict]:
    """All saved review events for this POPPS file (newest first)."""
    session_rows = [
        r
        for r in (st.session_state.get("popps_audit_log_session") or [])
        if r.get("report_fingerprint") == report_fingerprint
    ]
    if supabase is None:
        return sorted(session_rows, key=lambda r: r.get("created_at", ""), reverse=True)

    db_rows: list[dict] = []
    try:
        response = (
            supabase.table("popps_review_log")
            .select("*")
            .eq("report_fingerprint", report_fingerprint)
            .order("created_at", desc=True)
            .limit(2000)
            .execute()
        )
        db_rows = list(response.data or [])
    except Exception:
        pass

    if not db_rows:
        return sorted(session_rows, key=lambda r: r.get("created_at", ""), reverse=True)

    seen: set[str] = set()
    merged: list[dict] = []
    for row in db_rows + session_rows:
        stamp = f"{row.get('created_at')}|{row.get('entry_key')}|{row.get('notes')}"
        if stamp in seen:
            continue
        seen.add(stamp)
        merged.append(row)
    return sorted(merged, key=lambda r: r.get("created_at", ""), reverse=True)


def build_popps_audit_snapshot_df(reviews_store: dict[str, dict]) -> pd.DataFrame:
    """Latest review state per category / repair order for export."""
    rows: list[dict[str, Any]] = []
    for entry_key in sorted(reviews_store.keys()):
        entry = reviews_store[entry_key] or {}
        rows.append(
            {
                "Entry Key": entry_key,
                "Category": entry.get("category_label") or entry_key,
                "Priority / Section": entry.get("priority_label") or "",
                "Labor Operation": entry.get("labor_operation_code") or "",
                "RO or Claim Number": entry.get("ro_or_claim_number") or "",
                "Vehicle": entry.get("vehicle_identification") or "",
                "Review Status": _review_status_label(entry),
                "Notes": _notes_export_text(entry),
                "Reviewed By": entry.get("reviewed_by") or "",
                "Last Updated (UTC)": str(entry.get("updated_at") or "")[:19].replace("T", " "),
            }
        )
    return pd.DataFrame(rows)


def build_popps_audit_history_df(history: list[dict]) -> pd.DataFrame:
    if not history:
        return pd.DataFrame()
    rows = []
    for row in history:
        rows.append(
            {
                "Saved At (UTC)": str(row.get("created_at") or "")[:19].replace("T", " "),
                "Category": row.get("category_label") or "",
                "Priority / Section": row.get("priority_label") or "",
                "Labor Operation": row.get("labor_operation_code") or "",
                "RO or Claim Number": row.get("ro_or_claim_number") or "",
                "Vehicle": row.get("vehicle_identification") or "",
                "Review Status": _review_status_label(row),
                "Notes": row.get("notes") or "",
                "Reviewed By": row.get("reviewed_by") or "",
            }
        )
    return pd.DataFrame(rows)


def _merge_review_entry(
    existing: dict | None,
    *,
    entry_key: str,
    category_label: str,
    reviewer: str,
    report_context: dict[str, str] | None,
    priority_label: str,
    labor_operation_code: str,
    ro_or_claim_number: str,
    vehicle_identification: str,
    reviewed_no_issues: bool | None = None,
    reviewed_charged_back: bool | None = None,
    note_thread: list[dict] | None = None,
) -> dict:
    ctx = report_context or {}
    prior = dict(existing or {})
    updated_at = datetime.now(timezone.utc).isoformat()
    entry = {
        "entry_key": entry_key,
        "category_label": category_label,
        "reviewed_no_issues": (
            bool(reviewed_no_issues)
            if reviewed_no_issues is not None
            else bool(prior.get("reviewed_no_issues"))
        ),
        "reviewed_charged_back": (
            bool(reviewed_charged_back)
            if reviewed_charged_back is not None
            else bool(prior.get("reviewed_charged_back"))
        ),
        "note_thread": note_thread if note_thread is not None else _note_thread_from_entry(prior),
        "reviewed_by": reviewer or prior.get("reviewed_by") or "",
        "updated_at": updated_at,
        "dealer_code": ctx.get("dealer_code") or prior.get("dealer_code") or "",
        "report_period": ctx.get("report_period") or prior.get("report_period") or "",
        "source_file": ctx.get("source_file") or prior.get("source_file") or "",
        "priority_label": priority_label or prior.get("priority_label") or "",
        "labor_operation_code": labor_operation_code or prior.get("labor_operation_code") or "",
        "ro_or_claim_number": ro_or_claim_number or prior.get("ro_or_claim_number") or "",
        "vehicle_identification": vehicle_identification or prior.get("vehicle_identification") or "",
    }
    if entry["reviewed_no_issues"] and entry["reviewed_charged_back"]:
        entry["reviewed_charged_back"] = False
    entry["notes"] = _notes_export_text(entry)
    return entry


def _persist_popps_review_entry(
    supabase,
    report_fingerprint: str,
    entry_key: str,
    entry: dict,
    *,
    reviewer: str,
    audit_notes: str,
    audit_action: str = "save_review",
) -> None:
    cache_key = f"popps_reviews_{report_fingerprint}"
    store = dict(st.session_state.get(cache_key) or load_popps_reviews_store(supabase, report_fingerprint))
    store[entry_key] = entry
    st.session_state[cache_key] = store

    updated_at = str(entry.get("updated_at") or "")
    audit_row = {
        "report_fingerprint": report_fingerprint,
        "entry_key": entry_key,
        "dealer_code": entry.get("dealer_code"),
        "report_period": entry.get("report_period"),
        "source_file": entry.get("source_file"),
        "priority_label": entry.get("priority_label"),
        "labor_operation_code": entry.get("labor_operation_code"),
        "ro_or_claim_number": entry.get("ro_or_claim_number"),
        "vehicle_identification": entry.get("vehicle_identification"),
        "category_label": entry.get("category_label"),
        "reviewed_no_issues": entry.get("reviewed_no_issues"),
        "reviewed_charged_back": entry.get("reviewed_charged_back"),
        "notes": audit_notes,
        "reviewed_by": reviewer,
        "review_updated_at": updated_at,
        "created_at": updated_at,
        "audit_action": audit_action,
    }
    append_popps_audit_log(supabase, audit_row)

    if supabase is None:
        return

    try:
        response = (
            supabase.table("dealer_settings")
            .select("popps_reviews")
            .eq("id", 1)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        blob = _normalize_popps_reviews_blob(rows[0].get("popps_reviews") if rows else {})
        reports = dict(blob["reports"])
        report_data = dict(reports.get(report_fingerprint) or {})
        report_entries = dict(report_data.get("entries") or {})
        report_entries[entry_key] = entry
        report_data["entries"] = report_entries
        report_data["dealer_code"] = entry.get("dealer_code")
        report_data["report_period"] = entry.get("report_period")
        report_data["source_file"] = entry.get("source_file")
        report_data["updated_at"] = updated_at
        reports[report_fingerprint] = report_data
        supabase.table("dealer_settings").update(
            {"popps_reviews": {"reports": reports}}
        ).eq("id", 1).execute()
    except Exception as exc:
        st.warning(
            "Review saved for this session and audit log, but cloud JSON storage failed. "
            f"Confirm dealer_settings.popps_reviews exists. ({exc})"
        )


def save_popps_review_entry(
    supabase,
    report_fingerprint: str,
    entry_key: str,
    *,
    reviewed_no_issues: bool,
    reviewed_charged_back: bool,
    reviewer: str,
    category_label: str,
    report_context: dict[str, str] | None = None,
    priority_label: str = "",
    labor_operation_code: str = "",
    ro_or_claim_number: str = "",
    vehicle_identification: str = "",
) -> None:
    cache_key = f"popps_reviews_{report_fingerprint}"
    store = dict(st.session_state.get(cache_key) or load_popps_reviews_store(supabase, report_fingerprint))
    entry = _merge_review_entry(
        store.get(entry_key),
        entry_key=entry_key,
        category_label=category_label,
        reviewer=reviewer,
        report_context=report_context,
        priority_label=priority_label,
        labor_operation_code=labor_operation_code,
        ro_or_claim_number=ro_or_claim_number,
        vehicle_identification=vehicle_identification,
        reviewed_no_issues=reviewed_no_issues,
        reviewed_charged_back=reviewed_charged_back,
    )
    _persist_popps_review_entry(
        supabase,
        report_fingerprint,
        entry_key,
        entry,
        reviewer=reviewer,
        audit_notes=_notes_export_text(entry),
        audit_action="save_review",
    )


def add_popps_review_note(
    supabase,
    report_fingerprint: str,
    entry_key: str,
    *,
    note_text: str,
    reviewer: str,
    category_label: str,
    report_context: dict[str, str] | None = None,
    priority_label: str = "",
    labor_operation_code: str = "",
    ro_or_claim_number: str = "",
    vehicle_identification: str = "",
) -> None:
    text = str(note_text or "").strip()
    if not text:
        return

    cache_key = f"popps_reviews_{report_fingerprint}"
    store = dict(st.session_state.get(cache_key) or load_popps_reviews_store(supabase, report_fingerprint))
    thread = _note_thread_from_entry(store.get(entry_key))
    thread.append(
        {
            "id": secrets.token_hex(8),
            "text": text,
            "author": reviewer,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "deleted": False,
        }
    )
    entry = _merge_review_entry(
        store.get(entry_key),
        entry_key=entry_key,
        category_label=category_label,
        reviewer=reviewer,
        report_context=report_context,
        priority_label=priority_label,
        labor_operation_code=labor_operation_code,
        ro_or_claim_number=ro_or_claim_number,
        vehicle_identification=vehicle_identification,
        note_thread=thread,
    )
    _persist_popps_review_entry(
        supabase,
        report_fingerprint,
        entry_key,
        entry,
        reviewer=reviewer,
        audit_notes=text,
        audit_action="add_note",
    )


def delete_popps_review_note(
    supabase,
    report_fingerprint: str,
    entry_key: str,
    *,
    note_id: str,
    reviewer: str,
) -> bool:
    cache_key = f"popps_reviews_{report_fingerprint}"
    store = dict(st.session_state.get(cache_key) or load_popps_reviews_store(supabase, report_fingerprint))
    existing = store.get(entry_key)
    if not existing:
        return False

    thread = _note_thread_from_entry(existing)
    changed = False
    for note in thread:
        if str(note.get("id") or "") == note_id and not note.get("deleted"):
            note["deleted"] = True
            note["deleted_by"] = reviewer
            note["deleted_at"] = datetime.now(timezone.utc).isoformat()
            changed = True
            break
    if not changed:
        return False

    entry = dict(existing)
    entry["note_thread"] = thread
    entry["notes"] = _notes_export_text(entry)
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    _persist_popps_review_entry(
        supabase,
        report_fingerprint,
        entry_key,
        entry,
        reviewer=reviewer,
        audit_notes=f"Deleted note {note_id}",
        audit_action="delete_note",
    )
    return True


def _claim_heading(claim: PoppsClaimRow) -> str:
    if claim.row_type == "message":
        return (
            f"Claim {claim.claim_condition_or_number} · "
            f"Message Code {claim.labor_operation_or_message_code} · "
            f"{claim.vehicle_identification}"
        )
    return (
        f"Repair Order {claim.claim_condition_or_number} · "
        f"Vehicle {claim.vehicle_identification} · "
        f"Labor Operation {claim.labor_operation_or_message_code}"
    )


def _render_claim_detail_fields(claim: PoppsClaimRow) -> None:
    """Readable claim / repair order detail (shown after user selects an RO)."""
    if claim.row_type == "message":
        fields = [
            ("Fleet Vehicle", claim.fleet_vehicle),
            ("Vehicle Identification", claim.vehicle_identification),
            ("Vehicle Number", claim.vehicle_number),
            ("Claim Number", claim.claim_condition_or_number),
            ("Message Code", claim.labor_operation_or_message_code),
            ("Authorization Identifier", claim.authorization_flag),
            ("Technician Identification Number", claim.technician_id),
            ("Mileage", claim.mileage),
            ("Expense Amount", claim.expense_amount),
            ("Days to Process", claim.days_to_process),
            ("Concern Codes (plain language)", claim.concern_codes_plain),
        ]
    else:
        fields = [
            ("Repair Order Number", claim.claim_condition_or_number),
            ("Vehicle Identification", claim.vehicle_identification),
            ("Vehicle Number", claim.vehicle_number),
            ("Labor Operation Code", claim.labor_operation_or_message_code),
            ("Technician Identification Number", claim.technician_id),
            ("Mileage", claim.mileage),
            ("Authorization Flag", claim.authorization_flag or "—"),
            ("Expense Amount", claim.expense_amount),
            ("Concern Codes (plain language)", claim.concern_codes_plain),
        ]
    for label, value in fields:
        if str(value or "").strip():
            st.markdown(f"**{label}:** {value}")


def _render_popps_review_controls(
    *,
    entry_key: str,
    category_label: str,
    reviews_store: dict[str, dict],
    supabase,
    report_fingerprint: str,
    reviewer: str,
    report_context: dict[str, str] | None = None,
    priority_label: str = "",
    labor_operation_code: str = "",
    ro_or_claim_number: str = "",
    vehicle_identification: str = "",
    heading: str | None = None,
    widget_scope: str = "",
    notes_admin: bool = False,
) -> None:
    """Review checkboxes and append-only note thread for one POPPS claim."""
    stored = reviews_store.get(entry_key) or {}
    suffix = _safe_widget_suffix(entry_key, report_fingerprint, scope=widget_scope)
    no_key = f"popps_no_issues_{suffix}"
    charge_key = f"popps_charged_{suffix}"
    new_note_key = f"popps_new_note_{suffix}"

    if no_key not in st.session_state:
        st.session_state[no_key] = bool(stored.get("reviewed_no_issues"))
    if charge_key not in st.session_state:
        st.session_state[charge_key] = bool(stored.get("reviewed_charged_back"))

    def _clear_other(other_field: str) -> None:
        st.session_state[other_field] = False

    st.markdown(f"**{heading or 'Review'}**")
    if category_label and heading != category_label:
        st.caption(category_label)
    if stored.get("reviewed_by"):
        updated = str(stored.get("updated_at") or "")[:19].replace("T", " ")
        st.caption(f"Last review status saved by {stored.get('reviewed_by')} · {updated or '—'}")

    c1, c2 = st.columns(2)
    with c1:
        st.checkbox(
            "Reviewed RO, no issues found",
            key=no_key,
            on_change=_clear_other,
            args=(charge_key,),
        )
    with c2:
        st.checkbox(
            "Reviewed RO, charged claim back",
            key=charge_key,
            on_change=_clear_other,
            args=(no_key,),
        )

    if st.button("Save review status", key=f"popps_save_{suffix}", use_container_width=True):
        save_popps_review_entry(
            supabase,
            report_fingerprint,
            entry_key,
            reviewed_no_issues=bool(st.session_state.get(no_key)),
            reviewed_charged_back=bool(st.session_state.get(charge_key)),
            reviewer=reviewer,
            category_label=category_label,
            report_context=report_context,
            priority_label=priority_label,
            labor_operation_code=labor_operation_code,
            ro_or_claim_number=ro_or_claim_number,
            vehicle_identification=vehicle_identification,
        )
        st.success("Review status saved to audit trail.")
        st.rerun()

    st.markdown("**Notes**")
    st.caption("Notes cannot be edited after they are added. Add another note anytime. Only Admin can delete a note.")
    active_notes = _active_notes(stored)
    if active_notes:
        for note in active_notes:
            author = str(note.get("author") or "").strip() or "Unknown"
            created = str(note.get("created_at") or "")[:19].replace("T", " ")
            note_id = str(note.get("id") or "")
            when = f" · {created} UTC" if created else ""
            with st.container(border=True):
                st.markdown(f"**{author}**{when}")
                st.markdown(str(note.get("text") or ""))
            if notes_admin and note_id:
                if st.button(
                    "Delete note (Admin)",
                    key=f"popps_del_{suffix}_{note_id}",
                    type="secondary",
                ):
                    if delete_popps_review_note(
                        supabase,
                        report_fingerprint,
                        entry_key,
                        note_id=note_id,
                        reviewer=reviewer,
                    ):
                        st.success("Note removed.")
                        st.rerun()
                    else:
                        st.warning("Could not delete that note.")
    else:
        st.caption("No notes yet for this claim.")

    st.text_area(
        "Add a note",
        key=new_note_key,
        height=88,
        placeholder="Document what you verified, who you spoke with, or charge-back details.",
    )

    if st.button("Add note", key=f"popps_add_note_{suffix}", use_container_width=True):
        note_text = str(st.session_state.get(new_note_key) or "").strip()
        if not note_text:
            st.warning("Enter a note before saving.")
        else:
            add_popps_review_note(
                supabase,
                report_fingerprint,
                entry_key,
                note_text=note_text,
                reviewer=reviewer,
                category_label=category_label,
                report_context=report_context,
                priority_label=priority_label,
                labor_operation_code=labor_operation_code,
                ro_or_claim_number=ro_or_claim_number,
                vehicle_identification=vehicle_identification,
            )
            st.success("Note added.")
            st.rerun()


def _render_popps_priority_section(
    section: PoppsPrioritySection,
    *,
    reviews_store: dict[str, dict],
    supabase,
    report: PoppsReport,
    file_name: str,
    report_fp: str,
    reviewer_name: str,
    report_ctx: dict[str, str],
    notes_admin: bool = False,
) -> None:
    """Priority / message-code expander with per-claim notes and review."""
    title = (
        f"{section.priority_label} — "
        f"Labor Operation {section.labor_operation_code} — "
        f"{section.repair_description}"
    )
    review_exempt = _is_popps_review_exempt_section(section)

    if review_exempt:
        _render_popps_expander_header(title, "plain")
        _popps_expander_anchor("popps-anchor-plain")
        expander_label = "View details"
    else:
        _render_popps_expander_header(title, "priority")
        _popps_expander_anchor("popps-anchor-priority")
        expander_label = "View claims and notes"

    expander_key = f"popps_pri_{_safe_widget_suffix(section_review_entry_key(section), report_fp, scope='exp')}"
    with st.expander(expander_label, expanded=False, key=expander_key):
        c1, c2, c3 = st.columns(3)
        c1.metric("Quarters on POPPS", section.quarters_on_popps or "—")
        c2.metric("Total Conditions", section.total_conditions or "—")
        c3.metric(
            "Group values (Mar / Apr / May)",
            f"{section.group_march} / {section.group_april} / {section.group_may}",
        )
        st.markdown(f"**Concern codes:** {section.concern_codes_plain}")

        if not section.claims:
            if section.no_claims_message:
                st.info(section.no_claims_message)
            else:
                st.caption("No sample claims were listed for this group in the PDF.")
            return

        st.markdown("**Claims in this category**")
        st.dataframe(
            _claims_dataframe(section.claims),
            use_container_width=True,
            hide_index=True,
        )

        if review_exempt:
            return

        st.markdown(
            '<div class="popps-notes-panel">'
            "<h4>Notes &amp; review (below the table)</h4>"
            "<p>Each sample claim needs its own notes. Open a "
            "<strong>repair order tab</strong> to document that RO for your audit trail.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown("**Review each repair order / claim**")
        tab_labels: list[str] = []
        for claim_index, claim in enumerate(section.claims):
            claim_key = claim_review_entry_key(section, claim, claim_index=claim_index)
            stored = reviews_store.get(claim_key) or {}
            status = _review_status_label(stored)
            label = _claim_select_label(claim)
            if status != "Not reviewed":
                label = f"{label} ✓"
            tab_labels.append(label)

        claim_tabs = st.tabs(tab_labels)
        for claim_index, (claim, tab) in enumerate(zip(section.claims, claim_tabs)):
            claim_key = claim_review_entry_key(section, claim, claim_index=claim_index)
            widget_scope = f"pr{section.priority_rank}_c{claim_index}"
            with tab:
                st.markdown(f"#### {_claim_select_label(claim)}")
                _render_claim_detail_fields(claim)
                _render_popps_review_controls(
                    entry_key=claim_key,
                    category_label=_claim_heading(claim),
                    reviews_store=reviews_store,
                    supabase=supabase,
                    report_fingerprint=report_fp,
                    reviewer=reviewer_name,
                    report_context=report_ctx,
                    priority_label=section.priority_label,
                    labor_operation_code=section.labor_operation_code,
                    ro_or_claim_number=_claim_ro_or_claim_number(claim),
                    vehicle_identification=claim.vehicle_identification,
                    heading="Notes and review status",
                    widget_scope=widget_scope,
                    notes_admin=notes_admin,
                )


def _render_popps_audit_panel(
    *,
    reviews_store: dict[str, dict],
    supabase,
    report_fp: str,
    file_name: str,
    report: PoppsReport,
) -> None:
    snapshot = build_popps_audit_snapshot_df(reviews_store)
    history = fetch_popps_audit_history(supabase, report_fp)
    history_df = build_popps_audit_history_df(history)

    audit_key = f"popps_audit_{_safe_widget_suffix(report_fp, file_name, scope='trail')}"
    with st.expander(
        "POPPS review audit trail",
        expanded=bool(len(snapshot)),
        key=audit_key,
    ):
        st.caption(
            "Every **Save review status** or **Add note** writes an append-only audit record (cloud table when configured). "
            "Download the snapshot for audits and factory inquiries."
        )
        st.markdown(
            f"**Dealer {report.dealer_code}** · **Period** {report.period_label or '—'} · "
            f"**File** {file_name}"
        )
        if snapshot.empty:
            st.info("No POPPS reviews saved for this file yet.")
        else:
            st.dataframe(snapshot, use_container_width=True, hide_index=True)
            st.download_button(
                "Download review snapshot (CSV)",
                snapshot.to_csv(index=False),
                file_name=f"popps_reviews_{report.dealer_code}_{report.period_label or 'report'}.csv".replace(
                    " ", "_"
                ),
                mime="text/csv",
                key=f"popps_audit_snapshot_csv_{audit_key}",
            )
        if not history_df.empty:
            st.markdown("**Full save history (newest first)**")
            st.dataframe(history_df.head(200), use_container_width=True, hide_index=True)
            st.download_button(
                "Download full audit history (CSV)",
                history_df.to_csv(index=False),
                file_name=f"popps_audit_history_{report.dealer_code}.csv".replace(" ", "_"),
                mime="text/csv",
                key=f"popps_audit_history_csv_{audit_key}",
            )


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


def _popps_expander_anchor(css_class: str) -> None:
    """Hidden marker so the next Streamlit expander can be styled via CSS."""
    st.markdown(
        f'<div class="popps-expander-anchor {css_class}" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )


def _render_popps_expander_header(title: str, variant: str) -> None:
    """Prominent label row above a POPPS expander (archive or priority section)."""
    st.markdown(
        f'<div class="popps-expander-header popps-expander-header--{variant}">'
        f'<span class="popps-expander-header-text">{html.escape(title)}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _summary_row_label(row: PoppsSummaryRow) -> str:
    return (
        f"{row.rank_label} — Labor Operation {row.labor_operation_code} — "
        f"{row.repair_description}"
    )


def _popps_item_count_label(count: int) -> str:
    return f" ({count} item{'s' if count != 1 else ''})"


def popps_page_css(theme: str = "Dark") -> str:
    is_light = str(theme).lower() == "light"
    card_bg = "rgba(244, 248, 252, 0.96)" if is_light else "rgba(7, 19, 34, 0.88)"
    border = "#b6c7da" if is_light else "rgba(62, 150, 255, 0.28)"
    text = "#0f172a" if is_light else "#f8fbff"
    muted = "#475569" if is_light else "#94a3b8"
    popps_scope = ".stApp:has(.popps-workspace-marker)"
    archive_summary_bg = (
        "linear-gradient(135deg, rgba(14, 165, 233, 0.22), rgba(59, 130, 246, 0.08))"
        if is_light
        else "linear-gradient(135deg, rgba(14, 165, 233, 0.42), rgba(37, 99, 235, 0.14))"
    )
    archive_border = "#0284c7" if is_light else "rgba(56, 189, 248, 0.85)"
    archive_glow = "0 4px 22px rgba(2, 132, 199, 0.18)" if is_light else "0 4px 28px rgba(56, 189, 248, 0.22)"
    archive_medium_bg = (
        "linear-gradient(135deg, rgba(14, 165, 233, 0.28), rgba(59, 130, 246, 0.1))"
        if is_light
        else "linear-gradient(135deg, rgba(14, 165, 233, 0.38), rgba(37, 99, 235, 0.16))"
    )
    archive_medium_glow = (
        "0 2px 16px rgba(2, 132, 199, 0.14)"
        if is_light
        else "0 4px 20px rgba(56, 189, 248, 0.2)"
    )
    priority_summary_bg = (
        "linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(251, 191, 36, 0.06))"
        if is_light
        else "linear-gradient(135deg, rgba(245, 158, 11, 0.34), rgba(251, 191, 36, 0.1))"
    )
    priority_border = "#d97706" if is_light else "rgba(251, 191, 36, 0.75)"
    priority_glow = "0 4px 22px rgba(217, 119, 6, 0.16)" if is_light else "0 4px 28px rgba(251, 191, 36, 0.18)"
    anchor_container = f'{popps_scope} div[data-testid="stElementContainer"]'
    expander_adjacent_archive = (
        f"{anchor_container}:has(.popps-anchor-archive) + div[data-testid='stElementContainer'] "
        "details[data-testid='stExpander']"
    )
    expander_adjacent_priority = (
        f"{anchor_container}:has(.popps-anchor-priority) + div[data-testid='stElementContainer'] "
        "details[data-testid='stExpander']"
    )
    expander_in_archive = (
        f"{anchor_container}:has(.popps-anchor-archive) details[data-testid='stExpander']"
    )
    expander_in_priority = (
        f"{anchor_container}:has(.popps-anchor-priority) details[data-testid='stExpander']"
    )
    expander_adjacent_plain = (
        f"{anchor_container}:has(.popps-anchor-plain) + div[data-testid='stElementContainer'] "
        "details[data-testid='stExpander']"
    )
    expander_in_plain = (
        f"{anchor_container}:has(.popps-anchor-plain) details[data-testid='stExpander']"
    )
    expander_adjacent_summary_parent = (
        f"{anchor_container}:has(.popps-anchor-summary-parent) + div[data-testid='stElementContainer'] "
        "details[data-testid='stExpander']"
    )
    expander_in_summary_parent = (
        f"{anchor_container}:has(.popps-anchor-summary-parent) details[data-testid='stExpander']"
    )
    expander_adjacent_summary_child = (
        f"{anchor_container}:has(.popps-anchor-summary-child) + div[data-testid='stElementContainer'] "
        "details[data-testid='stExpander']"
    )
    expander_in_summary_child = (
        f"{anchor_container}:has(.popps-anchor-summary-child) details[data-testid='stExpander']"
    )
    expander_archive = f"{expander_adjacent_archive}, {expander_in_archive}"
    expander_priority = f"{expander_adjacent_priority}, {expander_in_priority}"
    expander_plain = f"{expander_adjacent_plain}, {expander_in_plain}"
    expander_adjacent_repair_notes = (
        f"{anchor_container}:has(.popps-anchor-repair-notes) + div[data-testid='stElementContainer'] "
        "details[data-testid='stExpander']"
    )
    expander_in_repair_notes = (
        f"{anchor_container}:has(.popps-anchor-repair-notes) details[data-testid='stExpander']"
    )
    expander_summary_parent = f"{expander_adjacent_summary_parent}, {expander_in_summary_parent}"
    expander_summary_child = f"{expander_adjacent_summary_child}, {expander_in_summary_child}"
    expander_repair_notes = f"{expander_adjacent_repair_notes}, {expander_in_repair_notes}"
    notes_border = "#059669" if is_light else "rgba(52, 211, 153, 0.9)"
    notes_header_bg = (
        "linear-gradient(135deg, rgba(16, 185, 129, 0.32), rgba(5, 150, 105, 0.12))"
        if is_light
        else "linear-gradient(135deg, rgba(16, 185, 129, 0.5), rgba(6, 95, 70, 0.22))"
    )
    notes_summary_bg = (
        "linear-gradient(135deg, rgba(16, 185, 129, 0.24), rgba(5, 150, 105, 0.08))"
        if is_light
        else "linear-gradient(135deg, rgba(16, 185, 129, 0.38), rgba(6, 95, 70, 0.16))"
    )
    notes_glow = (
        "0 4px 24px rgba(5, 150, 105, 0.2)"
        if is_light
        else "0 4px 28px rgba(52, 211, 153, 0.28)"
    )
    summary_parent_bg = (
        "linear-gradient(135deg, rgba(100, 116, 139, 0.2), rgba(71, 85, 105, 0.08))"
        if is_light
        else "linear-gradient(135deg, rgba(148, 163, 184, 0.28), rgba(51, 65, 85, 0.14))"
    )
    summary_child_bg = (
        "linear-gradient(135deg, rgba(71, 85, 105, 0.12), rgba(30, 41, 59, 0.05))"
        if is_light
        else "linear-gradient(135deg, rgba(51, 65, 85, 0.32), rgba(15, 23, 42, 0.12))"
    )
    summary_border = "#64748b" if is_light else "rgba(148, 163, 184, 0.55)"
    archive_header_bg = (
        "linear-gradient(135deg, rgba(14, 165, 233, 0.35), rgba(37, 99, 235, 0.12))"
        if is_light
        else "linear-gradient(135deg, rgba(14, 165, 233, 0.55), rgba(30, 64, 175, 0.22))"
    )
    priority_header_bg = (
        "linear-gradient(135deg, rgba(245, 158, 11, 0.32), rgba(251, 191, 36, 0.1))"
        if is_light
        else "linear-gradient(135deg, rgba(245, 158, 11, 0.48), rgba(180, 83, 9, 0.18))"
    )
    return f"""
    .popps-expander-header {{
        margin: 0.65rem 0 0 !important;
        padding: 0.95rem 1.15rem !important;
        border-radius: 14px 14px 0 0 !important;
        border: 2px solid transparent !important;
        box-sizing: border-box !important;
    }}
    .popps-expander-header-text {{
        display: block !important;
        color: {text} !important;
        font-size: 1.08rem !important;
        font-weight: 700 !important;
        line-height: 1.35 !important;
        letter-spacing: 0.01em !important;
    }}
    .popps-expander-header--archive {{
        background: {archive_header_bg} !important;
        border: 2px solid {archive_border} !important;
        border-left: 5px solid #38bdf8 !important;
        box-shadow: {archive_glow} !important;
    }}
    .popps-expander-header--notes {{
        background: {notes_header_bg} !important;
        border: 2px solid {notes_border} !important;
        border-left: 6px solid #34d399 !important;
        box-shadow: {notes_glow} !important;
    }}
    .popps-expander-header--notes .popps-expander-header-text {{
        color: {text} !important;
        font-size: 1.1rem !important;
    }}
    .popps-archive-zone {{
        display: none !important;
        height: 0 !important;
        width: 0 !important;
        pointer-events: none !important;
    }}
    {popps_scope}:has(.popps-archive-zone) {expander_archive} {{
        margin: 0 0 1.15rem 0 !important;
        border-radius: 0 0 14px 14px !important;
        border: 2px solid {archive_border} !important;
        border-top: none !important;
        background: {card_bg} !important;
        box-shadow: {archive_glow} !important;
        overflow: hidden !important;
    }}
    {popps_scope}:has(.popps-archive-zone) {expander_archive} > summary,
    {popps_scope}:has(.popps-archive-zone) {expander_archive}[open] > summary,
    {popps_scope}:has(.popps-archive-zone) {expander_archive} > summary:not(:hover):not(:focus):not(:focus-visible) {{
        background: {archive_medium_bg} !important;
        background-image: {archive_medium_bg} !important;
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        padding: 0.8rem 1.1rem !important;
        border-bottom: 1px solid {archive_border} !important;
    }}
    {popps_scope}:has(.popps-repair-notes-zone) {expander_repair_notes} {{
        margin: 0 0 1.15rem 0 !important;
        border-radius: 0 0 14px 14px !important;
        border: 2px solid {notes_border} !important;
        border-top: none !important;
        background: {card_bg} !important;
        box-shadow: {notes_glow} !important;
        overflow: hidden !important;
    }}
    {popps_scope}:has(.popps-repair-notes-zone) {expander_repair_notes} > summary,
    {popps_scope}:has(.popps-repair-notes-zone) {expander_repair_notes}[open] > summary,
    {popps_scope}:has(.popps-repair-notes-zone) {expander_repair_notes} > summary:not(:hover):not(:focus):not(:focus-visible) {{
        background: {notes_summary_bg} !important;
        background-image: {notes_summary_bg} !important;
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        font-size: 1rem !important;
        font-weight: 700 !important;
        padding: 0.8rem 1.1rem !important;
        border-bottom: 1px solid {notes_border} !important;
    }}
    {popps_scope}:has(.popps-repair-notes-zone) {expander_repair_notes} > summary *,
    {popps_scope}:has(.popps-repair-notes-zone) {expander_repair_notes} > summary p,
    {popps_scope}:has(.popps-repair-notes-zone) {expander_repair_notes} > summary span,
    {popps_scope}:has(.popps-repair-notes-zone) {expander_repair_notes} > summary div {{
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        font-weight: 700 !important;
    }}
    {popps_scope}:has(.popps-archive-zone) {expander_archive} > summary *,
    {popps_scope}:has(.popps-archive-zone) {expander_archive} > summary p,
    {popps_scope}:has(.popps-archive-zone) {expander_archive} > summary span,
    {popps_scope}:has(.popps-archive-zone) {expander_archive} > summary div {{
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        font-weight: 700 !important;
    }}
    {popps_scope}:has(.popps-summary-parent-zone) {expander_summary_parent} {{
        margin: 0.75rem 0 0.5rem 0 !important;
        border-radius: 12px !important;
        border: 2px solid {summary_border} !important;
        background: {card_bg} !important;
        overflow: hidden !important;
    }}
    {popps_scope}:has(.popps-summary-parent-zone) {expander_summary_parent} > summary,
    {popps_scope}:has(.popps-summary-parent-zone) {expander_summary_parent}[open] > summary {{
        background: {summary_parent_bg} !important;
        background-image: {summary_parent_bg} !important;
        color: {text} !important;
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        padding: 0.85rem 1.1rem !important;
        border-bottom: 1px solid {summary_border} !important;
    }}
    {popps_scope}:has(.popps-summary-children-zone) {expander_summary_child} {{
        margin: 0.35rem 0 0.45rem 0.65rem !important;
        border-radius: 10px !important;
        border: 1px solid {summary_border} !important;
        background: {card_bg} !important;
    }}
    {popps_scope}:has(.popps-summary-children-zone) {expander_summary_child} > summary,
    {popps_scope}:has(.popps-summary-children-zone) {expander_summary_child}[open] > summary {{
        background: {summary_child_bg} !important;
        background-image: {summary_child_bg} !important;
        color: {text} !important;
        font-size: 0.98rem !important;
        font-weight: 600 !important;
        padding: 0.7rem 0.95rem !important;
    }}
    .popps-summary-parent-zone,
    .popps-summary-children-zone,
    .popps-repair-notes-zone {{
        display: none !important;
        height: 0 !important;
        width: 0 !important;
        pointer-events: none !important;
    }}
    .popps-expander-header--priority {{
        background: {priority_header_bg} !important;
        border-color: {priority_border} !important;
        border-left: 6px solid #fbbf24 !important;
        box-shadow: {priority_glow} !important;
    }}
    .popps-expander-header--plain {{
        background: {card_bg} !important;
        border: 1px solid {border} !important;
        box-shadow: none !important;
        font-weight: 600 !important;
    }}
    .popps-expander-header--plain .popps-expander-header-text {{
        font-weight: 600 !important;
        font-size: 1rem !important;
        color: {muted} !important;
    }}
    .popps-expander-anchor {{
        display: none !important;
        height: 0 !important;
        width: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
        pointer-events: none !important;
    }}
    {expander_archive},
    {expander_priority},
    {expander_plain} {{
        margin: 0 0 0.85rem 0 !important;
        border-radius: 0 0 14px 14px !important;
        overflow: hidden !important;
    }}
    {expander_plain} {{
        border: 1px solid {border} !important;
        border-top: none !important;
        background: {card_bg} !important;
        box-shadow: none !important;
    }}
    {expander_plain} > summary,
    {expander_plain}[open] > summary {{
        background: {card_bg} !important;
        color: {muted} !important;
        font-weight: 600 !important;
        padding: 0.65rem 1rem !important;
        border-bottom: 1px solid {border} !important;
    }}
    {expander_priority} {{
        border: 2px solid {priority_border} !important;
        border-top: none !important;
        border-left: 6px solid #fbbf24 !important;
        background: {card_bg} !important;
        box-shadow: {priority_glow} !important;
    }}
    {expander_archive} > summary,
    {expander_archive}[open] > summary,
    {expander_archive} > summary:not(:hover):not(:focus):not(:focus-visible) {{
        background: {archive_summary_bg} !important;
        background-image: {archive_summary_bg} !important;
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        font-size: 1.06rem !important;
        font-weight: 700 !important;
        padding: 0.85rem 1.1rem !important;
        border-bottom: 1px solid {archive_border} !important;
    }}
    {expander_priority} > summary,
    {expander_priority}[open] > summary,
    {expander_priority} > summary:not(:hover):not(:focus):not(:focus-visible) {{
        background: {priority_summary_bg} !important;
        background-image: {priority_summary_bg} !important;
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        font-size: 1.04rem !important;
        font-weight: 700 !important;
        padding: 0.8rem 1.05rem !important;
        border-bottom: 1px solid {priority_border} !important;
    }}
    {expander_archive} > summary *,
    {expander_archive} > summary p,
    {expander_archive} > summary span,
    {expander_archive} > summary div,
    {expander_priority} > summary *,
    {expander_priority} > summary p,
    {expander_priority} > summary span,
    {expander_priority} > summary div {{
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        font-weight: 700 !important;
        background: transparent !important;
        opacity: 1 !important;
    }}
    {expander_archive} [data-testid="stExpanderToggleIcon"],
    {expander_priority} [data-testid="stExpanderToggleIcon"] {{
        color: {text} !important;
        opacity: 1 !important;
    }}
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
    .popps-review-hint {{
        margin: 0.75rem 0 0.5rem 0;
        padding: 10px 14px;
        border-radius: 10px;
        border: 1px solid {border};
        background: {card_bg};
        color: {muted} !important;
        font-size: 0.92rem !important;
    }}
    .popps-notes-panel {{
        margin: 1rem 0 0.75rem 0;
        padding: 14px 18px;
        border-radius: 12px;
        border: 2px solid rgba(62, 150, 255, 0.55);
        background: {card_bg};
    }}
    .popps-notes-panel h4 {{
        margin: 0 0 8px 0 !important;
        color: {text} !important;
        font-size: 1.05rem !important;
    }}
    .popps-daze-legend {{
        display: flex;
        flex-wrap: wrap;
        gap: 12px 20px;
        margin: 0.35rem 0 0.85rem 0;
        font-size: 0.88rem !important;
        color: {muted} !important;
    }}
    .popps-daze-legend span {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }}
    .popps-daze-swatch {{
        width: 11px;
        height: 11px;
        border-radius: 3px;
        display: inline-block;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        margin-bottom: 0.55rem;
    }}
    .popps-daze-metric-card {{
        padding: 2px 0 0 0;
    }}
    .popps-daze-metric-label-row {{
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 8px;
        margin-bottom: 6px !important;
    }}
    .popps-daze-metric-label {{
        color: {muted} !important;
        font-size: 0.84rem !important;
        line-height: 1.35 !important;
        margin-bottom: 6px !important;
        flex: 1;
        min-width: 0;
    }}
    .popps-daze-metric-label-row .popps-daze-metric-label {{
        margin-bottom: 0 !important;
    }}
    .popps-daze-help {{
        flex-shrink: 0;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 1.05rem;
        height: 1.05rem;
        border-radius: 50%;
        border: 1px solid rgba(148, 163, 184, 0.65);
        color: {muted} !important;
        font-size: 0.68rem !important;
        font-weight: 700 !important;
        line-height: 1 !important;
        cursor: help;
        margin-top: 1px;
    }}
    .popps-daze-help:hover {{
        color: {text} !important;
        border-color: rgba(96, 165, 250, 0.85);
    }}
    .popps-daze-metric-value {{
        font-size: 1.75rem !important;
        font-weight: 700 !important;
        line-height: 1.15 !important;
        margin: 0 !important;
    }}
    .popps-daze-metric-hint {{
        color: {muted} !important;
        font-size: 0.78rem !important;
        margin-top: 4px !important;
    }}
    .popps-daze-good {{
        color: #34d399 !important;
    }}
    .popps-daze-watch {{
        color: #fbbf24 !important;
    }}
    .popps-daze-high {{
        color: #f87171 !important;
    }}
    .popps-daze-neutral {{
        color: {text} !important;
    }}
    .popps-daze-swatch-good {{ background: #34d399; }}
    .popps-daze-swatch-watch {{ background: #fbbf24; }}
    .popps-daze-swatch-high {{ background: #f87171; }}
    .popps-daze-month-heading {{
        color: {text} !important;
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        margin: 0 0 0.65rem 0 !important;
    }}
    """


def render_popps_report(
    *,
    theme: str = "Dark",
    supabase=None,
    reviewer: str = "",
    auth_user: str = "",
    notes_admin: bool = False,
    is_warranty_admin: bool = False,
) -> None:
    """POPPS upload tab — plain-language breakdown of the factory report."""
    st.markdown(
        '<div class="popps-workspace-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"<style>{popps_page_css(theme)}</style>", unsafe_allow_html=True)

    from core.ui_polish import render_section_hero

    render_section_hero(
        "POPPS Report",
        "Upload DealerCONNECT POPPS PDFs. RO Guard stores every month and opens the newest month "
        "in the current calendar quarter automatically.",
        icon="📊",
        tips=["Multi-month archive", "WAM definitions", "Per-claim notes"],
    )
    st.caption(f"POPPS tools version: **{POPPS_UI_VERSION}**")

    reviewer_name = str(reviewer or "").strip() or "User"
    if supabase is None:
        st.caption(
            "Cloud save is unavailable — POPPS uploads will only persist until this browser session ends."
        )
    prepare_popps_tab_on_enter(supabase, auth_user=auth_user)
    hydrate_popps_report_from_cloud(supabase, auth_user=auth_user)

    load_error = str(st.session_state.get("popps_cloud_load_error") or "").strip()
    if load_error:
        st.error(
            f"Could not load the saved dealership POPPS report: {load_error}. "
            "Confirm Supabase has dealer_settings.popps_active_report (JSONB) and that your account can read dealer_settings."
        )

    if "popps_upload_nonce" not in st.session_state:
        st.session_state.popps_upload_nonce = 0

    uploaded = st.file_uploader(
        "Upload POPPS report(s) (PDF)",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"popps_upload_{st.session_state.popps_upload_nonce}",
        help=(
            "Select one or more monthly PDFs (for example Mar, Apr, and May). "
            "Everyone sees the newest month in the **current calendar quarter** on this screen."
        ),
    )

    if uploaded:
        files = uploaded if isinstance(uploaded, list) else [uploaded]
        st.session_state.pop("popps_restored_from_cloud", None)
        st.session_state.pop("popps_restored_meta", None)
        batch = import_popps_pdf_files(
            supabase,
            files,
            auth_user or reviewer_name,
            auth_user=auth_user,
        )
        imported = batch.get("imported") or []
        failed = batch.get("failed") or []
        persist_error = str(batch.get("persist_error") or "").strip()

        for item in failed:
            st.error(f"Could not read {item.get('file_name')}: {item.get('error')}")

        if imported and supabase is not None and persist_error:
            st.warning(
                "Parsed the PDF(s) but could not save for your team. "
                "Add dealer_settings.popps_reports_library and popps_active_report (JSONB) "
                f"in Supabase, then upload again. ({persist_error})"
            )
        elif imported and supabase is None:
            st.success(
                f"Loaded {len(imported)} report(s) for this session only (cloud save unavailable)."
            )
        elif imported:
            quarter = batch.get("active_quarter_label") or "current quarter"
            period = batch.get("active_period_label") or "newest month in quarter"
            names = ", ".join(str(e.get("file_name") or "") for e in imported[:5])
            extra = f" (+{len(imported) - 5} more)" if len(imported) > 5 else ""
            st.success(
                f"Imported {len(imported)} file(s): {names}{extra}. "
                f"**{quarter}** is on screen — showing **{period}** for your dealership."
            )
            st.session_state.popps_upload_nonce = int(st.session_state.get("popps_upload_nonce", 0)) + 1
            st.session_state.pop("_popps_compliance_status", None)
            st.rerun()

    action_cols = st.columns(2)
    with action_cols[0]:
        clear_clicked = st.button(
            "Clear all saved POPPS reports",
            key="popps_clear_report",
            use_container_width=True,
        )
    with action_cols[1]:
        reload_clicked = (
            supabase is not None
            and st.button(
                "Reload saved POPPS report",
                key="popps_reload_cloud",
                use_container_width=True,
            )
        )

    if clear_clicked:
        clear_active_popps_report(supabase)
        st.session_state.pop("popps_parsed_report", None)
        st.session_state.pop("popps_upload_name", None)
        st.session_state.pop("popps_selected_claim_key", None)
        st.session_state.pop("popps_viewing_fingerprint", None)
        reset_popps_hydrate_attempt_flags()
        st.session_state.pop("popps_restored_from_cloud", None)
        st.session_state.pop("popps_restored_meta", None)
        for key in list(st.session_state.keys()):
            if str(key).startswith("popps_"):
                st.session_state.pop(key, None)
        st.session_state.popps_upload_nonce = int(st.session_state.get("popps_upload_nonce", 0)) + 1
        st.rerun()

    if reload_clicked:
        reset_popps_hydrate_attempt_flags()
        hydrate_popps_report_from_cloud(supabase, auth_user=auth_user, force=True)
        st.rerun()

    report: PoppsReport | None = st.session_state.get("popps_parsed_report")
    if report is None:
        st.info(
            "No POPPS report is loaded. Click **Reload saved POPPS report** above or upload the PDF again. "
            "Once saved, every advisor and manager on your team will see the same report."
        )
        with st.expander("What is POPPS?", expanded=False, key="popps_what_is"):
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
    report_fp = popps_report_fingerprint(report, file_name)
    reviews_store = load_popps_reviews_store(supabase, report_fp)
    report_ctx = _popps_report_context(report, file_name, report_fp)

    library = load_popps_library(supabase)
    if st.session_state.get("_popps_compliance_status") is None:
        st.session_state["_popps_compliance_status"] = evaluate_popps_notes_compliance(
            supabase,
            library=library,
            report_fingerprint=report_fp,
            reviews_store=reviews_store,
            report=report,
            run_manager_alert=True,
        )
    compliance_status = st.session_state.get("_popps_compliance_status")
    render_popps_notes_compliance_messages(
        compliance_status,
        is_warranty_admin=is_warranty_admin,
        on_popps_tab=True,
    )
    active_fp = str(library.get("active_fingerprint") or report_fp)
    viewing_fp = str(st.session_state.get("popps_viewing_fingerprint") or "").strip()
    _render_popps_archive_panel(
        library,
        supabase=supabase,
        active_fingerprint=active_fp,
        viewing_fingerprint=viewing_fp,
    )

    if st.session_state.get("popps_restored_from_cloud"):
        meta = st.session_state.get("popps_restored_meta") or {}
        uploaded_at = str(meta.get("uploaded_at") or "")[:19].replace("T", " ")
        uploaded_by = str(meta.get("uploaded_by") or "").strip()
        who = f" by {uploaded_by}" if uploaded_by else ""
        when = f" on {uploaded_at} UTC" if uploaded_at else ""
        st.info(f"Restored your saved POPPS report ({file_name}){when}{who}.")

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

    st.markdown(
        f'<div class="popps-section-title">Three-month dealership overview ({DAZE_LABEL})</div>',
        unsafe_allow_html=True,
    )
    st.caption(DAZE_WAM_DEFINITION)
    st.markdown(
        '<div class="popps-daze-legend">'
        '<span><i class="popps-daze-swatch popps-daze-swatch-good"></i> '
        "At or below zone — favorable</span>"
        '<span><i class="popps-daze-swatch popps-daze-swatch-watch"></i> '
        "Near zone average</span>"
        '<span><i class="popps-daze-swatch popps-daze-swatch-high"></i> '
        "Above zone — higher spend vs benchmark</span>"
        "</div>",
        unsafe_allow_html=True,
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
            st.markdown(
                f'<div class="popps-daze-month-heading">{months[idx]}</div>',
                unsafe_allow_html=True,
            )
            dealer_tone, dealer_hint = _daze_compare_zone(dealership[idx], business_center[idx])
            _render_daze_colored_metric(
                f"Dealership {DAZE_LABEL}",
                dealership[idx] or "—",
                tone=dealer_tone,
                hint=dealer_hint,
                help_text=DAZE_HELP_DEALERSHIP,
            )
            _render_daze_colored_metric(
                f"Business Center {DAZE_LABEL} (zone benchmark)",
                business_center[idx] or "—",
                tone="neutral",
                hint="Compare to your dealership index above",
                help_text=DAZE_HELP_BUSINESS_CENTER,
            )
            prior_expense = expense[idx - 1] if idx > 0 else None
            expense_tone, expense_hint = _daze_expense_trend(expense[idx], prior_expense)
            _render_daze_colored_metric(
                f"{DAZE_LABEL} — warranty dollars",
                expense[idx] or "—",
                tone=expense_tone,
                hint=expense_hint,
                help_text=DAZE_HELP_EXPENSE,
            )

    if report.top_problems:
        top_count = len(report.top_problems)
        st.markdown('<div class="popps-summary-parent-zone" aria-hidden="true"></div>', unsafe_allow_html=True)
        _popps_expander_anchor("popps-anchor-summary-parent")
        with st.expander(
            f"Quarterly top problem summary{_popps_item_count_label(top_count)}",
            expanded=False,
            key="popps_sec_top_problems",
        ):
            st.caption("Summary only — add notes under each repair group with sample claims below.")
            st.markdown('<div class="popps-summary-children-zone" aria-hidden="true"></div>', unsafe_allow_html=True)
            for idx, row in enumerate(report.top_problems):
                _popps_expander_anchor("popps-anchor-summary-child")
                with st.expander(
                    _summary_row_label(row),
                    expanded=False,
                    key=f"popps_top_child_{idx}",
                ):
                    st.dataframe(
                        _summary_dataframe([row]),
                        use_container_width=True,
                        hide_index=True,
                    )

    if report.early_warning:
        ew_count = len(report.early_warning)
        st.markdown('<div class="popps-summary-parent-zone" aria-hidden="true"></div>', unsafe_allow_html=True)
        _popps_expander_anchor("popps-anchor-summary-parent")
        with st.expander(
            f"Early warning indicators{_popps_item_count_label(ew_count)}",
            expanded=False,
            key="popps_sec_early_warning",
        ):
            st.caption(
                "Early warning flags a labor operation that escalated quickly during the quarter. "
                "Add review notes on matching claims in the repair groups section below."
            )
            st.markdown('<div class="popps-summary-children-zone" aria-hidden="true"></div>', unsafe_allow_html=True)
            for idx, row in enumerate(report.early_warning):
                _popps_expander_anchor("popps-anchor-summary-child")
                with st.expander(
                    _summary_row_label(row),
                    expanded=False,
                    key=f"popps_ew_child_{idx}",
                ):
                    st.dataframe(
                        _summary_dataframe([row]),
                        use_container_width=True,
                        hide_index=True,
                    )

    care_child_count = len(report.customer_care) + 1
    if report.customer_care or CONCERN_CODE_DESCRIPTIONS:
        st.markdown('<div class="popps-summary-parent-zone" aria-hidden="true"></div>', unsafe_allow_html=True)
        _popps_expander_anchor("popps-anchor-summary-parent")
        with st.expander(
            f"Customer care metrics (summary){_popps_item_count_label(care_child_count)}",
            expanded=False,
            key="popps_sec_customer_care",
        ):
            st.markdown('<div class="popps-summary-children-zone" aria-hidden="true"></div>', unsafe_allow_html=True)
            for idx, row in enumerate(report.customer_care):
                _popps_expander_anchor("popps-anchor-summary-child")
                with st.expander(
                    row.metric_name,
                    expanded=False,
                    key=f"popps_care_child_{idx}",
                ):
                    if row.march_value or row.april_value or row.may_value:
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {
                                        "Metric": row.metric_name,
                                        MONTH_LABELS[0]: row.march_value,
                                        MONTH_LABELS[1]: row.april_value,
                                        MONTH_LABELS[2]: row.may_value,
                                    }
                                ]
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )
                    elif row.notes:
                        st.markdown(row.notes)

            _popps_expander_anchor("popps-anchor-summary-child")
            with st.expander(
                "Concern code reference (plain language)",
                expanded=False,
                key="popps_concern_codes_child",
            ):
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
        sections_needing_notes = _priority_sections_needing_notes(report)
        group_count = len(sections_needing_notes)
        repair_title = (
            f"Repair groups and related claims (add notes){_popps_item_count_label(group_count)}"
        )
        st.markdown('<div class="popps-repair-notes-zone" aria-hidden="true"></div>', unsafe_allow_html=True)
        _render_popps_expander_header(repair_title, "notes")
        _popps_expander_anchor("popps-anchor-repair-notes")
        with st.expander(
            "Open repair groups — add notes here",
            expanded=False,
            key="popps_sec_repair_groups",
        ):
            st.markdown(
                '<p class="popps-review-hint">'
                "Expand each <strong>Claims Analysis</strong> priority below. Scroll past the claims table to the blue "
                "<strong>Notes &amp; review</strong> box, then use the "
                "<strong>repair order tabs</strong> to add notes (with your name), set review status, "
                "and save. Notes cannot be edited — only Admin can delete a note."
                "</p>",
                unsafe_allow_html=True,
            )
            if sections_needing_notes:
                labels = [_priority_section_note_label(section) for section in sections_needing_notes]
                st.caption("**Repair groups that need notes:** " + " · ".join(labels))
            elif compliance_status and compliance_status.get("needs_warning"):
                st.caption("No sample claims are listed for review in this POPPS file.")
            for section in report.priority_sections:
                _render_popps_priority_section(
                    section,
                    reviews_store=reviews_store,
                    supabase=supabase,
                    report=report,
                    file_name=file_name,
                    report_fp=report_fp,
                    reviewer_name=reviewer_name,
                    report_ctx=report_ctx,
                    notes_admin=notes_admin,
                )

    _render_popps_audit_panel(
        reviews_store=reviews_store,
        supabase=supabase,
        report_fp=report_fp,
        file_name=file_name,
        report=report,
    )

    raw_key = f"popps_raw_text_{_safe_widget_suffix(report_fp, file_name, scope='raw')}"
    with st.expander(
        "View extracted PDF text (troubleshooting)",
        expanded=False,
        key=raw_key,
    ):
        st.text_area(
            "Extracted text",
            value=report.raw_text[:120000],
            height=280,
            label_visibility="collapsed",
            key=f"popps_raw_text_area_{raw_key}",
        )
