THEME_CSS = {
    "Dark": """
    .stApp {
        background:
            linear-gradient(rgba(1, 7, 14, .91), rgba(1, 7, 14, .95)),
            radial-gradient(circle at 14% 8%, rgba(0, 114, 255, .32), transparent 28%),
            radial-gradient(circle at 90% 10%, rgba(45, 156, 255, .18), transparent 26%),
            linear-gradient(135deg, #06101d 0%, #02070d 100%);
        color: #f8fbff;
    }
    header[data-testid="stHeader"] { background: rgba(0,0,0,0); }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #071322, #030811) !important;
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
    button[data-baseweb="tab"] {
        color: #d6e8ff !important;
        background-color: rgba(7, 19, 34, .55) !important;
        border: 1px solid rgba(62,150,255,.25) !important;
        border-radius: 10px 10px 0 0 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #ffffff !important;
        background-color: rgba(29, 78, 216, .55) !important;
        border-color: rgba(140, 200, 255, .85) !important;
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
    .stApp:has(.ro-login-active) section[data-testid="stSidebar"] {
        display: none !important;
    }
    .stApp:has(.ro-login-active) section.main .block-container {
        max-width: 520px;
        padding-top: 2.5rem;
        padding-bottom: 3rem;
    }
    .stApp:has(.ro-login-active) header[data-testid="stHeader"] {
        background: transparent !important;
    }
    .stApp:has(.ro-login-active) .login-hero {
        text-align: center;
        padding: 36px 28px 28px;
        margin-bottom: 8px;
        border-radius: 24px;
        background:
            linear-gradient(145deg, rgba(15, 40, 78, 0.55), rgba(4, 12, 24, 0.82));
        border: 1px solid rgba(96, 165, 250, 0.28);
        box-shadow:
            0 28px 70px rgba(0, 0, 0, 0.42),
            inset 0 1px 0 rgba(255, 255, 255, 0.06);
        position: relative;
        overflow: hidden;
    }
    .stApp:has(.ro-login-active) .login-hero::before {
        content: "";
        position: absolute;
        inset: -40% -20% auto -20%;
        height: 180px;
        background: radial-gradient(circle, rgba(59, 130, 246, 0.35), transparent 68%);
        pointer-events: none;
    }
    .stApp:has(.ro-login-active) .login-hero::after {
        content: "";
        position: absolute;
        inset: auto -30% -50% -30%;
        height: 160px;
        background: radial-gradient(circle, rgba(37, 99, 235, 0.18), transparent 70%);
        pointer-events: none;
    }
    .stApp:has(.ro-login-active) .login-badge {
        display: inline-block;
        position: relative;
        z-index: 1;
        margin-bottom: 14px;
        padding: 6px 14px;
        border-radius: 999px;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #bfdbfe !important;
        background: rgba(29, 78, 216, 0.22);
        border: 1px solid rgba(147, 197, 253, 0.35);
    }
    .stApp:has(.ro-login-active) .login-shield-wrap {
        position: relative;
        z-index: 1;
        width: 84px;
        height: 84px;
        margin: 0 auto 16px;
        display: grid;
        place-items: center;
        border-radius: 22px;
        background: linear-gradient(145deg, rgba(37, 99, 235, 0.35), rgba(15, 23, 42, 0.85));
        border: 1px solid rgba(147, 197, 253, 0.45);
        box-shadow: 0 12px 32px rgba(37, 99, 235, 0.28);
        font-size: 42px;
        line-height: 1;
    }
    .stApp:has(.ro-login-active) .login-hero h1 {
        position: relative;
        z-index: 1;
        margin: 0 0 8px 0;
        font-size: 42px;
        font-weight: 800;
        letter-spacing: 0.03em;
        color: #f8fbff !important;
        text-shadow: 0 4px 24px rgba(59, 130, 246, 0.35);
    }
    .stApp:has(.ro-login-active) .login-tagline {
        position: relative;
        z-index: 1;
        margin: 0 0 18px 0;
        color: #c7ddff !important;
        font-size: 16px;
        line-height: 1.5;
    }
    .stApp:has(.ro-login-active) .login-pills {
        position: relative;
        z-index: 1;
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 8px;
    }
    .stApp:has(.ro-login-active) .login-pills span {
        padding: 7px 12px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        color: #e0efff !important;
        background: rgba(8, 22, 42, 0.72);
        border: 1px solid rgba(96, 165, 250, 0.22);
    }
    .stApp:has(.ro-login-active) section[data-testid="stForm"] {
        background: linear-gradient(160deg, rgba(10, 26, 48, 0.92), rgba(5, 14, 28, 0.96));
        border: 1px solid rgba(96, 165, 250, 0.32);
        border-radius: 20px;
        padding: 26px 28px 18px;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.38);
    }
    .stApp:has(.ro-login-active) section[data-testid="stForm"] + div {
        margin-top: 8px;
    }
    .stApp:has(.ro-login-active) details[data-testid="stExpander"] {
        margin-top: 14px;
        background: rgba(8, 20, 38, 0.72);
        border: 1px solid rgba(96, 165, 250, 0.22);
        border-radius: 14px;
        overflow: hidden;
    }
    .stApp:has(.ro-login-active) details[data-testid="stExpander"] summary {
        color: #dbeafe !important;
        font-weight: 600;
    }
    .stApp:has(.ro-login-active) div[data-testid="stCaptionContainer"] p {
        text-align: center;
        color: #94a3b8 !important;
        font-size: 13px;
        line-height: 1.55;
        max-width: 420px;
        margin: 18px auto 0;
    }
    .stApp:has(.ro-login-active) .login-footer-note {
        text-align: center;
        margin-top: 18px;
        color: #94a3b8 !important;
        font-size: 13px;
        line-height: 1.55;
    }
    """,
    "Light": """
    .stApp {
        background: linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
        color: #0f172a;
    }
    header[data-testid="stHeader"] { background: rgba(255,255,255,0.75); }
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #ffffff, #f1f5f9) !important;
        border-right: 1px solid #cbd5e1;
    }
    .stApp, .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
        color: #0f172a;
    }
    .hero {
        padding: 28px 30px;
        border-radius: 22px;
        background: linear-gradient(135deg, #ffffff, #eef4ff);
        border: 1px solid #93c5fd;
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
        margin-bottom: 22px;
    }
    .hero h1 { margin: 0; font-size: 48px; letter-spacing: .5px; }
    .hero p { color: #334155 !important; font-size: 16px; }
    .section-card {
        padding: 18px;
        border-radius: 18px;
        background: #ffffff;
        border: 1px solid #dbeafe;
        margin: 10px 0 18px 0;
    }
    textarea, input, div[data-baseweb="input"] input {
        color: #0f172a !important;
        -webkit-text-fill-color: #0f172a !important;
        background-color: #ffffff !important;
        border: 1px solid #94a3b8 !important;
    }
    textarea::placeholder, input::placeholder { color: #64748b !important; opacity: 1 !important; }
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        border: 1px solid #94a3b8 !important;
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
        background-color: #ffffff !important;
        border: 1px solid #94a3b8 !important;
    }
    div[data-baseweb="popover"] li,
    li[role="option"] {
        color: #0f172a !important;
        background-color: #ffffff !important;
    }
    div[data-baseweb="popover"] li:hover,
    li[role="option"]:hover,
    li[role="option"][aria-selected="true"],
    div[data-baseweb="popover"] li[aria-selected="true"] {
        background-color: #eff6ff !important;
        color: #1d4ed8 !important;
    }
    section[data-testid="stFileUploaderDropzone"] {
        background-color: #ffffff !important;
        border: 1px dashed #64748b !important;
    }
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #dbeafe;
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
        background: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #64748b !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        min-height: 2.6rem !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.12) !important;
    }
    div.stButton > button:hover,
    button[kind="secondary"]:hover,
    button[data-testid="stBaseButton-secondary"]:hover {
        background: #eff6ff !important;
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
        background: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #64748b !important;
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
        background: #eff6ff !important;
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
        background-color: #ffffff !important;
        border-color: #64748b !important;
    }
    button[data-baseweb="tab"] {
        color: #334155 !important;
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 10px 10px 0 0 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #1d4ed8 !important;
        background-color: #eff6ff !important;
        border-color: #2563eb !important;
        font-weight: 700 !important;
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
        background: linear-gradient(135deg, #ffffff, #eef4ff);
        border: 1px solid #93c5fd;
        box-shadow: 0 10px 28px rgba(15, 23, 42, 0.08);
        margin-bottom: 18px;
    }
    .reporting-hero h2 { margin: 0 0 6px 0; font-size: 28px; color: #0f172a !important; }
    .reporting-hero p { margin: 0; color: #334155 !important; font-size: 15px; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(255, 255, 255, 0.88) !important;
        border-color: #dbeafe !important;
        border-radius: 16px !important;
        padding: 10px 14px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05) !important;
    }
    div[data-testid="stDataFrame"] {
        background: #ffffff !important;
        border: 1px solid #dbeafe !important;
        border-radius: 14px !important;
        padding: 4px !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05) !important;
    }
    div[data-testid="stImage"] {
        background: #ffffff;
        border: 1px solid #dbeafe;
        border-radius: 14px;
        padding: 8px;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
    }
    div[data-testid="stDateInput"] > div,
    div[data-testid="stDateInput"] input {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #94a3b8 !important;
    }
    """,
}
