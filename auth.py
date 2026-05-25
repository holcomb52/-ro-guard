"""Supabase Auth session helpers for RO Shield."""

from __future__ import annotations

import os
import re
from typing import Callable

import streamlit as st
import streamlit.components.v1 as components

AUTH_SESSION_KEY = "supabase_auth_session"
AUTH_USER_KEY = "supabase_auth_user"
PASSWORD_RECOVERY_KEY = "password_recovery_pending"

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.match(normalize_email(email)))


def app_redirect_url() -> str:
    url = os.getenv("RO_SHIELD_APP_URL", "").strip()
    if not url:
        try:
            url = str(st.secrets.get("RO_SHIELD_APP_URL", "")).strip()
        except Exception:
            url = ""
    if not url:
        url = "http://localhost:8531"
    return url.rstrip("/")


def inject_auth_hash_bridge() -> None:
    """Move Supabase recovery tokens from URL hash into query params for Streamlit."""
    components.html(
        """
        <script>
        (function () {
          try {
            const parent = window.parent;
            const href = parent.location.href;
            if (!href.includes("#")) return;
            const hash = parent.location.hash.startsWith("#")
              ? parent.location.hash.substring(1)
              : parent.location.hash;
            const hashParams = new URLSearchParams(hash);
            if (!hashParams.get("access_token")) return;
            const url = new URL(href.split("#")[0]);
            hashParams.forEach((value, key) => url.searchParams.set(key, value));
            parent.location.replace(url.toString());
          } catch (e) {}
        })();
        </script>
        """,
        height=0,
        width=0,
    )


def get_stored_session() -> dict | None:
    session = st.session_state.get(AUTH_SESSION_KEY)
    return session if isinstance(session, dict) else None


def is_authenticated() -> bool:
    session = get_stored_session()
    user = st.session_state.get(AUTH_USER_KEY)
    return bool(
        session
        and session.get("access_token")
        and session.get("refresh_token")
        and isinstance(user, dict)
        and user.get("email")
    )


def auth_user_email() -> str:
    user = st.session_state.get(AUTH_USER_KEY) or {}
    return str(user.get("email") or "").strip()


def auth_user_id() -> str:
    user = st.session_state.get(AUTH_USER_KEY) or {}
    return str(user.get("id") or "").strip()


def _store_session(session) -> None:
    st.session_state[AUTH_SESSION_KEY] = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
    }


def _store_auth_user(user) -> None:
    st.session_state[AUTH_USER_KEY] = {
        "id": user.id,
        "email": user.email,
        "user_metadata": dict(user.user_metadata or {}),
    }


def clear_auth_session() -> None:
    for key in (AUTH_SESSION_KEY, AUTH_USER_KEY):
        st.session_state.pop(key, None)
    for key in ("current_person_id", "current_person_name", "current_person_role"):
        st.session_state.pop(key, None)


def apply_session_to_client(supabase, session_dict: dict | None) -> None:
    if supabase is None or not session_dict:
        return
    access_token = session_dict.get("access_token")
    refresh_token = session_dict.get("refresh_token")
    if not access_token or not refresh_token:
        return
    try:
        supabase.auth.set_session(access_token, refresh_token)
    except Exception:
        pass


def restore_client_session(supabase) -> bool:
    session_dict = get_stored_session()
    if not session_dict or supabase is None:
        return False
    try:
        response = supabase.auth.set_session(
            session_dict["access_token"],
            session_dict["refresh_token"],
        )
        if response and getattr(response, "user", None):
            _store_auth_user(response.user)
            if getattr(response, "session", None):
                _store_session(response.session)
            return True
        user_response = supabase.auth.get_user(session_dict["access_token"])
        if user_response and getattr(user_response, "user", None):
            _store_auth_user(user_response.user)
            return True
    except Exception:
        clear_auth_session()
    return False


def sign_in_with_password(supabase, email: str, password: str) -> tuple[bool, str]:
    email = str(email or "").strip().lower()
    password = str(password or "")
    if not email or not password:
        return False, "Enter your email and password."
    if supabase is None:
        return False, "Supabase is not configured."

    try:
        response = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
    except Exception as exc:
        message = str(exc)
        lowered = message.lower()
        if "invalid login credentials" in lowered or "invalid email or password" in lowered:
            return False, "Invalid email or password."
        if "email not confirmed" in lowered:
            return False, "Confirm your email address before signing in."
        return False, f"Sign in failed: {message}"

    if not response.session or not response.user:
        return False, "Sign in failed. Check your email and password."

    _store_session(response.session)
    _store_auth_user(response.user)
    apply_session_to_client(supabase, get_stored_session())
    return True, ""


def sign_out(supabase) -> None:
    if supabase is not None:
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
    clear_auth_session()
    st.session_state.pop(PASSWORD_RECOVERY_KEY, None)


def request_password_reset(supabase, email: str) -> tuple[bool, str]:
    email = normalize_email(email)
    if not email:
        return False, "Enter your email address."
    if not is_valid_email(email):
        return False, "Enter a valid email address."
    if supabase is None:
        return False, "Supabase is not configured."

    redirect_to = f"{app_redirect_url()}/"
    try:
        supabase.auth.reset_password_for_email(
            email,
            {"redirect_to": redirect_to},
        )
    except Exception as exc:
        return False, f"Could not send reset email: {exc}"

    return (
        True,
        f"If an account exists for **{email}**, a password reset link has been sent. "
        "Check your inbox (and spam folder).",
    )


def recovery_tokens_from_query() -> dict | None:
    query = st.query_params
    if query.get("type") != "recovery":
        return None
    access_token = query.get("access_token")
    refresh_token = query.get("refresh_token")
    if not access_token or not refresh_token:
        return None
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


def bootstrap_recovery_session(supabase) -> bool:
    """Restore a password-reset session from URL tokens (survives browser refresh)."""
    tokens = recovery_tokens_from_query()
    if tokens:
        st.session_state[AUTH_SESSION_KEY] = tokens
        st.session_state[PASSWORD_RECOVERY_KEY] = True
    elif not st.session_state.get(PASSWORD_RECOVERY_KEY):
        return False

    session_dict = get_stored_session()
    if not session_dict or supabase is None:
        return False

    apply_session_to_client(supabase, session_dict)

    try:
        response = supabase.auth.set_session(
            session_dict["access_token"],
            session_dict["refresh_token"],
        )
        if response and getattr(response, "user", None):
            _store_auth_user(response.user)
            if getattr(response, "session", None):
                _store_session(response.session)
            return True
    except Exception:
        pass

    try:
        user_response = supabase.auth.get_user(session_dict["access_token"])
        if user_response and getattr(user_response, "user", None):
            _store_auth_user(user_response.user)
            apply_session_to_client(supabase, session_dict)
            return True
    except Exception:
        pass

    return bool(st.session_state.get(AUTH_USER_KEY))


def capture_recovery_from_query(supabase) -> bool:
    return bootstrap_recovery_session(supabase)


def is_password_recovery_mode() -> bool:
    if st.session_state.get(PASSWORD_RECOVERY_KEY):
        return True
    return recovery_tokens_from_query() is not None


def ensure_auth_client_ready(supabase) -> bool:
    if is_authenticated():
        apply_session_to_client(supabase, get_stored_session())
        return True
    if is_password_recovery_mode():
        return bootstrap_recovery_session(supabase)
    return False


def clear_recovery_query_params() -> None:
    for key in ("type", "access_token", "refresh_token", "expires_in", "token_type"):
        if key in st.query_params:
            del st.query_params[key]


def update_password(supabase, new_password: str) -> tuple[bool, str]:
    if len(new_password) < 8:
        return False, "Password must be at least 8 characters."
    if supabase is None:
        return False, "Supabase is not configured."
    if not ensure_auth_client_ready(supabase):
        return False, "Your reset session expired. Request a new reset link below."
    try:
        response = supabase.auth.update_user({"password": new_password})
        if response and getattr(response, "user", None):
            if getattr(response, "session", None):
                _store_session(response.session)
            _store_auth_user(response.user)
            st.session_state.pop(PASSWORD_RECOVERY_KEY, None)
            clear_recovery_query_params()
            return True, ""
        return False, "Password update failed."
    except Exception as exc:
        return False, f"Password update failed: {exc}"


def _render_recovery_expired_help(supabase) -> None:
    st.error(
        "This password reset link is invalid or has expired. "
        "Reset links are single-use — if you refreshed the page, you may need a new one."
    )
    st.markdown("**Request a new reset link**")
    with st.form("recovery_resend_form"):
        reset_email = st.text_input(
            "Account email",
            placeholder="you@dealership.com",
            key="recovery_resend_email",
        )
        send_reset = st.form_submit_button("Email new reset link", use_container_width=True)
    if send_reset:
        ok, message = request_password_reset(supabase, reset_email)
        if ok:
            st.success(message)
        else:
            st.error(message)
    if st.button("Back to sign in", key="recovery_back_to_login"):
        clear_recovery_query_params()
        st.session_state.pop(PASSWORD_RECOVERY_KEY, None)
        st.rerun()


def lookup_personnel_by_email(supabase, email: str) -> dict | None:
    if supabase is None or not email:
        return None
    try:
        response = (
            supabase.table("personnel")
            .select("id, name, role, email")
            .eq("email", normalize_email(email))
            .eq("active", True)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return rows[0] if rows else None
    except Exception:
        return None


def sync_personnel_identity(supabase) -> None:
    """Map the authenticated user to personnel when email is linked."""
    email = auth_user_email()
    if not email:
        return

    user = st.session_state.get(AUTH_USER_KEY) or {}
    metadata = user.get("user_metadata") or {}
    display_name = str(
        metadata.get("full_name")
        or metadata.get("name")
        or metadata.get("display_name")
        or ""
    ).strip()

    person = lookup_personnel_by_email(supabase, email)
    if person:
        st.session_state.current_person_id = person.get("id")
        st.session_state.current_person_name = str(person.get("name") or display_name or email)
        st.session_state.current_person_role = str(person.get("role") or "")
        return

    st.session_state.current_person_id = None
    st.session_state.current_person_name = display_name or email
    st.session_state.current_person_role = ""


def _mark_login_page() -> None:
    st.markdown('<div class="ro-login-active"></div>', unsafe_allow_html=True)


def _render_login_brand_panel(*, headline: str, lede: str, compact: bool = False) -> None:
    features_html = ""
    if not compact:
        features_html = """
            <div class="login-features">
                <div class="login-feature">
                    <div class="login-feature-icon">🛡</div>
                    <div>
                        <strong>Prevent Claim Rejections</strong>
                        <span>Catch hard stops before submission</span>
                    </div>
                </div>
                <div class="login-feature">
                    <div class="login-feature-icon">📋</div>
                    <div>
                        <strong>Audit-Ready Every Time</strong>
                        <span>Guided review with manual intelligence</span>
                    </div>
                </div>
                <div class="login-feature">
                    <div class="login-feature-icon">📈</div>
                    <div>
                        <strong>Maximize Warranty Recovery</strong>
                        <span>Protect profits and prove ROI</span>
                    </div>
                </div>
            </div>
            <div class="login-strapline">
                <span>Audit Protection · Claim Approval</span>
                <span>Protect Profits · Drive Performance</span>
            </div>
        """

    st.markdown(
        f"""
        <div class="login-brand-panel{' login-brand-panel-compact' if compact else ''}">
            <div class="login-brand-top">
                <div class="login-brand-row">
                    <div class="login-logo-shield" aria-hidden="true">
                        <svg viewBox="0 0 72 82" role="img" aria-label="RO Guard">
                            <path d="M36 4 L66 18 V40 C66 58 52 72 36 78 C20 72 6 58 6 40 V18 Z"
                                  fill="#2563eb" stroke="#1d4ed8" stroke-width="1.5"/>
                            <text x="36" y="46" text-anchor="middle" fill="#ffffff"
                                  font-size="20" font-weight="800" font-family="Arial, sans-serif">RO</text>
                            <path d="M28 52 L34 58 L46 44" fill="none" stroke="#ffffff"
                                  stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </div>
                    <div class="login-brand-text">
                        <div class="login-brand-name">RO GUARD</div>
                        <div class="login-brand-sub">Warranty Software</div>
                    </div>
                </div>
                <div class="login-badge">Patent Pending</div>
            </div>
            <h2 class="login-headline">{headline}</h2>
            <p class="login-lede">{lede}</p>
            {features_html}
            <div class="login-bottom-bar">Control the Claim · Protect the Profit</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_login_page(supabase, *, apply_style: Callable[[str], None]) -> None:
    apply_style("Dark")
    _mark_login_page()
    inject_auth_hash_bridge()

    if recovery_tokens_from_query():
        st.info("Loading your password reset…")
        if bootstrap_recovery_session(supabase):
            st.rerun()
        return

    brand_col, form_col = st.columns([1.05, 0.95], gap="large")
    with brand_col:
        _render_login_brand_panel(
            headline='Smarter Claims. <span>Stronger Profits.</span>',
            lede="Sign in to audit warranty ROs, catch compliance gaps, and protect claim dollars before they leave your store.",
        )

    with form_col:
        st.markdown("#### Sign In")
        st.caption("Use your dealership account to access review, reporting, and admin tools.")

        with st.form("ro_shield_login_form", clear_on_submit=False):
            email = st.text_input("Email", placeholder="you@dealership.com")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign In", type="primary", use_container_width=True)

        if submit:
            ok, error = sign_in_with_password(supabase, email, password)
            if ok:
                sync_personnel_identity(supabase)
                st.rerun()
            st.error(error)

        with st.expander("Forgot your password?"):
            st.caption(
                "We will email you a secure link to reset your password. "
                "Open the link once, set your new password, and **do not refresh** until finished."
            )
            with st.form("ro_shield_forgot_password_form"):
                reset_email = st.text_input(
                    "Account email",
                    placeholder="you@dealership.com",
                    key="forgot_password_email",
                )
                send_reset = st.form_submit_button(
                    "Email reset link",
                    use_container_width=True,
                )
            if send_reset:
                ok, message = request_password_reset(supabase, reset_email)
                if ok:
                    st.success(message)
                else:
                    st.error(message)

    st.markdown(
        """
        <p class="login-footer-note">
            Accounts are created by your administrator. Your login email must match
            the <strong>Email</strong> field on your Personnel record in Admin.
        </p>
        """,
        unsafe_allow_html=True,
    )


def render_password_reset_page(supabase, *, apply_style: Callable[[str], None]) -> None:
    apply_style("Dark")
    _mark_login_page()
    inject_auth_hash_bridge()
    bootstrap_recovery_session(supabase)

    if not ensure_auth_client_ready(supabase):
        brand_col, form_col = st.columns([1.05, 0.95], gap="large")
        with form_col:
            _render_recovery_expired_help(supabase)
        return

    brand_col, form_col = st.columns([1.05, 0.95], gap="large")
    with brand_col:
        _render_login_brand_panel(
            headline='Set a <span>New Password</span>',
            lede="Choose a secure password for your RO Guard account.",
            compact=True,
        )

    with form_col:
        st.markdown("#### Update Password")

        st.info(
            "Stay on this page until your password is saved. "
            "If you refresh before finishing, you may need to request a new reset link."
        )

        with st.form("ro_shield_new_password_form"):
            new_password = st.text_input("New password", type="password")
            confirm_password = st.text_input("Confirm new password", type="password")
            submit = st.form_submit_button("Update password", type="primary", use_container_width=True)

        if submit:
            if new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                ok, error = update_password(supabase, new_password)
                if ok:
                    sync_personnel_identity(supabase)
                    st.success("Password updated. Signing you in…")
                    st.rerun()
                else:
                    st.error(error)


def render_authenticated_sidebar(supabase) -> None:
    name = str(st.session_state.get("current_person_name") or auth_user_email() or "User")
    role = str(st.session_state.get("current_person_role") or "").strip()
    email = auth_user_email()

    st.sidebar.markdown("### Account")
    st.sidebar.markdown(f"**{name}**")
    if role:
        st.sidebar.caption(f"Role: **{role}**")
    elif email:
        st.sidebar.caption(email)
        st.sidebar.caption(
            "No personnel role linked — ask a Manager to add your login email under Admin → Personnel."
        )

    if st.sidebar.button("Sign out", use_container_width=True, key="auth_sign_out_btn"):
        sign_out(supabase)
        st.rerun()
