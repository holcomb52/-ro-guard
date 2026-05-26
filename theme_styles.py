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
    .stApp:has(.ro-login-active) section.main .block-container {
        max-width: 1080px;
        padding-top: 2rem;
        padding-bottom: 2.5rem;
    }
    .stApp:has(.ro-login-active) header[data-testid="stHeader"] {
        background: transparent !important;
    }
    .stApp:has(.ro-login-active) .login-brand-panel {
        position: relative;
        min-height: 100%;
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
        padding: 22px 24px 18px;
        border-bottom: 1px solid #e2e8f0;
    }
    .stApp:has(.ro-login-active) .login-brand-dark {
        padding: 22px 24px 20px;
        background: linear-gradient(180deg, #0b1424 0%, #060d18 100%);
    }
    .stApp:has(.ro-login-active) .login-brand-panel-compact .login-brand-dark {
        padding-bottom: 16px;
    }
    .stApp:has(.ro-login-active) .login-brand-row {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 12px;
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
        margin: 0 0 10px 0;
        font-size: 26px;
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
        margin: 0 0 16px 0;
        color: #cbd5e1 !important;
        font-size: 14px;
        line-height: 1.55;
        max-width: 100%;
    }
    .stApp:has(.ro-login-active) .login-features {
        position: relative;
        z-index: 1;
        display: grid;
        gap: 12px;
        margin-bottom: 18px;
    }
    .stApp:has(.ro-login-active) .login-feature {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 12px 14px;
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
        gap: 8px;
        margin-bottom: 16px;
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
        margin-top: 8px;
        padding: 12px 14px;
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
        margin: 0 0 4px 0;
        font-size: 28px;
        font-weight: 800;
        color: #0f172a !important;
        line-height: 1.1;
    }
    .stApp:has(.ro-login-active) div[data-testid="column"]:has(.login-form-column-marker),
    .stApp:has(.ro-login-active) div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child {
        background: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 18px !important;
        padding: 22px 22px 16px !important;
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
