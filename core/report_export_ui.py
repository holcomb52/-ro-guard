"""Branded report tables and PDF downloads — replaces Streamlit's generic CSV toolbar export."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import streamlit as st

from .pdf_reports import build_dataframe_report_pdf

BRANDED_EXPORT_CAPTION = (
    "Use **Download PDF report** for the branded RO GUARD export with ROGUARD watermark on every page."
)

_EXPORT_CSS_INJECTED = "_roguard_report_export_css"


def period_label_from_df(df: pd.DataFrame | None, *, default: str = "Selected period") -> str:
    if df is None or df.empty or "created_at" not in df.columns:
        return default
    series = pd.to_datetime(df["created_at"], errors="coerce")
    if series.notna().any():
        return f"{series.min()} to {series.max()}"
    return default


def _coerce_export_frame(df: Any) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    if isinstance(df, pd.DataFrame):
        return df.copy()
    if hasattr(df, "data") and isinstance(getattr(df, "data", None), pd.DataFrame):
        return df.data.copy()
    return pd.DataFrame(df)


def inject_report_export_styles() -> None:
    if st.session_state.get(_EXPORT_CSS_INJECTED):
        return
    st.session_state[_EXPORT_CSS_INJECTED] = True
    st.markdown(
        """
        <style>
        div.roguard-report-export-card {
            border: 1px solid rgba(62, 150, 255, 0.28);
            border-radius: 14px;
            padding: 0.35rem 0.5rem 0.15rem;
            margin-bottom: 0.75rem;
            background: rgba(7, 19, 34, 0.35);
        }
        div.roguard-report-export-card [data-testid="stDownloadButton"] button {
            min-height: 2rem;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _resolve_pdf_builder(
    export_frame: pd.DataFrame,
    *,
    pdf_builder: Callable[[], bytes] | None,
    pdf_title: str,
    period_label: str,
    pdf_subtitle: str,
    pdf_section: str,
    pdf_landscape: bool | None,
) -> Callable[[], bytes]:
    if pdf_builder is not None:
        return pdf_builder
    title = pdf_title or "RO GUARD Report"
    subtitle = pdf_subtitle or title

    def _build() -> bytes:
        return build_dataframe_report_pdf(
            export_frame,
            title=title,
            period_label=period_label,
            subtitle=subtitle,
            section_title=pdf_section,
            landscape=pdf_landscape,
        )

    return _build


def render_branded_pdf_download(
    *,
    pdf_builder: Callable[[], bytes],
    pdf_filename: str,
    export_key: str,
    caption: str = BRANDED_EXPORT_CAPTION,
    label: str = "Download PDF report",
) -> None:
    """Branded PDF download card (no table) — audit, ROI summary, etc."""
    inject_report_export_styles()

    pdf_bytes: bytes | None = None
    pdf_error: str | None = None
    try:
        pdf_bytes = pdf_builder()
    except ImportError:
        pdf_error = "PDF export needs fpdf2. Run: python3 -m pip install -r requirements.txt"
    except Exception as exc:
        pdf_error = f"PDF could not be generated: {exc}"

    st.markdown('<div class="roguard-report-export-card">', unsafe_allow_html=True)
    tool_left, tool_right = st.columns([1.6, 1])
    with tool_left:
        st.caption(caption)
    with tool_right:
        if pdf_bytes:
            st.download_button(
                label,
                data=pdf_bytes,
                file_name=pdf_filename,
                mime="application/pdf",
                key=f"{export_key}_pdf_primary",
                use_container_width=True,
                type="primary",
                help="Professional RO GUARD PDF with ROGUARD ghost watermark",
            )
        elif pdf_error:
            st.error(pdf_error)
    st.markdown("</div>", unsafe_allow_html=True)


def render_branded_report_table(
    df: Any,
    *,
    export_df: pd.DataFrame | None = None,
    pdf_builder: Callable[[], bytes] | None = None,
    pdf_title: str = "",
    period_label: str = "",
    pdf_subtitle: str = "",
    pdf_section: str = "Detail",
    pdf_landscape: bool | None = None,
    pdf_filename: str,
    export_key: str,
    csv_filename: str | None = None,
    show_csv: bool = True,
    table_caption: str = BRANDED_EXPORT_CAPTION,
    **dataframe_kwargs: Any,
) -> None:
    """Report table with Download PDF where users expect the toolbar download button."""
    inject_report_export_styles()
    export_frame = _coerce_export_frame(export_df if export_df is not None else df)
    builder = _resolve_pdf_builder(
        export_frame,
        pdf_builder=pdf_builder,
        pdf_title=pdf_title,
        period_label=period_label,
        pdf_subtitle=pdf_subtitle,
        pdf_section=pdf_section,
        pdf_landscape=pdf_landscape,
    )

    pdf_bytes: bytes | None = None
    pdf_error: str | None = None
    try:
        pdf_bytes = builder()
    except ImportError:
        pdf_error = "PDF export needs fpdf2. Run: python3 -m pip install -r requirements.txt"
    except Exception as exc:
        pdf_error = f"PDF could not be generated: {exc}"

    st.markdown('<div class="roguard-report-export-card">', unsafe_allow_html=True)

    tool_left, tool_right = st.columns([1.6, 1])
    with tool_left:
        st.caption(table_caption)
    with tool_right:
        if pdf_bytes:
            st.download_button(
                "Download PDF report",
                data=pdf_bytes,
                file_name=pdf_filename,
                mime="application/pdf",
                key=f"{export_key}_pdf_primary",
                use_container_width=True,
                type="primary",
                help="Professional RO GUARD PDF with ROGUARD ghost watermark",
            )
        elif pdf_error:
            st.error(pdf_error)

    st.dataframe(df, use_container_width=True, hide_index=True, **dataframe_kwargs)

    if show_csv and csv_filename:
        st.download_button(
            "Download CSV (spreadsheet)",
            export_frame.to_csv(index=False),
            csv_filename,
            "text/csv",
            use_container_width=True,
            key=f"{export_key}_csv_secondary",
        )

    st.markdown("</div>", unsafe_allow_html=True)
