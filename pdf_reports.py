"""PDF export for RO Shield audit and ROI reports."""

from __future__ import annotations

import io
import re
from datetime import datetime, timezone

from fpdf import FPDF


def _safe_text(value) -> str:
    text = str(value or "").strip()
    replacements = {
        "🔴": "",
        "🟡": "",
        "🟢": "",
        "…": "...",
        "’": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
        "•": "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"[^\x00-\xFF]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class _ReportPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_top_margin(22)

    def header(self):
        self._draw_page_background()
        self._draw_watermark()
        self.set_y(10)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(90, 90, 90)
        self.cell(0, 5, "Patent Pending", align="R", new_x="LMARGIN", new_y="NEXT")

    def _draw_page_background(self):
        self.set_fill_color(238, 244, 252)
        self.rect(0, 0, self.w, self.h, style="F")

    def _draw_watermark(self):
        self.set_font("Helvetica", "B", 54)
        self.set_text_color(225, 225, 225)
        cx = self.w / 2
        cy = self.h / 2
        text = "RO GUARD"
        text_w = self.get_string_width(text)
        x = cx - text_w / 2
        y = cy - 5
        with self.rotation(32, x=cx, y=cy):
            self.text(x, y, text)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, f"RO Shield - Patent Pending  |  Page {self.page_no()}", new_x="LMARGIN", new_y="NEXT")


def _ensure_left(pdf: FPDF):
    pdf.set_x(pdf.l_margin)


def _section_title(pdf: FPDF, title: str):
    _ensure_left(pdf)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(20, 60, 110)
    pdf.multi_cell(0, 6, _safe_text(title))
    pdf.ln(0.5)


def _body_text(pdf: FPDF, text: str, size: int = 10):
    _ensure_left(pdf)
    pdf.set_font("Helvetica", "", size)
    pdf.set_text_color(30, 30, 30)
    pdf.multi_cell(0, 5, _safe_text(text))
    pdf.ln(1)


def _bullet_list(pdf: FPDF, items: list[str]):
    _ensure_left(pdf)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    for item in items:
        if item:
            pdf.multi_cell(0, 5, f"- {_safe_text(item)}")
    pdf.ln(1)


def _truncate(text, max_len: int = 20) -> str:
    text = _safe_text(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _format_date(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:10]


def _format_status(value) -> str:
    text = _safe_text(value)
    for token in ("DO NOT SUBMIT", "NEEDS REVIEW", "READY"):
        if token in text.upper():
            return token
    return text[:24]


def _format_money(value) -> str:
    try:
        return f"${float(value or 0):,.0f}"
    except (TypeError, ValueError):
        return "$0"


def _report_header(pdf: FPDF, title: str, period_label: str):
    _ensure_left(pdf)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(10, 40, 80)
    pdf.multi_cell(0, 8, title)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    _ensure_left(pdf)
    pdf.multi_cell(0, 5, f"Period: {_safe_text(period_label)}")
    _ensure_left(pdf)
    pdf.multi_cell(
        0,
        5,
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    )
    pdf.ln(2)


def _summary_metrics_table(pdf: FPDF, metrics: list[tuple[str, str]]):
    """Render summary metrics in a clean 3-column grid."""
    _section_title(pdf, "Summary")
    _ensure_left(pdf)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_fill_color(20, 60, 110)
    col_w = pdf.epw / 3
    row_h = 8
    for idx, (label, value) in enumerate(metrics):
        if idx % 3 == 0 and idx > 0:
            pdf.ln(row_h)
        pdf.cell(col_w, row_h, _safe_text(label), border=1, fill=True, align="C")
    pdf.ln(row_h)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(20, 20, 20)
    for idx, (_, value) in enumerate(metrics):
        if idx % 3 == 0 and idx > 0:
            pdf.ln(row_h)
        if idx % 3 == 0:
            pdf.set_fill_color(245, 248, 252)
        elif idx % 3 == 1:
            pdf.set_fill_color(255, 255, 255)
        else:
            pdf.set_fill_color(245, 248, 252)
        pdf.cell(col_w, row_h, _safe_text(value), border=1, fill=True, align="C")
    pdf.ln(row_h + 2)


def _review_log_table(pdf: FPDF, rows):
    """Render review rows in a landscape-friendly table."""
    import pandas as pd

    headers = ["Date", "RO #", "Advisor", "Technician", "Admin", "Score", "Status", "Claim $", "HS", "Warn"]
    col_widths = (22, 18, 28, 28, 28, 14, 34, 18, 10, 10)

    def _cell_value(row, key, default=""):
        if key not in row.index:
            return default
        val = row[key]
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        return val

    _section_title(pdf, "Review Log")
    _ensure_left(pdf)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(255, 255, 255)
    pdf.set_fill_color(20, 60, 110)
    for width, label in zip(col_widths, headers):
        pdf.cell(width, 6, label, border=1, fill=True, align="C")
    pdf.ln(6)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(20, 20, 20)
    fill = False
    for _, row in rows.iterrows():
        _ensure_left(pdf)
        fill = not fill
        if fill:
            pdf.set_fill_color(245, 248, 252)
        else:
            pdf.set_fill_color(255, 255, 255)

        values = [
            _format_date(_cell_value(row, "created_at")),
            _truncate(_cell_value(row, "ro_number"), 12),
            _truncate(_cell_value(row, "advisor"), 16),
            _truncate(_cell_value(row, "technician"), 16),
            _truncate(_cell_value(row, "warranty_admin"), 16),
            str(int(float(_cell_value(row, "score") or 0))),
            _format_status(_cell_value(row, "status")),
            _format_money(_cell_value(row, "total_claim_value")),
            str(int(float(_cell_value(row, "hard_stop_count") or 0))),
            str(int(float(_cell_value(row, "warning_count") or 0))),
        ]
        aligns = ("L", "L", "L", "L", "L", "C", "L", "R", "C", "C")
        for width, value, align in zip(col_widths, values, aligns):
            pdf.cell(width, 5.5, _safe_text(value), border=1, fill=True, align=align)
        pdf.ln(5.5)

    pdf.ln(1)


def _key_value_lines(pdf: FPDF, pairs: list[tuple[str, str]]):
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    for label, value in pairs:
        _ensure_left(pdf)
        pdf.multi_cell(0, 5, _safe_text(f"{label}: {value}"))
    pdf.ln(1)


def _png_height_for_width(png_bytes: bytes, width_mm: float) -> float:
    """Scale PNG pixel dimensions to rendered height in mm."""
    if not png_bytes or png_bytes[:8] != b"\x89PNG\r\n\x1a\n" or len(png_bytes) < 24:
        return width_mm * 0.75
    w_px = int.from_bytes(png_bytes[16:20], "big")
    h_px = int.from_bytes(png_bytes[20:24], "big")
    if w_px <= 0:
        return width_mm * 0.75
    return width_mm * (h_px / w_px)


def _embed_chart_pair(
    pdf: FPDF,
    left_png: bytes | None,
    right_png: bytes | None,
    *,
    gap: float = 6,
    bottom_pad: float = 5,
    min_width_ratio: float = 0.82,
):
    """Place two charts side-by-side at readable size; new page before shrinking too small."""
    pngs = [p for p in (left_png, right_png) if p]
    if not pngs:
        return

    full_w = pdf.epw / 2 - gap / 2
    min_w = full_w * min_width_ratio

    def _pair_height(width: float) -> float:
        return max(_png_height_for_width(p, width) for p in pngs)

    y_row = pdf.get_y()
    available_h = pdf.page_break_trigger - y_row - bottom_pad
    chart_w = full_w
    max_h = _pair_height(chart_w)

    if max_h > available_h:
        fit_w = full_w * (available_h / max_h)
        if fit_w >= min_w:
            chart_w = fit_w
            max_h = _pair_height(chart_w)
        else:
            pdf.add_page()
            y_row = pdf.get_y()
            available_h = pdf.page_break_trigger - y_row - bottom_pad
            chart_w = full_w
            max_h = _pair_height(chart_w)
            if max_h > available_h:
                chart_w = max(min_w, full_w * (available_h / max_h))
                max_h = _pair_height(chart_w)

    left_x = pdf.l_margin
    right_x = pdf.l_margin + chart_w + gap

    if left_png:
        pdf.image(io.BytesIO(left_png), x=left_x, y=y_row, w=chart_w)
    if right_png:
        pdf.image(io.BytesIO(right_png), x=right_x, y=y_row, w=chart_w)

    pdf.set_y(y_row + max_h + bottom_pad)


def _embed_png(
    pdf: FPDF,
    png_bytes: bytes | None,
    width: float | None = None,
    *,
    max_height: float | None = None,
):
    if not png_bytes:
        return
    if width is None:
        width = pdf.epw
    y = pdf.get_y()
    available_h = pdf.page_break_trigger - y - 4
    if max_height is not None:
        available_h = min(available_h, max_height)
    height = _png_height_for_width(png_bytes, width)
    if height > available_h and available_h > 12:
        width = width * (available_h / height)
        height = _png_height_for_width(png_bytes, width)
    elif height > available_h:
        pdf.add_page()
        y = pdf.get_y()
        available_h = pdf.page_break_trigger - y - 4
        if max_height is not None:
            available_h = min(available_h, max_height)
        height = _png_height_for_width(png_bytes, width)
        if height > available_h and available_h > 12:
            width = width * (available_h / height)
            height = _png_height_for_width(png_bytes, width)
    pdf.image(io.BytesIO(png_bytes), x=pdf.l_margin, y=y, w=width)
    pdf.set_y(y + height + 4)


def build_audit_report_pdf(data: dict) -> bytes:
    """Build a shareable single-RO audit PDF."""
    pdf = _ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    ro_number = _safe_text(data.get("ro_number") or "RO")
    _ensure_left(pdf)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(10, 40, 80)
    pdf.multi_cell(0, 8, "RO Shield Warranty Audit Report")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(60, 60, 60)
    _ensure_left(pdf)
    pdf.multi_cell(0, 6, f"RO Number: {ro_number}")
    _ensure_left(pdf)
    pdf.multi_cell(
        0,
        6,
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    )
    pdf.ln(4)

    _section_title(pdf, "Summary")
    _key_value_lines(
        pdf,
        [
            ("Status", data.get("status", "")),
            ("Audit Score", str(data.get("score", ""))),
            ("Total Claim Value", f"${float(data.get('total_claim_value') or 0):,.2f}"),
            ("Hard Stop Value", f"${float(data.get('hard_stop_value') or 0):,.2f}"),
            ("Hard Stops", str(data.get("hard_stop_count", 0))),
            ("Warnings", str(data.get("warning_count", 0))),
            ("VIN", data.get("vin", "")),
            ("RO Invoiced", data.get("ro_invoiced", "")),
            ("Day Submitted", data.get("day_submitted", "")),
            ("Days to Submit", str(data.get("days_to_submit", ""))),
            ("Advisor", data.get("advisor", "")),
            ("Technician", data.get("technician", "")),
            ("Warranty Admin", data.get("warranty_admin", "")),
        ],
    )

    if data.get("first_pass_paid"):
        _body_text(pdf, "Paid on First Submission: Yes")
    if data.get("rejected"):
        _body_text(pdf, f"Rejected / Returned: Yes")
        if data.get("rejection_reason"):
            _body_text(pdf, f"Rejection Reason: {data.get('rejection_reason')}")
    if data.get("time_bypass"):
        _body_text(
            pdf,
            f"Time Validation Bypassed by: {data.get('time_bypass_user') or 'Not recorded'}",
        )

    jobs = data.get("jobs") or []
    for job in jobs:
        pdf.ln(2)
        _section_title(pdf, f"Job {job.get('job_no', '')}")
        _key_value_lines(
            pdf,
            [
                ("Job Score", str(job.get("score", ""))),
                ("Claim Value", f"${float(job.get('claim_value') or 0):,.2f}"),
                ("Tech Flagged Time", str(job.get("tech_flagged_time", ""))),
                ("Time Allotted", str(job.get("time_allotted", ""))),
            ],
        )

        if job.get("concern"):
            _body_text(pdf, f"Concern: {job.get('concern')}")
        if job.get("cause"):
            _body_text(pdf, f"Cause: {job.get('cause')}")
        if job.get("correction"):
            _body_text(pdf, f"Correction: {job.get('correction')}")

        hard_stops = job.get("hard_stops") or []
        warnings = job.get("warnings") or []
        if hard_stops:
            _section_title(pdf, "Hard Stops")
            _bullet_list(pdf, hard_stops)
        if warnings:
            _section_title(pdf, "Warnings")
            _bullet_list(pdf, warnings)

        manual_sections = job.get("manual_sections") or []
        if manual_sections:
            _section_title(pdf, "Applicable Warranty Manual Guidance")
            for sec in manual_sections:
                _body_text(
                    pdf,
                    f"{sec.get('section', 'Manual')} ({sec.get('source', 'WAM')})",
                    size=10,
                )
                _body_text(pdf, sec.get("snippet", ""), size=9)

    return bytes(pdf.output())


def build_roi_report_pdf(
    metrics: dict,
    *,
    period_label: str,
    rejection_rework_pct: float,
    minutes_saved: float,
    hourly_rate: float,
) -> bytes:
    """Build a manager-ready ROI summary PDF."""
    pdf = _ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    _ensure_left(pdf)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(10, 40, 80)
    pdf.multi_cell(0, 8, "RO Shield ROI Summary")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(60, 60, 60)
    _ensure_left(pdf)
    pdf.multi_cell(0, 6, f"Period: {_safe_text(period_label)}")
    _ensure_left(pdf)
    pdf.multi_cell(
        0,
        6,
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    )
    pdf.ln(4)

    _section_title(pdf, "Estimated Value Captured")
    _ensure_left(pdf)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(10, 40, 80)
    pdf.multi_cell(0, 10, f"${float(metrics.get('total_estimated_value') or 0):,.0f}")
    pdf.ln(2)

    _section_title(pdf, "Value at a Glance")
    _key_value_lines(
        pdf,
        [
            ("Claims Protected", f"${float(metrics.get('protected_value') or 0):,.0f}"),
            ("Est. Rework Avoided", f"${float(metrics.get('rework_savings') or 0):,.0f}"),
            ("Est. Labor Saved", f"${float(metrics.get('time_savings') or 0):,.0f}"),
            ("Reviews Audited", str(metrics.get("review_count", 0))),
        ],
    )

    _section_title(pdf, "Quality and Approval")
    _key_value_lines(
        pdf,
        [
            ("Average Audit Score", f"{float(metrics.get('avg_score') or 0):.1f}"),
            ("First-Pass Approval", f"{float(metrics.get('first_pass_pct') or 0):.1f}%"),
            ("Rejected Claim Value", f"${float(metrics.get('rejected_value') or 0):,.0f}"),
            ("Hard Stops Caught", str(metrics.get("hard_stop_count", 0))),
            ("Warnings Flagged", str(metrics.get("warning_count", 0))),
        ],
    )

    _section_title(pdf, "Audit Outcomes")
    _key_value_lines(
        pdf,
        [
            ("Do Not Submit", str(metrics.get("do_not_submit_count", 0))),
            ("Needs Review", str(metrics.get("needs_review_count", 0))),
            ("Ready", str(metrics.get("ready_count", 0))),
        ],
    )

    try:
        from charts import (
            advisor_hard_stops_chart,
            audit_outcomes_pie,
            first_pass_pie,
            issue_breakdown_pie,
            weekly_activity_chart,
        )

        _section_title(pdf, "Charts")
        pie1 = audit_outcomes_pie(metrics, compact=True)
        pie2 = first_pass_pie(metrics, compact=True)
        _embed_chart_pair(pdf, pie1, pie2)

        pie3 = issue_breakdown_pie(metrics, compact=True)
        weekly = metrics.get("weekly_trend")
        weekly_png = weekly_activity_chart(weekly, compact=True) if weekly is not None and not weekly.empty else None
        _embed_chart_pair(pdf, pie3, weekly_png)

        advisor_png = advisor_hard_stops_chart(metrics.get("advisor_summary"), compact=True)
        _embed_png(pdf, advisor_png)
    except Exception:
        pass

    advisor_df = metrics.get("advisor_summary")
    if advisor_df is not None and not advisor_df.empty:
        _section_title(pdf, "Advisor Coaching Focus")
        for _, row in advisor_df.head(10).iterrows():
            _body_text(
                pdf,
                (
                    f"{row.get('advisor', '')}: "
                    f"{int(row.get('reviews', 0))} reviews, "
                    f"avg score {float(row.get('avg_score', 0)):.1f}, "
                    f"{int(row.get('hard_stops', 0))} hard stops, "
                    f"${float(row.get('protected_value', 0)):,.0f} protected"
                ),
                size=9,
            )

    reasons = metrics.get("rejection_reasons")
    if reasons is not None and not reasons.empty:
        _section_title(pdf, "Top Rejection Reasons")
        for _, row in reasons.head(8).iterrows():
            _body_text(
                pdf,
                (
                    f"{row.get('rejection_reason', '')}: "
                    f"{int(row.get('count', 0))} claims, "
                    f"${float(row.get('total_value', 0)):,.0f}"
                ),
                size=9,
            )

    _section_title(pdf, "Assumptions Used")
    _key_value_lines(
        pdf,
        [
            ("Rework cost assumption", f"{rejection_rework_pct:.0%}"),
            ("Minutes saved per review", f"{minutes_saved:.0f}"),
            ("Admin hourly cost", f"${hourly_rate:,.0f}"),
        ],
    )

    _body_text(
        pdf,
        "Claims Protected reflects hard-stop claim dollars flagged before submission. "
        "Estimated Rework Avoided applies your rework assumption to that protected value. "
        "Estimated Labor Saved uses minutes saved per review at your admin hourly cost.",
        size=9,
    )

    return bytes(pdf.output())


def build_review_report_pdf(df, *, period_label: str = "All reviews") -> bytes:
    """Build a PDF summary of the Reporting review log."""
    import pandas as pd

    pdf = _ReportPDF(orientation="L", unit="mm", format="Letter")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    data = df.copy() if df is not None else pd.DataFrame()
    if data.empty:
        _body_text(pdf, "No reviews available for this report.")
        return bytes(pdf.output())

    for col in ("score", "total_claim_value", "hard_stop_value", "hard_stop_count", "warning_count"):
        if col in data.columns:
            data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0)

    _report_header(pdf, "RO Shield Review Report", period_label)

    summary_metrics = [
        ("Reviews", str(len(data))),
        ("Average Score", f"{float(data.get('score', pd.Series([0])).mean()):.1f}"),
        ("Total Claim Value", _format_money(data.get("total_claim_value", pd.Series([0])).sum())),
        ("Hard Stop Value", _format_money(data.get("hard_stop_value", pd.Series([0])).sum())),
        ("Hard Stops", str(int(data.get("hard_stop_count", pd.Series([0])).sum()))),
        ("Warnings", str(int(data.get("warning_count", pd.Series([0])).sum()))),
    ]
    _summary_metrics_table(pdf, summary_metrics)

    try:
        from charts import review_status_pie, score_distribution_chart

        _section_title(pdf, "Charts")
        status_png = review_status_pie(data, compact=True)
        score_png = score_distribution_chart(data, compact=True)
        _embed_chart_pair(pdf, status_png, score_png)
    except Exception:
        pass

    rows = data.sort_values("created_at", ascending=False) if "created_at" in data.columns else data
    max_rows = 100
    truncated = len(rows) > max_rows
    _review_log_table(pdf, rows.head(max_rows))

    if truncated:
        _body_text(
            pdf,
            f"Showing the most recent {max_rows} reviews. Use CSV export for the complete log.",
            size=9,
        )

    return bytes(pdf.output())
