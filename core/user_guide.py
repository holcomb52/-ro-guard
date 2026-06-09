"""Simple in-app help — visually separate from the real app toolbar."""

from __future__ import annotations

import html

import streamlit as st

# Short labels for the sidebar dropdown (grade-school simple).
GUIDE_TOPICS: list[tuple[str, str, str]] = [
    (
        "first_time",
        "1. First time here",
        "How to sign in and find your way around.",
    ),
    (
        "check_claim",
        "2. Check a claim",
        "Fill in the RO, run the audit, save it.",
    ),
    (
        "record_result",
        "3. Record paid or rejected",
        "Tell RO Guard what Stellantis did.",
    ),
    (
        "reports",
        "4. Get a report",
        "Look up history and download a PDF.",
    ),
    (
        "stuck",
        "5. Something wrong?",
        "Fix common problems fast.",
    ),
]

_TOPIC_BY_ID = {topic_id: (label, summary, topic_id) for topic_id, label, summary in GUIDE_TOPICS}


def user_guide_css(theme: str = "Dark") -> str:
    is_light = str(theme).lower() == "light"
    # Warm amber "instruction booklet" — not the app's blue toolbar look.
    paper = "#fffbeb" if is_light else "#1a1408"
    paper_edge = "#f59e0b" if is_light else "#d97706"
    ink = "#422006" if is_light else "#fef3c7"
    ink_soft = "#78350f" if is_light else "#fcd34d"
    step_bg = "#ffffff" if is_light else "#241a0a"
    step_border = "#fde68a" if is_light else "#92400e"
    where_bg = "#ecfdf5" if is_light else "#052e16"
    where_border = "#10b981" if is_light else "#34d399"
    where_text = "#065f46" if is_light else "#a7f3d0"

    return f"""
    /* Hide real app toolbar while reading help (it looked the same as guide tabs). */
    .stApp:has(.user-guide-mode) .rg-section-nav-marker,
    .stApp:has(.user-guide-mode) .rg-section-nav-marker + div[data-testid="stRadio"] {{
        display: none !important;
    }}

    .stApp:has(.user-guide-mode) .ug-shell {{
        border: 3px solid {paper_edge};
        background: {paper};
        border-radius: 20px;
        padding: 0;
        margin: 0 0 1rem 0;
        overflow: hidden;
        box-shadow: 0 16px 40px rgba(245, 158, 11, 0.18);
    }}
    .stApp:has(.user-guide-mode) .ug-banner {{
        background: linear-gradient(90deg, {paper_edge} 0%, #fbbf24 100%);
        color: #1c1917;
        padding: 1rem 1.25rem;
        text-align: center;
    }}
    .stApp:has(.user-guide-mode) .ug-banner-title {{
        font-size: 1.65rem;
        font-weight: 900;
        letter-spacing: 0.04em;
        margin: 0;
        text-transform: uppercase;
    }}
    .stApp:has(.user-guide-mode) .ug-banner-sub {{
        margin: .35rem 0 0;
        font-size: 1rem;
        font-weight: 650;
        color: #292524;
    }}
    .stApp:has(.user-guide-mode) .ug-body {{
        padding: 1.1rem 1.25rem 1.35rem;
    }}
    .stApp:has(.user-guide-mode) .ug-topic-title {{
        font-size: 1.35rem;
        font-weight: 800;
        color: {ink};
        margin: 0 0 .25rem;
    }}
    .stApp:has(.user-guide-mode) .ug-topic-lede {{
        color: {ink_soft};
        font-size: 1.02rem;
        margin: 0 0 1rem;
        line-height: 1.5;
    }}
    .stApp:has(.user-guide-mode) .ug-step {{
        display: grid;
        grid-template-columns: 3rem 1fr;
        gap: .75rem 1rem;
        background: {step_bg};
        border: 2px solid {step_border};
        border-radius: 14px;
        padding: 1rem 1.1rem;
        margin: .75rem 0;
    }}
    .stApp:has(.user-guide-mode) .ug-step-num {{
        width: 3rem;
        height: 3rem;
        border-radius: 999px;
        background: {paper_edge};
        color: #1c1917;
        font-weight: 900;
        font-size: 1.35rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    .stApp:has(.user-guide-mode) .ug-step-title {{
        margin: 0 0 .35rem;
        font-size: 1.12rem;
        font-weight: 800;
        color: {ink};
        line-height: 1.3;
    }}
    .stApp:has(.user-guide-mode) .ug-step-body {{
        margin: 0;
        font-size: 1.02rem;
        line-height: 1.55;
        color: {ink_soft};
    }}
    .stApp:has(.user-guide-mode) .ug-where {{
        grid-column: 1 / -1;
        border: 2px dashed {where_border};
        background: {where_bg};
        border-radius: 12px;
        padding: .75rem .9rem;
        margin-top: .15rem;
    }}
    .stApp:has(.user-guide-mode) .ug-where-label {{
        font-size: .72rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: {where_text};
        margin-bottom: .35rem;
    }}
    .stApp:has(.user-guide-mode) .ug-where-text {{
        font-size: 1rem;
        font-weight: 700;
        color: {where_text};
        line-height: 1.45;
    }}
    .stApp:has(.user-guide-mode) .ug-note {{
        border-radius: 12px;
        padding: .75rem 1rem;
        margin-top: .75rem;
        font-size: .98rem;
        line-height: 1.5;
        color: {ink};
        background: {"rgba(254, 243, 199, 0.65)" if is_light else "rgba(146, 64, 14, 0.35)"};
        border: 1px solid {step_border};
    }}
    .stApp:has(.user-guide-mode) div[data-testid="stSelectbox"] label {{
        font-size: 1rem !important;
        font-weight: 700 !important;
        color: {ink} !important;
    }}
    """


def sidebar_help_button_css(theme: str = "Dark") -> str:
    is_light = str(theme).lower() == "light"
    border = "rgba(245, 158, 11, 0.55)" if not is_light else "rgba(217, 119, 6, 0.45)"
    text = "#fef3c7" if not is_light else "#78350f"
    active_bg = "rgba(245, 158, 11, 0.28)" if not is_light else "rgba(251, 191, 36, 0.35)"

    return f"""
    section[data-testid="stSidebar"] .rg-sidebar-help-marker + div[data-testid="stVerticalBlock"] button {{
        border: 2px solid {border} !important;
        border-radius: 10px !important;
        font-weight: 750 !important;
        min-height: 2.5rem !important;
    }}
    section[data-testid="stSidebar"] .rg-sidebar-help-marker + div[data-testid="stVerticalBlock"] button[kind="secondary"] {{
        background: rgba(245, 158, 11, 0.12) !important;
        color: {text} !important;
    }}
    section[data-testid="stSidebar"] .rg-sidebar-help-marker + div[data-testid="stVerticalBlock"] button[kind="primary"] {{
        background: {active_bg} !important;
        border-color: #fbbf24 !important;
        color: #fef3c7 !important;
    }}
    section[data-testid="stSidebar"] .ug-sidebar-topic-label {{
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        color: #fcd34d;
        margin: 0.35rem 0 0.15rem;
    }}
    """


def clear_user_guide_view() -> None:
    st.session_state["show_user_guide"] = False


def _where(text: str) -> str:
    return (
        '<div class="ug-where">'
        '<div class="ug-where-label">Where to click in the real app</div>'
        f'<div class="ug-where-text">{text}</div>'
        "</div>"
    )


def _step(num: int, title: str, body: str, where: str = "") -> str:
    where_block = _where(where) if where else ""
    return f"""
<div class="ug-step">
  <div class="ug-step-num">{num}</div>
  <div>
    <p class="ug-step-title">{html.escape(title)}</p>
    <p class="ug-step-body">{body}</p>
  </div>
  {where_block}
</div>
"""


def _topic_first_time() -> str:
    return (
        _step(
            1,
            "Sign in",
            "Type the email and password your manager gave you. Tap <b>Sign In</b>.",
            where="Login screen → Email box → Password box → blue Sign In button",
        )
        + _step(
            2,
            "Find Help",
            "Help lives on the <b>left side</b>, under the RO GUARD logo. "
            "You are reading Help right now.",
            where="Left sidebar → orange Help & User Guide button (under Patent Pending)",
        )
        + _step(
            3,
            "Go to your work",
            "When you are done reading, tap a button below to jump back — "
            "or pick a topic from the drop-down list.",
        )
        + '<div class="ug-note"><b>Remember:</b> This yellow page is only for reading. '
        "It is not the same as the blue buttons at the top of the app.</div>"
    )


def _topic_check_claim() -> str:
    return (
        _step(
            1,
            "Open Review",
            "Review is where you check a repair order <b>before</b> you send the claim to Stellantis.",
            where="Top bar → Review",
        )
        + _step(
            2,
            "Fill in the RO",
            "Type the RO number, VIN, and job story (concern, cause, correction). "
            "You can also upload a PDF to fill some boxes for you.",
        )
        + _step(
            3,
            "Run the audit and save",
            "Tap the big button <b>Run Audit + Save Review</b>. "
            "Fix anything red that says DO NOT SUBMIT. Then submit in Dealer Connect.",
            where="Bottom of Review page → Run Audit + Save Review",
        )
    )


def _topic_record_result() -> str:
    return (
        _step(
            1,
            "Open Reporting",
            "After Stellantis pays or rejects the claim, open Reporting.",
            where="Top bar → Reporting",
        )
        + _step(
            2,
            "Open Claim Outcomes",
            "Pick the RO from the list. Choose one answer: Paid, Rejected, or Paid After Rejection.",
            where="Reporting → Claim Outcomes → pick RO → Save outcome",
        )
        + _step(
            3,
            "If they paid less money",
            "Check the box that says OEM paid less. Type how much they paid. "
            "Write a short note about why (required).",
        )
        + '<div class="ug-note"><b>Paid on the first try?</b> Choose First-Pass Paid. '
        "<b>Rejected and never paid?</b> Choose Rejected.</div>"
    )


def _topic_reports() -> str:
    return (
        _step(
            1,
            "Pick dates",
            "Open Reporting. Choose the dates you want to see.",
            where="Top bar → Reporting → date picker at the top",
        )
        + _step(
            2,
            "Download a PDF",
            "Scroll to a table. Tap <b>Download RO GUARD PDF</b>. "
            "That makes a branded report you can email or print.",
            where="Any report table → Download RO GUARD PDF button",
        )
    )


def _topic_stuck() -> str:
    return (
        _step(
            1,
            "Can't sign in?",
            "Ask your manager to check that your email is listed under Admin → Personnel. "
            "Use Forgot password on the login screen if you need a new password.",
        )
        + _step(
            2,
            "Save won't work?",
            "Read the red error message on screen. "
            "Short-pay claims need a written reason (at least a short sentence).",
        )
        + _step(
            3,
            "Still stuck?",
            "Tell your manager the RO number and copy the error message. "
            "They can reach your RO Guard admin.",
        )
    )


_TOPIC_RENDERERS = {
    "first_time": _topic_first_time,
    "check_claim": _topic_check_claim,
    "record_result": _topic_record_result,
    "reports": _topic_reports,
    "stuck": _topic_stuck,
}


def render_sidebar_help_nav(*, theme: str = "Dark") -> None:
    if "show_user_guide" not in st.session_state:
        st.session_state.show_user_guide = False
    if "user_guide_topic" not in st.session_state:
        st.session_state.user_guide_topic = GUIDE_TOPICS[0][0]

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
        "📖  Help (simple guide)",
        use_container_width=True,
        key="sidebar_help_btn",
        type="primary" if active else "secondary",
    ):
        st.session_state.show_user_guide = True
        st.rerun()

    if st.session_state.get("show_user_guide"):
        st.sidebar.markdown(
            '<p class="ug-sidebar-topic-label">Help topic</p>',
            unsafe_allow_html=True,
        )
        topic_labels = {topic_id: label for topic_id, label, _ in GUIDE_TOPICS}
        st.sidebar.selectbox(
            "Help topic",
            options=[t[0] for t in GUIDE_TOPICS],
            format_func=lambda tid: topic_labels.get(tid, tid),
            key="user_guide_topic",
            label_visibility="collapsed",
        )


def render_user_guide(*, theme: str = "Dark") -> None:
    st.markdown(
        '<div class="user-guide-mode" aria-hidden="true"></div>'
        '<div class="user-guide-marker" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"<style>{user_guide_css(theme)}</style>", unsafe_allow_html=True)

    topic_id = str(st.session_state.get("user_guide_topic") or GUIDE_TOPICS[0][0])
    topic_row = next((t for t in GUIDE_TOPICS if t[0] == topic_id), GUIDE_TOPICS[0])
    _, topic_label, topic_summary = topic_row

    render_fn = _TOPIC_RENDERERS.get(topic_id, _topic_first_time)
    steps_html = render_fn()

    st.markdown(
        f"""
<div class="ug-shell">
  <div class="ug-banner">
    <p class="ug-banner-title">📖 Help Page</p>
    <p class="ug-banner-sub">Read here. Work somewhere else. This page is not the app toolbar.</p>
  </div>
  <div class="ug-body">
    <p class="ug-topic-title">{html.escape(topic_label)}</p>
    <p class="ug-topic-lede">{html.escape(topic_summary)}</p>
    {steps_html}
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("#### Back to work")
    st.caption("Tap a button to close Help and open that part of the app.")
    back_cols = st.columns(4)
    jumps = [
        ("Review", "check_claim"),
        ("Reporting", "reports"),
        ("Pending Claims", "check_claim"),
        ("Admin", "first_time"),
    ]
    for col, (section, topic_hint) in zip(back_cols, jumps):
        with col:
            if st.button(section, use_container_width=True, key=f"ug_back_{section}"):
                st.session_state.show_user_guide = False
                st.session_state.main_section_nav = section
                if topic_hint:
                    st.session_state.user_guide_topic = topic_hint
                st.rerun()

    if st.button("Close Help", type="primary", key="ug_close_help"):
        clear_user_guide_view()
        st.rerun()
