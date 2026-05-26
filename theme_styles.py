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
        padding: 14px;
        min-height: 112px;
    }
    div[data-testid="stMetricValue"] {
        white-space: nowrap !important;
        overflow: visible !important;
        text-overflow: clip !important;
        font-size: 1.9rem !important;
        color: #ffffff !important;
    }
    div[data-testid="stMetricLabel"] {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        color: #d6e8ff !important;
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
        border-radius: 0 !important;
        box-shadow: none !important;
        padding: 0.62rem 0.95rem 0.72rem !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em;
        min-height: auto !important;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"]:hover {
        color: #e2e8f0 !important;
        background: transparent !important;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
        color: #f8fbff !important;
        background: transparent !important;
        border: none !important;
        font-weight: 700 !important;
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
        padding: 14px;
        min-height: 112px;
    }
    div[data-testid="stMetricValue"] {
        white-space: nowrap !important;
        overflow: visible !important;
        text-overflow: clip !important;
        font-size: 1.9rem !important;
        color: #0f172a !important;
    }
    div[data-testid="stMetricLabel"] {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        color: #334155 !important;
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
        border-radius: 0 !important;
        box-shadow: none !important;
        padding: 0.62rem 0.95rem 0.72rem !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em;
        min-height: auto !important;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"]:hover {
        color: #334155 !important;
        background: transparent !important;
    }
    div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
        color: #1d4ed8 !important;
        background: transparent !important;
        border: none !important;
        font-weight: 700 !important;
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
    details[data-testid="stExpander"] {
        background: var(--rg-surface) !important;
        border: 1px solid var(--rg-border) !important;
        border-radius: 14px !important;
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
