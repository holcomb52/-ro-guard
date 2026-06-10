"""Simple / Full layout helpers for the Review tab."""

from __future__ import annotations

import html

import streamlit as st

SIMPLE_STEP_LABELS = ("RO info", "Job story", "Documentation", "Save")


def review_simple_ui_css(theme: str = "Dark") -> str:
    is_light = str(theme).lower() == "light"
    border = "var(--rg-border, #b6c7da)" if is_light else "rgba(62, 150, 255, .24)"
    surface = "var(--rg-surface-card, #f4f8fc)" if is_light else "rgba(7, 19, 34, .82)"
    text = "#0f172a" if is_light else "#e8f0f8"
    muted = "#64748b" if is_light else "#94a3b8"
    accent = "#1d4ed8" if is_light else "#60a5fa"
    accent_soft = "rgba(29, 78, 216, .12)" if is_light else "rgba(96, 165, 250, .14)"

    return f"""
    .stApp:has(.review-simple-mode) .app-workspace-chips {{
        display: none !important;
    }}
    .stApp:has(.review-simple-mode) .review-open-claims-strip {{
        margin-bottom: 0.35rem !important;
        padding: 0.65rem 0.85rem !important;
    }}
    .review-view-bar {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 0.65rem 1rem;
        border: 1px solid {border};
        background: {surface};
        border-radius: 14px;
        padding: 0.65rem 0.85rem;
        margin: 0 0 0.75rem 0;
    }}
    .review-view-bar-title {{
        font-size: 0.92rem;
        font-weight: 700;
        color: {text};
    }}
    .review-view-bar-caption {{
        font-size: 0.78rem;
        color: {muted};
        margin-top: 0.1rem;
    }}
    .review-step-rail {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
        margin: 0 0 0.85rem 0;
    }}
    .review-step-pill {{
        border: 1px solid {border};
        border-radius: 999px;
        padding: 0.28rem 0.72rem;
        font-size: 0.78rem;
        font-weight: 650;
        color: {muted};
        background: {surface};
    }}
    .review-step-pill.active {{
        color: {accent};
        border-color: {accent};
        background: {accent_soft};
    }}
    .review-simple-section {{
        border: 1px solid {border};
        border-radius: 14px;
        padding: 0.15rem 0.85rem 0.65rem;
        margin: 0.55rem 0 0.75rem 0;
        background: {surface};
    }}
    .review-simple-section-title {{
        font-size: 0.98rem;
        font-weight: 750;
        color: {text};
        margin: 0.55rem 0 0.15rem;
    }}
    .review-simple-section-caption {{
        font-size: 0.8rem;
        color: {muted};
        margin: 0 0 0.35rem;
    }}
    .review-simple-more details > summary {{
        font-weight: 650;
        color: {accent};
        cursor: pointer;
        padding: 0.35rem 0;
    }}
    .live-submit-bar.compact {{
        padding: 0.65rem 0.9rem !important;
        margin-bottom: 0.75rem !important;
    }}
    .live-submit-bar.compact .live-submit-metrics {{
        gap: 0.65rem 1rem !important;
        font-size: 0.82rem !important;
    }}
    .live-submit-bar.compact .live-submit-main {{
        margin-bottom: 0.25rem !important;
    }}
    .review-doc-group-hint {{
        font-size: 0.76rem;
        color: {accent};
        font-weight: 650;
        margin: 0 0 0.35rem;
    }}
    """


def render_review_view_toggle(*, theme: str = "Dark") -> bool:
    """Return True when Simple view is selected."""
    if "review_view_mode" not in st.session_state:
        st.session_state.review_view_mode = "Simple"

    st.markdown(f"<style>{review_simple_ui_css(theme)}</style>", unsafe_allow_html=True)
    st.markdown(
        """
<div class="review-view-bar">
  <div>
    <div class="review-view-bar-title">Review layout</div>
    <div class="review-view-bar-caption">Simple hides optional tools until you need them.</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    mode = st.radio(
        "Review layout",
        ["Simple", "Full"],
        horizontal=True,
        label_visibility="collapsed",
        key="review_view_mode",
    )
    return str(mode) == "Simple"


def render_simple_step_rail(*, active_step: int = 2) -> None:
    pills = []
    for idx, label in enumerate(SIMPLE_STEP_LABELS, start=1):
        cls = "review-step-pill active" if idx == active_step else "review-step-pill"
        pills.append(f'<span class="{cls}">{idx}. {html.escape(label)}</span>')
    st.markdown(
        f'<div class="review-step-rail">{"".join(pills)}</div>',
        unsafe_allow_html=True,
    )


def render_simple_section_header(title: str, caption: str = "") -> None:
    cap = f'<div class="review-simple-section-caption">{html.escape(caption)}</div>' if caption else ""
    st.markdown(
        f"""
<div class="review-simple-section">
  <div class="review-simple-section-title">{html.escape(title)}</div>
  {cap}
        """,
        unsafe_allow_html=True,
    )


def close_simple_section() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_compact_live_status(summary: dict) -> None:
    status = summary["status"]
    if "DO NOT" in status:
        cls = "status-stop"
    elif "NEEDS" in status:
        cls = "status-review"
    else:
        cls = "status-ready"

    st.markdown(
        f"""
<div class="live-submit-bar compact {cls}">
  <div class="live-submit-main">
    <span class="live-submit-status">{html.escape(status)}</span>
    <span class="live-submit-reason">{html.escape(summary.get("status_reason", ""))}</span>
  </div>
  <div class="live-submit-metrics">
    <span><strong>Score</strong> {summary["score"]}</span>
    <span><strong>Claim</strong> ${summary["total_value"]:,.0f}</span>
    <span><strong>Stops</strong> {summary["hard_stop_count"]}</span>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
