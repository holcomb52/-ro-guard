"""Shared visual polish — professional warranty workspace with clearer hierarchy and light motion."""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from typing import Any

import streamlit as st

SECTION_NAV_GROUPS: list[tuple[str, list[str]]] = [
    (
        "Daily workspace",
        [
            "Review",
            "Pending Claims",
            "ROI Dashboard",
            "Coaching",
            "POPPS Report",
            "Reporting",
        ],
    ),
    (
        "Libraries",
        [
            "Claim Learning",
            "TSB / Bulletins",
            "OEM Audit Guide",
            "WAM",
        ],
    ),
    (
        "Administration",
        [
            "Admin",
            "Scheduled Reports",
        ],
    ),
]

SECTION_NAV_META: dict[str, dict[str, str]] = {
    "Review": {
        "icon": "🔍",
        "toast": "Review — scan ROs and run warranty audits",
        "tag": "Audit",
    },
    "Pending Claims": {
        "icon": "⏳",
        "toast": "Pending Claims — track open warranty work",
        "tag": "Queue",
    },
    "ROI Dashboard": {
        "icon": "📈",
        "toast": "ROI Dashboard — dollars protected and trends",
        "tag": "ROI",
    },
    "Coaching": {
        "icon": "🎯",
        "toast": "Coaching — focus areas for your team",
        "tag": "Coach",
    },
    "POPPS Report": {
        "icon": "📊",
        "toast": "POPPS — factory performance overview",
        "tag": "POPPS",
    },
    "Claim Learning": {
        "icon": "📚",
        "toast": "Claim Learning — patterns from paid and declined claims",
        "tag": "Learn",
    },
    "Reporting": {
        "icon": "📋",
        "toast": "Reporting — exports and summaries",
        "tag": "Reports",
    },
    "Admin": {
        "icon": "⚙️",
        "toast": "Admin — dealership settings and personnel",
        "tag": "Admin",
    },
    "TSB / Bulletins": {
        "icon": "📢",
        "toast": "TSB / Bulletins — technical service information",
        "tag": "TSB",
    },
    "OEM Audit Guide": {
        "icon": "🛡️",
        "toast": "OEM Audit Guide — WAM supplement & chargeback prevention",
        "tag": "OEM Audit",
    },
    "Scheduled Reports": {
        "icon": "🗓️",
        "toast": "Scheduled Reports — automated email delivery",
        "tag": "Schedule",
    },
    "WAM": {
        "icon": "📖",
        "toast": "WAM — warranty administration reference",
        "tag": "WAM",
    },
}


def _nav_button_key(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", str(label or "").lower()).strip("_")
    return slug or "section"


def _render_nav_button_row(
    items: list[str],
    *,
    current: str,
    on_change: Callable[[], Any] | None,
    key_prefix: str,
) -> None:
    if not items:
        return
    cols = st.columns(len(items))
    for col, label in zip(cols, items):
        with col:
            is_active = current == label
            if st.button(
                label,
                key=f"rg_main_nav_{key_prefix}_{_nav_button_key(label)}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                if label != current:
                    st.session_state["main_section_nav"] = label
                    st.session_state["_rg_main_nav_collapsed"] = True
                    if on_change is not None:
                        on_change()
                    st.rerun()


def render_main_section_nav(
    section_labels: list[str],
    *,
    on_change: Callable[[], Any] | None = None,
) -> str:
    """Grouped pill navigation — entire panel collapses to one line by default."""
    allowed = set(section_labels)
    current = str(st.session_state.get("main_section_nav") or "")
    if current not in allowed:
        st.session_state["main_section_nav"] = section_labels[0]
        current = section_labels[0]

    nav_collapsed = bool(st.session_state.get("_rg_main_nav_collapsed", True))
    marker_classes = "rg-section-nav-marker"
    if nav_collapsed:
        marker_classes += " rg-section-nav-collapsed"

    with st.container(border=True):
        st.markdown(
            f'<div class="{marker_classes}" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        toggle_label = (
            f"▸ Navigation · {current}"
            if nav_collapsed
            else f"▾ Navigation · {current}"
        )
        st.markdown(
            '<div class="rg-main-nav-toggle-marker" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        if st.button(
            toggle_label,
            key="rg_main_nav_toggle",
            use_container_width=True,
            type="secondary",
        ):
            st.session_state["_rg_main_nav_collapsed"] = not nav_collapsed
            st.rerun()

        if nav_collapsed:
            return str(st.session_state.get("main_section_nav") or section_labels[0])

        for group_label, group_items in SECTION_NAV_GROUPS:
            items = [item for item in group_items if item in allowed]
            if not items:
                continue
            st.markdown(
                f'<div class="rg-nav-group-label">{html.escape(group_label)}</div>',
                unsafe_allow_html=True,
            )
            _render_nav_button_row(
                items,
                current=current,
                on_change=on_change,
                key_prefix=_nav_button_key(group_label),
            )

    return str(st.session_state.get("main_section_nav") or section_labels[0])


def notify_section_change(active_section: str) -> None:
    """Brief toast when the user switches main workspace tabs."""
    previous = str(st.session_state.get("_rg_last_section") or "")
    if not active_section or active_section == previous:
        return
    st.session_state["_rg_last_section"] = active_section
    meta = SECTION_NAV_META.get(active_section) or {}
    message = meta.get("toast") or f"Opened {active_section}"
    st.toast(message, icon=meta.get("icon") or "📋")


def render_workspace_feature_chips() -> None:
    """Highlight core workspace capabilities under the main header."""
    st.markdown(
        """
<div class="app-workspace-chips" aria-label="Workspace highlights">
<span class="rg-chip rg-chip-audit"><span class="rg-chip-dot"></span>Live claim audits</span>
<span class="rg-chip rg-chip-roi"><span class="rg-chip-dot"></span>ROI tracking</span>
<span class="rg-chip rg-chip-popps"><span class="rg-chip-dot"></span>POPPS insights</span>
<span class="rg-chip rg-chip-team"><span class="rg-chip-dot"></span>Team-wide cloud save</span>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_form_section(
    title: str,
    caption: str | None = None,
    *,
    step: str | None = None,
) -> None:
    """Consistent in-form section heading used across Review and admin panels."""
    step_html = (
        f'<span class="rg-form-section-step">{html.escape(step)}</span>'
        if step
        else ""
    )
    cap_html = (
        f'<div class="rg-form-section-caption">{html.escape(caption)}</div>'
        if caption
        else ""
    )
    st.markdown(
        f"""
<div class="rg-form-section">
{step_html}
<div class="rg-form-section-title">{html.escape(title)}</div>
{cap_html}
</div>
        """,
        unsafe_allow_html=True,
    )


def render_hard_stop_panel(messages: list[str], *, title: str = "Fix before submit") -> None:
    """Single consolidated hard-stop list instead of stacked error banners."""
    cleaned = [str(message).strip() for message in messages if str(message).strip()]
    if not cleaned:
        return
    items = "".join(f"<li>{html.escape(message)}</li>" for message in cleaned)
    st.markdown(
        f"""
<div class="rg-hard-stop-panel">
<div class="rg-hard-stop-title">{html.escape(title)}</div>
<ul class="rg-hard-stop-list">{items}</ul>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_section_hero(
    title: str,
    subtitle: str,
    *,
    icon: str = "📋",
    tips: list[str] | None = None,
) -> None:
    """Section intro card — use below main navigation for key tabs."""
    tips = tips or []
    tips_html = ""
    if tips:
        chips = "".join(
            f'<span class="rg-tip-chip">{html.escape(str(tip))}</span>' for tip in tips
        )
        tips_html = f'<div class="rg-hero-tips">{chips}</div>'
    st.markdown(
        f"""
<div class="rg-section-hero">
<div class="rg-section-hero-icon" aria-hidden="true">{html.escape(icon)}</div>
<div class="rg-section-hero-body">
<div class="rg-section-hero-title">{html.escape(title)}</div>
<div class="rg-section-hero-sub">{html.escape(subtitle)}</div>
{tips_html}
</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def workspace_polish_css(theme: str = "Dark") -> str:
    """Animations, pill navigation, metric hover, and section heroes."""
    is_light = str(theme).lower() == "light"
    text = "#f8fbff" if not is_light else "#0f172a"
    muted = "#94a3b8" if not is_light else "#64748b"
    surface = "rgba(7, 19, 34, 0.72)" if not is_light else "rgba(255, 255, 255, 0.92)"
    border = "rgba(62, 150, 255, 0.32)" if not is_light else "#c7d5e3"
    primary = "#3b82f6" if not is_light else "#2563eb"
    glow = "rgba(59, 130, 246, 0.35)" if not is_light else "rgba(37, 99, 235, 0.22)"
    chip_bg = "rgba(37, 99, 235, 0.14)" if not is_light else "rgba(239, 246, 255, 0.95)"
    return f"""
    @keyframes rg-fade-up {{
        from {{ opacity: 0; transform: translateY(6px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes rg-chip-pulse {{
        0%, 100% {{ box-shadow: 0 0 0 0 {glow}; }}
        50% {{ box-shadow: 0 0 0 4px transparent; }}
    }}
    .app-workspace-chips {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px 10px;
        margin: 0 0 14px 0;
        animation: rg-fade-up 0.45s ease-out both;
    }}
    .rg-chip {{
        display: inline-flex;
        align-items: center;
        gap: 7px;
        padding: 6px 12px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        color: {text} !important;
        background: {chip_bg};
        border: 1px solid {border};
        transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
    }}
    .rg-chip:hover {{
        transform: translateY(-1px);
        border-color: {primary};
        box-shadow: 0 6px 18px {glow};
    }}
    .rg-chip-dot {{
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: {primary};
        animation: rg-chip-pulse 2.4s ease-in-out infinite;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.rg-section-nav-marker) {{
        margin: 0 0 14px 0 !important;
        padding: 0.55rem 0.65rem 0.45rem !important;
        border-radius: 14px !important;
        background: {surface} !important;
        border-color: {border} !important;
        box-shadow: none !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.rg-section-nav-collapsed) {{
        padding: 0.3rem 0.55rem !important;
        margin-bottom: 10px !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.rg-section-nav-marker) .rg-nav-group-label {{
        font-size: 0.66rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.08em !important;
        text-transform: uppercase !important;
        color: {muted} !important;
        margin: 0.45rem 0 0.35rem 0 !important;
        padding-left: 0.1rem !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.rg-section-nav-marker) .rg-nav-group-label:first-of-type {{
        margin-top: 0.1rem !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.rg-section-nav-marker) .rg-main-nav-toggle-marker + div div.stButton > button {{
        min-height: 1.85rem !important;
        padding: 0.28rem 0.55rem !important;
        border-radius: 10px !important;
        font-size: 0.74rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.04em !important;
        text-transform: uppercase !important;
        text-align: left !important;
        justify-content: flex-start !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.rg-section-nav-marker) div.stButton {{
        margin: 0 !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.rg-section-nav-marker) div.stButton > button {{
        min-height: 2rem !important;
        padding: 0.38rem 0.55rem !important;
        border-radius: 999px !important;
        font-size: 0.8rem !important;
        font-weight: 650 !important;
        white-space: nowrap !important;
        box-shadow: none !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.rg-section-nav-marker) div.stButton > button[kind="secondary"] {{
        color: {text} !important;
        background: {"rgba(15, 23, 42, 0.35)" if not is_light else "rgba(248, 250, 252, 0.95)"} !important;
        border: 1px solid {border} !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.rg-section-nav-marker) div.stButton > button[kind="secondary"]:hover {{
        color: {text} !important;
        border-color: {primary} !important;
        background: {"rgba(59, 130, 246, 0.16)" if not is_light else "rgba(219, 234, 254, 0.95)"} !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.rg-section-nav-marker) div.stButton > button[kind="primary"] {{
        color: #ffffff !important;
        background: {primary} !important;
        border: 1px solid {"#93c5fd" if not is_light else "#2563eb"} !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.rg-section-nav-marker) div.stButton > button[kind="primary"]:hover {{
        background: {"#2563eb" if not is_light else "#1d4ed8"} !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.rg-section-nav-marker) div[data-testid="column"] {{
        padding-left: 0.18rem !important;
        padding-right: 0.18rem !important;
    }}
    .rg-section-hero {{
        display: flex;
        align-items: flex-start;
        gap: 14px;
        margin: 0 0 16px 0;
        padding: 16px 18px;
        border-radius: 16px;
        background: linear-gradient(135deg, {"rgba(10, 31, 57, 0.92)" if not is_light else "rgba(239, 246, 255, 0.95)"} 0%, {surface} 100%);
        border: 1px solid {border};
        box-shadow: 0 12px 32px {glow};
        animation: rg-fade-up 0.45s ease-out both;
    }}
    .rg-section-hero-icon {{
        flex: 0 0 44px;
        width: 44px;
        height: 44px;
        display: grid;
        place-items: center;
        font-size: 1.35rem;
        border-radius: 12px;
        background: {"rgba(37, 99, 235, 0.22)" if not is_light else "rgba(219, 234, 254, 0.95)"};
        border: 1px solid {border};
    }}
    .rg-section-hero-title {{
        font-size: 1.35rem;
        font-weight: 800;
        color: {text} !important;
        line-height: 1.2;
        margin-bottom: 4px;
    }}
    .rg-section-hero-sub {{
        font-size: 0.92rem;
        line-height: 1.45;
        color: {muted} !important;
    }}
    .rg-hero-tips {{
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 10px;
    }}
    .rg-tip-chip {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 600;
        color: {text} !important;
        background: {"rgba(15, 23, 42, 0.45)" if not is_light else "rgba(241, 245, 249, 0.95)"};
        border: 1px solid {border};
    }}
    div[data-testid="stMetric"] {{
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }}
    div[data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        border-color: {primary} !important;
        box-shadow: 0 10px 26px {glow} !important;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }}
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
        border-color: {primary} !important;
        box-shadow: 0 8px 22px {glow} !important;
    }}
    section[data-testid="stFileUploaderDropzone"] {{
        transition: border-color 0.2s ease, background-color 0.2s ease, transform 0.2s ease;
    }}
    section[data-testid="stFileUploaderDropzone"]:hover {{
        transform: translateY(-1px);
        border-color: {primary} !important;
    }}
    div.stButton > button,
    button[kind="primary"],
    button[kind="secondary"] {{
        transition: transform 0.15s ease, box-shadow 0.15s ease, background 0.15s ease !important;
    }}
    div.stButton > button:active,
    button[kind="primary"]:active,
    button[kind="secondary"]:active {{
        transform: scale(0.98) !important;
    }}
    div[data-testid="stAlert"] {{
        border-radius: 12px !important;
        animation: rg-fade-up 0.35s ease-out both;
    }}
    @media (prefers-reduced-motion: reduce) {{
        .app-workspace-chips,
        .rg-section-hero,
        div[data-testid="stAlert"] {{
            animation: none !important;
        }}
        .rg-chip-dot {{
            animation: none !important;
        }}
        div[data-testid="stMetric"]:hover,
        div[data-testid="stVerticalBlockBorderWrapper"]:hover,
        section[data-testid="stFileUploaderDropzone"]:hover {{
            transform: none !important;
        }}
    }}
    """


def layout_system_css(theme: str = "Dark") -> str:
    """Shared spacing, form sections, and page rhythm outside Review-specific CSS."""
    is_light = str(theme).lower() == "light"
    text = "#0f172a" if is_light else "#f8fbff"
    muted = "#64748b" if is_light else "#94a3b8"
    border = "#c7d5e3" if is_light else "rgba(62, 150, 255, 0.28)"
    surface = "rgba(255, 255, 255, 0.92)" if is_light else "rgba(7, 19, 34, 0.55)"
    stop_bg = "#fef2f2" if is_light else "rgba(80, 12, 18, 0.55)"
    stop_border = "#f87171" if is_light else "rgba(255, 110, 110, 0.85)"
    stop_text = "#991b1b" if is_light else "#fecaca"
    return f"""
    .stApp:not(:has(.review-workspace-marker)) .app-workspace-chips {{
        display: none !important;
    }}
    .stApp:not(:has(.review-workspace-marker)) .app-workspace-header h2 {{
        font-size: 1.15rem !important;
        margin-bottom: 0.15rem !important;
    }}
    .stApp:not(:has(.review-workspace-marker)) .app-workspace-header p,
    .stApp:not(:has(.review-workspace-marker)) .app-workspace-accent {{
        display: none !important;
    }}
    .rg-form-section {{
        margin: 0.85rem 0 0.55rem 0;
        padding-bottom: 0.15rem;
        border-bottom: 1px solid {border};
    }}
    .rg-form-section-step {{
        display: inline-block;
        margin-bottom: 0.2rem;
        padding: 0.15rem 0.55rem;
        border-radius: 999px;
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: {"#1d4ed8" if is_light else "#93c5fd"} !important;
        background: {"rgba(219, 234, 254, 0.95)" if is_light else "rgba(37, 99, 235, 0.18)"};
        border: 1px solid {border};
    }}
    .rg-form-section-title {{
        font-size: 1rem;
        font-weight: 750;
        color: {text} !important;
        line-height: 1.25;
    }}
    .rg-form-section-caption {{
        margin-top: 0.2rem;
        font-size: 0.8rem;
        line-height: 1.4;
        color: {muted} !important;
    }}
    .rg-hard-stop-panel {{
        margin: 0.65rem 0 0.85rem 0;
        padding: 0.75rem 0.95rem;
        border-radius: 12px;
        border: 1px solid {stop_border};
        background: {stop_bg};
    }}
    .rg-hard-stop-title {{
        font-size: 0.82rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: {stop_text} !important;
        margin-bottom: 0.35rem;
    }}
    .rg-hard-stop-list {{
        margin: 0;
        padding-left: 1.1rem;
        color: {stop_text} !important;
        font-size: 0.88rem;
        line-height: 1.45;
    }}
    .rg-hard-stop-list li + li {{
        margin-top: 0.2rem;
    }}
    section.main div[data-testid="stMarkdownContainer"]:has(.rg-form-section) + div,
    section.main div[data-testid="stMarkdownContainer"]:has(.rg-hard-stop-panel) + div {{
        margin-top: 0 !important;
    }}
    div.roguard-report-export-card {{
        border: 1px solid {border} !important;
        border-radius: 12px !important;
        padding: 0.55rem 0.65rem 0.35rem !important;
        margin: 0.35rem 0 0.65rem 0 !important;
        background: {surface} !important;
    }}
    div.roguard-report-export-card [data-testid="stCaptionContainer"] p {{
        font-size: 0.76rem !important;
        line-height: 1.35 !important;
        margin-bottom: 0 !important;
    }}
    div.roguard-report-export-toolbar {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: space-between;
        gap: 0.45rem 0.75rem;
        margin-bottom: 0.35rem;
    }}
    div.roguard-report-export-label {{
        font-size: 0.78rem;
        color: {muted} !important;
        line-height: 1.35;
    }}
    """
