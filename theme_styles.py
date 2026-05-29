BRAND_TEXT = {
    "Dark": {
        "workspace_kicker": "#94a3b8",
        "workspace_h2": "#f8fbff",
        "workspace_body": "#94a3b8",
        "workspace_accent": "#60a5fa",
        "scan_h3": "#f8fbff",
        "scan_body": "#94a3b8",
        "scan_strong": "#cbd5e1",
        "sidebar_label": "#93c5fd",
        "sidebar_caption": "#94a3b8",
        "sidebar_brand": "#f8fbff",
        "sidebar_brand_sub": "#94a3b8",
    },
    "Light": {
        "workspace_kicker": "#64748b",
        "workspace_h2": "#0f172a",
        "workspace_body": "#475569",
        "workspace_accent": "#1d4ed8",
        "scan_h3": "#0f172a",
        "scan_body": "#475569",
        "scan_strong": "#334155",
        "sidebar_label": "#475569",
        "sidebar_caption": "#64748b",
        "sidebar_brand": "#0f172a",
        "sidebar_brand_sub": "#64748b",
    },
}


def brand_color_lock_css(theme: str = "Dark") -> str:
    """Force readable colors on branded chrome; appended last in apply_style()."""
    key = "Light" if str(theme).lower() == "light" else "Dark"
    c = BRAND_TEXT[key]

    def lock(selectors: str, color: str) -> str:
        return f"""
    {selectors} {{
        color: {color} !important;
        -webkit-text-fill-color: {color} !important;
    }}"""

    header = ".app-workspace-header"
    header_sel = (
        f"section.main div[data-testid='stMarkdownContainer'] {header}, "
        f"section.main {header}"
    )
    scan = ".review-scan-intro"
    scan_sel = (
        f"section.main div[data-testid='stMarkdownContainer'] {scan}, "
        f"section.main {scan}"
    )
    return (
        lock(
            f"{header_sel} .app-workspace-kicker, div.app-workspace-kicker",
            c["workspace_kicker"],
        )
        + lock(
            f"{header_sel} h2, {header_sel} h2 span, div.app-workspace-header h2, div.app-workspace-header h2 span",
            c["workspace_h2"],
        )
        + lock(f"{header_sel} p, div.app-workspace-header p", c["workspace_body"])
        + lock(
            f"{header_sel} .app-workspace-accent, div.app-workspace-accent",
            c["workspace_accent"],
        )
        + lock(f"{scan_sel} h3, div.review-scan-intro h3", c["scan_h3"])
        + lock(f"{scan_sel} p, div.review-scan-intro p", c["scan_body"])
        + lock(f"{scan_sel} strong, div.review-scan-intro strong", c["scan_strong"])
        + lock(
            "section[data-testid='stSidebar'] div[data-testid='stSelectbox'] label, "
            "section[data-testid='stSidebar'] div[data-testid='stSlider'] label, "
            "section[data-testid='stSidebar'] .rg-sidebar-settings-title",
            c["sidebar_label"],
        )
        + lock(
            "section[data-testid='stSidebar'] div[data-testid='stCaptionContainer'] p",
            c["sidebar_caption"],
        )
        + lock(
            "section[data-testid='stSidebar'] .app-sidebar-name",
            c["sidebar_brand"],
        )
        + lock(
            "section[data-testid='stSidebar'] .app-sidebar-sub",
            c["sidebar_brand_sub"],
        )
    )


def metric_display_css() -> str:
    """Compact metric cards with full label/value visibility (no ellipsis clipping)."""
    return """
    div[data-testid="stMetric"] {
        padding: 8px 10px !important;
        min-height: 64px !important;
        height: auto !important;
        overflow: visible !important;
        border-radius: 12px !important;
    }
    div[data-testid="stMetricLabel"],
    div[data-testid="stMetricLabel"] p,
    div[data-testid="stMetricLabel"] span,
    div[data-testid="stMetricLabel"] label {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        word-break: break-word !important;
        line-height: 1.25 !important;
        font-size: 0.78rem !important;
        max-width: 100% !important;
        display: block !important;
        -webkit-line-clamp: unset !important;
    }
    div[data-testid="stMetricValue"],
    div[data-testid="stMetricValue"] p,
    div[data-testid="stMetricValue"] span,
    div[data-testid="stMetricValue"] div {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        word-break: break-word !important;
        line-height: 1.2 !important;
        font-size: 1.15rem !important;
        max-width: 100% !important;
        -webkit-line-clamp: unset !important;
    }
    div[data-testid="stHorizontalBlock"]:has(div[data-testid="stMetric"]) > div[data-testid="column"] {
        overflow: visible !important;
        min-width: 0 !important;
        flex: 1 1 0 !important;
    }
    """


def expander_css(theme: str = "Dark") -> str:
    """Expander headers/content — overrides Streamlit bgMix on open expanders."""
    is_light = str(theme).lower() == "light"
    if is_light:
        surface = "var(--rg-surface, #dde8f2)"
        surface_hover = "var(--rg-surface-hover, #d2e0ed)"
        surface_inner = "var(--rg-surface-input, #e8f0f8)"
        border = "var(--rg-border, #b6c7da)"
        text = "#0f172a"
        muted = "#475569"
        icon = "#1d4ed8"
    else:
        surface = "rgba(7, 19, 34, .86)"
        surface_hover = "rgba(13, 30, 55, .96)"
        surface_inner = "rgba(7, 19, 34, .62)"
        border = "rgba(62, 150, 255, .28)"
        text = "#f8fbff"
        muted = "#d6e8ff"
        icon = "#93c5fd"

    scope = ".stApp details[data-testid='stExpander']"
    summary = f"{scope} > summary"
    summary_label = (
        f"{summary} *, "
        f"{summary} p, "
        f"{summary} span, "
        f"{summary} div, "
        f"{summary} div[data-testid='stMarkdownContainer'], "
        f"{summary} div[data-testid='stMarkdownContainer'] p"
    )
    return f"""
    {scope} {{
        background: {surface} !important;
        background-color: {surface} !important;
        border: 1px solid {border} !important;
        border-color: {border} !important;
        border-radius: 14px !important;
        overflow: hidden;
    }}
    {summary} {{
        background: {surface} !important;
        background-color: {surface} !important;
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        border: none !important;
        border-radius: 14px !important;
        opacity: 1 !important;
    }}
    {scope}[open] > summary {{
        background: {surface} !important;
        background-color: {surface} !important;
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        border-radius: 14px 14px 0 0 !important;
        opacity: 1 !important;
    }}
    {summary}:hover,
    {summary}:focus,
    {summary}:focus-visible,
    {summary}:active,
    {scope}[open] > summary:hover,
    {scope}[open] > summary:focus-visible,
    {scope}[open] > summary:active {{
        background: {surface_hover} !important;
        background-color: {surface_hover} !important;
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        opacity: 1 !important;
    }}
    {summary_label} {{
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        background: transparent !important;
        background-color: transparent !important;
        opacity: 1 !important;
    }}
    {scope} [data-testid="stExpanderDetails"],
    {scope} > div {{
        background: {surface_inner} !important;
        background-color: {surface_inner} !important;
        border-top: 1px solid {border} !important;
    }}
    {scope} [data-testid="stExpanderDetails"] p,
    {scope} [data-testid="stExpanderDetails"] label,
    {scope} [data-testid="stExpanderDetails"] span,
    {scope} [data-testid="stExpanderDetails"] div[data-testid="stMarkdownContainer"] {{
        color: {text} !important;
    }}
    {scope} div[data-testid="stCaptionContainer"] p {{
        color: {muted} !important;
    }}
    {scope} [data-testid="stExpanderToggleIcon"],
    {scope} summary svg,
    {scope} summary [data-testid="stIconMaterial"] {{
        color: {icon} !important;
        fill: {icon} !important;
    }}
    .dc-expander-anchor {{
        display: none !important;
        height: 0 !important;
        width: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: hidden !important;
        pointer-events: none !important;
    }}
    .stApp div[data-testid="stElementContainer"]:has(.dc-expander-anchor) + div[data-testid="stElementContainer"] details[data-testid="stExpander"] {{
        background: {surface} !important;
        background-color: {surface} !important;
        border: 1px solid {border} !important;
        border-color: {border} !important;
        border-radius: 14px !important;
        overflow: hidden;
    }}
    .stApp div[data-testid="stElementContainer"]:has(.dc-expander-anchor) + div[data-testid="stElementContainer"] details[data-testid="stExpander"] > summary,
    .stApp div[data-testid="stElementContainer"]:has(.dc-expander-anchor) + div[data-testid="stElementContainer"] details[data-testid="stExpander"] > summary:not(:hover):not(:focus):not(:focus-visible) {{
        background: {surface} !important;
        background-color: {surface} !important;
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        opacity: 1 !important;
    }}
    .stApp div[data-testid="stElementContainer"]:has(.dc-expander-anchor) + div[data-testid="stElementContainer"] details[data-testid="stExpander"] > summary *,
    .stApp div[data-testid="stElementContainer"]:has(.dc-expander-anchor) + div[data-testid="stElementContainer"] details[data-testid="stExpander"] > summary p,
    .stApp div[data-testid="stElementContainer"]:has(.dc-expander-anchor) + div[data-testid="stElementContainer"] details[data-testid="stExpander"] > summary span,
    .stApp div[data-testid="stElementContainer"]:has(.dc-expander-anchor) + div[data-testid="stElementContainer"] details[data-testid="stExpander"] > summary div,
    .stApp div[data-testid="stElementContainer"]:has(.dc-expander-anchor) + div[data-testid="stElementContainer"] details[data-testid="stExpander"] > summary div[data-testid="stMarkdownContainer"],
    .stApp div[data-testid="stElementContainer"]:has(.dc-expander-anchor) + div[data-testid="stElementContainer"] details[data-testid="stExpander"] > summary div[data-testid="stMarkdownContainer"] p {{
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        background: transparent !important;
        background-color: transparent !important;
        opacity: 1 !important;
    }}
    .stApp div[data-testid="stElementContainer"]:has(.dc-expander-applicable) + div[data-testid="stElementContainer"] details[data-testid="stExpander"]:not([open]) > summary {{
        box-shadow: inset 3px 0 0 {"#16a34a" if is_light else "#3ecf8e"} !important;
        background: {"rgba(22, 163, 74, 0.12)" if is_light else "rgba(62, 207, 142, 0.1)"} !important;
        background-color: {"rgba(22, 163, 74, 0.12)" if is_light else "rgba(62, 207, 142, 0.1)"} !important;
    }}
    """


def audit_result_panel_css(theme: str = "Dark") -> str:
    """Static audit job result headers (always expanded — no Streamlit expander)."""
    is_light = str(theme).lower() == "light"
    if is_light:
        surface = "var(--rg-surface, #dde8f2)"
        border = "var(--rg-border, #b6c7da)"
        text = "#0f172a"
    else:
        surface = "rgba(7, 19, 34, .86)"
        border = "rgba(62, 150, 255, .28)"
        text = "#f8fbff"

    return f"""
    .audit-job-result-header {{
        margin: -4px -2px 10px -2px;
        padding: 8px 10px;
        border-radius: 10px;
        background: {surface};
        border: 1px solid {border};
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
        font-weight: 700;
        font-size: 0.95rem;
        line-height: 1.35;
    }}
    """


def review_open_claims_strip_css(theme: str = "Dark") -> str:
    """Open-claims queue strip on the Review tab."""
    is_light = str(theme).lower() == "light"
    if is_light:
        bg = "rgba(255, 255, 255, 0.92)"
        border = "var(--rg-border, #b6c7da)"
        text = "#0f172a"
        muted = "#475569"
        accent = "#1d4ed8"
        clear_bg = "rgba(220, 252, 231, 0.85)"
        clear_border = "#22c55e"
        clear_text = "#166534"
        warn_text = "#b45309"
        stop_text = "#b91c1c"
    else:
        bg = "rgba(7, 19, 34, .88)"
        border = "rgba(62, 150, 255, .28)"
        text = "#f8fbff"
        muted = "#94a3b8"
        accent = "#93c5fd"
        clear_bg = "rgba(22, 101, 52, 0.35)"
        clear_border = "#4ade80"
        clear_text = "#bbf7d0"
        warn_text = "#fcd34d"
        stop_text = "#fca5a5"

    return f"""
    .review-open-claims-strip {{
        border-radius: 14px;
        border: 1px solid {border};
        background: {bg};
        padding: 12px 16px;
        margin: 0 0 14px 0;
        line-height: 1.45;
    }}
    .review-open-claims-strip--clear {{
        background: {clear_bg};
        border-color: {clear_border};
    }}
    .review-open-claims-strip__title {{
        color: {text} !important;
        font-size: 0.98rem;
        font-weight: 700;
        margin-bottom: 2px;
    }}
    .review-open-claims-strip__meta {{
        color: {muted} !important;
        font-size: 0.88rem;
    }}
    .review-open-claims-strip__meta strong {{
        color: {text} !important;
        font-weight: 700;
    }}
    .review-open-claims-strip__stop {{
        color: {stop_text} !important;
        font-weight: 700;
    }}
    .review-open-claims-strip__warn {{
        color: {warn_text} !important;
        font-weight: 700;
    }}
    .review-open-claims-strip__clear {{
        color: {clear_text} !important;
        font-weight: 600;
    }}
    .review-open-claims-strip__edit {{
        color: {accent} !important;
        font-weight: 700;
    }}
    div[data-testid="column"]:has(.review-open-claims-strip-btn-slot) div.stButton {{
        margin-top: 0.15rem;
    }}
    """


def vin_recall_alert_css(theme: str = "Dark") -> str:
    """Red recall alert button + dark details panel on Review."""
    is_light = str(theme).lower() == "light"
    if is_light:
        panel_bg = "var(--rg-surface, #dde8f2)"
        panel_border = "var(--rg-border, #b6c7da)"
        text = "#0f172a"
        match_bg = "rgba(254, 243, 199, 0.95)"
        match_border = "#f59e0b"
        match_text = "#92400e"
        critical_bg = "rgba(254, 226, 226, 0.95)"
        critical_border = "#ef4444"
        critical_text = "#991b1b"
    else:
        panel_bg = "rgba(7, 19, 34, .92)"
        panel_border = "rgba(252, 165, 165, 0.35)"
        text = "#f8fbff"
        match_bg = "rgba(120, 53, 15, 0.45)"
        match_border = "#f59e0b"
        match_text = "#fcd34d"
        critical_bg = "rgba(127, 29, 29, 0.55)"
        critical_border = "#f87171"
        critical_text = "#fecaca"

    btn_scope = 'div[data-testid="stVerticalBlock"]:has(.vin-recall-alert-wrap)'
    panel_scope = 'div[data-testid="stVerticalBlockBorderWrapper"]:has(.vin-recall-details-panel)'

    return f"""
    {btn_scope} div.stButton > button {{
        background: linear-gradient(180deg, #dc2626 0%, #b91c1c 100%) !important;
        background-color: #dc2626 !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border: 1px solid #fca5a5 !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        min-height: 2.75rem !important;
        box-shadow: 0 4px 14px rgba(220, 38, 38, 0.35) !important;
    }}
    {btn_scope} div.stButton > button:hover {{
        background: linear-gradient(180deg, #ef4444 0%, #dc2626 100%) !important;
        border-color: #ffffff !important;
        color: #ffffff !important;
    }}
    {panel_scope} {{
        background: {panel_bg} !important;
        border-color: {panel_border} !important;
        border-radius: 14px !important;
        margin-top: 8px !important;
        margin-bottom: 10px !important;
    }}
    {panel_scope} p,
    {panel_scope} label,
    {panel_scope} span,
    {panel_scope} div[data-testid="stMarkdownContainer"],
    {panel_scope} div[data-testid="stMarkdownContainer"] p {{
        color: {text} !important;
        -webkit-text-fill-color: {text} !important;
    }}
    {panel_scope} div[data-testid="stCaptionContainer"] p {{
        color: {text} !important;
        opacity: 0.82;
    }}
    .vin-recall-match-note {{
        margin: 8px 0 10px 0;
        padding: 10px 12px;
        border-radius: 10px;
        background: {match_bg};
        border: 1px solid {match_border};
        color: {match_text} !important;
        font-size: 0.9rem;
        line-height: 1.4;
    }}
    .vin-recall-critical-note {{
        margin: 8px 0 10px 0;
        padding: 10px 12px;
        border-radius: 10px;
        background: {critical_bg};
        border: 1px solid {critical_border};
        color: {critical_text} !important;
        font-size: 0.9rem;
        line-height: 1.4;
    }}
    """


def dealer_connect_panel_css(theme: str = "Dark") -> str:
    """Dealer Connect panels — dark bordered sections, code blocks, and notes (no expander white boxes)."""
    is_light = str(theme).lower() == "light"
    if is_light:
        code_bg = "var(--rg-surface-input, #e8f0f8)"
        code_border = "var(--rg-border, #b6c7da)"
        code_text = "#0f172a"
        label_muted = "#475569"
        panel_bg = "var(--rg-surface, #dde8f2)"
        panel_border = "var(--rg-border, #b6c7da)"
        info_bg = "rgba(219, 234, 254, 0.95)"
        info_border = "#93c5fd"
        warn_bg = "rgba(254, 243, 199, 0.95)"
        warn_border = "#f59e0b"
        warn_text = "#92400e"
        input_bg = "#e8f0f8"
    else:
        code_bg = "rgba(7, 19, 34, .92)"
        code_border = "rgba(62, 150, 255, .28)"
        code_text = "#f8fbff"
        label_muted = "#cbd5e1"
        panel_bg = "rgba(7, 19, 34, .92)"
        panel_border = "rgba(62, 150, 255, .28)"
        info_bg = "rgba(15, 40, 70, 0.62)"
        info_border = "rgba(62, 150, 255, .35)"
        warn_bg = "rgba(120, 53, 15, 0.48)"
        warn_border = "#f59e0b"
        warn_text = "#fcd34d"
        input_bg = "rgba(7, 19, 34, .86)"

    scope = 'div[data-testid="stVerticalBlock"]:has(.dealer-connect-workspace-marker)'
    panel_wrap = f'{scope} div[data-testid="stVerticalBlockBorderWrapper"]:has(.dealer-connect-panel)'
    job_wrap = f'{scope} div[data-testid="stVerticalBlockBorderWrapper"]:has(.dealer-connect-job-line)'
    job_bg = "rgba(7, 19, 34, .72)" if not is_light else "var(--rg-surface-hover, #d2e0ed)"
    return f"""
    {panel_wrap} {{
        background: {panel_bg} !important;
        background-color: {panel_bg} !important;
        border-color: {panel_border} !important;
        border-radius: 14px !important;
        margin-bottom: 12px !important;
        padding: 12px 14px !important;
    }}
    {panel_wrap} > div {{
        background: transparent !important;
        background-color: transparent !important;
    }}
    {panel_wrap} h5 {{
        color: {code_text} !important;
        margin: 0 0 10px 0 !important;
        padding: 0 !important;
        font-size: 1.05rem !important;
        font-weight: 700 !important;
    }}
    {job_wrap} {{
        background: {job_bg} !important;
        background-color: {job_bg} !important;
        border-color: {panel_border} !important;
        border-radius: 12px !important;
        margin-bottom: 10px !important;
    }}
    {scope} .dc-note-info {{
        margin: 8px 0 10px 0;
        padding: 10px 12px;
        border-radius: 10px;
        background: {info_bg};
        border: 1px solid {info_border};
        color: {code_text} !important;
        font-size: 0.9rem;
        line-height: 1.45;
    }}
    {scope} .dc-note-warn {{
        margin: 8px 0 10px 0;
        padding: 10px 12px;
        border-radius: 10px;
        background: {warn_bg};
        border: 1px solid {warn_border};
        color: {warn_text} !important;
        font-size: 0.9rem;
        line-height: 1.45;
    }}
    {scope} .dc-copy-value {{
        margin: 0 0 10px 0;
        padding: 10px 12px;
        border-radius: 10px;
        background: {code_bg} !important;
        border: 1px solid {code_border};
        color: {code_text} !important;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 0.92rem;
        line-height: 1.45;
        white-space: pre-wrap;
        word-break: break-word;
        user-select: all;
        -webkit-user-select: all;
        cursor: text;
    }}
    {scope} div[data-testid="stCaptionContainer"] p {{
        color: {label_muted} !important;
    }}
    {panel_wrap} textarea {{
        background: {input_bg} !important;
        background-color: {input_bg} !important;
        color: {code_text} !important;
        border: 1px solid {code_border} !important;
        border-radius: 10px !important;
    }}
    {panel_wrap} div[data-testid="stTextArea"] label {{
        color: {code_text} !important;
    }}
    {scope} details[data-testid="stExpander"] {{
        background: {panel_bg} !important;
        background-color: {panel_bg} !important;
        border: 1px solid {panel_border} !important;
        border-radius: 14px !important;
        margin-bottom: 12px !important;
        overflow: hidden;
    }}
    {scope} details[data-testid="stExpander"] > summary,
    {scope} details[data-testid="stExpander"] > summary:not(:hover):not(:focus):not(:focus-visible) {{
        background: {panel_bg} !important;
        background-color: {panel_bg} !important;
        color: {code_text} !important;
        -webkit-text-fill-color: {code_text} !important;
        font-weight: 700 !important;
        padding: 12px 14px !important;
        border: none !important;
        opacity: 1 !important;
    }}
    {scope} details[data-testid="stExpander"] > summary *,
    {scope} details[data-testid="stExpander"] > summary p,
    {scope} details[data-testid="stExpander"] > summary span,
    {scope} details[data-testid="stExpander"] > summary div,
    {scope} details[data-testid="stExpander"] > summary div[data-testid="stMarkdownContainer"],
    {scope} details[data-testid="stExpander"] > summary div[data-testid="stMarkdownContainer"] p {{
        color: {code_text} !important;
        -webkit-text-fill-color: {code_text} !important;
        background: transparent !important;
        background-color: transparent !important;
        opacity: 1 !important;
    }}
    {scope} details[data-testid="stExpander"][open] > summary {{
        border-radius: 14px 14px 0 0 !important;
        border-bottom: 1px solid {panel_border} !important;
    }}
    {scope} details[data-testid="stExpander"] [data-testid="stExpanderDetails"],
    {scope} details[data-testid="stExpander"] > div {{
        background: {panel_bg} !important;
        background-color: {panel_bg} !important;
        border-top: none !important;
        padding: 0 14px 12px 14px !important;
    }}
    {scope} details[data-testid="stExpander"] [data-testid="stExpanderDetails"] div[data-testid="stMarkdownContainer"],
    {scope} details[data-testid="stExpander"] [data-testid="stExpanderDetails"] div[data-testid="stVerticalBlock"] {{
        background: transparent !important;
        background-color: transparent !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.dealer-connect-collapsible) {{
        background: {panel_bg} !important;
        background-color: {panel_bg} !important;
        border: 1px solid {panel_border} !important;
        border-radius: 14px !important;
        margin-bottom: 12px !important;
        overflow: hidden;
    }}
    {scope} details[data-testid="stExpander"]:has(.dealer-connect-collapsible) > summary {{
        background: {panel_bg} !important;
        background-color: {panel_bg} !important;
        color: {code_text} !important;
        -webkit-text-fill-color: {code_text} !important;
        font-weight: 700 !important;
        padding: 12px 14px !important;
        border: none !important;
        opacity: 1 !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.dealer-connect-collapsible)[open] > summary {{
        border-radius: 14px 14px 0 0 !important;
        border-bottom: 1px solid {panel_border} !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.dealer-connect-collapsible) [data-testid="stExpanderDetails"],
    {scope} details[data-testid="stExpander"]:has(.dealer-connect-collapsible) > div {{
        background: {panel_bg} !important;
        background-color: {panel_bg} !important;
        border-top: none !important;
        padding: 0 14px 12px 14px !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.dealer-connect-collapsible) [data-testid="stExpanderDetails"] textarea,
    {scope} details[data-testid="stExpander"]:has(.dealer-connect-collapsible) textarea {{
        background: {input_bg} !important;
        background-color: {input_bg} !important;
        color: {code_text} !important;
        border: 1px solid {code_border} !important;
        border-radius: 10px !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.dealer-connect-collapsible) summary *,
    {scope} details[data-testid="stExpander"]:has(.dealer-connect-collapsible) summary p,
    {scope} details[data-testid="stExpander"]:has(.dealer-connect-collapsible) summary span,
    {scope} details[data-testid="stExpander"]:has(.dealer-connect-collapsible) summary div {{
        color: {code_text} !important;
        -webkit-text-fill-color: {code_text} !important;
        background: transparent !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.dealer-connect-collapsible) [data-testid="stExpanderToggleIcon"],
    {scope} details[data-testid="stExpander"]:has(.dealer-connect-collapsible) summary svg {{
        color: {code_text} !important;
        fill: {code_text} !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.review-collapsible-applicable) > summary {{
        box-shadow: inset 3px 0 0 #3ecf8e !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.review-collapsible-applicable):not([open]) > summary {{
        background: rgba(62, 207, 142, 0.1) !important;
        background-color: rgba(62, 207, 142, 0.1) !important;
    }}
    """


def review_collapsible_css(theme: str = "Dark") -> str:
    """Collapsible coaching panels on Review job tabs (Manual/TSB, Gap Coach, Declined)."""
    is_light = str(theme).lower() == "light"
    panel_bg = "var(--rg-surface-card, #f4f8fc)" if is_light else "rgba(7, 19, 34, .92)"
    panel_border = "var(--rg-border, #b6c7da)" if is_light else "rgba(62, 150, 255, .22)"
    code_text = "#0f172a" if is_light else "#f8fbff"
    highlight_bg = "rgba(22, 163, 74, 0.12)" if is_light else "rgba(62, 207, 142, 0.1)"
    accent_green = "#16a34a" if is_light else "#3ecf8e"
    scope = 'div[data-testid="stVerticalBlock"]:has(.review-job-coaching-marker)'
    return f"""
    {scope} details[data-testid="stExpander"]:has(.review-collapsible) {{
        background: {panel_bg} !important;
        background-color: {panel_bg} !important;
        border: 1px solid {panel_border} !important;
        border-radius: 14px !important;
        margin-bottom: 12px !important;
        overflow: hidden;
    }}
    {scope} details[data-testid="stExpander"]:has(.review-collapsible) > summary {{
        background: {panel_bg} !important;
        background-color: {panel_bg} !important;
        color: {code_text} !important;
        -webkit-text-fill-color: {code_text} !important;
        font-weight: 700 !important;
        padding: 12px 14px !important;
        border: none !important;
        opacity: 1 !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.review-collapsible)[open] > summary {{
        border-radius: 14px 14px 0 0 !important;
        border-bottom: 1px solid {panel_border} !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.review-collapsible) [data-testid="stExpanderDetails"],
    {scope} details[data-testid="stExpander"]:has(.review-collapsible) > div {{
        background: {panel_bg} !important;
        background-color: {panel_bg} !important;
        border-top: none !important;
        padding: 0 14px 12px 14px !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.review-collapsible) summary *,
    {scope} details[data-testid="stExpander"]:has(.review-collapsible) summary p,
    {scope} details[data-testid="stExpander"]:has(.review-collapsible) summary span,
    {scope} details[data-testid="stExpander"]:has(.review-collapsible) summary div {{
        color: {code_text} !important;
        -webkit-text-fill-color: {code_text} !important;
        background: transparent !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.review-collapsible) [data-testid="stExpanderToggleIcon"],
    {scope} details[data-testid="stExpander"]:has(.review-collapsible) summary svg {{
        color: {code_text} !important;
        fill: {code_text} !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.review-collapsible-applicable) > summary {{
        box-shadow: inset 3px 0 0 {accent_green} !important;
    }}
    {scope} details[data-testid="stExpander"]:has(.review-collapsible-applicable):not([open]) > summary {{
        background: {highlight_bg} !important;
        background-color: {highlight_bg} !important;
    }}
    """


def narrative_copy_button_css(theme: str = "Dark") -> str:
    """Transparent iframe copy buttons beside narrative and Dealer Connect fields."""
    is_light = str(theme).lower() == "light"
    btn_bg = "var(--rg-surface-input, #e8f0f8)" if is_light else "rgba(7, 19, 34, .75)"
    btn_border = "var(--rg-border, #b6c7da)" if is_light else "rgba(62, 150, 255, .35)"
    btn_text = "#0f172a" if is_light else "#f8fbff"
    scope = (
        'div[data-testid="stVerticalBlock"]:has(.review-job-narratives-marker), '
        'div[data-testid="stVerticalBlock"]:has(.dealer-connect-workspace-marker)'
    )
    return f"""
    {scope} iframe {{
        background: transparent !important;
        background-color: transparent !important;
    }}
    {scope} div[data-testid="stColumn"]:has(iframe) {{
        display: flex !important;
        align-items: flex-start !important;
        justify-content: flex-end !important;
        padding-top: 2px !important;
    }}
    {scope} div[data-testid="stColumn"]:has(iframe) button {{
        background: {btn_bg} !important;
        border: 1px solid {btn_border} !important;
        color: {btn_text} !important;
    }}
    """


def claim_learning_css(theme: str = "Dark") -> str:
    """Green Paid / red Declined tabs and panel banners on Claim Learning."""
    is_light = str(theme).lower() == "light"
    paid_text = "#166534" if is_light else "#bbf7d0"
    paid_muted = "#15803d" if is_light else "#86efac"
    paid_bg = "rgba(220, 252, 231, 0.95)" if is_light else "rgba(22, 101, 52, 0.42)"
    paid_border = "#22c55e" if is_light else "#4ade80"
    declined_text = "#991b1b" if is_light else "#fecaca"
    declined_muted = "#b91c1c" if is_light else "#fca5a5"
    declined_bg = "rgba(254, 226, 226, 0.95)" if is_light else "rgba(127, 29, 29, 0.42)"
    declined_border = "#ef4444" if is_light else "#f87171"
    tab_scope = (
        'div[data-testid="stVerticalBlock"]:has(.claim-learning-tabs-marker) '
        'div[data-testid="stTabs"]'
    )
    return f"""
    {tab_scope} [data-baseweb="tab-list"] button[data-baseweb="tab"]:nth-child(1) {{
        color: {paid_muted} !important;
        font-weight: 700 !important;
    }}
    {tab_scope} [data-baseweb="tab-list"] button[data-baseweb="tab"]:nth-child(1)[aria-selected="true"] {{
        background: {paid_bg} !important;
        color: {paid_text} !important;
        border-bottom: 3px solid {paid_border} !important;
        box-shadow: inset 0 -1px 0 {paid_border} !important;
    }}
    {tab_scope} [data-baseweb="tab-list"] button[data-baseweb="tab"]:nth-child(2) {{
        color: {declined_muted} !important;
        font-weight: 700 !important;
    }}
    {tab_scope} [data-baseweb="tab-list"] button[data-baseweb="tab"]:nth-child(2)[aria-selected="true"] {{
        background: {declined_bg} !important;
        color: {declined_text} !important;
        border-bottom: 3px solid {declined_border} !important;
        box-shadow: inset 0 -1px 0 {declined_border} !important;
    }}
    .claim-outcome-banner {{
        border-radius: 12px;
        padding: 12px 16px;
        margin: 0 0 14px 0;
        border: 1px solid transparent;
        font-size: 14px;
        line-height: 1.45;
    }}
    .claim-outcome-banner strong {{
        display: block;
        font-size: 18px;
        font-weight: 800;
        margin-bottom: 4px;
    }}
    .claim-outcome-banner--paid {{
        background: {paid_bg};
        border-color: {paid_border};
        color: {paid_text};
    }}
    .claim-outcome-banner--declined {{
        background: {declined_bg};
        border-color: {declined_border};
        color: {declined_text};
    }}
    div[data-testid="stVerticalBlock"]:has(.claim-panel-paid-marker) section[data-testid="stFileUploaderDropzone"] {{
        border-color: {paid_border} !important;
        background: {paid_bg} !important;
    }}
    div[data-testid="stVerticalBlock"]:has(.claim-panel-declined-marker) section[data-testid="stFileUploaderDropzone"] {{
        border-color: {declined_border} !important;
        background: {declined_bg} !important;
    }}
    """


THEME_CSS = {
    "Dark": """
    .stApp {
        position: relative;
        isolation: isolate;
        color: #f8fbff;
        background-color: #02070d;
        background-image:
            radial-gradient(ellipse 90% 55% at 50% -15%, rgba(37, 99, 235, 0.38), transparent 58%),
            radial-gradient(circle at 92% 18%, rgba(45, 156, 255, 0.22), transparent 32%),
            radial-gradient(circle at 8% 72%, rgba(29, 78, 216, 0.16), transparent 38%),
            radial-gradient(circle at 48% 100%, rgba(15, 118, 255, 0.10), transparent 42%),
            linear-gradient(165deg, #071222 0%, #041018 42%, #02070d 100%);
        background-attachment: fixed;
    }
    .stApp::before {
        content: "";
        position: fixed;
        inset: 0;
        z-index: 0;
        pointer-events: none;
        background-image:
            linear-gradient(rgba(96, 165, 250, 0.045) 1px, transparent 1px),
            linear-gradient(90deg, rgba(96, 165, 250, 0.045) 1px, transparent 1px),
            radial-gradient(circle at 18% 22%, rgba(96, 165, 250, 0.09) 0%, transparent 28%),
            radial-gradient(circle at 82% 68%, rgba(59, 130, 246, 0.07) 0%, transparent 24%);
        background-size: 64px 64px, 64px 64px, 100% 100%, 100% 100%;
        mask-image: radial-gradient(ellipse 95% 85% at 50% 45%, black 20%, transparent 100%);
        -webkit-mask-image: radial-gradient(ellipse 95% 85% at 50% 45%, black 20%, transparent 100%);
    }
    .stApp::after {
        content: "";
        position: fixed;
        right: -6%;
        bottom: -8%;
        width: min(480px, 52vw);
        height: min(560px, 62vh);
        z-index: 0;
        pointer-events: none;
        opacity: 0.09;
        background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 72 82'%3E%3Cpath d='M36 4 L66 18 V40 C66 58 52 72 36 78 C20 72 6 58 6 40 V18 Z' fill='none' stroke='%2360a5fa' stroke-width='1.8'/%3E%3Cpath d='M36 12 L60 24 V40 C60 54 50 66 36 72 C22 66 12 54 12 40 V24 Z' fill='none' stroke='%233b82f6' stroke-width='1' opacity='0.65'/%3E%3Ctext x='36' y='43' text-anchor='middle' fill='%2393c5fd' font-size='9' font-weight='800' font-family='Arial,sans-serif'%3ERO-%3C/text%3E%3Ctext x='36' y='54' text-anchor='middle' fill='%2393c5fd' font-size='9' font-weight='800' font-family='Arial,sans-serif'%3EGuard%3C/text%3E%3C/svg%3E") no-repeat center / contain;
    }
    .stApp:has(.ro-login-active)::before,
    .stApp:has(.ro-login-active)::after {
        display: none;
    }
    header[data-testid="stHeader"],
    section[data-testid="stSidebar"],
    section.main,
    div[data-testid="stAppViewContainer"] {
        position: relative;
        z-index: 1;
    }
    header[data-testid="stHeader"] { background: rgba(0,0,0,0); }
    section[data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 50% 0%, rgba(37, 99, 235, 0.18), transparent 58%),
            linear-gradient(180deg, #071322, #030811) !important;
        border-right: 1px solid rgba(36,135,255,.30);
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 0.75rem;
    }
    section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
        gap: 0.45rem !important;
    }
    section[data-testid="stSidebar"] hr {
        margin: 0.65rem 0 !important;
        border-color: rgba(96, 165, 250, 0.22) !important;
    }
    section[data-testid="stSidebar"] .rg-sidebar-settings-title {
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #93c5fd !important;
        margin: 0.15rem 0 0.1rem 0;
    }
    [data-testid="stIconMaterial"],
    span[data-testid="stIconMaterial"],
    .material-symbols-rounded {
        font-family: "Material Symbols Rounded" !important;
        font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        -webkit-text-fill-color: currentColor !important;
    }
    .stApp, .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
        color: #f8fbff;
    }
    .hero {
        padding: 28px 30px;
        border-radius: 22px;
        background: linear-gradient(135deg, rgba(10, 31, 57, .94), rgba(2, 9, 19, .94));
        border: 1px solid rgba(62,150,255,.40);
        box-shadow: 0 20px 60px rgba(0,0,0,.35);
        margin-bottom: 22px;
    }
    .hero h1 { margin: 0; font-size: 48px; letter-spacing: .5px; }
    .hero p { color: #d6e8ff !important; font-size: 16px; }
    .section-card {
        padding: 18px;
        border-radius: 18px;
        background: rgba(7, 19, 34, .62);
        border: 1px solid rgba(62,150,255,.22);
        margin: 10px 0 18px 0;
    }
    textarea, input, div[data-baseweb="input"] input {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        background-color: rgba(13, 30, 55, .96) !important;
        border: 1px solid rgba(140, 200, 255, .70) !important;
    }
    div[data-testid="stTextInput"] input,
    div[data-testid="stTextInput"] textarea,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stTextInput"] div[data-baseweb="input"],
    div[data-testid="stTextInput"] div[data-baseweb="base-input"],
    div[data-testid="stTextInput"] div[data-baseweb="input"] > div,
    div[data-testid="stTextInput"] div[data-baseweb="base-input"] > div,
    section[data-testid="stForm"] div[data-baseweb="input"],
    section[data-testid="stForm"] div[data-baseweb="base-input"],
    section[data-testid="stForm"] div[data-baseweb="input"] > div,
    section[data-testid="stForm"] div[data-baseweb="base-input"] > div {
        background-color: rgba(13, 30, 55, .96) !important;
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        border-color: rgba(140, 200, 255, .70) !important;
    }
    div[data-testid="stTextInput"] label,
    section[data-testid="stForm"] label {
        color: #f8fbff !important;
    }
    input:-webkit-autofill,
    input:-webkit-autofill:hover,
    input:-webkit-autofill:focus {
        -webkit-box-shadow: 0 0 0 1000px rgba(13, 30, 55, .96) inset !important;
        -webkit-text-fill-color: #ffffff !important;
        caret-color: #ffffff !important;
    }
    textarea::placeholder, input::placeholder { color: #d8eaff !important; opacity: 1 !important; }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-baseweb="select"] > div {
        background-color: rgba(13, 30, 55, .96) !important;
        border: 1px solid rgba(140, 200, 255, .70) !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] span,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] div,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] p,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] input,
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div,
    div[data-baseweb="select"] p,
    div[data-baseweb="select"] input,
    div[data-baseweb="select"] svg {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
        fill: #ffffff !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] label {
        color: #f8fbff !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        background-color: rgba(13, 30, 55, .98) !important;
        color: #ffffff !important;
    }
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] [data-baseweb="select"],
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] [data-baseweb="select"] * {
        color: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    div[data-baseweb="popover"] div[data-baseweb="menu"],
    div[data-baseweb="popover"] ul,
    ul[role="listbox"] {
        background-color: #0d1e37 !important;
        border: 1px solid rgba(140, 200, 255, .70) !important;
    }
    div[data-baseweb="popover"] li,
    li[role="option"] {
        color: #ffffff !important;
        background-color: #0d1e37 !important;
    }
    div[data-baseweb="popover"] li:hover,
    li[role="option"]:hover,
    li[role="option"][aria-selected="true"],
    div[data-baseweb="popover"] li[aria-selected="true"] {
        background-color: rgba(29, 78, 216, .65) !important;
        color: #ffffff !important;
    }
    section[data-testid="stFileUploaderDropzone"] {
        background-color: rgba(13, 30, 55, .92) !important;
        border: 1px dashed rgba(140, 200, 255, .70) !important;
    }
    div[data-testid="stMetric"] {
        background: rgba(7, 19, 34, .86);
        border: 1px solid rgba(62,150,255,.28);
        border-radius: 16px;
        padding: 14px 16px;
        min-height: 96px;
        height: auto !important;
        overflow: visible !important;
    }
    div[data-testid="stMetricValue"] {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        word-break: break-word;
        font-size: clamp(1.15rem, 2.2vw, 1.75rem) !important;
        line-height: 1.25 !important;
        color: #ffffff !important;
    }
    div[data-testid="stMetricLabel"] {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        line-height: 1.35 !important;
        color: #d6e8ff !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        overflow: visible !important;
        min-width: 7.5rem;
    }
    div.stButton > button,
    button[kind="secondary"],
    button[data-testid="stBaseButton-secondary"] {
        background: linear-gradient(180deg, #1f4f92 0%, #163b70 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(140, 200, 255, 0.85) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        min-height: 2.6rem !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25) !important;
    }
    div.stButton > button:hover,
    button[kind="secondary"]:hover,
    button[data-testid="stBaseButton-secondary"]:hover {
        background: linear-gradient(180deg, #2a66b8 0%, #1f4f92 100%) !important;
        border-color: #ffffff !important;
        color: #ffffff !important;
    }
    button[kind="primary"],
    button[data-testid="stBaseButton-primary"],
    div.stButton > button[kind="primary"] {
        background: linear-gradient(180deg, #2f80ff 0%, #1d4ed8 100%) !important;
        color: #ffffff !important;
        border: 1px solid #93c5fd !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        min-height: 2.8rem !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.45) !important;
    }
    button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(180deg, #60a5fa 0%, #2563eb 100%) !important;
        color: #ffffff !important;
    }
    div[data-testid="stFormSubmitButton"] > button,
    div[data-testid="stFormSubmitButton"] button,
    section[data-testid="stForm"] div.stButton > button,
    section[data-testid="stForm"] button[kind="secondary"],
    section[data-testid="stForm"] button[data-testid="stBaseButton-secondary"],
    section[data-testid="stForm"] button[data-testid="stBaseButton-secondaryFormSubmit"] {
        background: linear-gradient(180deg, #1f4f92 0%, #163b70 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(140, 200, 255, 0.85) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        min-height: 2.6rem !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25) !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover,
    div[data-testid="stFormSubmitButton"] button:hover,
    section[data-testid="stForm"] div.stButton > button:hover,
    section[data-testid="stForm"] button[kind="secondary"]:hover,
    section[data-testid="stForm"] button[data-testid="stBaseButton-secondary"]:hover,
    section[data-testid="stForm"] button[data-testid="stBaseButton-secondaryFormSubmit"]:hover {
        background: linear-gradient(180deg, #2a66b8 0%, #1f4f92 100%) !important;
        border-color: #ffffff !important;
        color: #ffffff !important;
    }
    section[data-testid="stForm"] button[kind="primary"],
    section[data-testid="stForm"] button[data-testid="stBaseButton-primary"],
    section[data-testid="stForm"] button[data-testid="stBaseButton-primaryFormSubmit"] {
        background: linear-gradient(180deg, #2f80ff 0%, #1d4ed8 100%) !important;
        color: #ffffff !important;
        border: 1px solid #93c5fd !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        min-height: 2.8rem !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.45) !important;
    }
    section[data-testid="stForm"] button[kind="primary"]:hover,
    section[data-testid="stForm"] button[data-testid="stBaseButton-primary"]:hover,
    section[data-testid="stForm"] button[data-testid="stBaseButton-primaryFormSubmit"]:hover {
        background: linear-gradient(180deg, #60a5fa 0%, #2563eb 100%) !important;
        color: #ffffff !important;
    }
    label[data-baseweb="checkbox"],
    label[data-baseweb="checkbox"] span,
    label[data-baseweb="checkbox"] p {
        color: #f8fbff !important;
    }
    div[data-baseweb="checkbox"] {
        background-color: rgba(13, 30, 55, .96) !important;
        border-color: rgba(140, 200, 255, .85) !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 2px;
        border-bottom: 1px solid rgba(96, 165, 250, 0.22) !important;
        background: transparent !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background-color: transparent !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-border"] {
        background-color: #3b82f6 !important;
        height: 2px !important;
        border-radius: 2px 2px 0 0;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"] {
        color: #94a3b8 !important;
        background: transparent !important;
        border: none !important;
        border-radius: 8px 8px 0 0 !important;
        box-shadow: none !important;
        padding: 0.62rem 0.95rem 0.72rem !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em;
        min-height: auto !important;
        cursor: pointer !important;
        transition: color 0.15s ease, background-color 0.15s ease;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"]:hover:not([aria-selected="true"]) {
        color: #dbeafe !important;
        background: rgba(59, 130, 246, 0.16) !important;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
        color: #f8fbff !important;
        background: transparent !important;
        border: none !important;
        font-weight: 700 !important;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"]:hover {
        color: #ffffff !important;
        background: rgba(59, 130, 246, 0.10) !important;
    }
    .stApp:has(.app-workspace-header) div[data-testid="stTabs"]:first-of-type button[data-baseweb="tab"] {
        font-size: 0.94rem !important;
        padding: 0.72rem 1.05rem 0.82rem !important;
    }
    .status-ready {background:rgba(0,150,90,.20); border:1px solid rgba(0,220,130,.45); padding:16px; border-radius:16px;}
    .status-review {background:rgba(255,200,0,.18); border:1px solid rgba(255,210,0,.50); padding:16px; border-radius:16px;}
    .status-stop {background:rgba(255,50,50,.18); border:1px solid rgba(255,90,90,.50); padding:16px; border-radius:16px;}
    .live-submit-bar {
        position: sticky;
        top: 0.75rem;
        z-index: 999;
        padding: 14px 18px;
        border-radius: 16px;
        margin-bottom: 16px;
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 28px rgba(0,0,0,.35);
    }
    .live-submit-main {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: 10px 16px;
        margin-bottom: 8px;
    }
    .live-submit-status {
        font-size: 1.35rem;
        font-weight: 700;
        color: #f8fbff !important;
    }
    .live-submit-reason {
        font-size: 0.95rem;
        color: #d6e8ff !important;
    }
    .live-submit-metrics {
        display: flex;
        flex-wrap: wrap;
        gap: 8px 20px;
        font-size: 0.92rem;
        color: #e8f2ff !important;
    }
    .live-submit-metrics strong {
        color: #ffffff !important;
        margin-right: 4px;
    }
    .live-submit-note {
        margin-top: 8px;
        font-size: 0.9rem;
        font-weight: 600;
        color: #ffe08a !important;
    }
    section.main .block-container,
    div[data-testid="stMainBlockContainer"],
    div[data-testid="stAppViewContainer"] > section.main {
        background: transparent !important;
    }
    .reporting-hero {
        padding: 22px 26px;
        border-radius: 18px;
        background: linear-gradient(135deg, rgba(10, 31, 57, .94), rgba(2, 9, 19, .94));
        border: 1px solid rgba(62,150,255,.40);
        box-shadow: 0 16px 40px rgba(0,0,0,.28);
        margin-bottom: 18px;
    }
    .reporting-hero h2 { margin: 0 0 6px 0; font-size: 28px; color: #f8fbff !important; }
    .reporting-hero p { margin: 0; color: #d6e8ff !important; font-size: 15px; }
    .app-sidebar-brand {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 4px 4px 12px;
        margin-bottom: 6px;
        border-bottom: 1px solid rgba(96, 165, 250, 0.22);
    }
    .app-sidebar-logo svg {
        width: 46px;
        height: 52px;
        display: block;
        filter: drop-shadow(0 6px 14px rgba(37, 99, 235, 0.28));
    }
    .app-sidebar-name {
        font-size: 17px;
        font-weight: 900;
        letter-spacing: 0.05em;
        color: #f8fbff !important;
        line-height: 1.1;
    }
    .app-sidebar-sub {
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: #94a3b8 !important;
        margin-top: 3px;
    }
    .app-sidebar-badge {
        display: inline-block;
        margin-top: 6px;
        padding: 3px 8px;
        border-radius: 999px;
        font-size: 8px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #bfdbfe !important;
        background: rgba(37, 99, 235, 0.18);
        border: 1px solid rgba(96, 165, 250, 0.28);
    }
    .app-workspace-header {
        margin: 0 0 4px 0;
        padding: 0;
        background: transparent;
        border: none;
        box-shadow: none;
    }
    div[data-testid="column"]:has(.app-top-refresh-slot) {
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
    }
    div[data-testid="column"]:has(.app-top-refresh-slot) div.stButton {
        margin-top: 0.35rem;
        width: 100%;
    }
    div[data-testid="column"]:has(.app-top-refresh-slot) div.stButton > button {
        min-height: 2.35rem !important;
        font-size: 0.82rem !important;
        padding: 0.35rem 0.55rem !important;
        white-space: nowrap;
    }
    .review-scan-hero {
        margin-bottom: 8px;
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid rgba(96, 165, 250, 0.28);
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.25);
        background: linear-gradient(145deg, rgba(10, 31, 57, 0.94), rgba(2, 9, 19, 0.96));
    }
    .review-scan-hero-top {
        padding: 12px 18px 10px;
    }
    .app-workspace-kicker,
    .review-scan-kicker {
        margin-bottom: 6px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.04em;
        color: #94a3b8 !important;
    }
    .app-workspace-header h2,
    .review-scan-hero-top h2 {
        margin: 0 0 8px 0;
        color: #f8fbff !important;
        font-size: 28px;
        font-weight: 800;
        line-height: 1.15;
    }
    .app-workspace-header h2 span,
    .review-scan-hero-top h2 span {
        color: #f8fbff !important;
    }
    .app-workspace-header p,
    .review-scan-hero-top p {
        margin: 0 0 8px 0;
        color: #94a3b8 !important;
        font-size: 15px;
        line-height: 1.45;
    }
    .app-workspace-header strong,
    .review-scan-hero-top strong {
        color: #cbd5e1 !important;
    }
    .app-workspace-accent {
        margin-top: 6px;
        padding: 0;
        text-align: left;
        font-size: 15px;
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #60a5fa !important;
        background: transparent;
    }
    .review-scan-accent {
        padding: 0;
        text-align: left;
        font-size: 13px;
        font-weight: 600;
        letter-spacing: normal;
        text-transform: none;
        color: #94a3b8 !important;
        background: transparent;
    }
    .review-scan-intro {
        margin: 16px 0 8px 0;
        padding: 0;
        border: none;
        border-radius: 0;
        background: transparent;
    }
    .review-scan-intro h3 {
        margin: 0 0 6px 0;
        color: #f8fbff !important;
        font-size: 18px;
        font-weight: 700;
    }
    .review-scan-intro p {
        margin: 0;
        color: #94a3b8 !important;
        font-size: 14px;
        line-height: 1.45;
    }
    .review-scan-intro strong {
        color: #cbd5e1 !important;
        font-weight: 600;
    }
    .stApp:has(.app-workspace-header) div[data-testid="stTabs"]:first-of-type {
        margin-top: 0 !important;
    }
    .review-section-header {
        margin: 2px 0 8px 0;
        padding-bottom: 6px;
        border-bottom: 1px solid rgba(96, 165, 250, 0.18);
    }
    .review-section-title {
        font-size: 22px;
        font-weight: 800;
        color: #f8fbff !important;
        line-height: 1.15;
    }
    .review-section-sub {
        margin-top: 3px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.05em;
        color: #94a3b8 !important;
    }
    .stApp:has(.review-scan-hero) section[data-testid="stFileUploaderDropzone"],
    .stApp:has(.review-scan-intro) section[data-testid="stFileUploaderDropzone"] {
        background-color: rgba(13, 30, 55, .92) !important;
        border: 1px dashed rgba(96, 165, 250, 0.45) !important;
        border-radius: 14px !important;
    }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(7, 19, 34, .58) !important;
        border-color: rgba(62,150,255,.28) !important;
        border-radius: 16px !important;
        padding: 10px 14px !important;
        margin-bottom: 12px !important;
    }
    div[data-testid="stDataFrame"] {
        background: rgba(7, 19, 34, .72) !important;
        border: 1px solid rgba(62,150,255,.28) !important;
        border-radius: 14px !important;
        padding: 4px !important;
    }
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] {
        background: transparent !important;
    }
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] button,
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] [data-testid="stBaseButton-header"],
    div[data-testid="stDataFrame"] button[kind="header"] {
        background: linear-gradient(180deg, #1f4f92 0%, #163b70 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(140, 200, 255, 0.85) !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.22) !important;
    }
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] button:hover,
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] [data-testid="stBaseButton-header"]:hover,
    div[data-testid="stDataFrame"] button[kind="header"]:hover {
        background: linear-gradient(180deg, #2a66b8 0%, #1f4f92 100%) !important;
        color: #ffffff !important;
        border-color: #ffffff !important;
    }
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] button svg,
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] span,
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] [data-testid="stIconMaterial"] {
        color: #ffffff !important;
        fill: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    [data-testid="stElementToolbar"] button,
    [data-testid="stElementToolbar"] [data-testid="stBaseButton-header"],
    button[kind="header"],
    [data-testid="stBaseButton-header"] {
        background: linear-gradient(180deg, #1f4f92 0%, #163b70 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(140, 200, 255, 0.85) !important;
        border-radius: 8px !important;
    }
    [data-testid="stElementToolbar"] button svg,
    [data-testid="stElementToolbar"] span,
    [data-testid="stElementToolbar"] [data-testid="stIconMaterial"],
    button[kind="header"] svg,
    [data-testid="stBaseButton-header"] svg {
        color: #ffffff !important;
        fill: #ffffff !important;
        -webkit-text-fill-color: #ffffff !important;
    }
    div[data-testid="stImage"] {
        background: rgba(7, 19, 34, .72);
        border: 1px solid rgba(62,150,255,.28);
        border-radius: 14px;
        padding: 8px;
    }
    div[data-testid="stCaptionContainer"] p {
        color: #d6e8ff !important;
    }
    div[data-testid="stDateInput"] > div,
    div[data-testid="stDateInput"] input {
        background-color: rgba(13, 30, 55, .96) !important;
        color: #ffffff !important;
        border: 1px solid rgba(140, 200, 255, .70) !important;
    }
    .ro-login-active { display: none !important; }
    .stApp:has(.ro-login-active) .login-form-column-marker {
        display: none !important;
    }
    .stApp:has(.ro-login-active) {
        background:
            linear-gradient(rgba(4, 10, 20, 0.94), rgba(4, 10, 20, 0.98)),
            radial-gradient(circle at 85% 20%, rgba(37, 99, 235, 0.16), transparent 42%),
            linear-gradient(160deg, #060d18 0%, #0b1424 45%, #050a12 100%) !important;
    }
    .stApp:has(.ro-login-active) section[data-testid="stSidebar"] {
        display: none !important;
    }
    .stApp:has(.ro-login-active) section.main {
        padding-top: 0 !important;
    }
    .stApp:has(.ro-login-active) section.main .block-container {
        max-width: 1080px;
        padding-top: 0.35rem;
        padding-bottom: 1rem;
    }
    .stApp:has(.ro-login-active) header[data-testid="stHeader"] {
        background: transparent !important;
        height: 0 !important;
        min-height: 0 !important;
        visibility: hidden !important;
    }
    .stApp:has(.ro-login-active) div[data-testid="stVerticalBlock"] {
        gap: 0.35rem !important;
    }
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] {
        gap: 0.85rem !important;
        align-items: stretch !important;
    }
    .stApp:has(.ro-login-active) .login-brand-panel {
        position: relative;
        min-height: auto;
        padding: 0;
        border-radius: 18px;
        overflow: hidden;
        background: #08111f;
        border: 1px solid rgba(148, 163, 184, 0.28);
        box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
    }
    .stApp:has(.ro-login-active) .login-brand-top {
        position: relative;
        z-index: 1;
        background: #ffffff;
        padding: 16px 20px 14px;
        border-bottom: 1px solid #e2e8f0;
    }
    .stApp:has(.ro-login-active) .login-brand-dark {
        padding: 16px 20px 14px;
        background: linear-gradient(180deg, #0b1424 0%, #060d18 100%);
    }
    .stApp:has(.ro-login-active) .login-brand-panel-compact .login-brand-dark {
        padding-bottom: 16px;
    }
    .stApp:has(.ro-login-active) .login-brand-row {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 8px;
    }
    .stApp:has(.ro-login-active) .login-logo-shield {
        width: 62px;
        height: 70px;
        flex: 0 0 62px;
    }
    .stApp:has(.ro-login-active) .login-logo-shield svg {
        width: 62px;
        height: 70px;
        display: block;
        filter: drop-shadow(0 8px 18px rgba(37, 99, 235, 0.35));
    }
    .stApp:has(.ro-login-active) .login-brand-name {
        font-size: 28px;
        font-weight: 900;
        letter-spacing: 0.05em;
        color: #0f172a !important;
        line-height: 1.05;
    }
    .stApp:has(.ro-login-active) .login-brand-sub {
        margin-top: 5px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: #64748b !important;
    }
    .stApp:has(.ro-login-active) .login-badge {
        display: inline-block;
        margin-bottom: 0;
        padding: 4px 11px;
        border-radius: 999px;
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #1d4ed8 !important;
        background: rgba(37, 99, 235, 0.10);
        border: 1px solid rgba(37, 99, 235, 0.22);
    }
    .stApp:has(.ro-login-active) .login-headline {
        position: relative;
        z-index: 1;
        margin: 0 0 6px 0;
        font-size: 24px;
        font-weight: 800;
        line-height: 1.2;
        color: #f8fafc !important;
    }
    .stApp:has(.ro-login-active) .login-brand-panel-compact .login-headline {
        color: #f8fafc !important;
    }
    .stApp:has(.ro-login-active) .login-brand-panel-compact .login-headline span {
        color: #60a5fa !important;
    }
    .stApp:has(.ro-login-active) .login-headline span {
        color: #60a5fa !important;
    }
    .stApp:has(.ro-login-active) .login-lede {
        position: relative;
        z-index: 1;
        margin: 0 0 10px 0;
        color: #cbd5e1 !important;
        font-size: 13px;
        line-height: 1.55;
        max-width: 100%;
    }
    .stApp:has(.ro-login-active) .login-features {
        position: relative;
        z-index: 1;
        display: grid;
        gap: 8px;
        margin-bottom: 10px;
    }
    .stApp:has(.ro-login-active) .login-feature {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 8px 10px;
        border-radius: 12px;
        background: rgba(15, 23, 42, 0.55);
        border: 1px solid rgba(96, 165, 250, 0.18);
    }
    .stApp:has(.ro-login-active) .login-feature-icon {
        width: 34px;
        height: 34px;
        border-radius: 10px;
        display: grid;
        place-items: center;
        font-size: 16px;
        background: rgba(37, 99, 235, 0.18);
        border: 1px solid rgba(96, 165, 250, 0.35);
        flex: 0 0 34px;
    }
    .stApp:has(.ro-login-active) .login-feature strong {
        display: block;
        color: #eff6ff !important;
        font-size: 13px;
        margin-bottom: 2px;
    }
    .stApp:has(.ro-login-active) .login-feature span {
        display: block;
        color: #94a3b8 !important;
        font-size: 11px;
        line-height: 1.45;
    }
    .stApp:has(.ro-login-active) .login-strapline {
        position: relative;
        z-index: 1;
        display: grid;
        gap: 4px;
        margin-bottom: 10px;
    }
    .stApp:has(.ro-login-active) .login-strapline span {
        display: block;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #dbeafe !important;
    }
    .stApp:has(.ro-login-active) .login-bottom-bar {
        position: relative;
        z-index: 1;
        margin-top: 4px;
        padding: 9px 12px;
        border-radius: 10px;
        text-align: center;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #ffffff !important;
        background: linear-gradient(180deg, #2563eb 0%, #1d4ed8 100%);
        box-shadow: 0 10px 24px rgba(37, 99, 235, 0.28);
    }
    .stApp:has(.ro-login-active) .login-form-title {
        margin: 0 0 2px 0;
        font-size: 24px;
        font-weight: 800;
        color: #0f172a !important;
        line-height: 1.1;
    }
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker),
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 18px !important;
        padding: 16px 18px 12px !important;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35) !important;
    }
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker) h4,
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker) label,
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker) p,
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker) span,
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child h4,
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child label,
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child p,
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child span {
        color: #0f172a !important;
    }
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker) div[data-testid="stCaptionContainer"] p,
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child div[data-testid="stCaptionContainer"] p {
        color: #475569 !important;
        font-size: 13px !important;
    }
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker) input,
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker) div[data-baseweb="input"],
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker) div[data-baseweb="input"] > div,
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker) div[data-baseweb="base-input"],
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker) div[data-baseweb="base-input"] > div,
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child input,
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child div[data-baseweb="input"],
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child div[data-baseweb="input"] > div,
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child div[data-baseweb="base-input"],
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child div[data-baseweb="base-input"] > div {
        background-color: #ffffff !important;
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
        border-color: #94a3b8 !important;
    }
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker) input::placeholder,
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child input::placeholder {
        color: #64748b !important;
        -webkit-text-fill-color: #64748b !important;
    }
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker) input:-webkit-autofill,
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker) input:-webkit-autofill:focus,
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child input:-webkit-autofill,
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child input:-webkit-autofill:focus {
        -webkit-box-shadow: 0 0 0 1000px #ffffff inset !important;
        -webkit-text-fill-color: #0f172a !important;
        caret-color: #0f172a !important;
    }
    .stApp:has(.ro-login-active) section[data-testid="stForm"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }
    .stApp:has(.ro-login-active) details[data-testid="stExpander"] {
        margin-top: 12px;
        background: #f8fafc;
        border: 1px solid #cbd5e1;
        border-radius: 12px;
        overflow: hidden;
    }
    .stApp:has(.ro-login-active) details[data-testid="stExpander"] summary {
        color: #1d4ed8 !important;
        font-weight: 600;
    }
    .stApp:has(.ro-login-active) details[data-testid="stExpander"] p,
    .stApp:has(.ro-login-active) details[data-testid="stExpander"] label {
        color: #334155 !important;
    }
    .stApp:has(.ro-login-active) div[data-testid="stCaptionContainer"] p {
        color: #64748b !important;
    }
    .stApp:has(.ro-login-active) .login-footer-note {
        text-align: center;
        margin-top: 8px;
        color: #94a3b8 !important;
        font-size: 12px;
        line-height: 1.45;
    }
    """,
    "Light": """
    .stApp {
        position: relative;
        isolation: isolate;
        color: #0f172a;
        background-color: #c8d6e4;
        background-image:
            radial-gradient(ellipse 85% 50% at 50% -12%, rgba(147, 197, 253, 0.34), transparent 55%),
            radial-gradient(circle at 88% 20%, rgba(96, 165, 250, 0.16), transparent 30%),
            radial-gradient(circle at 12% 78%, rgba(147, 197, 253, 0.20), transparent 35%),
            linear-gradient(180deg, #dbe6f0 0%, #c8d6e4 55%, #bccddd 100%);
        background-attachment: fixed;
        --rg-surface: #dde8f2;
        --rg-surface-input: #e8f0f8;
        --rg-surface-hover: #d2e0ed;
        --rg-border: #b6c7da;
    }
    .stApp::before {
        content: "";
        position: fixed;
        inset: 0;
        z-index: 0;
        pointer-events: none;
        background-image:
            linear-gradient(rgba(37, 99, 235, 0.08) 1px, transparent 1px),
            linear-gradient(90deg, rgba(37, 99, 235, 0.08) 1px, transparent 1px),
            radial-gradient(circle at 22% 18%, rgba(59, 130, 246, 0.14) 0%, transparent 26%),
            radial-gradient(circle at 78% 72%, rgba(100, 116, 139, 0.12) 0%, transparent 22%);
        background-size: 64px 64px, 64px 64px, 100% 100%, 100% 100%;
        mask-image: radial-gradient(ellipse 95% 85% at 50% 45%, black 20%, transparent 100%);
        -webkit-mask-image: radial-gradient(ellipse 95% 85% at 50% 45%, black 20%, transparent 100%);
    }
    .stApp::after {
        content: "";
        position: fixed;
        right: -6%;
        bottom: -8%;
        width: min(480px, 52vw);
        height: min(560px, 62vh);
        z-index: 0;
        pointer-events: none;
        opacity: 0.13;
        background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 72 82'%3E%3Cpath d='M36 4 L66 18 V40 C66 58 52 72 36 78 C20 72 6 58 6 40 V18 Z' fill='none' stroke='%231d4ed8' stroke-width='1.8'/%3E%3Cpath d='M36 12 L60 24 V40 C60 54 50 66 36 72 C22 66 12 54 12 40 V24 Z' fill='none' stroke='%232563eb' stroke-width='1' opacity='0.75'/%3E%3Ctext x='36' y='43' text-anchor='middle' fill='%231d4ed8' font-size='9' font-weight='800' font-family='Arial,sans-serif'%3ERO-%3C/text%3E%3Ctext x='36' y='54' text-anchor='middle' fill='%231d4ed8' font-size='9' font-weight='800' font-family='Arial,sans-serif'%3EGuard%3C/text%3E%3C/svg%3E") no-repeat center / contain;
    }
    .stApp:has(.ro-login-active)::before,
    .stApp:has(.ro-login-active)::after {
        display: none;
    }
    header[data-testid="stHeader"],
    section[data-testid="stSidebar"],
    section.main,
    div[data-testid="stAppViewContainer"] {
        position: relative;
        z-index: 1;
    }
    header[data-testid="stHeader"] { background: rgba(255,255,255,0.75); }
    section[data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 50% 0%, rgba(147, 197, 253, 0.26), transparent 58%),
            linear-gradient(180deg, #e8eff6, #d8e4ef) !important;
        border-right: 1px solid #cbd5e1;
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 0.75rem;
    }
    section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
        gap: 0.45rem !important;
    }
    section[data-testid="stSidebar"] hr {
        margin: 0.65rem 0 !important;
        border-color: #c7d5e3 !important;
    }
    section[data-testid="stSidebar"] .rg-sidebar-settings-title {
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #475569 !important;
        margin: 0.15rem 0 0.1rem 0;
    }
    [data-testid="stIconMaterial"],
    span[data-testid="stIconMaterial"],
    .material-symbols-rounded {
        font-family: "Material Symbols Rounded" !important;
        font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        -webkit-text-fill-color: currentColor !important;
    }
    .stApp, .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
        color: #0f172a;
    }
    .hero {
        padding: 28px 30px;
        border-radius: 22px;
        background: linear-gradient(135deg, var(--rg-surface-input), var(--rg-surface));
        border: 1px solid var(--rg-border);
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
        margin-bottom: 22px;
    }
    .hero h1 { margin: 0; font-size: 48px; letter-spacing: .5px; }
    .hero p { color: #334155 !important; font-size: 16px; }
    .section-card {
        padding: 18px;
        border-radius: 18px;
        background: var(--rg-surface);
        border: 1px solid var(--rg-border);
        margin: 10px 0 18px 0;
    }
    textarea, input, div[data-baseweb="input"] input {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
        background-color: var(--rg-surface-input) !important;
        border: 1px solid var(--rg-border) !important;
    }
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stTextInput"] input,
    div[data-testid="stTextInput"] textarea,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stTextArea"] div[data-baseweb="base-input"],
    div[data-testid="stTextArea"] div[data-baseweb="base-input"] > div,
    section[data-testid="stForm"] textarea,
    section[data-testid="stForm"] input {
        background-color: var(--rg-surface-input) !important;
        border-color: var(--rg-border) !important;
    }
    textarea::placeholder, input::placeholder { color: #64748b !important; opacity: 1 !important; }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-baseweb="select"] > div {
        background-color: var(--rg-surface-input) !important;
        border: 1px solid var(--rg-border) !important;
    }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] span,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] div,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] p,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] input,
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div,
    div[data-baseweb="select"] p,
    div[data-baseweb="select"] input,
    div[data-baseweb="select"] svg {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
        fill: #0f172a !important;
    }
    div[data-baseweb="popover"] div[data-baseweb="menu"],
    div[data-baseweb="popover"] ul,
    ul[role="listbox"] {
        background-color: var(--rg-surface-input) !important;
        border: 1px solid var(--rg-border) !important;
    }
    div[data-baseweb="popover"] li,
    li[role="option"] {
        color: #0f172a !important;
        background-color: var(--rg-surface-input) !important;
    }
    div[data-baseweb="popover"] li:hover,
    li[role="option"]:hover,
    li[role="option"][aria-selected="true"],
    div[data-baseweb="popover"] li[aria-selected="true"] {
        background-color: var(--rg-surface-hover) !important;
        color: #1d4ed8 !important;
    }
    section[data-testid="stFileUploaderDropzone"] {
        background-color: var(--rg-surface-input) !important;
        border: 1px dashed var(--rg-border) !important;
    }
    div[data-testid="stMetric"] {
        background: var(--rg-surface);
        border: 1px solid var(--rg-border);
        border-radius: 16px;
        padding: 14px 16px;
        min-height: 96px;
        height: auto !important;
        overflow: visible !important;
    }
    div[data-testid="stMetricValue"] {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        word-break: break-word;
        font-size: clamp(1.15rem, 2.2vw, 1.75rem) !important;
        line-height: 1.25 !important;
        color: #0f172a !important;
    }
    div[data-testid="stMetricLabel"] {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: unset !important;
        line-height: 1.35 !important;
        color: #334155 !important;
    }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        overflow: visible !important;
        min-width: 7.5rem;
    }
    div.stButton > button,
    button[kind="secondary"],
    button[data-testid="stBaseButton-secondary"] {
        background: var(--rg-surface) !important;
        color: #0f172a !important;
        border: 1px solid var(--rg-border) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        min-height: 2.6rem !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12) !important;
    }
    div.stButton > button:hover,
    button[kind="secondary"]:hover,
    button[data-testid="stBaseButton-secondary"]:hover {
        background: var(--rg-surface-hover) !important;
        border-color: #2563eb !important;
        color: #1d4ed8 !important;
    }
    button[kind="primary"],
    button[data-testid="stBaseButton-primary"],
    div.stButton > button[kind="primary"] {
        background: linear-gradient(180deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: #ffffff !important;
        border: 1px solid #1e40af !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        min-height: 2.8rem !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.28) !important;
    }
    button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%) !important;
        color: #ffffff !important;
    }
    div[data-testid="stFormSubmitButton"] > button,
    div[data-testid="stFormSubmitButton"] button,
    section[data-testid="stForm"] div.stButton > button,
    section[data-testid="stForm"] button[kind="secondary"],
    section[data-testid="stForm"] button[data-testid="stBaseButton-secondary"],
    section[data-testid="stForm"] button[data-testid="stBaseButton-secondaryFormSubmit"] {
        background: var(--rg-surface) !important;
        color: #0f172a !important;
        border: 1px solid var(--rg-border) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        min-height: 2.6rem !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12) !important;
    }
    div[data-testid="stFormSubmitButton"] > button:hover,
    div[data-testid="stFormSubmitButton"] button:hover,
    section[data-testid="stForm"] div.stButton > button:hover,
    section[data-testid="stForm"] button[kind="secondary"]:hover,
    section[data-testid="stForm"] button[data-testid="stBaseButton-secondary"]:hover,
    section[data-testid="stForm"] button[data-testid="stBaseButton-secondaryFormSubmit"]:hover {
        background: var(--rg-surface-hover) !important;
        border-color: #2563eb !important;
        color: #1d4ed8 !important;
    }
    section[data-testid="stForm"] button[kind="primary"],
    section[data-testid="stForm"] button[data-testid="stBaseButton-primary"],
    section[data-testid="stForm"] button[data-testid="stBaseButton-primaryFormSubmit"] {
        background: linear-gradient(180deg, #2563eb 0%, #1d4ed8 100%) !important;
        color: #ffffff !important;
        border: 1px solid #1e40af !important;
        border-radius: 10px !important;
        font-weight: 700 !important;
        min-height: 2.8rem !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.28) !important;
    }
    label[data-baseweb="checkbox"],
    label[data-baseweb="checkbox"] span,
    label[data-baseweb="checkbox"] p {
        color: #0f172a !important;
    }
    div[data-baseweb="checkbox"] {
        background-color: var(--rg-surface-input) !important;
        border-color: var(--rg-border) !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 2px;
        border-bottom: 1px solid #c7d5e3 !important;
        background: transparent !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background-color: transparent !important;
    }
    div[data-testid="stTabs"] [data-baseweb="tab-border"] {
        background-color: #2563eb !important;
        height: 2px !important;
        border-radius: 2px 2px 0 0;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"] {
        color: #64748b !important;
        background: transparent !important;
        border: none !important;
        border-radius: 8px 8px 0 0 !important;
        box-shadow: none !important;
        padding: 0.62rem 0.95rem 0.72rem !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em;
        min-height: auto !important;
        cursor: pointer !important;
        transition: color 0.15s ease, background-color 0.15s ease;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"]:hover:not([aria-selected="true"]) {
        color: #1d4ed8 !important;
        background: rgba(37, 99, 235, 0.12) !important;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
        color: #1d4ed8 !important;
        background: transparent !important;
        border: none !important;
        font-weight: 700 !important;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"]:hover {
        color: #1e40af !important;
        background: rgba(37, 99, 235, 0.08) !important;
    }
    .stApp:has(.app-workspace-header) div[data-testid="stTabs"]:first-of-type button[data-baseweb="tab"] {
        font-size: 0.94rem !important;
        padding: 0.72rem 1.05rem 0.82rem !important;
    }
    .status-ready {background:#ecfdf5; border:1px solid #34d399; padding:16px; border-radius:16px; color:#065f46 !important;}
    .status-review {background:#fffbeb; border:1px solid #fbbf24; padding:16px; border-radius:16px; color:#92400e !important;}
    .status-stop {background:#fef2f2; border:1px solid #f87171; padding:16px; border-radius:16px; color:#991b1b !important;}
    .live-submit-bar {
        position: sticky;
        top: 0.75rem;
        z-index: 999;
        padding: 14px 18px;
        border-radius: 16px;
        margin-bottom: 16px;
        backdrop-filter: blur(8px);
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
    }
    .live-submit-main {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        gap: 10px 16px;
        margin-bottom: 8px;
    }
    .live-submit-status {
        font-size: 1.35rem;
        font-weight: 700;
    }
    .live-submit-reason {
        font-size: 0.95rem;
        opacity: 0.92;
    }
    .live-submit-metrics {
        display: flex;
        flex-wrap: wrap;
        gap: 8px 20px;
        font-size: 0.92rem;
    }
    .live-submit-metrics strong {
        margin-right: 4px;
    }
    .live-submit-note {
        margin-top: 8px;
        font-size: 0.9rem;
        font-weight: 600;
        color: #b45309 !important;
    }
    section.main .block-container,
    div[data-testid="stMainBlockContainer"],
    div[data-testid="stAppViewContainer"] > section.main {
        background: transparent !important;
    }
    .reporting-hero {
        padding: 22px 26px;
        border-radius: 18px;
        background: linear-gradient(135deg, var(--rg-surface-input), var(--rg-surface));
        border: 1px solid var(--rg-border);
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
        margin-bottom: 18px;
    }
    .reporting-hero h2 { margin: 0 0 6px 0; font-size: 28px; color: #0f172a !important; }
    .reporting-hero p { margin: 0; color: #334155 !important; font-size: 15px; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--rg-surface) !important;
        border: 1px solid var(--rg-border) !important;
        border-radius: 16px !important;
        padding: 10px 14px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04) !important;
    }
    div[data-testid="stDataFrame"] {
        background: var(--rg-surface) !important;
        border: 1px solid var(--rg-border) !important;
        border-radius: 14px !important;
        padding: 4px !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04) !important;
    }
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] {
        background: transparent !important;
    }
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] button,
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] [data-testid="stBaseButton-header"],
    div[data-testid="stDataFrame"] button[kind="header"] {
        background: var(--rg-surface-input) !important;
        color: #0f172a !important;
        border: 1px solid var(--rg-border) !important;
        border-radius: 8px !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12) !important;
    }
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] button:hover,
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] [data-testid="stBaseButton-header"]:hover,
    div[data-testid="stDataFrame"] button[kind="header"]:hover {
        background: var(--rg-surface-hover) !important;
        color: #1d4ed8 !important;
        border-color: #2563eb !important;
    }
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] button svg,
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] span,
    div[data-testid="stDataFrame"] [data-testid="stElementToolbar"] [data-testid="stIconMaterial"] {
        color: #0f172a !important;
        fill: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }
    [data-testid="stElementToolbar"] button,
    [data-testid="stElementToolbar"] [data-testid="stBaseButton-header"],
    button[kind="header"],
    [data-testid="stBaseButton-header"] {
        background: var(--rg-surface-input) !important;
        color: #0f172a !important;
        border: 1px solid var(--rg-border) !important;
        border-radius: 8px !important;
    }
    [data-testid="stElementToolbar"] button svg,
    [data-testid="stElementToolbar"] span,
    [data-testid="stElementToolbar"] [data-testid="stIconMaterial"],
    button[kind="header"] svg,
    [data-testid="stBaseButton-header"] svg {
        color: #0f172a !important;
        fill: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
    }
    div[data-testid="stImage"] {
        background: var(--rg-surface);
        border: 1px solid var(--rg-border);
        border-radius: 14px;
        padding: 8px;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
    }
    div[data-testid="stDateInput"] > div,
    div[data-testid="stDateInput"] input {
        background-color: var(--rg-surface-input) !important;
        color: #0f172a !important;
        border: 1px solid var(--rg-border) !important;
    }
    section[data-testid="stForm"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    .app-sidebar-brand {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 4px 4px 12px;
        margin-bottom: 6px;
        border-bottom: 1px solid #e2e8f0;
    }
    .app-sidebar-logo svg {
        width: 46px;
        height: 52px;
        display: block;
    }
    .app-sidebar-name {
        font-size: 17px;
        font-weight: 900;
        letter-spacing: 0.05em;
        color: #0f172a !important;
        line-height: 1.1;
    }
    .app-sidebar-sub {
        font-size: 9px;
        font-weight: 700;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: #64748b !important;
        margin-top: 3px;
    }
    .app-sidebar-badge {
        display: inline-block;
        margin-top: 6px;
        padding: 3px 8px;
        border-radius: 999px;
        font-size: 8px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #1d4ed8 !important;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
    }
    .app-workspace-header {
        margin: 0 0 4px 0;
        padding: 0;
    }
    .app-workspace-kicker {
        margin-bottom: 6px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.04em;
        color: #64748b !important;
    }
    .app-workspace-header h2 {
        margin: 0 0 8px 0;
        color: #0f172a !important;
        font-size: 28px;
        font-weight: 800;
        line-height: 1.15;
    }
    .app-workspace-header h2 span {
        color: #0f172a !important;
    }
    .app-workspace-header p {
        margin: 0 0 8px 0;
        color: #475569 !important;
        font-size: 15px;
        line-height: 1.45;
    }
    .app-workspace-accent {
        margin-top: 6px;
        padding: 0;
        text-align: left;
        font-size: 15px;
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #1d4ed8 !important;
        background: transparent;
    }
    .review-scan-intro {
        margin: 16px 0 8px 0;
        padding: 0;
    }
    .review-scan-intro h3 {
        margin: 0 0 6px 0;
        color: #0f172a !important;
        font-size: 18px;
        font-weight: 700;
    }
    .review-scan-intro p {
        margin: 0;
        color: #475569 !important;
        font-size: 14px;
        line-height: 1.45;
    }
    .review-scan-intro strong {
        color: #334155 !important;
        font-weight: 600;
    }
    .stApp:has(.app-workspace-header) div[data-testid="stTabs"]:first-of-type {
        margin-top: 0 !important;
    }
    """,
}


def pricing_page_css(theme: str = "Dark") -> str:
    """Pricing cards and ROI calculator chrome."""
    key = "Light" if str(theme).lower() == "light" else "Dark"
    if key == "Light":
        card_bg = "rgba(255, 255, 255, .92)"
        card_border = "rgba(29, 78, 216, .22)"
        featured_border = "rgba(29, 78, 216, .55)"
        text = "#0f172a"
        muted = "#64748b"
        accent = "#1d4ed8"
        badge_bg = "rgba(29, 78, 216, .12)"
    else:
        card_bg = "rgba(7, 19, 34, .72)"
        card_border = "rgba(62, 150, 255, .24)"
        featured_border = "rgba(96, 165, 250, .55)"
        text = "#f8fbff"
        muted = "#94a3b8"
        accent = "#60a5fa"
        badge_bg = "rgba(96, 165, 250, .16)"

    return f"""
    .pricing-card {{
        padding: 20px 18px 18px 18px;
        border-radius: 18px;
        background: {card_bg};
        border: 1px solid {card_border};
        min-height: 360px;
        margin-bottom: 8px;
        box-shadow: 0 12px 36px rgba(0,0,0,.18);
    }}
    .pricing-card-featured {{
        border-color: {featured_border};
        box-shadow: 0 16px 44px rgba(37, 99, 235, .18);
    }}
    .pricing-card-selected {{
        outline: 2px solid {accent};
        outline-offset: 2px;
    }}
    .pricing-badge {{
        display: inline-block;
        font-size: 0.72rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: {accent} !important;
        background: {badge_bg};
        border-radius: 999px;
        padding: 4px 10px;
        margin-bottom: 10px;
    }}
    .pricing-name {{
        font-size: 1.35rem;
        font-weight: 700;
        color: {text} !important;
        margin-bottom: 4px;
    }}
    .pricing-tagline {{
        color: {muted} !important;
        font-size: 0.88rem;
        line-height: 1.35;
        margin-bottom: 14px;
        min-height: 2.4em;
    }}
    .pricing-price {{
        font-size: 2rem;
        font-weight: 800;
        color: {text} !important;
        line-height: 1.1;
        margin-bottom: 4px;
    }}
    .pricing-price span {{
        font-size: 0.95rem;
        font-weight: 600;
        color: {muted} !important;
    }}
    .pricing-annual {{
        color: {muted} !important;
        font-size: 0.82rem;
        margin-bottom: 14px;
    }}
    .pricing-features {{
        margin: 0;
        padding-left: 1.1rem;
        color: {muted} !important;
        font-size: 0.88rem;
        line-height: 1.55;
    }}
    .pricing-features li {{
        margin-bottom: 4px;
    }}
    .pricing-contact-card {{
        margin-top: 8px;
    }}
    .pricing-contact-card a {{
        color: {accent} !important;
        text-decoration: none;
        font-weight: 600;
    }}
    """


def multiselect_css(theme: str = "Dark") -> str:
    """Role tags and chips on st.multiselect — readable, on-brand, not red/error styling."""
    key = "Light" if str(theme).lower() == "light" else "Dark"
    if key == "Light":
        field_bg = "rgba(255, 255, 255, .96)"
        field_border = "rgba(29, 78, 216, .45)"
        label = "#0f172a"
        tag_bg = "rgba(29, 78, 216, 0.14)"
        tag_border = "rgba(29, 78, 216, 0.45)"
        tag_text = "#1e3a8a"
    else:
        field_bg = "rgba(13, 30, 55, .96)"
        field_border = "rgba(140, 200, 255, .70)"
        label = "#f8fbff"
        tag_bg = "rgba(37, 99, 235, 0.88)"
        tag_border = "rgba(147, 197, 253, 0.55)"
        tag_text = "#ffffff"

    scope = (
        'div[data-testid="stMultiSelect"], '
        'section[data-testid="stForm"] div[data-testid="stMultiSelect"]'
    )

    return f"""
    {scope} label {{
        color: {label} !important;
    }}
    {scope} div[data-baseweb="select"] > div {{
        background-color: {field_bg} !important;
        border: 1px solid {field_border} !important;
        min-height: 2.75rem !important;
        padding: 6px 8px !important;
        overflow: visible !important;
        flex-wrap: wrap !important;
        align-items: center !important;
        gap: 6px !important;
    }}
    {scope} div[data-baseweb="select"] > div > div {{
        flex-wrap: wrap !important;
        align-items: center !important;
        gap: 6px !important;
        overflow: visible !important;
        max-width: 100% !important;
    }}
    {scope} span[data-baseweb="tag"] {{
        display: inline-flex !important;
        align-items: center !important;
        background-color: {tag_bg} !important;
        border: 1px solid {tag_border} !important;
        border-radius: 8px !important;
        color: {tag_text} !important;
        -webkit-text-fill-color: {tag_text} !important;
        padding: 4px 10px !important;
        margin: 0 !important;
        overflow: visible !important;
        max-width: none !important;
        white-space: nowrap !important;
        line-height: 1.25 !important;
        box-shadow: none !important;
    }}
    {scope} span[data-baseweb="tag"] span,
    {scope} span[data-baseweb="tag"] div {{
        color: {tag_text} !important;
        -webkit-text-fill-color: {tag_text} !important;
        overflow: visible !important;
        text-overflow: unset !important;
        white-space: nowrap !important;
        padding: 0 !important;
        margin: 0 !important;
    }}
    {scope} span[data-baseweb="tag"] svg,
    {scope} span[data-baseweb="tag"] button,
    {scope} span[data-baseweb="tag"] [role="button"] {{
        color: {tag_text} !important;
        fill: {tag_text} !important;
        background: transparent !important;
        border: none !important;
        margin-left: 4px !important;
        flex-shrink: 0 !important;
    }}
    {scope} div[data-baseweb="select"] input {{
        color: {tag_text if key == "Dark" else label} !important;
        -webkit-text-fill-color: {tag_text if key == "Dark" else label} !important;
        background: transparent !important;
        min-width: 3rem !important;
        width: auto !important;
        flex: 1 1 3rem !important;
        margin: 0 !important;
        padding: 2px 0 !important;
        position: static !important;
    }}
    """
