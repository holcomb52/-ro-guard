"""In-app user guide with step-by-step instructions and visual mockups."""

from __future__ import annotations

import html

import streamlit as st


def user_guide_css(theme: str = "Dark") -> str:
    is_light = str(theme).lower() == "light"
    surface = "var(--rg-surface-card, #f4f8fc)" if is_light else "rgba(7, 19, 34, .88)"
    surface_alt = "var(--rg-surface-hover, #e8f0f8)" if is_light else "rgba(15, 35, 60, .75)"
    border = "var(--rg-border, #b6c7da)" if is_light else "rgba(62, 150, 255, .28)"
    text = "#0f172a" if is_light else "#e8f0f8"
    muted = "#64748b" if is_light else "#94a3b8"
    accent = "#1d4ed8" if is_light else "#60a5fa"
    accent_soft = "rgba(29, 78, 216, .12)" if is_light else "rgba(96, 165, 250, .14)"
    success = "#15803d" if is_light else "#4ade80"
    warn = "#b45309" if is_light else "#fbbf24"
    danger = "#b91c1c" if is_light else "#f87171"

    return f"""
    .stApp:has(.user-guide-marker) .ug-hero {{
        border: 1px solid {border};
        background: linear-gradient(135deg, {surface} 0%, {surface_alt} 100%);
        border-radius: 16px;
        padding: 1.35rem 1.5rem 1.25rem;
        margin-bottom: 1rem;
    }}
    .stApp:has(.user-guide-marker) .ug-hero h3 {{
        margin: 0 0 .35rem;
        color: {text};
        font-size: 1.35rem;
    }}
    .stApp:has(.user-guide-marker) .ug-hero p {{
        margin: 0;
        color: {muted};
        line-height: 1.55;
    }}
    .stApp:has(.user-guide-marker) .ug-step {{
        display: grid;
        grid-template-columns: 2.4rem 1fr;
        gap: .85rem 1rem;
        border: 1px solid {border};
        background: {surface};
        border-radius: 14px;
        padding: 1rem 1.1rem;
        margin: .65rem 0;
    }}
    .stApp:has(.user-guide-marker) .ug-step-num {{
        width: 2.4rem;
        height: 2.4rem;
        border-radius: 999px;
        background: {accent_soft};
        color: {accent};
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1rem;
    }}
    .stApp:has(.user-guide-marker) .ug-step-title {{
        color: {text};
        font-weight: 650;
        margin: 0 0 .25rem;
        font-size: 1.02rem;
    }}
    .stApp:has(.user-guide-marker) .ug-step-body {{
        color: {muted};
        margin: 0;
        line-height: 1.55;
        font-size: .94rem;
    }}
    .stApp:has(.user-guide-marker) .ug-visual {{
        grid-column: 1 / -1;
        border: 1px dashed {border};
        background: {surface_alt};
        border-radius: 12px;
        padding: .85rem 1rem;
        margin-top: .15rem;
    }}
    .stApp:has(.user-guide-marker) .ug-nav-mock {{
        display: flex;
        flex-wrap: wrap;
        gap: .35rem;
    }}
    .stApp:has(.user-guide-marker) .ug-nav-pill {{
        border: 1px solid {border};
        border-radius: 999px;
        padding: .28rem .65rem;
        font-size: .78rem;
        color: {muted};
        background: {surface};
    }}
    .stApp:has(.user-guide-marker) .ug-nav-pill.active {{
        background: {accent_soft};
        color: {accent};
        border-color: {accent};
        font-weight: 650;
    }}
    .stApp:has(.user-guide-marker) .ug-panel {{
        border: 1px solid {border};
        border-radius: 10px;
        background: {surface};
        padding: .65rem .75rem;
        margin-top: .45rem;
    }}
    .stApp:has(.user-guide-marker) .ug-panel-label {{
        font-size: .72rem;
        text-transform: uppercase;
        letter-spacing: .04em;
        color: {muted};
        margin-bottom: .25rem;
    }}
    .stApp:has(.user-guide-marker) .ug-panel-value {{
        color: {text};
        font-size: .88rem;
    }}
    .stApp:has(.user-guide-marker) .ug-btn {{
        display: inline-block;
        border-radius: 8px;
        padding: .35rem .75rem;
        font-size: .82rem;
        font-weight: 600;
        margin-top: .35rem;
        margin-right: .35rem;
    }}
    .stApp:has(.user-guide-marker) .ug-btn-primary {{
        background: {accent};
        color: #fff;
    }}
    .stApp:has(.user-guide-marker) .ug-btn-secondary {{
        border: 1px solid {border};
        color: {text};
        background: transparent;
    }}
    .stApp:has(.user-guide-marker) .ug-highlight {{
        outline: 2px solid {accent};
        outline-offset: 2px;
        border-radius: 8px;
    }}
    .stApp:has(.user-guide-marker) .ug-flow {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: .35rem .5rem;
        margin-top: .35rem;
    }}
    .stApp:has(.user-guide-marker) .ug-flow-box {{
        border: 1px solid {border};
        border-radius: 8px;
        padding: .35rem .55rem;
        font-size: .78rem;
        color: {text};
        background: {surface};
    }}
    .stApp:has(.user-guide-marker) .ug-flow-arrow {{
        color: {accent};
        font-weight: 700;
    }}
    .stApp:has(.user-guide-marker) .ug-tip {{
        border-left: 3px solid {accent};
        padding: .55rem .75rem;
        background: {accent_soft};
        border-radius: 0 8px 8px 0;
        color: {text};
        font-size: .88rem;
        margin: .5rem 0;
    }}
    .stApp:has(.user-guide-marker) .ug-warn {{
        border-left: 3px solid {warn};
        padding: .55rem .75rem;
        background: rgba(251, 191, 36, .12);
        border-radius: 0 8px 8px 0;
        color: {text};
        font-size: .88rem;
        margin: .5rem 0;
    }}
    .stApp:has(.user-guide-marker) .ug-status {{
        display: inline-block;
        border-radius: 999px;
        padding: .15rem .55rem;
        font-size: .74rem;
        font-weight: 650;
        margin-right: .35rem;
    }}
    .stApp:has(.user-guide-marker) .ug-status-ready {{
        background: rgba(74, 222, 128, .15);
        color: {success};
    }}
    .stApp:has(.user-guide-marker) .ug-status-warn {{
        background: rgba(251, 191, 36, .15);
        color: {warn};
    }}
    .stApp:has(.user-guide-marker) .ug-status-stop {{
        background: rgba(248, 113, 113, .15);
        color: {danger};
    }}
    .stApp:has(.user-guide-marker) .ug-grid-2 {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: .55rem;
    }}
    @media (max-width: 720px) {{
        .stApp:has(.user-guide-marker) .ug-grid-2 {{
            grid-template-columns: 1fr;
        }}
    }}
    """


def sidebar_help_button_css(theme: str = "Dark") -> str:
    is_light = str(theme).lower() == "light"
    border = "var(--rg-border, #b6c7da)" if is_light else "rgba(96, 165, 250, .32)"
    text = "#0f172a" if is_light else "#e8f0f8"
    accent = "#1d4ed8" if is_light else "#60a5fa"
    accent_soft = "rgba(29, 78, 216, .14)" if is_light else "rgba(96, 165, 250, .16)"
    active_bg = "rgba(29, 78, 216, .22)" if is_light else "rgba(37, 99, 235, .28)"

    return f"""
    section[data-testid="stSidebar"] .rg-sidebar-help-marker + div[data-testid="stVerticalBlock"] button {{
        border: 1px solid {border} !important;
        border-radius: 10px !important;
        font-weight: 650 !important;
        letter-spacing: 0.01em !important;
        min-height: 2.35rem !important;
    }}
    section[data-testid="stSidebar"] .rg-sidebar-help-marker + div[data-testid="stVerticalBlock"] button[kind="secondary"] {{
        background: {accent_soft} !important;
        color: {text} !important;
    }}
    section[data-testid="stSidebar"] .rg-sidebar-help-marker + div[data-testid="stVerticalBlock"] button[kind="secondary"]:hover {{
        border-color: {accent} !important;
        color: {accent} !important;
    }}
    section[data-testid="stSidebar"] .rg-sidebar-help-marker + div[data-testid="stVerticalBlock"] button[kind="primary"] {{
        background: {active_bg} !important;
        border-color: {accent} !important;
        color: {accent} !important;
    }}
    """


def _nav_mock(active: str) -> str:
    tabs = [
        "Review",
        "Pending Claims",
        "Reporting",
        "Claim Learning",
        "Admin",
    ]
    pills = []
    for tab in tabs:
        cls = "ug-nav-pill active" if tab == active else "ug-nav-pill"
        pills.append(f'<span class="{cls}">{html.escape(tab)}</span>')
    return f'<div class="ug-nav-mock">{"".join(pills)}</div>'


def _flow(*items: str) -> str:
    parts = []
    for idx, item in enumerate(items):
        if idx:
            parts.append('<span class="ug-flow-arrow">→</span>')
        parts.append(f'<span class="ug-flow-box">{html.escape(item)}</span>')
    return f'<div class="ug-flow">{"".join(parts)}</div>'


def _step(num: int, title: str, body: str, visual: str = "") -> str:
    visual_block = f'<div class="ug-visual">{visual}</div>' if visual else ""
    return f"""
<div class="ug-step">
  <div class="ug-step-num">{num}</div>
  <div>
    <p class="ug-step-title">{html.escape(title)}</p>
    <p class="ug-step-body">{body}</p>
  </div>
  {visual_block}
</div>
"""


def _topic_getting_started() -> str:
    return (
        _step(
            1,
            "Use your dealership email",
            "Sign in with the email your administrator added under <strong>Admin → Personnel</strong>. "
            "If login fails, ask a Manager to confirm your email matches Personnel exactly.",
            visual=(
                '<div class="ug-panel"><div class="ug-panel-label">Sign in</div>'
                '<div class="ug-panel-value">Email · Password · <span class="ug-btn ug-btn-primary">Sign In</span></div></div>'
            ),
        )
        + _step(
            2,
            "Reset your password if needed",
            "On the login screen, open <strong>Forgot your password?</strong>, enter your email, "
            "and use the link once — do not refresh until your new password is saved.",
        )
        + _step(
            3,
            "Open Help from the sidebar",
            "Under the RO GUARD logo, click <strong>Help & User Guide</strong> for step-by-step instructions "
            "with visual cues. Select any main tab above to return to your work.",
            visual=(
                '<div class="ug-panel"><div class="ug-panel-label">Sidebar</div>'
                '<div class="ug-panel-value">RO GUARD · Patent Pending</div>'
                '<span class="ug-btn ug-btn-primary ug-highlight">❓ Help & User Guide</span>'
                '<div class="ug-panel-value" style="margin-top:.45rem">Account · Sign out</div></div>'
            ),
        )
        + _step(
            4,
            "Pick a section from the top bar",
            "Use the horizontal tabs to move between Review, Reporting, Admin, and other tools.",
            visual=_nav_mock("Review"),
        )
        + _step(
            5,
            "Adjust display in the sidebar",
            "Use <strong>Appearance</strong> (Dark/Light) and font size below the divider if text is hard to read.",
        )
        + '<div class="ug-tip"><strong>Tip:</strong> Use sidebar <strong>Refresh data</strong> to reload Supabase data without signing out.</div>'
    )


def _topic_review() -> str:
    return (
        _step(
            1,
            "Open the Review tab",
            "This is where you audit a warranty RO before submission to Stellantis.",
            visual=_nav_mock("Review"),
        )
        + _step(
            2,
            "Enter RO details or scan a PDF",
            "Fill in RO number, VIN, advisor, and job lines — or upload a Dealer Connect RO PDF "
            "to auto-fill fields where supported.",
            visual=(
                '<div class="ug-grid-2">'
                '<div class="ug-panel"><div class="ug-panel-label">RO header</div>'
                '<div class="ug-panel-value">RO # · VIN · Invoice date · Advisor</div></div>'
                '<div class="ug-panel"><div class="ug-panel-label">Jobs</div>'
                '<div class="ug-panel-value">Concern · Cause · Correction · Op code · Times</div></div>'
                '</div>'
            ),
        )
        + _step(
            3,
            "Run the audit",
            "Click <strong>Run Audit + Save Review</strong>. RO Guard checks narratives, time punches, "
            "rentals, recalls, and other compliance rules.",
            visual=(
                '<span class="ug-btn ug-btn-primary ug-highlight">Run Audit + Save Review</span>'
                + '<div style="margin-top:.55rem">'
                + '<span class="ug-status ug-status-ready">READY TO SUBMIT</span>'
                + '<span class="ug-status ug-status-warn">NEEDS REVIEW</span>'
                + '<span class="ug-status ug-status-stop">DO NOT SUBMIT</span>'
                + '</div>'
            ),
        )
        + _step(
            4,
            "Fix hard stops before submitting",
            "Red <strong>DO NOT SUBMIT</strong> items must be corrected in Dealer Connect before you submit the claim. "
            "Yellow warnings should be reviewed but may not block submission.",
        )
        + _step(
            5,
            "Record OEM outcome (optional on Review)",
            "After Stellantis responds, you can mark First-Pass Paid, Rejected, or Paid After Rejection "
            "on the same Review screen — or update later under Reporting → Claim Outcomes.",
        )
        + _flow(
            "Enter RO",
            "Run Audit",
            "Save Review",
            "Submit in Dealer Connect",
            "Record OEM outcome",
        )
    )


def _topic_pending() -> str:
    return (
        _step(
            1,
            "Find open claims",
            "Open <strong>Pending Claims</strong> to see saved reviews that do not yet have an OEM paid/rejected outcome.",
            visual=_nav_mock("Pending Claims"),
        )
        + _step(
            2,
            "Use the queue strip on Review",
            "At the top of Review, the <strong>Open claims queue</strong> shows how many claims still need an outcome. "
            "Click <strong>Open next</strong> to load the next RO in the form.",
            visual=(
                '<div class="ug-panel">'
                '<div class="ug-panel-label">Open claims queue</div>'
                '<div class="ug-panel-value"><strong>3</strong> open claims · '
                '<span class="ug-status ug-status-stop">1 DO NOT SUBMIT</span></div>'
                '<span class="ug-btn ug-btn-primary">Open next</span>'
                '</div>'
            ),
        )
        + _step(
            3,
            "Edit a saved review",
            "From Pending Claims, select a row and open it in Review to update narratives, re-run the audit, "
            "or record the OEM outcome.",
        )
    )


def _topic_outcomes() -> str:
    return (
        _step(
            1,
            "Go to Reporting → Claim Outcomes",
            "Warranty staff use this view to update OEM results after claims are submitted.",
            visual=_nav_mock("Reporting"),
        )
        + _step(
            2,
            "Filter and select a review",
            "Use filters like <strong>Pending only</strong>, <strong>Rejected (Final)</strong>, or "
            "<strong>Paid After Rejection</strong>, then pick the RO from the dropdown.",
        )
        + _step(
            3,
            "Choose one OEM outcome",
            "Select exactly one: Pending, First-Pass Paid, Rejected / Returned, or Paid After Rejection.",
            visual=(
                '<div class="ug-panel"><div class="ug-panel-label">OEM outcome</div>'
                '<div class="ug-panel-value">○ Pending · ○ First-Pass Paid · ○ Rejected · ○ Paid After Rejection</div>'
                '<span class="ug-btn ug-btn-primary">Save outcome</span></div>'
            ),
        )
        + _step(
            4,
            "Add a rejection reason when required",
            "For <strong>Rejected / Returned</strong>, pick a reason from the library (managed in Admin). "
            "For <strong>Paid After Rejection</strong>, enter why the claim was initially declined.",
        )
        + '<div class="ug-tip"><strong>Metrics tip:</strong> '
        "<strong>Paid After Rejection</strong> counts under both "
        "<strong>Paid After Rejection</strong> and <strong>OEM Rejections (Total)</strong> — "
        "not under <strong>Rejected (Final)</strong>.</div>"
    )


def _topic_short_pay() -> str:
    return (
        _step(
            1,
            "When OEM pays less than audited value",
            "On Review or Claim Outcomes, check <strong>OEM paid less than full claim</strong> "
            "when overlapping labor or adjustments reduced payment.",
        )
        + _step(
            2,
            "Enter OEM paid amount",
            "Type what Stellantis actually paid. RO Guard calculates the short-pay difference automatically.",
            visual=(
                '<div class="ug-panel">'
                '<div class="ug-panel-label">Partial payment</div>'
                '<div class="ug-panel-value">☑ OEM paid less than full claim</div>'
                '<div class="ug-panel-value">OEM paid amount: <strong>$1,800.00</strong></div>'
                '<div class="ug-panel-value">Short pay: <strong>$200.00</strong></div>'
                '</div>'
            ),
        )
        + _step(
            3,
            "Explain why (required)",
            "The <strong>Why was it short paid?</strong> field requires at least 10 characters. "
            "Saving is blocked until you provide a clear explanation.",
        )
        + _step(
            4,
            "Review in Reporting → Short Pay",
            "All partial-pay claims appear in the Short Pay report with branded PDF export for meetings and records.",
            visual=_nav_mock("Reporting"),
        )
    )


def _topic_reporting() -> str:
    return (
        _step(
            1,
            "Set your date range",
            "At the top of Reporting, choose the period (defaults to month-to-date). All views respect this filter.",
        )
        + _step(
            2,
            "Pick a reporting view",
            "Use the view selector for Overview, Claim Outcomes, Rejections, Short Pay, Team Performance, or Review Log.",
            visual=(
                '<div class="ug-nav-mock">'
                '<span class="ug-nav-pill">Overview</span>'
                '<span class="ug-nav-pill">Claim Outcomes</span>'
                '<span class="ug-nav-pill active">Short Pay</span>'
                '<span class="ug-nav-pill">Review Log</span>'
                '</div>'
            ),
        )
        + _step(
            3,
            "Download branded PDF reports",
            "Use <strong>Download RO GUARD PDF</strong> on any report table — exports include the ROGUARD watermark "
            "and navy header. CSV is still available if needed.",
            visual=(
                '<span class="ug-btn ug-btn-primary">Download RO GUARD PDF</span>'
                '<span class="ug-btn ug-btn-secondary">Download CSV</span>'
            ),
        )
        + _step(
            4,
            "Refresh if data looks stale",
            "Click <strong>Refresh Reporting</strong> after someone else saves outcomes in another session.",
        )
    )


def _topic_learning() -> str:
    return (
        _step(
            1,
            "Upload paid claims (Claim Learning)",
            "Managers and Warranty Admins can upload paid warranty claim PDFs. RO Guard learns narratives "
            "to coach advisors on Review.",
            visual=_nav_mock("Claim Learning"),
        )
        + _step(
            2,
            "Upload WAM / policy PDFs",
            "Under the <strong>WAM</strong> tab, upload warranty manual sections for audit reference during Review.",
        )
        + _step(
            3,
            "Use coaching on Review",
            "After jobs are filled in, expand paid-claim helpers and narrative gap coaching to compare "
            "your RO to similar paid claims.",
        )
    )


def _topic_admin() -> str:
    return (
        _step(
            1,
            "Manage personnel (Admin)",
            "Add advisors, technicians, warranty admins, and managers. Each person’s <strong>Email</strong> "
            "must match their Supabase login.",
            visual=_nav_mock("Admin"),
        )
        + _step(
            2,
            "Configure dealer settings",
            "Managers set time-punch thresholds, rental warnings, rejection reason library, and other audit rules.",
        )
        + _step(
            3,
            "Scheduled Reports (optional)",
            "Warranty Admins can configure email delivery of report PDFs on a daily/weekly schedule.",
        )
        + '<div class="ug-warn"><strong>Roles:</strong> Advisors can run reviews; Managers and Warranty Admins '
        "can change settings, personnel, and libraries.</div>"
    )


def _topic_troubleshooting() -> str:
    return (
        _step(
            1,
            "Cannot sign in",
            "Confirm your email is on the Personnel list in Admin. Use Forgot password once — "
            "request a new link if the reset page expired.",
        )
        + _step(
            2,
            "Outcome will not save",
            "Run the latest SQL from <code>docs/SUPABASE_SCHEMA.sql</code> in Supabase "
            "(columns like <code>oem_paid_amount</code>, <code>short_pay_reason</code>). "
            "Ask your platform admin if you see column errors.",
        )
        + _step(
            3,
            "Reporting is empty or outdated",
            "Click <strong>Refresh Reporting</strong>. Confirm you are in the correct date range. "
            "Reviews must be saved with <strong>Run Audit + Save Review</strong> first.",
        )
        + _step(
            4,
            "Short-pay reason required error",
            "When partial pay is checked, enter at least 10 characters explaining why OEM paid less. "
            "Uncheck partial pay if OEM paid the full audited amount.",
        )
        + _step(
            5,
            "PDF download shows CSV only in table toolbar",
            "Use the RO GUARD PDF button below the table — the Streamlit dataframe toolbar is hidden "
            "on purpose so all exports use branded PDFs.",
        )
        + '<div class="ug-tip"><strong>Still stuck?</strong> Contact your dealership RO Guard administrator '
        "with the RO number, tab you were on, and the exact error message.</div>"
    )


def clear_user_guide_view() -> None:
    st.session_state["show_user_guide"] = False


def render_sidebar_help_nav(*, theme: str = "Dark") -> None:
    """Help entry point in the sidebar under RO GUARD branding."""
    if "show_user_guide" not in st.session_state:
        st.session_state.show_user_guide = False

    st.markdown(
        f"<style>{sidebar_help_button_css(theme)}</style>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        '<div class="rg-sidebar-help-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    active = bool(st.session_state.get("show_user_guide"))
    if st.sidebar.button(
        "❓  Help & User Guide",
        use_container_width=True,
        key="sidebar_help_btn",
        type="primary" if active else "secondary",
    ):
        st.session_state.show_user_guide = True
        st.rerun()


GUIDE_TOPICS: list[tuple[str, str, callable]] = [
    ("Getting Started", "Sign in, navigation, and display settings", _topic_getting_started),
    ("Run a Review", "Audit an RO before submission", _topic_review),
    ("Pending Claims", "Open queue and editing saved reviews", _topic_pending),
    ("OEM Outcomes", "Record paid, rejected, and paid-after-rejection", _topic_outcomes),
    ("Partial Pay", "Short-pay amounts and required explanations", _topic_short_pay),
    ("Reporting & PDFs", "Views, date filters, and branded exports", _topic_reporting),
    ("Claim Learning & WAM", "Upload claims and manuals for coaching", _topic_learning),
    ("Admin & Roles", "Personnel, settings, and scheduled reports", _topic_admin),
    ("Troubleshooting", "Common errors and fixes", _topic_troubleshooting),
]


def render_user_guide(*, theme: str = "Dark") -> None:
    st.markdown('<div class="user-guide-marker" aria-hidden="true"></div>', unsafe_allow_html=True)
    st.markdown(
        f"<style>{user_guide_css(theme)}</style>",
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="ug-hero">
  <h3>RO Guard User Guide</h3>
  <p>Step-by-step help for warranty reviews, OEM outcomes, reporting, and common issues.
  Pick a topic below — each section includes visual cues for where to click in the app.</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    labels = [label for label, _, _ in GUIDE_TOPICS]
    summaries = {label: summary for label, summary, _ in GUIDE_TOPICS}
    topic = st.radio(
        "Guide topic",
        labels,
        horizontal=True,
        label_visibility="collapsed",
        key="user_guide_topic",
    )
    st.caption(summaries.get(topic, ""))

    render_fn = next(fn for label, _, fn in GUIDE_TOPICS if label == topic)
    st.markdown(render_fn(), unsafe_allow_html=True)

    with st.expander("Quick reference — main tabs"):
        st.markdown(
            """
| Tab | Who uses it | What it does |
|-----|-------------|--------------|
| **Review** | Advisors, warranty staff | Audit ROs before submit; save reviews |
| **Pending Claims** | Warranty staff | Open claims missing OEM outcome |
| **Reporting** | Managers, warranty admins | History, outcomes, Short Pay, PDF exports |
| **Claim Learning** | Managers, warranty admins | Upload paid claims for narrative coaching |
| **Admin** | Managers, warranty admins | Personnel, audit rules, rejection library |
| **Coaching / ROI / POPPS** | Managers | Performance and business metrics |
            """
        )
