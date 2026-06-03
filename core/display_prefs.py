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


def _theme_key(theme: str) -> str:
    return "Light" if str(theme).lower() == "light" else "Dark"


def _hex_luminance(hex_color: str) -> float:
    value = str(hex_color or "").strip().lstrip("#")
    if len(value) != 6:
        return 0.5
    red = int(value[0:2], 16)
    green = int(value[2:4], 16)
    blue = int(value[4:6], 16)
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255


def color_readable_on_theme(color: str, theme: str) -> bool:
    lum = _hex_luminance(color)
    if _theme_key(theme) == "Light":
        return lum <= 0.58
    return lum >= 0.42


def default_display_prefs(theme: str = "Dark") -> dict:
    theme_key = _theme_key(theme)
    return {
        "font_family": "System Default",
        "font_color": DEFAULT_TEXT_COLOR[theme_key],
        "font_colors": dict(DEFAULT_TEXT_COLOR),
        "font_size": FONT_SIZE_DEFAULT,
    }


def _normalize_hex_color(color: str, *, fallback: str) -> str:
    value = str(color or fallback).strip().lower()
    if not re.fullmatch(r"#[0-9a-f]{6}", value):
        return fallback
    return value


def color_for_theme(raw: dict | None, theme: str) -> str:
    theme_key = _theme_key(theme)
    defaults = default_display_prefs(theme)
    raw = raw or {}
    colors = raw.get("font_colors")
    if isinstance(colors, dict):
        stored = colors.get(theme_key)
        if stored:
            candidate = _normalize_hex_color(stored, fallback=defaults["font_color"])
            if color_readable_on_theme(candidate, theme_key):
                return candidate
    legacy = raw.get("font_color")
    if legacy:
        candidate = _normalize_hex_color(legacy, fallback=defaults["font_color"])
        if color_readable_on_theme(candidate, theme_key):
            return candidate
    return defaults["font_color"]


def normalize_display_prefs(raw: dict | None, *, theme: str = "Dark") -> dict:
    defaults = default_display_prefs(theme)
    theme_key = _theme_key(theme)
    raw = raw or {}
    family = str(raw.get("font_family") or defaults["font_family"])
    if family not in FONT_FAMILY_OPTIONS:
        family = defaults["font_family"]
    color = color_for_theme(raw, theme)
    try:
        size = int(raw.get("font_size", defaults["font_size"]))
    except (TypeError, ValueError):
        size = defaults["font_size"]
    size = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, size))

    font_colors = dict(DEFAULT_TEXT_COLOR)
    stored_colors = raw.get("font_colors")
    if isinstance(stored_colors, dict):
        for key in ("Dark", "Light"):
            if stored_colors.get(key):
                candidate = _normalize_hex_color(stored_colors[key], fallback=DEFAULT_TEXT_COLOR[key])
                if color_readable_on_theme(candidate, key):
                    font_colors[key] = candidate
    font_colors[theme_key] = color

    return {
        "font_family": family,
        "font_color": color,
        "font_colors": font_colors,
        "font_size": size,
    }


def ensure_display_prefs_loaded(supabase, *, theme: str = "Dark") -> dict:
    theme_key = _theme_key(theme)
    if "user_display_prefs" not in st.session_state:
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

    normalized = normalize_display_prefs(st.session_state.user_display_prefs, theme=theme)
    previous_theme = st.session_state.get("_display_prefs_theme")
    if previous_theme != theme_key:
        st.session_state._display_prefs_theme = theme_key
        request_display_widget_resync()
    st.session_state.user_display_prefs = normalized
    return normalized


def save_display_prefs(supabase, prefs: dict, *, theme: str = "Dark") -> None:
    normalized = normalize_display_prefs(prefs, theme=theme)
    st.session_state.user_display_prefs = normalized
    person_id = st.session_state.get("current_person_id")
    if supabase is None or not person_id:
        return
    try:
        supabase.table("personnel").update({"display_prefs": normalized}).eq("id", int(person_id)).execute()
    except Exception:
        pass


def seed_display_widget_state(prefs: dict) -> None:
    """Set widget keys from prefs. Call only before those widgets render."""
    st.session_state.user_display_font_family = prefs["font_family"]
    st.session_state.user_display_font_color = prefs["font_color"]
    st.session_state.user_display_font_size = int(prefs["font_size"])


def request_display_widget_resync() -> None:
    st.session_state._display_widget_resync = True


def build_user_display_css(prefs: dict, *, theme: str = "Dark") -> str:
    prefs = normalize_display_prefs(prefs, theme=theme)
    family = FONT_FAMILY_OPTIONS[prefs["font_family"]]
    family_css = html.escape(family, quote=True)
    size = int(prefs["font_size"])
    theme_key = _theme_key(theme)

    shared = f"""
    .stApp {{
        --rg-user-font-family: {family_css};
        --rg-user-font-size: {size}px;
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

    if theme_key == "Light":
        return shared

    color = html.escape(prefs["font_color"], quote=True)
    return shared + f"""
    .stApp {{
        --rg-user-text-color: {color};
    }}
    section.main div[data-testid="stMarkdownContainer"]:not(:has(.app-workspace-header)):not(:has(.review-scan-intro)) p,
    section.main div[data-testid="stTextInput"] label,
    section.main div[data-testid="stTextArea"] label,
    section.main div[data-testid="stNumberInput"] label,
    section.main div[data-testid="stSelectbox"] label,
    section.main div[data-testid="stCheckbox"] label,
    section.main div[data-testid="stDateInput"] label {{
        color: var(--rg-user-text-color) !important;
    }}
    """


def render_display_settings_sidebar(supabase, *, theme: str = "Dark") -> dict:
    prefs = ensure_display_prefs_loaded(supabase, theme=theme)
    if (
        st.session_state.pop("_display_widget_resync", False)
        or "user_display_font_family" not in st.session_state
    ):
        seed_display_widget_state(prefs)

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
    if _theme_key(theme) == "Dark":
        font_color = st.sidebar.color_picker(
            "Font color",
            key="user_display_font_color",
        )
    else:
        st.sidebar.caption("Light mode keeps theme text colors for readability.")
        font_color = prefs["font_color"]
    font_size = st.sidebar.slider(
        "Font size",
        min_value=FONT_SIZE_MIN,
        max_value=FONT_SIZE_MAX,
        step=1,
        help=f"Limited to {FONT_SIZE_MAX}px so text fits the layout without clipping.",
        key="user_display_font_size",
    )
    if st.sidebar.button("Reset display defaults", key="user_display_reset", use_container_width=True):
        save_display_prefs(supabase, default_display_prefs(theme), theme=theme)
        request_display_widget_resync()
        st.rerun()

    theme_key = _theme_key(theme)
    font_colors = dict(prefs.get("font_colors") or DEFAULT_TEXT_COLOR)
    font_colors[theme_key] = _normalize_hex_color(
        font_color,
        fallback=DEFAULT_TEXT_COLOR[theme_key],
    )
    if not color_readable_on_theme(font_colors[theme_key], theme_key):
        font_colors[theme_key] = DEFAULT_TEXT_COLOR[theme_key]

    updated = normalize_display_prefs(
        {
            "font_family": font_family,
            "font_color": font_colors[theme_key],
            "font_colors": font_colors,
            "font_size": font_size,
        },
        theme=theme,
    )
    changed = (
        updated.get("font_family") != prefs.get("font_family")
        or updated.get("font_size") != prefs.get("font_size")
        or updated.get("font_color") != prefs.get("font_color")
        or updated.get("font_colors") != prefs.get("font_colors")
    )
    if changed:
        save_display_prefs(supabase, updated, theme=theme)
        if (
            _theme_key(theme) == "Dark"
            and (
                updated["font_color"] != font_color
                or updated["font_family"] != font_family
                or updated["font_size"] != font_size
            )
        ):
            request_display_widget_resync()
            st.rerun()
    return updated
