"""Parse and display Dealer POPPS (Performance Overview & Potential Problem Summary) PDFs."""

from __future__ import annotations

import hashlib
import io
import re
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
POPPS_UI_VERSION = "2026-06-02-daze-labels"

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


def load_active_popps_report(supabase) -> tuple[PoppsReport | None, str, dict, str]:
    """Load the dealer's last saved POPPS parse from cloud storage."""
    if supabase is None:
        return None, "", {}, "Supabase is not configured"
    try:
        response = (
            supabase.table("dealer_settings")
            .select("popps_active_report")
            .eq("id", 1)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        if not rows or not rows[0].get("popps_active_report"):
            return None, "", {}, ""
        blob = rows[0]["popps_active_report"] or {}
        report_data = blob.get("report")
        if not report_data:
            return None, "", {}, ""
        try:
            parsed = popps_report_from_storage_dict(report_data)
        except Exception as exc:
            return None, "", {}, f"Stored POPPS report could not be loaded: {exc}"
        return (
            parsed,
            str(blob.get("file_name") or "POPPS report").strip(),
            {
                "file_name": blob.get("file_name"),
                "uploaded_at": blob.get("uploaded_at"),
                "uploaded_by": blob.get("uploaded_by"),
            },
            "",
        )
    except Exception as exc:
        return None, "", {}, str(exc)


def save_active_popps_report(
    supabase,
    report: PoppsReport,
    file_name: str,
    uploaded_by: str,
    *,
    auth_user: str = "",
) -> tuple[bool, str]:
    """Persist parsed POPPS so it survives logout and is visible to all dealership users."""
    if supabase is None:
        return False, "Supabase is not configured"
    payload = {
        "file_name": str(file_name or "").strip(),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "uploaded_by": str(uploaded_by or "").strip(),
        "report": popps_report_to_storage_dict(report),
    }
    try:
        supabase.table("dealer_settings").update(
            {"popps_active_report": payload}
        ).eq("id", 1).execute()
        user_marker = re.sub(
            r"[^a-zA-Z0-9@._-]", "_", str(auth_user or uploaded_by or "").strip().lower()
        ) or "_anonymous"
        st.session_state[f"_popps_hydrate_ok_{user_marker}"] = True
        st.session_state.pop(f"_popps_hydrate_empty_{user_marker}", None)
        st.session_state.pop("popps_cloud_load_error", None)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def clear_active_popps_report(supabase) -> None:
    if supabase is None:
        return
    try:
        supabase.table("dealer_settings").update(
            {"popps_active_report": None}
        ).eq("id", 1).execute()
    except Exception:
        pass


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

    report, file_name, meta, load_error = load_active_popps_report(supabase)
    st.session_state.popps_cloud_load_error = load_error or ""

    if load_error:
        return False

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


def _slug_token(text: str, *, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(text or "").strip()).strip("_")
    return slug[:max_len] or "item"


def _safe_widget_suffix(entry_key: str, report_fingerprint: str) -> str:
    """Stable unique Streamlit widget key (avoids truncation collisions)."""
    raw = f"{report_fingerprint}|{entry_key}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    return f"popps_{digest}"


def section_review_entry_key(section: PoppsPrioritySection) -> str:
    rank = _slug_token(section.priority_rank, max_len=24)
    lop = _slug_token(section.labor_operation_code, max_len=24)
    desc = _slug_token(section.repair_description, max_len=40)
    return f"section:{rank}:{lop}:{desc}"


def claim_review_entry_key(section: PoppsPrioritySection, claim: PoppsClaimRow) -> str:
    claim_id = re.sub(r"\s+", "_", claim.claim_condition_or_number)
    return f"{section_review_entry_key(section)}:claim:{claim_id}"


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


def _review_status_label(entry: dict | None) -> str:
    entry = entry or {}
    if entry.get("reviewed_charged_back"):
        return "Charged claim back"
    if entry.get("reviewed_no_issues"):
        return "No issues found"
    if str(entry.get("notes") or "").strip():
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
                "Notes": entry.get("notes") or "",
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


def save_popps_review_entry(
    supabase,
    report_fingerprint: str,
    entry_key: str,
    *,
    reviewed_no_issues: bool,
    reviewed_charged_back: bool,
    notes: str,
    reviewer: str,
    category_label: str,
    report_context: dict[str, str] | None = None,
    priority_label: str = "",
    labor_operation_code: str = "",
    ro_or_claim_number: str = "",
    vehicle_identification: str = "",
) -> None:
    if reviewed_no_issues and reviewed_charged_back:
        reviewed_charged_back = False

    ctx = report_context or {}
    updated_at = datetime.now(timezone.utc).isoformat()
    entry = {
        "entry_key": entry_key,
        "category_label": category_label,
        "reviewed_no_issues": bool(reviewed_no_issues),
        "reviewed_charged_back": bool(reviewed_charged_back),
        "notes": str(notes or "").strip(),
        "reviewed_by": reviewer,
        "updated_at": updated_at,
        "dealer_code": ctx.get("dealer_code", ""),
        "report_period": ctx.get("report_period", ""),
        "source_file": ctx.get("source_file", ""),
        "priority_label": priority_label,
        "labor_operation_code": labor_operation_code,
        "ro_or_claim_number": ro_or_claim_number,
        "vehicle_identification": vehicle_identification,
    }

    cache_key = f"popps_reviews_{report_fingerprint}"
    store = dict(st.session_state.get(cache_key) or load_popps_reviews_store(supabase, report_fingerprint))
    store[entry_key] = entry
    st.session_state[cache_key] = store

    audit_row = {
        "report_fingerprint": report_fingerprint,
        "entry_key": entry_key,
        "dealer_code": entry.get("dealer_code"),
        "report_period": entry.get("report_period"),
        "source_file": entry.get("source_file"),
        "priority_label": priority_label,
        "labor_operation_code": labor_operation_code,
        "ro_or_claim_number": ro_or_claim_number,
        "vehicle_identification": vehicle_identification,
        "category_label": category_label,
        "reviewed_no_issues": entry["reviewed_no_issues"],
        "reviewed_charged_back": entry["reviewed_charged_back"],
        "notes": entry["notes"],
        "reviewed_by": reviewer,
        "review_updated_at": updated_at,
        "created_at": updated_at,
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
) -> None:
    """Notes and review checkboxes for one POPPS category or claim."""
    stored = reviews_store.get(entry_key) or {}
    suffix = _safe_widget_suffix(entry_key, report_fingerprint)
    no_key = f"popps_no_issues_{suffix}"
    charge_key = f"popps_charged_{suffix}"
    notes_key = f"popps_notes_{suffix}"

    if no_key not in st.session_state:
        st.session_state[no_key] = bool(stored.get("reviewed_no_issues"))
    if charge_key not in st.session_state:
        st.session_state[charge_key] = bool(stored.get("reviewed_charged_back"))
    if notes_key not in st.session_state:
        st.session_state[notes_key] = str(stored.get("notes") or "")

    def _clear_other(other_field: str) -> None:
        st.session_state[other_field] = False

    st.markdown(f"**{heading or 'Review'}**")
    if category_label and heading != category_label:
        st.caption(category_label)
    if stored.get("reviewed_by"):
        updated = str(stored.get("updated_at") or "")[:19].replace("T", " ")
        st.caption(f"Last saved by {stored.get('reviewed_by')} · {updated or '—'}")

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

    st.text_area(
        "Notes",
        key=notes_key,
        height=88,
        placeholder="Document what you verified, who you spoke with, or charge-back details.",
    )

    if st.button("Save review", key=f"popps_save_{suffix}", use_container_width=True):
        save_popps_review_entry(
            supabase,
            report_fingerprint,
            entry_key,
            reviewed_no_issues=bool(st.session_state.get(no_key)),
            reviewed_charged_back=bool(st.session_state.get(charge_key)),
            notes=str(st.session_state.get(notes_key) or ""),
            reviewer=reviewer,
            category_label=category_label,
            report_context=report_context,
            priority_label=priority_label,
            labor_operation_code=labor_operation_code,
            ro_or_claim_number=ro_or_claim_number,
            vehicle_identification=vehicle_identification,
        )
        st.success("Review saved to audit trail.")
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
) -> None:
    """Priority / message-code expander with per-claim notes and review."""
    title = (
        f"{section.priority_label} — "
        f"Labor Operation {section.labor_operation_code} — "
        f"{section.repair_description}"
    )

    open_by_default = bool(section.claims) or section.priority_rank == "1"
    with st.expander(title, expanded=open_by_default):
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
        for claim in section.claims:
            claim_key = claim_review_entry_key(section, claim)
            stored = reviews_store.get(claim_key) or {}
            status = _review_status_label(stored)
            label = _claim_select_label(claim)
            if status != "Not reviewed":
                label = f"{label} ✓"
            tab_labels.append(label)

        claim_tabs = st.tabs(tab_labels)
        for claim, tab in zip(section.claims, claim_tabs):
            claim_key = claim_review_entry_key(section, claim)
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

    with st.expander("POPPS review audit trail", expanded=bool(len(snapshot))):
        st.caption(
            "Every **Save review** writes an append-only audit record (cloud table when configured). "
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
                key="popps_audit_snapshot_csv",
            )
        if not history_df.empty:
            st.markdown("**Full save history (newest first)**")
            st.dataframe(history_df.head(200), use_container_width=True, hide_index=True)
            st.download_button(
                "Download full audit history (CSV)",
                history_df.to_csv(index=False),
                file_name=f"popps_audit_history_{report.dealer_code}.csv".replace(" ", "_"),
                mime="text/csv",
                key="popps_audit_history_csv",
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
    """


def render_popps_report(
    *,
    theme: str = "Dark",
    supabase=None,
    reviewer: str = "",
    auth_user: str = "",
) -> None:
    """POPPS upload tab — plain-language breakdown of the factory report."""
    st.markdown(
        '<div class="popps-workspace-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"<style>{popps_page_css(theme)}</style>", unsafe_allow_html=True)

    st.header("POPPS Report")
    st.caption(f"POPPS tools version: **{POPPS_UI_VERSION}**")
    st.caption(
        "Upload your Dealer **Performance Overview & Potential Problem Summary (POPPS)** "
        "PDF from DealerCONNECT. RO Guard expands abbreviations into plain language for coaching and review. "
        "The active POPPS report is saved for your entire dealership — any signed-in user can review it."
    )

    reviewer_name = str(reviewer or "").strip() or "User"
    if supabase is None:
        st.caption(
            "Cloud save is unavailable — POPPS uploads will only persist until this browser session ends."
        )
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
            st.session_state.pop("popps_restored_from_cloud", None)
            st.session_state.pop("popps_restored_meta", None)
            saved_ok, save_error = save_active_popps_report(
                supabase,
                report,
                uploaded.name,
                auth_user or reviewer_name,
                auth_user=auth_user,
            )
            if saved_ok:
                st.success(
                    f"Loaded and saved {uploaded.name} for your dealership. "
                    "All signed-in users will see this report."
                )
            else:
                st.success(f"Loaded {uploaded.name} for this session only.")
                if supabase is not None:
                    st.warning(
                        "Could not save this report for your team. "
                        "Add dealer_settings.popps_active_report (JSONB) in Supabase, then upload again. "
                        f"({save_error or 'unknown error'})"
                    )
        except Exception as exc:
            st.error(f"Could not read that PDF: {exc}")

    action_cols = st.columns(2)
    with action_cols[0]:
        clear_clicked = st.button("Clear POPPS report", key="popps_clear_report", use_container_width=True)
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
    report_fp = popps_report_fingerprint(report, file_name)
    reviews_store = load_popps_reviews_store(supabase, report_fp)
    report_ctx = _popps_report_context(report, file_name, report_fp)

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
            st.metric(
                f"Dealership {DAZE_LABEL}",
                dealership[idx] or "—",
                help=DAZE_METRIC_HELP,
            )
            st.metric(
                f"Business Center {DAZE_LABEL}",
                business_center[idx] or "—",
                help=(
                    f"{DAZE_METRIC_HELP} This value is the zone (Business Center) benchmark "
                    "for comparison."
                ),
            )
            st.metric(
                f"{DAZE_LABEL} — warranty dollars",
                expense[idx] or "—",
                help=(
                    f"{DAZE_FULL_NAME} (DAZE) expense dollars for this month — warranty costs "
                    "counted in the DAZE measure per WAM / DWIN POPPS reporting."
                ),
            )

    if report.top_problems:
        st.markdown('<div class="popps-section-title">Quarterly top problem summary</div>', unsafe_allow_html=True)
        st.caption("Summary only — add notes under each repair group with sample claims below.")
        for row in report.top_problems:
            label = (
                f"{row.rank_label} — Labor Operation {row.labor_operation_code} — "
                f"{row.repair_description}"
            )
            with st.expander(label, expanded=False):
                st.dataframe(
                    _summary_dataframe([row]),
                    use_container_width=True,
                    hide_index=True,
                )

    if report.early_warning:
        st.markdown('<div class="popps-section-title">Early warning indicators</div>', unsafe_allow_html=True)
        st.caption(
            "Early warning flags a labor operation that escalated quickly during the quarter. "
            "Add review notes on matching claims in the repair groups section below."
        )
        for row in report.early_warning:
            label = (
                f"{row.rank_label} — Labor Operation {row.labor_operation_code} — "
                f"{row.repair_description}"
            )
            with st.expander(label, expanded=False):
                st.dataframe(
                    _summary_dataframe([row]),
                    use_container_width=True,
                    hide_index=True,
                )

    if report.customer_care:
        st.markdown('<div class="popps-section-title">Customer care metrics (summary)</div>', unsafe_allow_html=True)
        for row in report.customer_care:
            label = row.metric_name
            with st.expander(label, expanded=False):
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
        st.markdown(
            '<p class="popps-review-hint">'
            "Under each priority area, scroll past the claims table to the blue "
            "<strong>Notes &amp; review</strong> box, then use the "
            "<strong>repair order tabs</strong> (one tab per RO) for notes, checkboxes, and Save review."
            "</p>",
            unsafe_allow_html=True,
        )
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
            )

    _render_popps_audit_panel(
        reviews_store=reviews_store,
        supabase=supabase,
        report_fp=report_fp,
        file_name=file_name,
        report=report,
    )

    with st.expander("View extracted PDF text (troubleshooting)", expanded=False):
        st.text_area(
            "Extracted text",
            value=report.raw_text[:120000],
            height=280,
            label_visibility="collapsed",
        )
