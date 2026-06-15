"""Shared visual polish — professional warranty workspace with clearer hierarchy and light motion."""

from __future__ import annotations

import html
import streamlit as st

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
        "toast": "OEM Audit Guide — upload Stellantis warranty audit rules",
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
    .rg-section-nav-marker + div[data-testid="stRadio"],
    .stApp:has(.rg-section-nav-marker) div[data-testid="stRadio"] {{
        margin: 0 0 12px 0 !important;
        padding: 10px 12px !important;
        border-radius: 16px !important;
        background: {surface} !important;
        border: 1px solid {border} !important;
        box-shadow: 0 10px 28px {glow};
        animation: rg-fade-up 0.5s ease-out 0.05s both;
    }}
    .stApp:has(.rg-section-nav-marker) div[data-testid="stRadio"] > label {{
        font-size: 0 !important;
        padding: 0 !important;
        min-height: 0 !important;
    }}
    .stApp:has(.rg-section-nav-marker) div[data-testid="stRadio"] > div {{
        gap: 6px !important;
    }}
    .stApp:has(.rg-section-nav-marker) div[data-testid="stRadio"] label[data-baseweb="radio"] {{
        margin: 0 !important;
        padding: 0 !important;
        background: transparent !important;
    }}
    .stApp:has(.rg-section-nav-marker) div[data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child {{
        display: none !important;
    }}
    .stApp:has(.rg-section-nav-marker) div[data-testid="stRadio"] label[data-baseweb="radio"] > div:last-child {{
        padding: 0.48rem 0.82rem !important;
        border-radius: 10px !important;
        border: 1px solid transparent !important;
        font-size: 0.86rem !important;
        font-weight: 600 !important;
        color: {muted} !important;
        transition: color 0.15s ease, background-color 0.15s ease, transform 0.15s ease, border-color 0.15s ease;
    }}
    .stApp:has(.rg-section-nav-marker) div[data-testid="stRadio"] label[data-baseweb="radio"]:has(input:checked) > div:last-child {{
        color: {text} !important;
        background: linear-gradient(180deg, {primary} 0%, {"#1d4ed8" if not is_light else "#1e40af"} 100%) !important;
        border-color: {"#93c5fd" if not is_light else "#93c5fd"} !important;
        box-shadow: 0 4px 14px {glow};
        transform: translateY(-1px);
    }}
    .stApp:has(.rg-section-nav-marker) div[data-testid="stRadio"] label[data-baseweb="radio"]:hover > div:last-child {{
        color: {text} !important;
        background: {"rgba(59, 130, 246, 0.18)" if not is_light else "rgba(37, 99, 235, 0.12)"} !important;
    }}
    .stApp:has(.rg-section-nav-marker) div[data-testid="stRadio"] [role="radiogroup"] {{
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 6px !important;
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
        .rg-section-nav-marker + div[data-testid="stRadio"],
        .stApp:has(.rg-section-nav-marker) div[data-testid="stRadio"],
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
