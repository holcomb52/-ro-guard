"""Deployment and Streamlit secrets — app owner login only (RO_SHIELD_OWNER_EMAIL)."""

from __future__ import annotations

import os

import streamlit as st

REQUIRED_APP_SECRETS = (
    ("SUPABASE_URL", "Supabase project URL — required for all data"),
    ("SUPABASE_KEY", "Supabase anon/publishable key — required for all data"),
)

OPTIONAL_APP_SECRETS = (
    ("RO_SHIELD_APP_URL", "Live app URL for password-reset links"),
    ("RO_SHIELD_OWNER_EMAIL", "Owner login(s) that see Manage app and this page (comma-separated)"),
)

REPORT_SMTP_SECRETS = (
    ("REPORT_SMTP_HOST", "SMTP server for scheduled Reporting emails"),
    ("REPORT_SMTP_PORT", "SMTP port (usually 587)"),
    ("REPORT_SMTP_USER", "SMTP username"),
    ("REPORT_SMTP_PASSWORD", "SMTP password or app password"),
    ("REPORT_SMTP_FROM", "From address (optional)"),
    ("REPORT_SMTP_USE_TLS", "Use TLS — true/false (optional)"),
)


def _read_secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(name, "") or "").strip()
    except Exception:
        return ""


def secret_is_configured(name: str) -> bool:
    return bool(_read_secret(name))


def owner_emails() -> set[str]:
    from auth import normalize_email

    raw = _read_secret("RO_SHIELD_OWNER_EMAIL")
    return {normalize_email(part) for part in raw.replace(";", ",").split(",") if part.strip()}


def user_can_view_deployment() -> bool:
    """True only for logins listed in RO_SHIELD_OWNER_EMAIL."""
    from auth import auth_user_email, normalize_email

    owners = owner_emails()
    if not owners:
        return False
    email = normalize_email(auth_user_email())
    return bool(email and email in owners)


def _render_secret_rows(items: tuple[tuple[str, str], ...]) -> None:
    for name, description in items:
        ok = secret_is_configured(name)
        icon = "✅" if ok else "⬜"
        st.markdown(f"{icon} **`{name}`** — {description}")


def _report_smtp_status() -> tuple[bool, str]:
    from scheduled_reports import smtp_config_status

    return smtp_config_status()


def render_admin_profile_deployment_sidebar() -> None:
    if not user_can_view_deployment():
        return
    from auth import auth_user_email

    with st.sidebar.expander("Deployment & secrets", expanded=False):
        st.caption(f"App owner — {auth_user_email()}")
        missing_required = [name for name, _ in REQUIRED_APP_SECRETS if not secret_is_configured(name)]
        if missing_required:
            st.warning(f"Missing: {', '.join(missing_required)}")
        else:
            st.success("Core Supabase secrets are set.")
        smtp_ok, _ = _report_smtp_status()
        if smtp_ok:
            st.caption("Report SMTP: configured")
        else:
            st.caption("Report SMTP: not configured")
        st.link_button(
            "Open Streamlit Cloud",
            "https://share.streamlit.io/",
            use_container_width=True,
            help="Manage app → Settings → Secrets (use your Streamlit owner login)",
        )
        st.caption(
            "Lower-right **Manage app** appears only for this owner login. "
            "You must also be signed into Streamlit Cloud in this browser."
        )
        st.caption("Or use **Admin → Deployment & Secrets**.")


def render_deployment_secrets_admin() -> None:
    if not user_can_view_deployment():
        return

    st.header("Deployment & Secrets")
    st.caption(
        "Streamlit Cloud stores secrets outside the app. This page shows what is configured "
        "and how to open the Secrets editor."
    )

    from auth import auth_user_email

    email = auth_user_email()
    owners = owner_emails()

    st.subheader("Your access")
    st.markdown(f"**Signed in as:** {email or '—'}")
    st.info(
        "**Manage app** (lower-right) requires **both**:\n"
        "1. RO Guard login as an address in `RO_SHIELD_OWNER_EMAIL`\n"
        "2. The same browser session signed into [Streamlit Cloud](https://share.streamlit.io/) "
        "as the GitHub owner who deployed this app"
    )
    st.link_button(
        "Open Streamlit Cloud workspace",
        "https://share.streamlit.io/",
        help="Open your app → overflow menu → Settings → Secrets",
    )
    if owners:
        st.caption(f"`RO_SHIELD_OWNER_EMAIL`: {', '.join(sorted(owners))}")

    st.divider()
    st.subheader("Open Streamlit Secrets")
    st.markdown(
        """
1. On the live app (`ro-guard.streamlit.app`), click **Manage app** (lower-right).
2. Go to **Settings** → **Secrets**.
3. Paste or update keys, then **Save** (the app reboots).

See `docs/DEPLOY_STREAMLIT.md` for the full template.
        """
    )

    st.subheader("App secrets status")
    st.markdown("**Required**")
    _render_secret_rows(REQUIRED_APP_SECRETS)
    st.markdown("**Optional — auth & deployment**")
    _render_secret_rows(OPTIONAL_APP_SECRETS)
    st.markdown("**Optional — scheduled Reporting emails**")
    _render_secret_rows(REPORT_SMTP_SECRETS)
    smtp_ok, smtp_message = _report_smtp_status()
    if smtp_ok:
        st.success(smtp_message)
    else:
        st.caption(smtp_message)

    st.divider()
    st.subheader("Secrets template (copy into Streamlit)")
    st.code(
        '\n'.join(
            [
                'SUPABASE_URL = "https://your-project.supabase.co"',
                'SUPABASE_KEY = "your_publishable_key"',
                'RO_SHIELD_APP_URL = "https://ro-guard.streamlit.app"',
                'RO_SHIELD_OWNER_EMAIL = "holcomb52@yahoo.com"',
                "",
                "# Scheduled Reporting PDF emails (optional)",
                'REPORT_SMTP_HOST = "smtp.office365.com"',
                "REPORT_SMTP_PORT = 587",
                'REPORT_SMTP_USER = "reports@dealership.com"',
                'REPORT_SMTP_PASSWORD = "your_app_password"',
                'REPORT_SMTP_FROM = "reports@dealership.com"',
                "REPORT_SMTP_USE_TLS = true",
            ]
        ),
        language="toml",
    )

    st.subheader("GitHub Actions secrets")
    st.caption(
        "Automatic scheduled emails also need the same Supabase and `REPORT_SMTP_*` keys in "
        "GitHub → **Settings** → **Secrets and variables** → **Actions**. "
        "See `docs/SCHEDULED_REPORTS.md`."
    )

    st.subheader("Supabase Auth SMTP")
    st.caption(
        "Password-reset email is configured in **Supabase** (not Streamlit). "
        "See `docs/SUPABASE_SMTP.md`."
    )
