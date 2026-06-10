"""Supabase credentials and client setup for RO Guard."""

from __future__ import annotations

import os
from pathlib import Path

# Cursor IDE / VPN proxy env can break outbound Supabase HTTPS from local Streamlit.
for _proxy_var in (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "http_proxy",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "SOCKS_PROXY",
    "SOCKS5_PROXY",
    "socks_proxy",
    "socks5_proxy",
):
    os.environ.pop(_proxy_var, None)

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def load_local_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(_ENV_PATH, override=True)
    except ImportError:
        pass


def load_supabase_credentials() -> tuple[str, str]:
    """Read Supabase URL/key from local `.env`, then Streamlit Cloud secrets."""
    load_local_env()
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_KEY", "").strip()
    try:
        import streamlit as st

        if not url:
            url = str(st.secrets.get("SUPABASE_URL", "")).strip()
        if not key:
            key = str(st.secrets.get("SUPABASE_KEY", "")).strip()
    except Exception:
        pass
    return url, key


def create_supabase_client():
    """Return `(client, url, key)`; client is `None` when Supabase is not configured."""
    url, key = load_supabase_credentials()
    if not url or not key:
        return None, url, key
    try:
        from supabase import create_client
    except Exception:
        return None, url, key
    return create_client(url, key), url, key
