"""Per-user display preferences (font family, color, size)."""

from __future__ import annotations

import html
import re

import streamlit as st

FONT_FAMILY_OPTIONS = {
    "System Default": "inherit",
    "Arial": "Arial, Helvetica, sans-serif",
    "Verdana": "Verdana, Geneva, sans-serif",
    "Trebuchet MS": "'Trebuchet MS', Tahoma, sans-serif",
    "Georgia": "Georgia, 'Times New Roman', serif",
    "Tahoma": "Tahoma, Geneva, sans-serif",
}

FONT_SIZE_MIN = 12
FONT_SIZE_MAX = 18
FONT_SIZE_DEFAULT = 15

DEFAULT_TEXT_COLOR = {
    "Dark": "#f8fbff",
    "Light": "#0f172a",
}


def default_display_prefs(theme: str = "Dark") -> dict:
    theme_key = "Light" if str(theme).lower() == "light" else "Dark"
    return {
        "font_family": "System Default",
        "font_color": DEFAULT_TEXT_COLOR[theme_key],
        "font_size": FONT_SIZE_DEFAULT,
    }


def normalize_display_prefs(raw: dict | None, *, theme: str = "Dark") -> dict:
    defaults = default_display_prefs(theme)
    raw = raw or {}
    family = str(raw.get("font_family") or defaults["font_family"])
    if family not in FONT_FAMILY_OPTIONS:
        family = defaults["font_family"]
    color = str(raw.get("font_color") or defaults["font_color"]).strip().lower()
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", color):
        color = defaults["font_color"]
    try:
        size = int(raw.get("font_size", defaults["font_size"]))
    except (TypeError, ValueError):
        size = defaults["font_size"]
    size = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, size))
    return {
        "font_family": family,
        "font_color": color,
        "font_size": size,
    }


def ensure_display_prefs_loaded(supabase, *, theme: str = "Dark") -> dict:
    if "user_display_prefs" in st.session_state:
        return st.session_state.user_display_prefs

    prefs = default_display_prefs(theme)
    person_id = st.session_state.get("current_person_id")
    if supabase is not None and person_id:
        try:
            row = (
                supabase.table("personnel")
                .select("display_prefs")
                .eq("id", int(person_id))
                .limit(1)
                .execute()
            )
            data = (row.data or [{}])[0]
            stored = data.get("display_prefs")
            if isinstance(stored, dict) and stored:
                prefs = normalize_display_prefs(stored, theme=theme)
        except Exception:
            pass

    st.session_state.user_display_prefs = prefs
    return prefs


def save_display_prefs(supabase, prefs: dict) -> None:
    st.session_state.user_display_prefs = prefs
    person_id = st.session_state.get("current_person_id")
    if supabase is None or not person_id:
        return
    try:
        supabase.table("personnel").update({"display_prefs": prefs}).eq("id", int(person_id)).execute()
    except Exception:
        pass


def build_user_display_css(prefs: dict) -> str:
    prefs = normalize_display_prefs(prefs)
    family = FONT_FAMILY_OPTIONS[prefs["font_family"]]
    family_css = html.escape(family, quote=True)
    color = html.escape(prefs["font_color"], quote=True)
    size = int(prefs["font_size"])
    return f"""
    .stApp {{
        --rg-user-font-family: {family_css};
        --rg-user-font-size: {size}px;
        --rg-user-text-color: {color};
    }}
    section.main .block-container {{
        font-family: var(--rg-user-font-family) !important;
        font-size: var(--rg-user-font-size) !important;
    }}
    section.main p,
    section.main label,
    section.main li,
    section.main td,
    section.main th,
    section.main div[data-testid="stMarkdownContainer"],
    section.main div[data-testid="stMarkdownContainer"] p,
    section.main div[data-testid="stCaptionContainer"] p,
    section.main div[data-testid="stTextInput"] label,
    section.main div[data-testid="stTextArea"] label,
    section.main div[data-testid="stNumberInput"] label,
    section.main div[data-testid="stSelectbox"] label,
    section.main div[data-testid="stCheckbox"] label,
    section.main div[data-testid="stDateInput"] label {{
        font-family: var(--rg-user-font-family) !important;
        font-size: var(--rg-user-font-size) !important;
        color: var(--rg-user-text-color) !important;
    }}
    section.main h1 {{ font-size: calc(var(--rg-user-font-size) * 1.55) !important; }}
    section.main h2 {{ font-size: calc(var(--rg-user-font-size) * 1.35) !important; }}
    section.main h3 {{ font-size: calc(var(--rg-user-font-size) * 1.15) !important; }}
    section.main h4 {{ font-size: calc(var(--rg-user-font-size) * 1.05) !important; }}
    section.main h1,
    section.main h2,
    section.main h3,
    section.main h4,
    section.main h5,
    section.main h6 {{
        font-family: var(--rg-user-font-family) !important;
        color: var(--rg-user-text-color) !important;
    }}
    section[data-testid="stSidebar"] .app-sidebar-name,
    section[data-testid="stSidebar"] .app-sidebar-sub,
    section[data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] p,
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] label,
    section[data-testid="stSidebar"] div[data-testid="stSlider"] label,
    section[data-testid="stSidebar"] .rg-sidebar-settings-title {{
        font-family: var(--rg-user-font-family) !important;
        font-size: var(--rg-user-font-size) !important;
        color: var(--rg-user-text-color) !important;
    }}
    .app-workspace-kicker,
    .app-workspace-header p,
    .review-scan-intro p,
    .review-scan-intro h3 {{
        font-family: var(--rg-user-font-family) !important;
        color: var(--rg-user-text-color) !important;
    }}
    .app-workspace-header h2 {{
        font-family: var(--rg-user-font-family) !important;
        font-size: calc(var(--rg-user-font-size) * 1.35) !important;
        color: var(--rg-user-text-color) !important;
    }}
    .app-workspace-header h2 span {{
        color: var(--rg-user-text-color) !important;
    }}
    [data-testid="stIconMaterial"],
    span[data-testid="stIconMaterial"],
    .material-symbols-rounded {{
        font-family: "Material Symbols Rounded" !important;
        font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        -webkit-text-fill-color: currentColor !important;
    }}
    """


def render_display_settings_sidebar(supabase, *, theme: str = "Dark") -> dict:
    prefs = ensure_display_prefs_loaded(supabase, theme=theme)
    if "user_display_font_family" not in st.session_state:
        st.session_state.user_display_font_family = prefs["font_family"]
        st.session_state.user_display_font_color = prefs["font_color"]
        st.session_state.user_display_font_size = int(prefs["font_size"])

    family_labels = list(FONT_FAMILY_OPTIONS.keys())

    st.sidebar.markdown(
        '<div class="rg-sidebar-settings-title">My Display</div>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption("Personalize fonts on your screen.")
    font_family = st.sidebar.selectbox(
        "Font style",
        family_labels,
        key="user_display_font_family",
    )
    font_color = st.sidebar.color_picker(
        "Font color",
        key="user_display_font_color",
    )
    font_size = st.sidebar.slider(
        "Font size",
        min_value=FONT_SIZE_MIN,
        max_value=FONT_SIZE_MAX,
        step=1,
        help=f"Limited to {FONT_SIZE_MAX}px so text fits the layout without clipping.",
        key="user_display_font_size",
    )
    if st.sidebar.button("Reset display defaults", key="user_display_reset", use_container_width=True):
        reset = default_display_prefs(theme)
        save_display_prefs(supabase, reset)
        st.session_state.user_display_font_family = reset["font_family"]
        st.session_state.user_display_font_color = reset["font_color"]
        st.session_state.user_display_font_size = reset["font_size"]
        st.rerun()

    updated = normalize_display_prefs(
        {
            "font_family": font_family,
            "font_color": font_color,
            "font_size": font_size,
        },
        theme=theme,
    )
    if updated != prefs:
        save_display_prefs(supabase, updated)
    return updated
